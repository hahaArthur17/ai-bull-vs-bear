from __future__ import annotations

from typing import Any

import httpx

from app.schemas import AnalysisResponse
from app.services.demo_store import DemoStore


class RepositoryError(RuntimeError):
    pass


class SupabaseStore(DemoStore):
    """Use Supabase for user data while retaining deterministic market fixtures."""

    def __init__(
        self,
        supabase_url: str,
        anon_key: str,
        client: httpx.Client | None = None,
    ) -> None:
        super().__init__()
        self.rest_url = f"{supabase_url.rstrip('/')}/rest/v1"
        self.anon_key = anon_key
        self.client = client

    def _request(
        self,
        method: str,
        table: str,
        access_token: str | None,
        *,
        params: dict[str, str] | None = None,
        json: object | None = None,
        prefer: str | None = None,
    ) -> httpx.Response:
        if not access_token:
            raise RepositoryError("A user access token is required for Supabase persistence")
        headers = {
            "apikey": self.anon_key,
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        if prefer:
            headers["Prefer"] = prefer
        try:
            requester = self.client.request if self.client is not None else httpx.request
            response = requester(
                method,
                f"{self.rest_url}/{table}",
                params=params,
                json=json,
                headers=headers,
                timeout=10.0,
            )
        except httpx.RequestError as exc:
            raise RepositoryError("Supabase persistence is unavailable") from exc
        if response.status_code >= 400:
            raise RepositoryError(
                f"Supabase {table} request failed with status {response.status_code}"
            )
        return response

    def _stock_id(self, ticker: str, access_token: str) -> int:
        response = self._request(
            "GET",
            "stocks",
            access_token,
            params={"select": "id", "ticker": f"eq.{ticker.upper()}", "limit": "1"},
        )
        rows = response.json()
        if not rows:
            raise RepositoryError(f"Stock {ticker.upper()} is not seeded in Supabase")
        return int(rows[0]["id"])

    def get_watchlist(self, user_id: str, access_token: str | None = None) -> list[str]:
        response = self._request(
            "GET",
            "watchlists",
            access_token,
            params={"select": "stocks(ticker)", "user_id": f"eq.{user_id}"},
        )
        tickers = [row.get("stocks", {}).get("ticker") for row in response.json()]
        return sorted(ticker for ticker in tickers if isinstance(ticker, str))

    def add_watchlist(
        self,
        user_id: str,
        ticker: str,
        access_token: str | None = None,
    ) -> list[str]:
        if not access_token:
            raise RepositoryError("A user access token is required for Supabase persistence")
        stock_id = self._stock_id(ticker, access_token)
        self._request(
            "POST",
            "watchlists",
            access_token,
            params={"on_conflict": "user_id,stock_id"},
            json={"user_id": user_id, "stock_id": stock_id},
            prefer="resolution=ignore-duplicates,return=minimal",
        )
        return self.get_watchlist(user_id, access_token)

    def remove_watchlist(
        self,
        user_id: str,
        ticker: str,
        access_token: str | None = None,
    ) -> list[str]:
        if not access_token:
            raise RepositoryError("A user access token is required for Supabase persistence")
        stock_id = self._stock_id(ticker, access_token)
        self._request(
            "DELETE",
            "watchlists",
            access_token,
            params={"user_id": f"eq.{user_id}", "stock_id": f"eq.{stock_id}"},
            prefer="return=minimal",
        )
        return self.get_watchlist(user_id, access_token)

    def save_analysis(
        self,
        user_id: str,
        analysis_id: str,
        response: object,
        access_token: str | None = None,
    ) -> None:
        if not access_token:
            raise RepositoryError("A user access token is required for Supabase persistence")
        analysis = AnalysisResponse.model_validate(response)
        stock_id = self._stock_id(analysis.ticker, access_token)
        self._request(
            "POST",
            "analysis_runs",
            access_token,
            json={
                "id": analysis_id,
                "user_id": user_id,
                "stock_id": stock_id,
                "question": analysis.question,
                "final_summary": analysis.judge.summary,
                "guardrail_status": analysis.guardrail_status,
                "risk_level": analysis.judge.risk_level,
                "created_at": analysis.created_at,
            },
            prefer="return=minimal",
        )
        outputs = [
            {"analysis_run_id": analysis_id, "agent_name": "bull", "output_json": analysis.bull.model_dump(mode="json")},
            {"analysis_run_id": analysis_id, "agent_name": "bear", "output_json": analysis.bear.model_dump(mode="json")},
            {"analysis_run_id": analysis_id, "agent_name": "judge", "output_json": analysis.judge.model_dump(mode="json")},
            {"analysis_run_id": analysis_id, "agent_name": "trace", "output_json": [step.model_dump(mode="json") for step in analysis.trace]},
            {"analysis_run_id": analysis_id, "agent_name": "response", "output_json": analysis.model_dump(mode="json")},
        ]
        self._request(
            "POST",
            "agent_outputs",
            access_token,
            json=outputs,
            prefer="return=minimal",
        )
        self._request(
            "POST",
            "token_usage",
            access_token,
            json={"analysis_run_id": analysis_id, **analysis.token_usage.model_dump(mode="json")},
            prefer="return=minimal",
        )
        self._save_claim_evidence(analysis, access_token)

    def _save_claim_evidence(self, analysis: AnalysisResponse, access_token: str) -> None:
        evidence_ids = sorted(set(analysis.bull.evidence_ids + analysis.bear.evidence_ids))
        if not evidence_ids:
            return
        response = self._request(
            "GET",
            "evidence_documents",
            access_token,
            params={
                "select": "id,external_id",
                "external_id": f"in.({','.join(evidence_ids)})",
            },
        )
        document_ids = {
            row["external_id"]: row["id"]
            for row in response.json()
            if row.get("external_id") and row.get("id") is not None
        }
        links: list[dict[str, Any]] = []
        for claim in (analysis.bull, analysis.bear):
            links.extend(
                {
                    "claim_id": claim.id,
                    "analysis_run_id": analysis.analysis_id,
                    "evidence_document_id": document_ids[evidence_id],
                }
                for evidence_id in claim.evidence_ids
                if evidence_id in document_ids
            )
        if links:
            self._request(
                "POST",
                "claim_evidence",
                access_token,
                json=links,
                prefer="return=minimal",
            )

    def get_analysis(
        self,
        user_id: str,
        analysis_id: str,
        access_token: str | None = None,
    ) -> AnalysisResponse | None:
        response = self._request(
            "GET",
            "agent_outputs",
            access_token,
            params={
                "select": "output_json",
                "analysis_run_id": f"eq.{analysis_id}",
                "agent_name": "eq.response",
                "limit": "1",
            },
        )
        rows = response.json()
        return AnalysisResponse.model_validate(rows[0]["output_json"]) if rows else None

    def list_analyses(
        self,
        user_id: str,
        access_token: str | None = None,
    ) -> list[AnalysisResponse]:
        response = self._request(
            "GET",
            "analysis_runs",
            access_token,
            params={
                "select": "id",
                "user_id": f"eq.{user_id}",
                "order": "created_at.desc",
            },
        )
        analyses = [
            self.get_analysis(user_id, row["id"], access_token)
            for row in response.json()
        ]
        return [analysis for analysis in analyses if analysis is not None]
