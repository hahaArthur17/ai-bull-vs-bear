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
from app.domain.jobs import DebateJob, DebateJobStatus
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
