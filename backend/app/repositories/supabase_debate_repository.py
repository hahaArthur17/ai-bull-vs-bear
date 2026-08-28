from __future__ import annotations

from typing import Any, TypeVar
from uuid import UUID

import httpx
from pydantic import ValidationError

from app.domain.base import ImmutableDomainModel
from app.domain.debate import (
    DebateIntervention,
    DebateMessage,
    DebateMessageEvidence,
    DebateSession,
    DebateSessionStatus,
)
from app.domain.jobs import (
    ClaimedDebateQueueMessage,
    DebateJob,
    DebateJobStatus,
    DebateQueueMessage,
)
from app.repositories.debate_repository import (
    DebateConcurrencyError,
    DebateRepositoryError,
)
from app.services.debate_persistence import (
    DebatePersistenceValidationError,
    validate_job_update,
    validate_session_update,
)
from app.services.supabase_headers import service_headers


DomainModel = TypeVar("DomainModel", bound=ImmutableDomainModel)


class SupabaseDebateRepository:
    """Canonical Debate persistence using a server-only Supabase key."""

    def __init__(
        self,
        supabase_url: str,
        secret_key: str,
        client: httpx.Client | None = None,
    ) -> None:
        if not supabase_url.strip() or not secret_key.strip():
            raise ValueError("Supabase Debate persistence requires a URL and secret key")
        self.rest_url = f"{supabase_url.rstrip('/')}/rest/v1"
        self.secret_key = secret_key
        self.client = client

    def create_session(self, session: DebateSession) -> DebateSession:
        response = self._request(
            "POST",
            "debate_sessions",
            json=session.model_dump(mode="json"),
        )
        return self._one_model(response.json(), DebateSession, "Debate session")

    def get_session(self, session_id: UUID, user_id: UUID) -> DebateSession | None:
        response = self._request(
            "GET",
            "debate_sessions",
            params={
                "select": "*",
                "id": f"eq.{session_id}",
                "user_id": f"eq.{user_id}",
                "limit": "1",
            },
        )
        return self._optional_model(response.json(), DebateSession, "Debate session")

    def list_sessions(
        self,
        user_id: UUID,
        *,
        limit: int = 50,
    ) -> list[DebateSession]:
        response = self._request(
            "GET",
            "debate_sessions",
            params={
                "select": "*",
                "user_id": f"eq.{user_id}",
                "order": "created_at.desc,id.desc",
                "limit": str(max(1, min(limit, 100))),
            },
        )
        return self._models(response.json(), DebateSession, "Debate session")

    def update_session(
        self,
        session: DebateSession,
        *,
        expected_status: DebateSessionStatus,
    ) -> DebateSession:
        current = self.get_session(session.id, session.user_id)
        if current is None or current.status != expected_status:
            raise DebateConcurrencyError("Debate session status changed concurrently")
        try:
            validate_session_update(current, session)
        except DebatePersistenceValidationError as exc:
            raise DebateRepositoryError(str(exc)) from exc
        payload = session.model_dump(mode="json", include={
            "status",
            "active_branch_id",
            "active_generation_id",
            "interim_judge_message_id",
            "final_judge_message_id",
            "guardrail_status",
            "safe_error_code",
            "updated_at",
            "completed_at",
        })
        response = self._request(
            "PATCH",
            "debate_sessions",
            params={"id": f"eq.{session.id}", "status": f"eq.{expected_status}"},
            json=payload,
        )
        updated = self._optional_model(response.json(), DebateSession, "Debate session")
        if updated is None:
            raise DebateConcurrencyError("Debate session status changed concurrently")
        if updated != session:
            raise DebateConcurrencyError("Debate session update was not canonical")
        return updated

    def append_message(
        self,
        message: DebateMessage,
        citations: tuple[DebateMessageEvidence, ...] = (),
    ) -> DebateMessage:
        response = self._request(
            "POST",
            "rpc/append_debate_message",
            json={
                "message_payload": message.model_dump(mode="json"),
                "citations_payload": [citation.model_dump(mode="json") for citation in citations],
            },
        )
        payload = self._object(response.json(), "Debate message transaction")
        stored_message = self._model(payload.get("message"), DebateMessage, "Debate message")
        stored_citations = tuple(
            self._models(payload.get("citations"), DebateMessageEvidence, "Debate citation")
        )
        if stored_message != message or stored_citations != citations:
            raise DebateConcurrencyError("Debate message idempotency conflict")
        return stored_message

    def list_messages(
        self,
        session_id: UUID,
        user_id: UUID,
        *,
        branch_id: UUID,
    ) -> list[DebateMessage]:
        if self.get_session(session_id, user_id) is None:
            return []
        response = self._request(
            "GET",
            "debate_messages",
            params={
                "select": "*",
                "session_id": f"eq.{session_id}",
                "branch_id": f"eq.{branch_id}",
                "order": "sequence_number.asc",
            },
        )
        return self._models(response.json(), DebateMessage, "Debate message")

    def list_message_evidence(
        self,
        message_id: UUID,
        user_id: UUID,
    ) -> tuple[DebateMessageEvidence, ...]:
        message_response = self._request(
            "GET",
            "debate_messages",
            params={"select": "session_id", "id": f"eq.{message_id}", "limit": "1"},
        )
        rows = message_response.json()
        if not isinstance(rows, list) or not rows:
            return ()
        try:
            session_id = UUID(str(rows[0]["session_id"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise DebateRepositoryError("Supabase Debate message returned an invalid row") from exc
        if self.get_session(session_id, user_id) is None:
            return ()
        response = self._request(
            "GET",
            "debate_message_evidence",
            params={
                "select": "*",
                "message_id": f"eq.{message_id}",
                "order": "citation_order.asc",
            },
        )
        return tuple(self._models(response.json(), DebateMessageEvidence, "Debate citation"))

    def create_intervention(
        self,
        intervention: DebateIntervention,
    ) -> DebateIntervention:
        response = self._request(
            "POST",
            "debate_interventions",
            json=intervention.model_dump(mode="json"),
        )
        return self._one_model(response.json(), DebateIntervention, "Debate intervention")

    def create_job(self, job: DebateJob) -> DebateJob:
        response = self._request(
            "POST",
            "debate_jobs",
            json=job.model_dump(mode="json"),
        )
        return self._one_model(response.json(), DebateJob, "Debate job")

    def get_job(self, job_id: UUID) -> DebateJob | None:
        response = self._request(
            "GET",
            "debate_jobs",
            params={"select": "*", "id": f"eq.{job_id}", "limit": "1"},
        )
        return self._optional_model(response.json(), DebateJob, "Debate job")

    def get_active_job(self, session_id: UUID, user_id: UUID) -> DebateJob | None:
        if self.get_session(session_id, user_id) is None:
            return None
        response = self._request(
            "GET",
            "debate_jobs",
            params={
                "select": "*",
                "session_id": f"eq.{session_id}",
                "user_id": f"eq.{user_id}",
                "status": "in.(queued,running)",
                "order": "created_at.desc",
                "limit": "2",
            },
        )
        jobs = self._models(response.json(), DebateJob, "Debate job")
        if len(jobs) > 1:
            raise DebateRepositoryError("Debate session has multiple active jobs")
        return jobs[0] if jobs else None

    def update_job(
        self,
        job: DebateJob,
        *,
        expected_status: DebateJobStatus,
    ) -> DebateJob:
        current = self.get_job(job.id)
        if current is None:
            raise DebateRepositoryError("Debate job not found")
        if current.status != expected_status:
            raise DebateConcurrencyError("Debate job status changed concurrently")
        try:
            validate_job_update(current, job)
        except DebatePersistenceValidationError as exc:
            raise DebateRepositoryError(str(exc)) from exc
        payload = job.model_dump(mode="json", include={
            "status",
            "queue_message_id",
            "attempt_count",
            "started_at",
            "finished_at",
            "safe_error_code",
            "provider_request_count",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "updated_at",
        })
        response = self._request(
            "PATCH",
            "debate_jobs",
            params={"id": f"eq.{job.id}", "status": f"eq.{expected_status}"},
            json=payload,
        )
        updated = self._optional_model(response.json(), DebateJob, "Debate job")
        if updated is None:
            raise DebateConcurrencyError("Debate job status changed concurrently")
        if updated != job:
            raise DebateConcurrencyError("Debate job update was not canonical")
        return updated

    def create_session_with_job(
        self,
        session: DebateSession,
        job: DebateJob,
    ) -> tuple[DebateSession, DebateJob]:
        if job.session_id != session.id or job.user_id != session.user_id:
            raise DebateRepositoryError("Initial Debate job owner does not match its session")
        response = self._request(
            "POST",
            "rpc/create_debate_session_with_job",
            json={
                "session_payload": session.model_dump(mode="json"),
                "job_payload": job.model_dump(mode="json"),
            },
        )
        payload = self._object(response.json(), "Initial Debate transaction")
        stored_session = self._model(payload.get("session"), DebateSession, "Debate session")
        stored_job = self._model(payload.get("job"), DebateJob, "Debate job")
        if stored_session != session or stored_job != job:
            raise DebateConcurrencyError("Initial Debate idempotency conflict")
        return stored_session, stored_job

    def create_session_with_job_and_enqueue(
        self,
        session: DebateSession,
        job: DebateJob,
        message: DebateQueueMessage,
    ) -> tuple[DebateSession, DebateJob]:
        if job.session_id != session.id or job.user_id != session.user_id:
            raise DebateRepositoryError("Initial Debate job owner does not match its session")
        if job.status != "queued" or job.queue_message_id is not None:
            raise DebateRepositoryError("A new Queue admission requires an unbound queued job")
        if (
            message.job_id != job.id
            or message.session_id != session.id
            or message.job_type != job.job_type
        ):
            raise DebateRepositoryError("Debate Queue message does not match its job")
        response = self._request(
            "POST",
            "rpc/enqueue_debate_session_job",
            json={
                "session_payload": session.model_dump(mode="json"),
                "job_payload": job.model_dump(mode="json"),
                "queue_payload": message.model_dump(mode="json"),
            },
        )
        payload = self._object(response.json(), "Queued Debate admission")
        stored_session = self._model(payload.get("session"), DebateSession, "Debate session")
        stored_job = self._model(payload.get("job"), DebateJob, "Debate job")
        if stored_job.queue_message_id is None:
            raise DebateRepositoryError("Queued Debate job is missing its Queue message")
        expected_job = DebateJob.model_validate(
            {
                **job.model_dump(mode="python"),
                "queue_message_id": stored_job.queue_message_id,
            }
        )
        if stored_session != session or stored_job != expected_job:
            raise DebateConcurrencyError("Queued Debate admission idempotency conflict")
        if payload.get("queue_message_id") != stored_job.queue_message_id:
            raise DebateConcurrencyError("Queued Debate message identifier conflict")
        return stored_session, stored_job

    def claim_job(
        self,
        *,
        visibility_timeout_seconds: int,
    ) -> ClaimedDebateQueueMessage | None:
        if not 30 <= visibility_timeout_seconds <= 3600:
            raise DebateRepositoryError("Queue visibility timeout is outside safe bounds")
        response = self._request(
            "POST",
            "rpc/claim_debate_job",
            json={"visibility_timeout_seconds": visibility_timeout_seconds},
        )
        payload = response.json()
        if payload is None:
            return None
        return self._model(payload, ClaimedDebateQueueMessage, "Claimed Debate Queue message")

    def archive_job_message(self, queue_message_id: int) -> bool:
        if queue_message_id <= 0:
            raise DebateRepositoryError("Queue message identifier must be positive")
        response = self._request(
            "POST",
            "rpc/archive_debate_job",
            json={"queue_message_id": queue_message_id},
        )
        payload = response.json()
        if not isinstance(payload, bool):
            raise DebateRepositoryError("Supabase Queue archive returned an invalid response")
        return payload

    def retry_job_message(self, queue_message_id: int, *, delay_seconds: int) -> bool:
        if queue_message_id <= 0 or not 0 <= delay_seconds <= 3600:
            raise DebateRepositoryError("Queue retry arguments are outside safe bounds")
        response = self._request(
            "POST",
            "rpc/retry_debate_job",
            json={
                "queue_message_id": queue_message_id,
                "delay_seconds": delay_seconds,
            },
        )
        payload = response.json()
        if not isinstance(payload, bool):
            raise DebateRepositoryError("Supabase Queue retry returned an invalid response")
        return payload

    def requeue_running_job(
        self,
        job_id: UUID,
        *,
        expected_attempt_count: int,
        provider_request_count: int = 0,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> tuple[DebateSession, DebateJob]:
        if expected_attempt_count < 1 or min(
            provider_request_count,
            prompt_tokens,
            completion_tokens,
        ) < 0:
            raise DebateRepositoryError("Debate retry observations are outside safe bounds")
        response = self._request(
            "POST",
            "rpc/requeue_debate_job",
            json={
                "debate_job_id": str(job_id),
                "expected_attempt_count": expected_attempt_count,
                "observed_provider_request_count": provider_request_count,
                "observed_prompt_tokens": prompt_tokens,
                "observed_completion_tokens": completion_tokens,
            },
        )
        payload = self._object(response.json(), "Retried Debate transaction")
        session = self._model(payload.get("session"), DebateSession, "Debate session")
        job = self._model(payload.get("job"), DebateJob, "Debate job")
        expected_session_status = (
            "queued_round_1" if job.job_type == "round_1" else "queued_round_2"
        )
        if (
            job.id != job_id
            or job.status != "queued"
            or job.attempt_count != expected_attempt_count
            or session.id != job.session_id
            or session.user_id != job.user_id
            or session.status != expected_session_status
        ):
            raise DebateConcurrencyError("Supabase Debate retry returned conflicting state")
        return session, job

    def fail_exhausted_job(
        self,
        job_id: UUID,
        *,
        expected_attempt_count: int,
    ) -> tuple[DebateSession, DebateJob]:
        if expected_attempt_count < 1:
            raise DebateRepositoryError("Debate retry attempt is outside safe bounds")
        response = self._request(
            "POST",
            "rpc/fail_exhausted_debate_job",
            json={
                "debate_job_id": str(job_id),
                "expected_attempt_count": expected_attempt_count,
            },
        )
        payload = self._object(response.json(), "Exhausted Debate transaction")
        session = self._model(payload.get("session"), DebateSession, "Debate session")
        job = self._model(payload.get("job"), DebateJob, "Debate job")
        if (
            job.id != job_id
            or job.status != "failed"
            or job.safe_error_code != "debate_retry_exhausted"
            or session.id != job.session_id
            or session.status != "failed"
            or session.safe_error_code != "debate_retry_exhausted"
        ):
            raise DebateConcurrencyError(
                "Supabase exhausted Debate Job returned conflicting state"
            )
        return session, job

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: object | None = None,
    ) -> httpx.Response:
        try:
            requester = self.client.request if self.client is not None else httpx.request
            response = requester(
                method,
                f"{self.rest_url}/{path}",
                params=params,
                json=json,
                headers=service_headers(self.secret_key, "return=representation"),
                timeout=10.0,
            )
        except httpx.RequestError as exc:
            raise DebateRepositoryError("Supabase Debate persistence is unavailable") from exc
        if response.status_code == 409:
            raise DebateConcurrencyError("Supabase Debate persistence conflict")
        if response.status_code >= 400:
            raise DebateRepositoryError(
                f"Supabase Debate request failed with status {response.status_code}"
            )
        return response

    @classmethod
    def _one_model(
        cls,
        payload: object,
        model_type: type[DomainModel],
        label: str,
    ) -> DomainModel:
        model = cls._optional_model(payload, model_type, label)
        if model is None:
            raise DebateRepositoryError(f"Supabase {label} write returned no row")
        return model

    @classmethod
    def _optional_model(
        cls,
        payload: object,
        model_type: type[DomainModel],
        label: str,
    ) -> DomainModel | None:
        models = cls._models(payload, model_type, label)
        return models[0] if models else None

    @staticmethod
    def _models(
        payload: object,
        model_type: type[DomainModel],
        label: str,
    ) -> list[DomainModel]:
        if not isinstance(payload, list):
            raise DebateRepositoryError(f"Supabase {label} returned an invalid payload")
        try:
            return [model_type.model_validate(row) for row in payload]
        except ValidationError as exc:
            raise DebateRepositoryError(f"Supabase {label} returned an invalid row") from exc

    @staticmethod
    def _model(
        payload: object,
        model_type: type[DomainModel],
        label: str,
    ) -> DomainModel:
        try:
            return model_type.model_validate(payload)
        except ValidationError as exc:
            raise DebateRepositoryError(f"Supabase {label} returned an invalid row") from exc

    @staticmethod
    def _object(payload: object, label: str) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise DebateRepositoryError(f"Supabase {label} returned an invalid payload")
        return payload
