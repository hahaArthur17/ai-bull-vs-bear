from uuid import UUID

from app.domain.debate import (
    DebateIntervention,
    DebateMessage,
    DebateMessageEvidence,
    DebateSession,
    DebateSessionStatus,
)
from app.domain.jobs import DebateJob, DebateJobStatus
from app.repositories.debate_repository import (
    DebateJobRepository,
    DebateSessionRepository,
    DebateUnitOfWork,
)


class ContractOnlyRepository:
    """Signature proof only; persistence behaviour is tested with Phase 3 adapters."""

    def create_session(self, session: DebateSession) -> DebateSession:
        return session

    def get_session(self, session_id: UUID, user_id: UUID) -> DebateSession | None:
        return None

    def list_sessions(self, user_id: UUID, *, limit: int = 50) -> list[DebateSession]:
        return []

    def update_session(
        self,
        session: DebateSession,
        *,
        expected_status: DebateSessionStatus,
    ) -> DebateSession:
        return session

    def append_message(
        self,
        message: DebateMessage,
        citations: tuple[DebateMessageEvidence, ...] = (),
    ) -> DebateMessage:
        return message

    def list_messages(
        self,
        session_id: UUID,
        user_id: UUID,
        *,
        branch_id: UUID,
    ) -> list[DebateMessage]:
        return []

    def list_message_evidence(
        self,
        message_id: UUID,
        user_id: UUID,
    ) -> tuple[DebateMessageEvidence, ...]:
        return ()

    def create_intervention(
        self,
        intervention: DebateIntervention,
    ) -> DebateIntervention:
        return intervention

    def create_job(self, job: DebateJob) -> DebateJob:
        return job

    def get_job(self, job_id: UUID) -> DebateJob | None:
        return None

    def update_job(
        self,
        job: DebateJob,
        *,
        expected_status: DebateJobStatus,
    ) -> DebateJob:
        return job

    def create_session_with_job(
        self,
        session: DebateSession,
        job: DebateJob,
    ) -> tuple[DebateSession, DebateJob]:
        return session, job


def test_repository_contracts_are_structural_and_database_independent() -> None:
    repository = ContractOnlyRepository()

    assert isinstance(repository, DebateSessionRepository)
    assert isinstance(repository, DebateJobRepository)
    assert isinstance(repository, DebateUnitOfWork)
