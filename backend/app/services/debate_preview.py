from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from uuid import UUID, uuid4, uuid5

from pydantic import JsonValue

from app.domain.debate import DebateIntervention, DebateSession, DebateSide
from app.domain.events import DebateEventType
from app.domain.factors import AnalysisContext, FactorSnapshot
from app.domain.jobs import DebateJob, DebateQueueMessage
from app.providers.debate_agents import (
    DebateJudgeProvider,
    DebateStreamingJudgeProvider,
    DebateStreamingTurnProvider,
    DebateTurnProvider,
)
from app.repositories.debate_repository import (
    DebateConcurrencyError,
    DebateQueueRepository,
    DebateRepositoryError,
    DebateUnitOfWork,
)
from app.services.debate_event_broker import DebateEventPublisher
from app.services.debate_orchestrator import DebateOrchestrator
from app.services.debate_state import transition_session


class DebatePreviewService:
    """Default-off admission facade for synchronous and queued Debate paths."""

    def __init__(
        self,
        repository: DebateUnitOfWork,
        turn_provider: DebateTurnProvider,
        judge_provider: DebateJudgeProvider,
        *,
        streaming_turn_provider: DebateStreamingTurnProvider | None = None,
        streaming_judge_provider: DebateStreamingJudgeProvider | None = None,
        checkpoint_drafts: bool = False,
        event_publisher: DebateEventPublisher | None = None,
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
            streaming_turn_provider=streaming_turn_provider,
            streaming_judge_provider=streaming_judge_provider,
            checkpoint_drafts=checkpoint_drafts,
            event_publisher=event_publisher,
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
        self._emit(
            queued.id,
            "session.created",
            {
                "status": queued.status,
                "ticker": queued.ticker,
                "generation_id": str(queued.active_generation_id),
            },
        )
        self._emit(
            queued.id,
            "job.queued",
            {"job_id": str(job.id), "job_type": job.job_type},
        )
        return self.orchestrator.execute_job(job.id), job

    def create_queued_round_one(
        self,
        *,
        user_id: UUID,
        stock_id: int,
        ticker: str,
        opening_side: DebateSide,
        question: str | None,
        idempotency_key: str | None,
        analysis_context: AnalysisContext,
        factor_snapshot: FactorSnapshot,
    ) -> tuple[DebateSession, DebateJob]:
        if not isinstance(self.repository, DebateQueueRepository):
            raise DebateRepositoryError("Debate Queue persistence is not configured")

        created_at = self.clock()
        if idempotency_key:
            session_id = uuid5(user_id, f"debate:{idempotency_key}")
            branch_id = uuid5(session_id, "branch:initial")
            generation_id = uuid5(session_id, "generation:round-1")
            job_id = uuid5(session_id, "job:round-1")
            existing_session = self.repository.get_session(session_id, user_id)
            existing_job = self.repository.get_job(job_id)
            if existing_session is not None or existing_job is not None:
                if (
                    existing_session is None
                    or existing_job is None
                    or existing_session.stock_id != stock_id
                    or existing_session.ticker != ticker.upper()
                    or existing_session.opening_side != opening_side
                    or existing_session.initial_question != question
                    or existing_job.session_id != session_id
                    or existing_job.job_type != "round_1"
                ):
                    raise DebateConcurrencyError(
                        "Debate idempotency key conflicts with another request"
                    )
                return existing_session, existing_job
            job_idempotency_key = f"round-1:{user_id}:{idempotency_key}"
        else:
            session_id = self.id_factory()
            branch_id = self.id_factory()
            generation_id = self.id_factory()
            job_id = self.id_factory()
            job_idempotency_key = f"round-1:{session_id}:{branch_id}"

        session = DebateSession(
            id=session_id,
            user_id=user_id,
            stock_id=stock_id,
            ticker=ticker,
            mode="demo",
            opening_side=opening_side,
            initial_question=question,
            active_branch_id=branch_id,
            active_generation_id=generation_id,
            analysis_context=analysis_context,
            factor_snapshot=factor_snapshot,
            created_at=created_at,
            updated_at=created_at,
        )
        queued = transition_session(session, "queued_round_1", at=created_at)
        job = DebateJob(
            id=job_id,
            session_id=queued.id,
            user_id=user_id,
            job_type="round_1",
            idempotency_key=job_idempotency_key,
            available_at=created_at,
            created_at=created_at,
            updated_at=created_at,
        )
        message = DebateQueueMessage(
            job_id=job.id,
            session_id=queued.id,
            job_type=job.job_type,
            trace_id=f"trace_{job.id.hex}",
            enqueued_at=created_at,
        )
        queued, job = self.repository.create_session_with_job_and_enqueue(
            queued,
            job,
            message,
        )
        self._emit(
            queued.id,
            "session.created",
            {
                "status": queued.status,
                "ticker": queued.ticker,
                "generation_id": str(queued.active_generation_id),
                "execution_mode": "queued",
            },
        )
        self._emit(
            queued.id,
            "job.queued",
            {
                "job_id": str(job.id),
                "job_type": job.job_type,
                "queue_message_id": job.queue_message_id,
                "generation_id": str(queued.active_generation_id),
            },
        )
        return queued, job

    def has_queued_round_one_admission(
        self,
        user_id: UUID,
        idempotency_key: str | None,
    ) -> bool:
        """Detect an idempotent retry before applying new-work admission limits."""

        if not idempotency_key or not isinstance(self.repository, DebateQueueRepository):
            return False
        session_id = uuid5(user_id, f"debate:{idempotency_key}")
        job_id = uuid5(session_id, "job:round-1")
        return (
            self.repository.get_session(session_id, user_id) is not None
            or self.repository.get_job(job_id) is not None
        )

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
        queued = self.orchestrator.submit_challenge(intervention, job)
        self._emit(
            queued.id,
            "job.queued",
            {
                "job_id": str(job.id),
                "job_type": job.job_type,
                "generation_id": str(queued.active_generation_id),
            },
        )
        return self.orchestrator.execute_job(job.id), job

    def create_queued_round_two(
        self,
        *,
        session: DebateSession,
        selected_message_id: UUID,
        selected_text: str,
        question: str,
        idempotency_key: str | None,
    ) -> tuple[DebateSession, DebateJob]:
        if not isinstance(self.repository, DebateQueueRepository):
            raise DebateRepositoryError("Debate Queue persistence is not configured")

        if idempotency_key:
            intervention_id = uuid5(session.id, f"intervention:{idempotency_key}")
            job_id = uuid5(session.id, f"job:round-2:{idempotency_key}")
            question_id = uuid5(
                session.id,
                f"intervention-message:{intervention_id}",
            )
            existing_job = self.repository.get_job(job_id)
            if existing_job is not None:
                current = self.repository.get_session(session.id, session.user_id)
                transcript = self.repository.list_messages(
                    session.id,
                    session.user_id,
                    branch_id=session.active_branch_id,
                )
                stored_question = next(
                    (message for message in transcript if message.id == question_id),
                    None,
                )
                if (
                    current is None
                    or stored_question is None
                    or existing_job.session_id != session.id
                    or existing_job.user_id != session.user_id
                    or existing_job.job_type != "round_2"
                    or existing_job.queue_message_id is None
                    or stored_question.content != question
                    or stored_question.metadata.get("selected_message_id")
                    != str(selected_message_id)
                    or stored_question.metadata.get("selected_text") != selected_text
                    or stored_question.metadata.get("intervention_id")
                    != str(intervention_id)
                ):
                    raise DebateConcurrencyError(
                        "Debate challenge idempotency key conflicts with another request"
                    )
                return current, existing_job
            job_idempotency_key = f"round-2:{session.id}:{idempotency_key}"
        else:
            intervention_id = self.id_factory()
            job_id = self.id_factory()
            job_idempotency_key = f"round-2:{session.id}:{intervention_id}"

        created_at = max(self.clock(), session.updated_at)
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
            id=job_id,
            session_id=session.id,
            user_id=session.user_id,
            job_type="round_2",
            idempotency_key=job_idempotency_key,
            available_at=created_at,
            created_at=created_at,
            updated_at=created_at,
        )
        queued, user_question = self.orchestrator.prepare_challenge(intervention, job)
        message = DebateQueueMessage(
            job_id=job.id,
            session_id=queued.id,
            job_type=job.job_type,
            trace_id=f"trace_{job.id.hex}",
            enqueued_at=created_at,
        )
        queued, job = self.repository.create_round_two_with_job_and_enqueue(
            intervention,
            user_question,
            queued,
            job,
            message,
        )
        self._emit(
            queued.id,
            "job.queued",
            {
                "job_id": str(job.id),
                "job_type": job.job_type,
                "queue_message_id": job.queue_message_id,
                "generation_id": str(queued.active_generation_id),
            },
        )
        return queued, job

    def _emit(
        self,
        session_id: UUID,
        event_type: DebateEventType,
        payload: dict[str, JsonValue],
    ) -> None:
        publisher = self.orchestrator.event_publisher
        if publisher is None:
            return
        try:
            publisher.publish(
                session_id,
                event_type,
                payload=payload,
            )
        except Exception:
            # Canonical Session/Job records remain valid if the transient
            # process-local preview stream is unavailable.
            return
