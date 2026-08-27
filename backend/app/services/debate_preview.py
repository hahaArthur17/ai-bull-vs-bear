from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.domain.debate import DebateIntervention, DebateSession, DebateSide
from app.domain.factors import AnalysisContext, FactorSnapshot
from app.domain.jobs import DebateJob
from app.providers.debate_agents import DebateJudgeProvider, DebateTurnProvider
from app.repositories.debate_repository import DebateUnitOfWork
from app.services.debate_orchestrator import DebateOrchestrator
from app.services.debate_state import transition_session


class DebatePreviewService:
    """Synchronous Phase 3 adapter around the durable Debate domain.

    This service deliberately has no Queue or streaming behavior. It exists so
    the default-off API can exercise the canonical Session/Message workflow
    before later phases replace synchronous execution with a Worker.
    """

    def __init__(
        self,
        repository: DebateUnitOfWork,
        turn_provider: DebateTurnProvider,
        judge_provider: DebateJudgeProvider,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], UUID] | None = None,
    ) -> None:
        self.repository = repository
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.id_factory = id_factory or uuid4
        self.orchestrator = DebateOrchestrator(
            repository,
            turn_provider,
            judge_provider,
            clock=self.clock,
        )

    def create_and_execute_round_one(
        self,
        *,
        user_id: UUID,
        stock_id: int,
        ticker: str,
        opening_side: DebateSide,
        question: str | None,
        analysis_context: AnalysisContext,
        factor_snapshot: FactorSnapshot,
    ) -> tuple[DebateSession, DebateJob]:
        created_at = self.clock()
        session_id = self.id_factory()
        branch_id = self.id_factory()
        session = DebateSession(
            id=session_id,
            user_id=user_id,
            stock_id=stock_id,
            ticker=ticker,
            mode="demo",
            opening_side=opening_side,
            initial_question=question,
            active_branch_id=branch_id,
            active_generation_id=self.id_factory(),
            analysis_context=analysis_context,
            factor_snapshot=factor_snapshot,
            created_at=created_at,
            updated_at=created_at,
        )
        queued = transition_session(session, "queued_round_1", at=created_at)
        job = DebateJob(
            id=self.id_factory(),
            session_id=queued.id,
            user_id=user_id,
            job_type="round_1",
            idempotency_key=f"round-1:{queued.id}:{branch_id}",
            available_at=created_at,
            created_at=created_at,
            updated_at=created_at,
        )
        self.repository.create_session_with_job(queued, job)
        return self.orchestrator.execute_job(job.id), job

    def submit_challenge_and_execute_round_two(
        self,
        *,
        session: DebateSession,
        selected_message_id: UUID,
        selected_text: str,
        question: str,
    ) -> tuple[DebateSession, DebateJob]:
        created_at = max(self.clock(), session.updated_at)
        intervention_id = self.id_factory()
        intervention = DebateIntervention(
            id=intervention_id,
            session_id=session.id,
            user_id=session.user_id,
            selected_message_id=selected_message_id,
            selected_text=selected_text,
            question=question,
            mode="challenge",
            created_at=created_at,
        )
        job = DebateJob(
            id=self.id_factory(),
            session_id=session.id,
            user_id=session.user_id,
            job_type="round_2",
            idempotency_key=f"round-2:{session.id}:{intervention_id}",
            available_at=created_at,
            created_at=created_at,
            updated_at=created_at,
        )
        self.orchestrator.submit_challenge(intervention, job)
        return self.orchestrator.execute_job(job.id), job
