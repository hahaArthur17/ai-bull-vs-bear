from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

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


class DebateRepositoryError(RuntimeError):
    """Safe persistence failure that must not expose database payloads."""


class DebateConcurrencyError(DebateRepositoryError):
    """Optimistic state or idempotency conflict."""


@runtime_checkable
class DebateSessionRepository(Protocol):
    def create_session(self, session: DebateSession) -> DebateSession:
        ...

    def get_session(self, session_id: UUID, user_id: UUID) -> DebateSession | None:
        ...

    def list_sessions(
        self,
        user_id: UUID,
        *,
        limit: int = 50,
    ) -> list[DebateSession]:
        ...

    def update_session(
        self,
        session: DebateSession,
        *,
        expected_status: DebateSessionStatus,
    ) -> DebateSession:
        ...

    def append_message(
        self,
        message: DebateMessage,
        citations: tuple[DebateMessageEvidence, ...] = (),
    ) -> DebateMessage:
        ...

    def list_messages(
        self,
        session_id: UUID,
        user_id: UUID,
        *,
        branch_id: UUID,
    ) -> list[DebateMessage]:
        ...

    def list_message_evidence(
        self,
        message_id: UUID,
        user_id: UUID,
    ) -> tuple[DebateMessageEvidence, ...]:
        ...

    def create_intervention(
        self,
        intervention: DebateIntervention,
    ) -> DebateIntervention:
        ...


@runtime_checkable
class DebateJobRepository(Protocol):
    def create_job(self, job: DebateJob) -> DebateJob:
        ...

    def get_job(self, job_id: UUID) -> DebateJob | None:
        ...

    def get_active_job(self, session_id: UUID, user_id: UUID) -> DebateJob | None:
        ...

    def update_job(
        self,
        job: DebateJob,
        *,
        expected_status: DebateJobStatus,
    ) -> DebateJob:
        ...


@runtime_checkable
class DebateUnitOfWork(DebateSessionRepository, DebateJobRepository, Protocol):
    def create_session_with_job(
        self,
        session: DebateSession,
        job: DebateJob,
    ) -> tuple[DebateSession, DebateJob]:
        """Persist initial state atomically before Queue publication."""

        ...


@runtime_checkable
class DebateQueueRepository(Protocol):
    def create_session_with_job_and_enqueue(
        self,
        session: DebateSession,
        job: DebateJob,
        message: DebateQueueMessage,
    ) -> tuple[DebateSession, DebateJob]:
        """Atomically create canonical admission records and enqueue one stage."""

        ...

    def claim_job(
        self,
        *,
        visibility_timeout_seconds: int,
    ) -> ClaimedDebateQueueMessage | None:
        ...

    def archive_job_message(self, queue_message_id: int) -> bool:
        ...

    def retry_job_message(self, queue_message_id: int, *, delay_seconds: int) -> bool:
        ...

    def requeue_running_job(
        self,
        job_id: UUID,
        *,
        expected_attempt_count: int,
        provider_request_count: int = 0,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> tuple[DebateSession, DebateJob]:
        """Atomically return a running Job and Session to their queued states."""

        ...

    def fail_exhausted_job(
        self,
        job_id: UUID,
        *,
        expected_attempt_count: int,
    ) -> tuple[DebateSession, DebateJob]:
        """Atomically terminalize a running Job whose retry budget is exhausted."""

        ...
