from __future__ import annotations

from threading import RLock
from typing import TypeVar
from uuid import UUID

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


DomainModel = TypeVar("DomainModel", bound=ImmutableDomainModel)


def _clone(model: DomainModel) -> DomainModel:
    """Return a deep validated copy so nested mutable JSON cannot leak state."""

    return type(model).model_validate(model.model_dump(mode="python"))


class InMemoryDebateRepository:
    """Deterministic Phase 3 repository with production-equivalent invariants.

    This adapter is the credential-free execution/test implementation. Supabase
    remains the target canonical store; both adapters share the same domain
    protocols and optimistic status checks.
    """

    def __init__(self) -> None:
        self._sessions: dict[UUID, DebateSession] = {}
        self._messages: dict[UUID, DebateMessage] = {}
        self._message_keys: dict[tuple[UUID, UUID, int], UUID] = {}
        self._citations: dict[UUID, tuple[DebateMessageEvidence, ...]] = {}
        self._interventions: dict[UUID, DebateIntervention] = {}
        self._jobs: dict[UUID, DebateJob] = {}
        self._job_keys: dict[str, UUID] = {}
        self._lock = RLock()

    def create_session(self, session: DebateSession) -> DebateSession:
        with self._lock:
            if session.id in self._sessions:
                raise DebateConcurrencyError("Debate session already exists")
            self._sessions[session.id] = _clone(session)
            return _clone(session)

    def get_session(self, session_id: UUID, user_id: UUID) -> DebateSession | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None or session.user_id != user_id:
                return None
            return _clone(session)

    def list_sessions(
        self,
        user_id: UUID,
        *,
        limit: int = 50,
    ) -> list[DebateSession]:
        bounded_limit = max(1, min(limit, 100))
        with self._lock:
            sessions = sorted(
                (session for session in self._sessions.values() if session.user_id == user_id),
                key=lambda session: (session.created_at, str(session.id)),
                reverse=True,
            )
            return [_clone(session) for session in sessions[:bounded_limit]]

    def update_session(
        self,
        session: DebateSession,
        *,
        expected_status: DebateSessionStatus,
    ) -> DebateSession:
        with self._lock:
            current = self._sessions.get(session.id)
            if current is None:
                raise DebateRepositoryError("Debate session not found")
            if current.status != expected_status:
                raise DebateConcurrencyError("Debate session status changed concurrently")
            try:
                validate_session_update(current, session)
            except DebatePersistenceValidationError as exc:
                raise DebateRepositoryError(str(exc)) from exc
            self._sessions[session.id] = _clone(session)
            return _clone(session)

    def append_message(
        self,
        message: DebateMessage,
        citations: tuple[DebateMessageEvidence, ...] = (),
    ) -> DebateMessage:
        with self._lock:
            session = self._sessions.get(message.session_id)
            if session is None:
                raise DebateRepositoryError("Debate session not found")
            self._validate_citations(message, citations)
            existing = self._messages.get(message.id)
            if existing is not None:
                if existing == message and self._citations.get(message.id, ()) == citations:
                    return _clone(existing)
                raise DebateConcurrencyError("Debate message identifier already exists")
            unique_key = (message.session_id, message.branch_id, message.sequence_number)
            if unique_key in self._message_keys:
                raise DebateConcurrencyError("Debate message sequence already exists")
            self._messages[message.id] = _clone(message)
            self._message_keys[unique_key] = message.id
            self._citations[message.id] = tuple(_clone(citation) for citation in citations)
            return _clone(message)

    def list_messages(
        self,
        session_id: UUID,
        user_id: UUID,
        *,
        branch_id: UUID,
    ) -> list[DebateMessage]:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None or session.user_id != user_id:
                return []
            messages = sorted(
                (
                    message
                    for message in self._messages.values()
                    if message.session_id == session_id and message.branch_id == branch_id
                ),
                key=lambda message: message.sequence_number,
            )
            return [_clone(message) for message in messages]

    def list_message_evidence(
        self,
        message_id: UUID,
        user_id: UUID,
    ) -> tuple[DebateMessageEvidence, ...]:
        with self._lock:
            message = self._messages.get(message_id)
            if message is None:
                return ()
            session = self._sessions.get(message.session_id)
            if session is None or session.user_id != user_id:
                return ()
            return tuple(_clone(citation) for citation in self._citations.get(message_id, ()))

    def create_intervention(
        self,
        intervention: DebateIntervention,
    ) -> DebateIntervention:
        with self._lock:
            session = self._sessions.get(intervention.session_id)
            if session is None or session.user_id != intervention.user_id:
                raise DebateRepositoryError("Debate session not found")
            selected_message = self._messages.get(intervention.selected_message_id)
            if selected_message is None or selected_message.session_id != intervention.session_id:
                raise DebateRepositoryError("Selected Debate message not found")
            existing = self._interventions.get(intervention.id)
            if existing is not None:
                if existing == intervention:
                    return _clone(existing)
                raise DebateConcurrencyError("Debate intervention identifier already exists")
            self._interventions[intervention.id] = _clone(intervention)
            return _clone(intervention)

    def create_job(self, job: DebateJob) -> DebateJob:
        with self._lock:
            self._validate_job_owner(job)
            existing = self._jobs.get(job.id)
            if existing is not None:
                if existing == job:
                    return _clone(existing)
                raise DebateConcurrencyError("Debate job identifier already exists")
            existing_id = self._job_keys.get(job.idempotency_key)
            if existing_id is not None:
                existing_job = self._jobs[existing_id]
                if existing_job == job:
                    return _clone(existing_job)
                raise DebateConcurrencyError("Debate job idempotency key already exists")
            self._jobs[job.id] = _clone(job)
            self._job_keys[job.idempotency_key] = job.id
            return _clone(job)

    def get_job(self, job_id: UUID) -> DebateJob | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return _clone(job) if job is not None else None

    def update_job(
        self,
        job: DebateJob,
        *,
        expected_status: DebateJobStatus,
    ) -> DebateJob:
        with self._lock:
            current = self._jobs.get(job.id)
            if current is None:
                raise DebateRepositoryError("Debate job not found")
            if current.status != expected_status:
                raise DebateConcurrencyError("Debate job status changed concurrently")
            try:
                validate_job_update(current, job)
            except DebatePersistenceValidationError as exc:
                raise DebateRepositoryError(str(exc)) from exc
            self._jobs[job.id] = _clone(job)
            return _clone(job)

    def create_session_with_job(
        self,
        session: DebateSession,
        job: DebateJob,
    ) -> tuple[DebateSession, DebateJob]:
        with self._lock:
            if job.session_id != session.id or job.user_id != session.user_id:
                raise DebateRepositoryError("Initial Debate job owner does not match its session")
            existing_session = self._sessions.get(session.id)
            existing_job = self._jobs.get(job.id)
            if existing_session is not None or existing_job is not None:
                if existing_session == session and existing_job == job:
                    return _clone(existing_session), _clone(existing_job)
                raise DebateConcurrencyError("Initial Debate session or job already exists")
            if job.idempotency_key in self._job_keys:
                raise DebateConcurrencyError("Debate job idempotency key already exists")
            self._sessions[session.id] = _clone(session)
            self._jobs[job.id] = _clone(job)
            self._job_keys[job.idempotency_key] = job.id
            return _clone(session), _clone(job)

    @staticmethod
    def _validate_citations(
        message: DebateMessage,
        citations: tuple[DebateMessageEvidence, ...],
    ) -> None:
        if any(citation.message_id != message.id for citation in citations):
            raise DebateRepositoryError("Citation message does not match the Debate message")
        orders = [citation.citation_order for citation in citations]
        evidence_ids = [citation.evidence_id for citation in citations]
        if len(orders) != len(set(orders)) or len(evidence_ids) != len(set(evidence_ids)):
            raise DebateConcurrencyError("Debate message citations must be unique")

    def _validate_job_owner(self, job: DebateJob) -> None:
        session = self._sessions.get(job.session_id)
        if session is None or session.user_id != job.user_id:
            raise DebateRepositoryError("Debate session not found")
