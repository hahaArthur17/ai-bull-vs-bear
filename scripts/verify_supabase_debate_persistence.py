#!/usr/bin/env python3
"""Verify hosted Debate persistence, RLS, and service-only writes.

The verifier creates two disposable Debate fixtures through the same
server-only repository used by the application, checks authenticated reads and
write rejection, and removes both Sessions (with cascading child rows) before
returning.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from uuid import UUID, uuid4

import httpx

from app.config import get_settings
from app.domain.debate import (
    DebateIntervention,
    DebateMessage,
    DebateMessageEvidence,
    DebateSession,
)
from app.domain.factors import AnalysisContext, FactorSnapshot
from app.domain.jobs import DebateJob
from app.repositories.supabase_debate_repository import SupabaseDebateRepository
from app.services.supabase_headers import service_headers


@dataclass(frozen=True)
class AuthSession:
    user_id: UUID
    access_token: str


@dataclass(frozen=True)
class DebateFixture:
    session: DebateSession
    queued_session: DebateSession
    running_session: DebateSession
    job: DebateJob
    running_job: DebateJob
    message: DebateMessage
    citation: DebateMessageEvidence
    intervention: DebateIntervention


class HostedDebatePersistenceVerifier:
    TABLES = (
        "debate_sessions",
        "debate_messages",
        "debate_message_evidence",
        "debate_interventions",
        "debate_jobs",
    )

    def __init__(
        self,
        supabase_url: str,
        anon_key: str,
        secret_key: str,
        client: httpx.Client | None = None,
    ) -> None:
        if not supabase_url.strip() or not anon_key.strip() or not secret_key.strip():
            raise ValueError("Hosted Debate verification requires Supabase credentials")
        self.supabase_url = supabase_url.rstrip("/")
        self.rest_url = f"{self.supabase_url}/rest/v1"
        self.anon_key = anon_key
        self.secret_key = secret_key
        self.client = client or httpx.Client(timeout=15.0)
        self.repository = SupabaseDebateRepository(
            self.supabase_url,
            self.secret_key,
            self.client,
        )

    def sign_in(self, email: str, password: str) -> AuthSession:
        response = self.client.post(
            f"{self.supabase_url}/auth/v1/token",
            params={"grant_type": "password"},
            headers={"apikey": self.anon_key, "Content-Type": "application/json"},
            json={"email": email, "password": password},
        )
        self._require(response, {200}, "sign in")
        payload = response.json()
        return AuthSession(
            user_id=UUID(str(payload["user"]["id"])),
            access_token=str(payload["access_token"]),
        )

    def stock_id(self, ticker: str = "AAPL") -> int:
        response = self.client.get(
            f"{self.rest_url}/stocks",
            params={"select": "id", "ticker": f"eq.{ticker}", "limit": "1"},
            headers={
                "apikey": self.anon_key,
                "Authorization": f"Bearer {self.anon_key}",
            },
        )
        self._require(response, {200}, "read public stock")
        rows = response.json()
        if not rows:
            raise RuntimeError(f"Stock {ticker} is not seeded")
        return int(rows[0]["id"])

    def verify(
        self,
        user_a: AuthSession,
        user_b: AuthSession,
        stock_id: int,
    ) -> dict[str, bool]:
        base_time = datetime.now(timezone.utc).replace(microsecond=0)
        fixtures = (
            self._build_fixture(user_a.user_id, stock_id, base_time, "a"),
            self._build_fixture(
                user_b.user_id,
                stock_id,
                base_time + timedelta(seconds=10),
                "b",
            ),
        )
        session_ids = tuple(fixture.session.id for fixture in fixtures)
        report: dict[str, bool] = {}
        try:
            service_checks = [self._persist_fixture(fixture) for fixture in fixtures]
            report.update(
                {
                    "service_atomic_session_job": all(
                        item["service_atomic_session_job"] for item in service_checks
                    ),
                    "service_expected_status_updates": all(
                        item["service_expected_status_updates"] for item in service_checks
                    ),
                    "service_atomic_message_citations": all(
                        item["service_atomic_message_citations"]
                        for item in service_checks
                    ),
                    "service_intervention_write": all(
                        item["service_intervention_write"] for item in service_checks
                    ),
                }
            )

            own_a = self._read_fixture(user_a, fixtures[0])
            own_b = self._read_fixture(user_b, fixtures[1])
            cross_a = self._read_fixture(user_a, fixtures[1])
            cross_b = self._read_fixture(user_b, fixtures[0])
            report["owner_reads_all_tables"] = all(own_a.values()) and all(own_b.values())
            report["cross_user_reads_hidden"] = not any(cross_a.values()) and not any(
                cross_b.values()
            )
            report["authenticated_table_writes_rejected"] = all(
                self._authenticated_write_rejected(user_a, table)
                for table in self.TABLES
            )
            report["authenticated_rpcs_rejected"] = self._authenticated_rpcs_rejected(
                user_a,
                fixtures[0],
            )
        finally:
            report["cleanup_removed"] = self._cleanup_sessions(session_ids)

        if not all(report.values()):
            raise RuntimeError(f"Hosted Debate persistence verification failed: {report}")
        return report

    def _persist_fixture(self, fixture: DebateFixture) -> dict[str, bool]:
        first = self.repository.create_session_with_job(fixture.session, fixture.job)
        replay = self.repository.create_session_with_job(fixture.session, fixture.job)
        stored_queued_session = self.repository.update_session(
            fixture.queued_session,
            expected_status="created",
        )
        stored_running_session = self.repository.update_session(
            fixture.running_session,
            expected_status="queued_round_1",
        )
        stored_job = self.repository.update_job(
            fixture.running_job,
            expected_status="queued",
        )
        first_message = self.repository.append_message(
            fixture.message,
            (fixture.citation,),
        )
        replayed_message = self.repository.append_message(
            fixture.message,
            (fixture.citation,),
        )
        stored_citations = self.repository.list_message_evidence(
            fixture.message.id,
            fixture.session.user_id,
        )
        stored_intervention = self.repository.create_intervention(fixture.intervention)
        return {
            "service_atomic_session_job": first == replay == (
                fixture.session,
                fixture.job,
            ),
            "service_expected_status_updates": (
                stored_queued_session == fixture.queued_session
                and stored_running_session == fixture.running_session
                and stored_job == fixture.running_job
            ),
            "service_atomic_message_citations": (
                first_message == replayed_message == fixture.message
                and stored_citations == (fixture.citation,)
            ),
            "service_intervention_write": stored_intervention == fixture.intervention,
        }

    def _read_fixture(
        self,
        session: AuthSession,
        fixture: DebateFixture,
    ) -> dict[str, bool]:
        filters = {
            "debate_sessions": {"id": f"eq.{fixture.session.id}"},
            "debate_messages": {"id": f"eq.{fixture.message.id}"},
            "debate_message_evidence": {
                "message_id": f"eq.{fixture.message.id}",
            },
            "debate_interventions": {"id": f"eq.{fixture.intervention.id}"},
            "debate_jobs": {"id": f"eq.{fixture.job.id}"},
        }
        visible: dict[str, bool] = {}
        for table, params in filters.items():
            response = self._authenticated_request(
                "GET",
                table,
                session,
                params={"select": "*", **params},
            )
            self._require(response, {200}, f"read {table}")
            visible[table] = len(response.json()) == 1
        return visible

    def _authenticated_write_rejected(
        self,
        session: AuthSession,
        table: str,
    ) -> bool:
        response = self._authenticated_request("POST", table, session, json={})
        return response.status_code in {401, 403}

    def _authenticated_rpcs_rejected(
        self,
        session: AuthSession,
        fixture: DebateFixture,
    ) -> bool:
        create_response = self._authenticated_request(
            "POST",
            "rpc/create_debate_session_with_job",
            session,
            json={
                "session_payload": fixture.session.model_dump(mode="json"),
                "job_payload": fixture.job.model_dump(mode="json"),
            },
        )
        append_response = self._authenticated_request(
            "POST",
            "rpc/append_debate_message",
            session,
            json={
                "message_payload": fixture.message.model_dump(mode="json"),
                "citations_payload": [fixture.citation.model_dump(mode="json")],
            },
        )
        denied = {401, 403, 404}
        return create_response.status_code in denied and append_response.status_code in denied

    def _authenticated_request(
        self,
        method: str,
        path: str,
        session: AuthSession,
        **kwargs: object,
    ) -> httpx.Response:
        return self.client.request(
            method,
            f"{self.rest_url}/{path}",
            headers={
                "apikey": self.anon_key,
                "Authorization": f"Bearer {session.access_token}",
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
            **kwargs,
        )

    def _cleanup_sessions(self, session_ids: tuple[UUID, ...]) -> bool:
        identifiers = ",".join(str(session_id) for session_id in session_ids)
        response = self.client.delete(
            f"{self.rest_url}/debate_sessions",
            params={"id": f"in.({identifiers})"},
            headers=service_headers(self.secret_key, "return=minimal"),
        )
        self._require(response, {200, 204}, "clean up Debate sessions")
        check = self.client.get(
            f"{self.rest_url}/debate_sessions",
            params={"select": "id", "id": f"in.({identifiers})"},
            headers=service_headers(self.secret_key, "return=minimal"),
        )
        self._require(check, {200}, "verify Debate cleanup")
        return check.json() == []

    @staticmethod
    def _build_fixture(
        user_id: UUID,
        stock_id: int,
        created_at: datetime,
        label: str,
    ) -> DebateFixture:
        session_id = uuid4()
        branch_id = uuid4()
        generation_id = uuid4()
        as_of = created_at.isoformat()
        session = DebateSession(
            id=session_id,
            user_id=user_id,
            stock_id=stock_id,
            ticker="AAPL",
            mode="demo",
            status="created",
            opening_side="bull",
            active_branch_id=branch_id,
            active_generation_id=generation_id,
            analysis_context=AnalysisContext(ticker="AAPL", as_of=as_of),
            factor_snapshot=FactorSnapshot(ticker="AAPL", as_of=as_of),
            created_at=created_at,
            updated_at=created_at,
        )
        job = DebateJob(
            id=uuid4(),
            session_id=session_id,
            user_id=user_id,
            job_type="round_1",
            status="queued",
            idempotency_key=f"hosted-verify-{label}-{uuid4()}",
            available_at=created_at,
            created_at=created_at,
            updated_at=created_at,
        )
        queued_at = created_at + timedelta(seconds=1)
        queued_session = DebateSession.model_validate(
            {
                **session.model_dump(mode="python"),
                "status": "queued_round_1",
                "updated_at": queued_at,
            }
        )
        running_at = created_at + timedelta(seconds=2)
        running_session = DebateSession.model_validate(
            {
                **queued_session.model_dump(mode="python"),
                "status": "running_round_1",
                "updated_at": running_at,
            }
        )
        running_job = DebateJob.model_validate(
            {
                **job.model_dump(mode="python"),
                "status": "running",
                "attempt_count": 1,
                "started_at": running_at,
                "updated_at": running_at,
            }
        )
        message = DebateMessage(
            id=uuid4(),
            session_id=session_id,
            branch_id=branch_id,
            generation_id=generation_id,
            sequence_number=1,
            round_number=1,
            exchange_number=1,
            role="bull",
            message_kind="argument",
            content="Hosted persistence verification message.",
            confidence="medium",
            signal_strength="medium",
            created_at=created_at + timedelta(seconds=3),
        )
        citation = DebateMessageEvidence(
            message_id=message.id,
            evidence_id=f"hosted-verify-evidence-{label}",
            citation_order=1,
            support_span="Disposable verification citation.",
        )
        intervention = DebateIntervention(
            id=uuid4(),
            session_id=session_id,
            user_id=user_id,
            selected_message_id=message.id,
            selected_text="verification message",
            question="Explain this disposable verification passage.",
            mode="explain",
            created_at=created_at + timedelta(seconds=4),
        )
        return DebateFixture(
            session=session,
            queued_session=queued_session,
            running_session=running_session,
            job=job,
            running_job=running_job,
            message=message,
            citation=citation,
            intervention=intervention,
        )

    @staticmethod
    def _require(
        response: httpx.Response,
        statuses: set[int],
        operation: str,
    ) -> None:
        if response.status_code not in statuses:
            raise RuntimeError(
                f"Supabase Debate {operation} failed with status {response.status_code}"
            )


def main() -> None:
    settings = get_settings()
    required = {
        "SUPABASE_URL": settings.supabase_url,
        "SUPABASE_ANON_KEY": settings.supabase_anon_key,
        "SUPABASE_SECRET_KEY": settings.supabase_secret_key,
        "SUPABASE_RLS_USER_A_EMAIL": settings.supabase_rls_user_a_email,
        "SUPABASE_RLS_USER_A_PASSWORD": settings.supabase_rls_user_a_password,
        "SUPABASE_RLS_USER_B_EMAIL": settings.supabase_rls_user_b_email,
        "SUPABASE_RLS_USER_B_PASSWORD": settings.supabase_rls_user_b_password,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise SystemExit(f"Missing required environment variables: {', '.join(missing)}")

    verifier = HostedDebatePersistenceVerifier(
        str(settings.supabase_url),
        str(settings.supabase_anon_key),
        str(settings.supabase_secret_key),
    )
    user_a = verifier.sign_in(
        str(settings.supabase_rls_user_a_email),
        str(settings.supabase_rls_user_a_password),
    )
    user_b = verifier.sign_in(
        str(settings.supabase_rls_user_b_email),
        str(settings.supabase_rls_user_b_password),
    )
    report = verifier.verify(user_a, user_b, verifier.stock_id())
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
