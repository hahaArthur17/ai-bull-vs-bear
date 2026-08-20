from __future__ import annotations

from datetime import date, datetime, timezone
import logging
from typing import Any

import httpx
from pydantic import ValidationError

from app.schemas import AnalysisResponse
from app.services.demo_store import DemoStore
from app.services.evidence_freshness import classify_evidence_freshness
from app.services.rag import retrieve_evidence


logger = logging.getLogger(__name__)


class RepositoryError(RuntimeError):
    pass


class SupabaseStore(DemoStore):
    """Use Supabase for user data while retaining deterministic market fixtures."""

    def __init__(
        self,
        supabase_url: str,
        anon_key: str,
        client: httpx.Client | None = None,
        price_stale_after_days: int = 5,
    ) -> None:
        super().__init__()
        self.rest_url = f"{supabase_url.rstrip('/')}/rest/v1"
        self.anon_key = anon_key
        self.client = client
        self.price_stale_after_days = price_stale_after_days

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

    def get_prices(self, ticker: str) -> list[dict[str, object]]:
        normalized = ticker.upper()
        try:
            stock_response = self._public_request(
                "stocks",
                params={"select": "id", "ticker": f"eq.{normalized}", "limit": "1"},
            )
            stock_rows = stock_response.json()
            if not stock_rows:
                return self._demo_prices(normalized)
            price_response = self._public_request(
                "stock_prices",
                params={
                    "select": "trading_date,open,high,low,close,volume",
                    "stock_id": f"eq.{stock_rows[0]['id']}",
                    "order": "trading_date.asc",
                    "limit": "100",
                },
            )
            rows = price_response.json()
            if not rows:
                return self._demo_prices(normalized)
            latest_date = max(date.fromisoformat(str(row["trading_date"])) for row in rows)
            age_days = (datetime.now(timezone.utc).date() - latest_date).days
            is_stale = age_days > self.price_stale_after_days
            return [
                {
                    "date": str(row["trading_date"]),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": int(row["volume"]),
                    "source": "daily_market_cache",
                    "is_stale": is_stale,
                }
                for row in rows
            ]
        except (KeyError, RepositoryError, TypeError, ValueError):
            return self._demo_prices(normalized)

    def get_price_history(self, ticker: str, frequency: str = "weekly") -> list[dict[str, object]]:
        normalized = ticker.upper()
        if frequency != "weekly":
            raise ValueError(f"Unsupported history frequency: {frequency}")
        stock_response = self._public_request(
            "stocks",
            params={"select": "id", "ticker": f"eq.{normalized}", "limit": "1"},
        )
        stock_rows = stock_response.json()
        if not stock_rows:
            return []
        response = self._public_request(
            "stock_price_history",
            params={
                "select": "trading_date,open,high,low,close,volume,frequency,source,retrieved_at",
                "stock_id": f"eq.{stock_rows[0]['id']}",
                "frequency": f"eq.{frequency}",
                "order": "trading_date.asc",
                "limit": "260",
            },
        )
        return [
            {
                "date": str(row["trading_date"]),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": int(row["volume"]),
                "frequency": row["frequency"],
                "source": row["source"],
                "retrieved_at": row["retrieved_at"],
            }
            for row in response.json()
        ]

    def _demo_prices(self, ticker: str) -> list[dict[str, object]]:
        return [
            {
                **point,
                "source": "demo_fallback",
                "is_stale": True,
            }
            for point in super().get_prices(ticker)
        ]

    def get_macro_series(self) -> list[dict[str, object]]:
        response = self._public_request(
            "macro_series",
            params={"select": "code,name,source,unit,frequency,metadata", "order": "code.asc"},
        )
        return [
            {
                "code": row["code"],
                "name": row["name"],
                "source": row["source"],
                "unit": row["unit"],
                "frequency": row["frequency"],
                "metadata": row.get("metadata") or {},
            }
            for row in response.json()
        ]

    def get_macro_observations(self, series_code: str, limit: int = 400) -> list[dict[str, object]]:
        response = self._public_request(
            "macro_observations",
            params={
                "select": "series_code,observation_date,value,metadata,retrieved_at",
                "series_code": f"eq.{series_code}",
                "order": "observation_date.desc",
                "limit": str(limit),
            },
        )
        return [
            {
                "series_code": row["series_code"],
                "observation_date": row["observation_date"],
                "value": float(row["value"]),
                "metadata": row.get("metadata") or {},
                "retrieved_at": row["retrieved_at"],
            }
            for row in response.json()
        ]

    def get_evidence(self, ticker: str) -> list[dict[str, object]]:
        technical = super().get_evidence(ticker)
        stock_response = self._public_request(
            "stocks",
            params={"select": "id", "ticker": f"eq.{ticker.upper()}", "limit": "1"},
        )
        stock_rows = stock_response.json()
        if not stock_rows:
            return technical
        evidence_response = self._public_request(
            "evidence_documents",
            params={
                "select": "id,external_id,source_type,title,url,published_at,raw_text,metadata,created_at",
                "stock_id": f"eq.{stock_rows[0]['id']}",
                "order": "published_at.desc.nullslast,created_at.desc",
                "limit": "20",
            },
        )
        live_documents = [
            {
                "id": row.get("external_id") or f"evidence-{row['id']}",
                "ticker": ticker.upper(),
                "source_type": row["source_type"],
                "title": row["title"],
                "url": row.get("url"),
                "published_at": row.get("published_at"),
                "excerpt": row["raw_text"],
                "metadata": {
                    **(row.get("metadata") or {}),
                    "storage": "supabase",
                    "document_id": str(row["id"]),
                },
                "freshness": classify_evidence_freshness(
                    str(row["source_type"]),
                    row.get("published_at"),
                ),
            }
            for row in evidence_response.json()
        ]
        return technical + live_documents if live_documents else technical

    def search_evidence(self, ticker: str, query: str, limit: int = 6) -> list[dict[str, object]]:
        try:
            response = self._public_rpc(
                "match_evidence_chunks",
                {
                    "query_text": query,
                    "match_count": limit,
                    "filter_ticker": ticker.upper(),
                    "filter_source_type": None,
                },
            )
        except RepositoryError:
            return self._fallback_search_evidence(ticker, query, limit, "rpc_unavailable")
        rows = response.json()
        if not rows:
            return self._fallback_search_evidence(ticker, query, limit, "no_vector_matches")
        return [
            {
                "id": f"chunk-{row['chunk_id']}",
                "ticker": row["ticker"],
                "source_type": row["source_type"],
                "title": row["title"],
                "url": row.get("url"),
                "published_at": row.get("published_at"),
                "excerpt": row["chunk_text"],
                "metadata": {
                    **(row.get("metadata") or {}),
                    "document_id": str(row["document_id"]),
                    "similarity": str(row["similarity"]),
                    "storage": "supabase",
                },
                "freshness": classify_evidence_freshness(
                    str(row["source_type"]),
                    row.get("published_at"),
                ),
            }
            for row in rows
        ]

    def _fallback_search_evidence(
        self,
        ticker: str,
        query: str,
        limit: int,
        reason: str,
    ) -> list[dict[str, object]]:
        # A Supabase-backed analysis must never quietly explain a current price
        # with deterministic demo news or filings. When vector search is not
        # available, score only the same stored documents exposed by
        # ``get_evidence``. A repository failure is allowed to surface instead
        # of returning fabricated fallback context.
        results = retrieve_evidence(self.get_evidence(ticker), query, limit)
        for item in results:
            metadata = item.get("metadata")
            item["metadata"] = {
                **(metadata if isinstance(metadata, dict) else {}),
                "retrieval_mode": "document_fallback",
                "fallback_reason": reason,
            }
        return results

    def _public_request(
        self,
        table: str,
        *,
        params: dict[str, str],
    ) -> httpx.Response:
        headers = {"apikey": self.anon_key, "Authorization": f"Bearer {self.anon_key}"}
        try:
            requester = self.client.request if self.client is not None else httpx.request
            response = requester(
                "GET",
                f"{self.rest_url}/{table}",
                params=params,
                headers=headers,
                timeout=10.0,
            )
        except httpx.RequestError as exc:
            raise RepositoryError("Supabase evidence retrieval is unavailable") from exc
        if response.status_code >= 400:
            raise RepositoryError(
                f"Supabase {table} request failed with status {response.status_code}"
            )
        return response

    def _public_rpc(self, function: str, payload: object) -> httpx.Response:
        headers = {
            "apikey": self.anon_key,
            "Authorization": f"Bearer {self.anon_key}",
            "Content-Type": "application/json",
        }
        try:
            requester = self.client.request if self.client is not None else httpx.request
            response = requester(
                "POST",
                f"{self.rest_url}/rpc/{function}",
                json=payload,
                headers=headers,
                timeout=10.0,
            )
        except httpx.RequestError as exc:
            raise RepositoryError("Supabase vector retrieval is unavailable") from exc
        if response.status_code >= 400:
            raise RepositoryError(
                f"Supabase RPC {function} failed with status {response.status_code}"
            )
        return response

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
        return self._parse_stored_analysis(rows[0]["output_json"]) if rows else None

    @staticmethod
    def _parse_stored_analysis(payload: object) -> AnalysisResponse | None:
        """Read current-format records without letting legacy rows break history.

        Analysis responses written before the immutable snapshot contract do not
        contain the context needed to represent a reproducible Debate. Keep
        those rows in storage, but omit them from the current-history response
        instead of manufacturing a snapshot or failing every user's history.
        """

        try:
            return AnalysisResponse.model_validate(payload)
        except ValidationError:
            logger.warning("Skipping an incompatible legacy analysis response")
            return None

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
