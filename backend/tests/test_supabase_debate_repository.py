from datetime import timedelta
import json
from urllib.parse import parse_qs
from uuid import UUID

import httpx
import pytest

from app.domain.debate import DebateIntervention, DebateMessageEvidence
from app.domain.jobs import DebateJob
from app.repositories.debate_repository import (
    DebateConcurrencyError,
    DebateRepositoryError,
    DebateUnitOfWork,
)
from app.repositories.supabase_debate_repository import SupabaseDebateRepository
from app.services.debate_state import transition_session
from test_debate_domain import BRANCH_ID, NOW, USER_ID, build_session
from test_memory_debate_repository import build_job, build_message


class FakeDebatePostgrest:
    def __init__(self) -> None:
        self.sessions: dict[str, dict[str, object]] = {}
        self.jobs: dict[str, dict[str, object]] = {}
        self.messages: dict[str, dict[str, object]] = {}
        self.citations: dict[str, list[dict[str, object]]] = {}
        self.interventions: dict[str, dict[str, object]] = {}
        self.rpc_calls: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        assert request.headers["apikey"] == "sb_secret_debate"
        assert "authorization" not in request.headers
        assert request.headers["prefer"] == "return=representation"
        path = request.url.path.split("/rest/v1/", 1)[1]
        query = parse_qs(request.url.query.decode())
        body = json.loads(request.content or b"null")

        if path == "rpc/create_debate_session_with_job":
            self.rpc_calls.append(path)
            session = body["session_payload"]
            job = body["job_payload"]
            self.sessions.setdefault(session["id"], session)
            self.jobs.setdefault(job["id"], job)
            return httpx.Response(
                200,
                json={"session": self.sessions[session["id"]], "job": self.jobs[job["id"]]},
            )
        if path == "rpc/append_debate_message":
            self.rpc_calls.append(path)
            message = body["message_payload"]
            self.messages.setdefault(message["id"], message)
            self.citations.setdefault(message["id"], body["citations_payload"])
            return httpx.Response(
                200,
                json={
                    "message": self.messages[message["id"]],
                    "citations": self.citations[message["id"]],
                },
            )
        if path == "debate_sessions":
            if request.method == "POST":
                self.sessions[body["id"]] = body
                return httpx.Response(201, json=[body])
            rows = list(self.sessions.values())
            rows = self._filter(rows, query, "id", "user_id", "status")
            if request.method == "PATCH":
                if not rows:
                    return httpx.Response(200, json=[])
                updated = {**rows[0], **body}
                self.sessions[str(updated["id"])] = updated
                return httpx.Response(200, json=[updated])
            return httpx.Response(200, json=rows)
        if path == "debate_messages":
            rows = self._filter(
                list(self.messages.values()),
                query,
                "id",
                "session_id",
                "branch_id",
            )
            if query.get("select") == ["session_id"]:
                rows = [{"session_id": row["session_id"]} for row in rows]
            return httpx.Response(200, json=rows)
        if path == "debate_message_evidence":
            message_id = query["message_id"][0].removeprefix("eq.")
            return httpx.Response(200, json=self.citations.get(message_id, []))
        if path == "debate_interventions" and request.method == "POST":
            self.interventions[body["id"]] = body
            return httpx.Response(201, json=[body])
        if path == "debate_jobs":
            if request.method == "POST":
                self.jobs[body["id"]] = body
                return httpx.Response(201, json=[body])
            rows = self._filter(
                list(self.jobs.values()),
                query,
                "id",
                "session_id",
                "user_id",
                "status",
            )
            if request.method == "PATCH":
                if not rows:
                    return httpx.Response(200, json=[])
                updated = {**rows[0], **body}
                self.jobs[str(updated["id"])] = updated
                return httpx.Response(200, json=[updated])
            return httpx.Response(200, json=rows)
        raise AssertionError(f"Unexpected Debate request: {request.method} {request.url}")

    @staticmethod
    def _filter(
        rows: list[dict[str, object]],
        query: dict[str, list[str]],
        *fields: str,
    ) -> list[dict[str, object]]:
        for field in fields:
            if field in query:
                expression = query[field][0]
                if expression.startswith("in.(") and expression.endswith(")"):
                    expected = set(expression[4:-1].split(","))
                    rows = [row for row in rows if str(row[field]) in expected]
                else:
                    expected_value = expression.removeprefix("eq.")
                    rows = [row for row in rows if str(row[field]) == expected_value]
        return rows[: int(query.get("limit", [str(len(rows) or 1)])[0])]


def build_repository(fake: FakeDebatePostgrest) -> SupabaseDebateRepository:
    client = httpx.Client(transport=httpx.MockTransport(fake))
    return SupabaseDebateRepository(
        "https://example.supabase.co",
        "sb_secret_debate",
        client,
    )


def test_supabase_repository_uses_service_only_atomic_creation() -> None:
    fake = FakeDebatePostgrest()
    repository = build_repository(fake)
    session = build_session()
    job = build_job(session)

    assert isinstance(repository, DebateUnitOfWork)
    assert repository.create_session_with_job(session, job) == (session, job)
    assert repository.create_session_with_job(session, job) == (session, job)
    assert fake.rpc_calls == [
        "rpc/create_debate_session_with_job",
        "rpc/create_debate_session_with_job",
    ]
    assert repository.get_session(session.id, USER_ID) == session
    assert repository.get_session(
        session.id,
        UUID("00000000-0000-4000-8000-000000000999"),
    ) is None
    assert repository.get_active_job(session.id, USER_ID) == job


def test_supabase_repository_round_trips_messages_citations_and_interventions() -> None:
    fake = FakeDebatePostgrest()
    repository = build_repository(fake)
    session = build_session()
    repository.create_session_with_job(session, build_job(session))
    message = build_message()
    citation = DebateMessageEvidence(
        message_id=message.id,
        evidence_id="technical-aapl-001",
        citation_order=1,
    )

    assert repository.append_message(message, (citation,)) == message
    assert repository.list_messages(session.id, USER_ID, branch_id=BRANCH_ID) == [message]
    assert repository.list_message_evidence(message.id, USER_ID) == (citation,)

    intervention = DebateIntervention(
        id=UUID("00000000-0000-4000-8000-000000000107"),
        session_id=session.id,
        user_id=USER_ID,
        selected_message_id=message.id,
        selected_text="moving average",
        question="What does this term mean here?",
        mode="explain",
        created_at=NOW,
    )
    assert repository.create_intervention(intervention) == intervention
    assert "rpc/append_debate_message" in fake.rpc_calls


def test_supabase_repository_updates_sessions_and_jobs_optimistically() -> None:
    fake = FakeDebatePostgrest()
    repository = build_repository(fake)
    session = build_session()
    queued_job = build_job(session)
    repository.create_session_with_job(session, queued_job)

    queued_session = transition_session(
        session,
        "queued_round_1",
        at=NOW + timedelta(seconds=1),
    )
    assert repository.update_session(queued_session, expected_status="created") == queued_session
    with pytest.raises(DebateConcurrencyError, match="concurrently"):
        repository.update_session(queued_session, expected_status="created")

    running_job = DebateJob.model_validate(
        {
            **queued_job.model_dump(mode="python"),
            "status": "running",
            "attempt_count": 1,
            "started_at": NOW + timedelta(seconds=1),
            "updated_at": NOW + timedelta(seconds=1),
        }
    )
    assert repository.update_job(running_job, expected_status="queued") == running_job
    assert repository.get_active_job(session.id, USER_ID) == running_job
    with pytest.raises(DebateConcurrencyError, match="concurrently"):
        repository.update_job(running_job, expected_status="queued")


def test_supabase_repository_maps_remote_errors_without_leaking_response_payload() -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"secret": "must-not-leak"})

    repository = SupabaseDebateRepository(
        "https://example.supabase.co",
        "sb_secret_debate",
        httpx.Client(transport=httpx.MockTransport(fail)),
    )

    with pytest.raises(DebateRepositoryError) as error:
        repository.get_job(UUID("00000000-0000-4000-8000-000000000108"))
    assert "must-not-leak" not in str(error.value)
