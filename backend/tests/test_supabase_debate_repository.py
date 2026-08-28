from datetime import timedelta
import json
from urllib.parse import parse_qs
from uuid import UUID

import httpx
import pytest

from app.domain.debate import DebateIntervention, DebateMessageEvidence
from app.domain.jobs import DebateJob, DebateQueueMessage
from app.repositories.debate_repository import (
    DebateConcurrencyError,
    DebateRepositoryError,
    DebateQueueRepository,
    DebateUnitOfWork,
)
from app.repositories.supabase_debate_repository import SupabaseDebateRepository
from app.services.debate_job_state import start_job
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
        self.queue_messages: dict[int, dict[str, object]] = {}
        self.queue_read_counts: dict[int, int] = {}
        self.next_queue_message_id = 1

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
        if path == "rpc/enqueue_debate_session_job":
            self.rpc_calls.append(path)
            session = body["session_payload"]
            requested_job = body["job_payload"]
            stored_job = self.jobs.get(requested_job["id"])
            if stored_job is None:
                queue_message_id = self.next_queue_message_id
                self.next_queue_message_id += 1
                stored_job = {**requested_job, "queue_message_id": queue_message_id}
                self.sessions[session["id"]] = session
                self.jobs[requested_job["id"]] = stored_job
                self.queue_messages[queue_message_id] = body["queue_payload"]
            queue_message_id = int(stored_job["queue_message_id"])
            return httpx.Response(
                200,
                json={
                    "session": self.sessions[session["id"]],
                    "job": stored_job,
                    "queue_message_id": queue_message_id,
                },
            )
        if path == "rpc/enqueue_debate_round_two":
            self.rpc_calls.append(path)
            intervention = body["intervention_payload"]
            question = body["question_payload"]
            session = body["session_payload"]
            requested_job = body["job_payload"]
            stored_job = self.jobs.get(requested_job["id"])
            if stored_job is None:
                queue_message_id = self.next_queue_message_id
                self.next_queue_message_id += 1
                stored_job = {**requested_job, "queue_message_id": queue_message_id}
                self.interventions[intervention["id"]] = intervention
                self.messages[question["id"]] = question
                self.citations[question["id"]] = []
                self.sessions[session["id"]] = session
                self.jobs[requested_job["id"]] = stored_job
                self.queue_messages[queue_message_id] = body["queue_payload"]
            queue_message_id = int(stored_job["queue_message_id"])
            return httpx.Response(
                200,
                json={
                    "session": self.sessions[session["id"]],
                    "job": stored_job,
                    "intervention": self.interventions[intervention["id"]],
                    "question": self.messages[question["id"]],
                    "queue_message_id": queue_message_id,
                },
            )
        if path == "rpc/claim_debate_job":
            self.rpc_calls.append(path)
            if not self.queue_messages:
                return httpx.Response(200, content=b"null")
            queue_message_id = min(self.queue_messages)
            payload = self.queue_messages[queue_message_id]
            read_count = self.queue_read_counts.get(queue_message_id, 0) + 1
            self.queue_read_counts[queue_message_id] = read_count
            return httpx.Response(
                200,
                json={
                    "queue_message_id": queue_message_id,
                    "read_count": read_count,
                    "enqueued_at": payload["enqueued_at"],
                    "visibility_deadline": (NOW + timedelta(minutes=15)).isoformat(),
                    "payload": payload,
                },
            )
        if path == "rpc/archive_debate_job":
            self.rpc_calls.append(path)
            queue_message_id = int(body["queue_message_id"])
            archived = self.queue_messages.pop(queue_message_id, None) is not None
            return httpx.Response(200, json=archived)
        if path == "rpc/retry_debate_job":
            self.rpc_calls.append(path)
            return httpx.Response(
                200,
                json=int(body["queue_message_id"]) in self.queue_messages,
            )
        if path == "rpc/requeue_debate_job":
            self.rpc_calls.append(path)
            job = self.jobs[body["debate_job_id"]]
            session = self.sessions[str(job["session_id"])]
            retried_job = {
                **job,
                "status": "queued",
                "started_at": None,
                "provider_request_count": max(
                    int(job["provider_request_count"]),
                    int(body["observed_provider_request_count"]),
                ),
                "prompt_tokens": max(
                    int(job["prompt_tokens"]),
                    int(body["observed_prompt_tokens"]),
                ),
                "completion_tokens": max(
                    int(job["completion_tokens"]),
                    int(body["observed_completion_tokens"]),
                ),
            }
            retried_job["total_tokens"] = int(retried_job["prompt_tokens"]) + int(
                retried_job["completion_tokens"]
            )
            retried_session = {**session, "status": "queued_round_1"}
            self.jobs[str(job["id"])] = retried_job
            self.sessions[str(session["id"])] = retried_session
            return httpx.Response(
                200,
                json={"session": retried_session, "job": retried_job},
            )
        if path == "rpc/fail_exhausted_debate_job":
            self.rpc_calls.append(path)
            job = self.jobs[body["debate_job_id"]]
            session = self.sessions[str(job["session_id"])]
            failed_job = {
                **job,
                "status": "failed",
                "finished_at": job["updated_at"],
                "safe_error_code": "debate_retry_exhausted",
            }
            failed_session = {
                **session,
                "status": "failed",
                "safe_error_code": "debate_retry_exhausted",
                "completed_at": session["updated_at"],
            }
            self.jobs[str(job["id"])] = failed_job
            self.sessions[str(session["id"])] = failed_session
            return httpx.Response(
                200,
                json={"session": failed_session, "job": failed_job},
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
    assert isinstance(repository, DebateQueueRepository)
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


def test_supabase_repository_round_trips_durable_queue_operations() -> None:
    fake = FakeDebatePostgrest()
    repository = build_repository(fake)
    session = transition_session(
        build_session(),
        "queued_round_1",
        at=NOW + timedelta(seconds=1),
    )
    job = build_job(
        session,
        available_at=session.updated_at,
        created_at=session.updated_at,
        updated_at=session.updated_at,
    )
    message = DebateQueueMessage(
        job_id=job.id,
        session_id=session.id,
        job_type=job.job_type,
        trace_id="trace_queue_003",
        enqueued_at=session.updated_at,
    )

    admitted = repository.create_session_with_job_and_enqueue(session, job, message)
    repeated = repository.create_session_with_job_and_enqueue(session, job, message)
    assert admitted == repeated
    assert admitted[1].queue_message_id == 1

    claimed = repository.claim_job(visibility_timeout_seconds=900)
    assert claimed is not None
    assert claimed.queue_message_id == admitted[1].queue_message_id
    assert claimed.payload == message
    assert claimed.read_count == 1
    assert repository.retry_job_message(claimed.queue_message_id, delay_seconds=30)
    assert repository.archive_job_message(claimed.queue_message_id)
    assert repository.claim_job(visibility_timeout_seconds=900) is None


def test_supabase_repository_round_trips_atomic_retry_settlement() -> None:
    fake = FakeDebatePostgrest()
    repository = build_repository(fake)
    queued_session = transition_session(
        build_session(),
        "queued_round_1",
        at=NOW + timedelta(seconds=1),
    )
    queued_job = build_job(
        queued_session,
        max_attempts=2,
        available_at=queued_session.updated_at,
        created_at=queued_session.updated_at,
        updated_at=queued_session.updated_at,
    )
    message = DebateQueueMessage(
        job_id=queued_job.id,
        session_id=queued_session.id,
        job_type=queued_job.job_type,
        trace_id="trace_retry_002",
        enqueued_at=queued_session.updated_at,
    )
    _, queued_job = repository.create_session_with_job_and_enqueue(
        queued_session,
        queued_job,
        message,
    )
    running_job = start_job(queued_job, at=NOW + timedelta(seconds=2))
    repository.update_job(running_job, expected_status="queued")
    running_session = transition_session(
        queued_session,
        "running_round_1",
        at=NOW + timedelta(seconds=2),
    )
    repository.update_session(running_session, expected_status="queued_round_1")

    retried_session, retried_job = repository.requeue_running_job(
        queued_job.id,
        expected_attempt_count=1,
        provider_request_count=1,
    )
    second_job = start_job(
        retried_job,
        at=NOW + timedelta(seconds=3),
    )
    repository.update_job(second_job, expected_status="queued")
    second_session = transition_session(
        retried_session,
        "running_round_1",
        at=NOW + timedelta(seconds=3),
    )
    repository.update_session(second_session, expected_status="queued_round_1")
    failed_session, failed_job = repository.fail_exhausted_job(
        queued_job.id,
        expected_attempt_count=2,
    )

    assert retried_session.status == "queued_round_1"
    assert retried_job.status == "queued"
    assert failed_session.safe_error_code == "debate_retry_exhausted"
    assert failed_job.safe_error_code == "debate_retry_exhausted"
    assert "rpc/requeue_debate_job" in fake.rpc_calls
    assert "rpc/fail_exhausted_debate_job" in fake.rpc_calls


def test_supabase_repository_round_trips_atomic_round_two_admission() -> None:
    from test_debate_orchestrator import (
        INTERVENTION_ID,
        build_round_two_job,
        start_round_one,
    )

    source_repository, _, orchestrator, awaiting = start_round_one()
    transcript = source_repository.list_messages(
        awaiting.id,
        awaiting.user_id,
        branch_id=awaiting.active_branch_id,
    )
    target = transcript[-1]
    fake = FakeDebatePostgrest()
    fake.sessions[str(awaiting.id)] = awaiting.model_dump(mode="json")
    fake.messages = {
        str(message.id): message.model_dump(mode="json") for message in transcript
    }
    repository = build_repository(fake)
    intervention = DebateIntervention(
        id=INTERVENTION_ID,
        session_id=awaiting.id,
        user_id=awaiting.user_id,
        selected_message_id=target.id,
        selected_text=target.content[:40],
        question="Which missing evidence could change this assessment?",
        mode="challenge",
        created_at=awaiting.updated_at + timedelta(seconds=1),
    )
    job = build_round_two_job(awaiting)
    queued, question = orchestrator.prepare_challenge(intervention, job)
    message = DebateQueueMessage(
        job_id=job.id,
        session_id=queued.id,
        job_type=job.job_type,
        trace_id="trace_round_two_002",
        enqueued_at=job.created_at,
    )

    admitted = repository.create_round_two_with_job_and_enqueue(
        intervention,
        question,
        queued,
        job,
        message,
    )
    repeated = repository.create_round_two_with_job_and_enqueue(
        intervention,
        question,
        queued,
        job,
        message,
    )

    assert admitted == repeated
    assert admitted[0] == queued
    assert admitted[1].queue_message_id == 1
    assert "rpc/enqueue_debate_round_two" in fake.rpc_calls
