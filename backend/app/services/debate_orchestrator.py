from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timezone
import logging
from uuid import UUID, uuid4, uuid5

from pydantic import JsonValue

from app.domain.agents import (
    DebateJudgeDraft,
    DebateJudgeRequest,
    DebateJudgeStreamDelta,
    DebateTurnDraft,
    DebateTurnRequest,
    DebateTurnStreamDelta,
    DebateTurnStreamUsage,
)
from app.domain.debate import (
    DebateIntervention,
    DebateDraftCheckpoint,
    DebateMessage,
    DebateMessageEvidence,
    DebateRoundPlan,
    DebateSession,
    DebateSessionStatus,
    ProviderAttempt,
    build_round_plan,
)
from app.domain.events import DebateEventType
from app.domain.jobs import DebateJob
from app.providers.debate_agents import (
    DebateJudgeProvider,
    DebateStreamingJudgeProvider,
    DebateStreamingTurnProvider,
    DebateTurnProvider,
)
from app.providers.streaming_debate import (
    WholeDraftJudgeStreamAdapter,
    WholeDraftTurnStreamAdapter,
    preview_text_chunks,
)
from app.repositories.debate_repository import DebateConcurrencyError, DebateUnitOfWork
from app.services.debate_job_state import cancel_job, complete_job, fail_job, start_job
from app.services.debate_event_broker import DebateEventPublisher
from app.services.debate_presentation import build_debate_message_presentation
from app.services.debate_state import (
    attach_judge_message,
    request_session_cancellation,
    transition_session,
)
from app.services.debate_streaming import (
    DebateTurnStreamError,
    collect_debate_judge_stream,
    collect_debate_turn_stream,
)


logger = logging.getLogger(__name__)


class DebateOrchestrationError(RuntimeError):
    """Safe workflow failure that does not expose provider or persistence data."""


class DebateGenerationCancelled(RuntimeError):
    """Internal control flow for a generation invalidated during execution."""


class DebateRetryableOrchestrationError(DebateOrchestrationError):
    """Safe temporary failure carrying only bounded retry accounting metadata."""

    def __init__(
        self,
        *,
        retry_after_seconds: int | None,
        provider_request_count: int,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        super().__init__("Debate provider is temporarily unavailable")
        self.retry_after_seconds = retry_after_seconds
        self.provider_request_count = provider_request_count
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


class DebateOrchestrator:
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
    ) -> None:
        self.repository = repository
        self.checkpoint_drafts = checkpoint_drafts
        self.turn_provider = turn_provider
        self.judge_provider = judge_provider
        self.streaming_turn_provider = streaming_turn_provider or WholeDraftTurnStreamAdapter(
            turn_provider
        )
        self.streaming_judge_provider = streaming_judge_provider or WholeDraftJudgeStreamAdapter(
            judge_provider
        )
        self.event_publisher = event_publisher
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def execute_job(self, job_id: UUID) -> DebateSession:
        job = self.repository.get_job(job_id)
        if job is None:
            raise DebateOrchestrationError("Debate job not found")
        session = self.repository.get_session(job.session_id, job.user_id)
        if session is None:
            raise DebateOrchestrationError("Debate session not found")
        if job.status == "completed":
            return session
        if job.status != "queued" or job.job_type not in {"round_1", "round_2"}:
            raise DebateOrchestrationError("Debate job is not executable")

        round_number = 1 if job.job_type == "round_1" else 2
        queued_status = "queued_round_1" if round_number == 1 else "queued_round_2"
        running_status = "running_round_1" if round_number == 1 else "running_round_2"
        if session.status != queued_status:
            raise DebateOrchestrationError("Debate session is not ready for this job")

        provider_request_count = 0
        try:
            running_job = start_job(job, at=self._at_or_after(job.updated_at))
            running_job = self.repository.update_job(running_job, expected_status="queued")
            self._emit(
                session.id,
                "job.started",
                {
                    "job_id": str(running_job.id),
                    "job_type": running_job.job_type,
                    "attempt_count": running_job.attempt_count,
                },
            )
            running_session = transition_session(
                session,
                running_status,
                at=self._at_or_after(session.updated_at),
            )
            running_session = self.repository.update_session(
                running_session,
                expected_status=queued_status,
                expected_generation_id=session.active_generation_id,
            )
            plan = build_round_plan(round_number, running_session.opening_side)
            transcript = self.repository.list_messages(
                running_session.id,
                running_session.user_id,
                branch_id=running_session.active_branch_id,
            )
            user_intervention = next(
                (
                    message.content
                    for message in reversed(transcript)
                    if message.role == "user" and message.message_kind == "question"
                ),
                None,
            )

            for turn in plan.turns:
                self._assert_generation_active(running_session, running_status)
                provider_request_count += 1
                if turn.role == "judge":
                    running_session = self._append_judge(
                        running_session,
                        transcript,
                        phase=turn.judge_phase or "final",
                        round_number=round_number,
                    )
                else:
                    self._append_turn(
                        running_session,
                        transcript,
                        role=turn.role,
                        message_kind=turn.message_kind,
                        round_number=round_number,
                        exchange_number=turn.exchange_number,
                        user_intervention=user_intervention,
                    )
                transcript = self.repository.list_messages(
                    running_session.id,
                    running_session.user_id,
                    branch_id=running_session.active_branch_id,
                )

            target_status = "awaiting_user" if round_number == 1 else "completed"
            self._assert_generation_active(running_session, running_status)
            finished_session = transition_session(
                running_session,
                target_status,
                at=self._at_or_after(running_session.updated_at),
            )
            finished_session = self.repository.update_session(
                finished_session,
                expected_status=running_status,
                expected_generation_id=running_session.active_generation_id,
            )
            completed_job = complete_job(
                running_job,
                at=self._at_or_after(running_job.updated_at),
                provider_request_count=provider_request_count,
            )
            self.repository.update_job(completed_job, expected_status="running")
            self._emit(
                finished_session.id,
                "session.awaiting_user" if round_number == 1 else "session.completed",
                {
                    "status": finished_session.status,
                    "generation_id": str(finished_session.active_generation_id),
                    "job_id": str(completed_job.id),
                },
            )
            return finished_session
        except DebateGenerationCancelled:
            return self._finish_cancelled_execution(
                job.id,
                session,
                provider_request_count=provider_request_count,
            )
        except Exception as exc:
            if self._generation_was_invalidated(session):
                return self._finish_cancelled_execution(
                    job.id,
                    session,
                    provider_request_count=provider_request_count,
                )
            self._record_safe_failure(job.id, session.id, session.user_id, provider_request_count, session.active_generation_id)
            raise DebateOrchestrationError("Debate job execution failed") from exc

    async def execute_job_streaming(self, job_id: UUID) -> DebateSession:
        """Execute a stage through the async per-turn provider contract."""

        job = self.repository.get_job(job_id)
        if job is None:
            raise DebateOrchestrationError("Debate job not found")
        session = self.repository.get_session(job.session_id, job.user_id)
        if session is None:
            raise DebateOrchestrationError("Debate session not found")
        if job.status == "completed":
            return session
        if job.status != "queued" or job.job_type not in {"round_1", "round_2"}:
            raise DebateOrchestrationError("Debate job is not executable")

        round_number = 1 if job.job_type == "round_1" else 2
        queued_status = "queued_round_1" if round_number == 1 else "queued_round_2"
        running_status = "running_round_1" if round_number == 1 else "running_round_2"
        if session.status != queued_status:
            raise DebateOrchestrationError("Debate session is not ready for this job")

        provider_request_count = job.provider_request_count
        prompt_tokens = job.prompt_tokens
        completion_tokens = job.completion_tokens
        try:
            running_job = start_job(job, at=self._at_or_after(job.updated_at))
            running_job = self.repository.update_job(running_job, expected_status="queued")
            running_session = transition_session(
                session,
                running_status,
                at=self._at_or_after(session.updated_at),
            )
            running_session = self.repository.update_session(
                running_session,
                expected_status=queued_status,
                expected_generation_id=session.active_generation_id,
            )
            plan = build_round_plan(round_number, running_session.opening_side)
            transcript = self.repository.list_messages(
                running_session.id,
                running_session.user_id,
                branch_id=running_session.active_branch_id,
            )
            running_session, completed_turn_count = self._resume_plan_prefix(
                running_session,
                transcript,
                plan,
            )
            self._emit(
                session.id,
                "job.started",
                {
                    "job_id": str(running_job.id),
                    "job_type": running_job.job_type,
                    "attempt_count": running_job.attempt_count,
                    "execution_mode": "async_stream",
                    "resumed_turn_count": completed_turn_count,
                },
            )
            user_intervention = next(
                (
                    message.content
                    for message in reversed(transcript)
                    if message.role == "user" and message.message_kind == "question"
                ),
                None,
            )

            for turn in plan.turns[completed_turn_count:]:
                self._assert_generation_active(running_session, running_status)
                provider_request_count += 1
                if turn.role == "judge":
                    running_session, usage = await self._append_streaming_judge(
                        running_session,
                        transcript,
                        phase=turn.judge_phase or "final",
                        round_number=round_number,
                    )
                    prompt_tokens += usage.prompt_tokens
                    completion_tokens += usage.completion_tokens
                else:
                    _, usage = await self._append_streaming_turn(
                        running_session,
                        transcript,
                        role=turn.role,
                        message_kind=turn.message_kind,
                        round_number=round_number,
                        exchange_number=turn.exchange_number,
                        user_intervention=user_intervention,
                    )
                    prompt_tokens += usage.prompt_tokens
                    completion_tokens += usage.completion_tokens
                transcript = self.repository.list_messages(
                    running_session.id,
                    running_session.user_id,
                    branch_id=running_session.active_branch_id,
                )

            target_status = "awaiting_user" if round_number == 1 else "completed"
            self._assert_generation_active(running_session, running_status)
            finished_session = transition_session(
                running_session,
                target_status,
                at=self._at_or_after(running_session.updated_at),
            )
            finished_session = self.repository.update_session(
                finished_session,
                expected_status=running_status,
                expected_generation_id=running_session.active_generation_id,
            )
            completed_job = complete_job(
                running_job,
                at=self._at_or_after(running_job.updated_at),
                provider_request_count=provider_request_count,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
            self.repository.update_job(completed_job, expected_status="running")
            self._emit(
                finished_session.id,
                "session.awaiting_user" if round_number == 1 else "session.completed",
                {
                    "status": finished_session.status,
                    "generation_id": str(finished_session.active_generation_id),
                    "job_id": str(completed_job.id),
                    "execution_mode": "async_stream",
                },
            )
            return finished_session
        except DebateGenerationCancelled:
            return self._finish_cancelled_execution(
                job.id,
                session,
                provider_request_count=provider_request_count,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
        except Exception as exc:
            if self._generation_was_invalidated(session):
                return self._finish_cancelled_execution(
                    job.id,
                    session,
                    provider_request_count=provider_request_count,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                )
            if isinstance(exc, DebateTurnStreamError) and exc.retryable:
                raise DebateRetryableOrchestrationError(
                    retry_after_seconds=exc.retry_after_seconds,
                    provider_request_count=provider_request_count,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                ) from exc
            self._record_safe_failure(job.id, session.id, session.user_id, provider_request_count, session.active_generation_id)
            raise DebateOrchestrationError("Debate streaming job execution failed") from exc

    def _resume_plan_prefix(
        self,
        session: DebateSession,
        transcript: list[DebateMessage],
        plan: DebateRoundPlan,
    ) -> tuple[DebateSession, int]:
        completed = [
            message
            for message in transcript
            if message.branch_id == session.active_branch_id and message.is_complete
            and message.round_number == plan.round_number
            and message.role in {"bull", "bear", "judge"}
        ]
        if len(completed) > len(plan.turns):
            raise DebateOrchestrationError("Debate transcript exceeds its round plan")
        for message, turn in zip(completed, plan.turns, strict=False):
            if (
                not message.is_complete
                or message.role != turn.role
                or message.message_kind != turn.message_kind
                or message.exchange_number != turn.exchange_number
            ):
                raise DebateOrchestrationError(
                    "Debate transcript is not a completed round-plan prefix"
                )

        if completed and completed[-1].role == "judge":
            judge = completed[-1]
            phase = "interim" if plan.round_number == 1 else "final"
            field_name = (
                "interim_judge_message_id"
                if phase == "interim"
                else "final_judge_message_id"
            )
            attached_id = getattr(session, field_name)
            if attached_id is None:
                attached = attach_judge_message(
                    session,
                    phase=phase,
                    message_id=judge.id,
                    at=self._at_or_after(session.updated_at),
                )
                session = self.repository.update_session(
                    attached,
                    expected_status=session.status,
                    expected_generation_id=session.active_generation_id,
                )
            elif attached_id != judge.id:
                raise DebateOrchestrationError(
                    "Debate Judge pointer conflicts with the completed round plan"
                )
        return session, len(completed)

    def request_cancellation(
        self,
        session_id: UUID,
        user_id: UUID,
        generation_id: UUID,
    ) -> DebateSession:
        """Invalidate one expected generation and settle what can stop immediately."""

        session = self.repository.get_session(session_id, user_id)
        if session is None:
            raise DebateOrchestrationError("Debate session not found")
        if session.status in {"cancel_requested", "cancelled"}:
            return self._settle_requested_cancellation(session)
        if session.status in {"completed", "failed"}:
            raise DebateOrchestrationError("A terminal Debate session cannot be cancelled")
        if session.active_generation_id != generation_id:
            raise DebateOrchestrationError("Debate generation changed before cancellation")

        requested, cancelled_generation_id = request_session_cancellation(
            session,
            at=self._at_or_after(session.updated_at),
        )
        try:
            requested = self.repository.update_session(
                requested,
                expected_status=session.status,
                expected_generation_id=session.active_generation_id,
            )
        except DebateConcurrencyError as exc:
            current = self.repository.get_session(session_id, user_id)
            if current is not None and current.status in {"cancel_requested", "cancelled"}:
                return self._settle_requested_cancellation(current)
            raise DebateOrchestrationError(
                "Debate state changed before cancellation"
            ) from exc

        self._emit(
            requested.id,
            "session.cancel_requested",
            {
                "status": requested.status,
                "cancelled_generation_id": str(cancelled_generation_id),
                "generation_id": str(requested.active_generation_id),
            },
        )
        return self._settle_requested_cancellation(requested)

    def publish_retry_scheduled(
        self,
        session: DebateSession,
        job: DebateJob,
        *,
        retry_delay_seconds: int,
    ) -> None:
        if (
            session.status not in {"queued_round_1", "queued_round_2"}
            or job.status != "queued"
            or job.session_id != session.id
            or not 0 <= retry_delay_seconds <= 3600
        ):
            raise DebateOrchestrationError("Debate retry event state is invalid")
        self._emit(
            session.id,
            "job.retry_scheduled",
            {
                "job_id": str(job.id),
                "job_type": job.job_type,
                "attempt_count": job.attempt_count,
                "retry_delay_seconds": retry_delay_seconds,
                "generation_id": str(session.active_generation_id),
            },
        )

    def publish_retry_exhausted(
        self,
        session: DebateSession,
        job: DebateJob,
    ) -> None:
        if (
            session.status != "failed"
            or job.status != "failed"
            or session.safe_error_code != "debate_retry_exhausted"
            or job.safe_error_code != "debate_retry_exhausted"
            or job.session_id != session.id
        ):
            raise DebateOrchestrationError("Exhausted Debate event state is invalid")
        payload = {
            "job_id": str(job.id),
            "job_type": job.job_type,
            "attempt_count": job.attempt_count,
            "safe_error_code": job.safe_error_code,
            "generation_id": str(session.active_generation_id),
        }
        self._emit(session.id, "job.failed", payload)
        self._emit(
            session.id,
            "session.failed",
            {
                "status": session.status,
                "safe_error_code": session.safe_error_code,
                "generation_id": str(session.active_generation_id),
                "job_id": str(job.id),
            },
        )

    def submit_challenge(
        self,
        intervention: DebateIntervention,
        round_two_job: DebateJob,
    ) -> DebateSession:
        if intervention.mode != "challenge":
            raise DebateOrchestrationError("Only a challenge can queue Debate round two")
        session = self.repository.get_session(intervention.session_id, intervention.user_id)
        if session is None:
            raise DebateOrchestrationError("Debate session is not awaiting a user challenge")
        expected_generation_id = uuid5(session.id, f"generation:{intervention.id}")
        if session.status == "queued_round_2":
            existing_job = self.repository.get_job(round_two_job.id)
            if (
                existing_job == round_two_job
                and session.active_generation_id == expected_generation_id
            ):
                return session
        if session.status != "awaiting_user":
            raise DebateOrchestrationError("Debate session is not awaiting a user challenge")
        queued, question = self.prepare_challenge(intervention, round_two_job)
        self.repository.create_intervention(intervention)
        self.repository.append_message(question)
        self.repository.create_job(round_two_job)
        return self.repository.update_session(queued, expected_status="awaiting_user",
            expected_generation_id=session.active_generation_id)

    def prepare_challenge(
        self,
        intervention: DebateIntervention,
        round_two_job: DebateJob,
    ) -> tuple[DebateSession, DebateMessage]:
        """Validate and build Round 2 records without mutating persistence."""

        if intervention.mode != "challenge":
            raise DebateOrchestrationError("Only a challenge can queue Debate round two")
        session = self.repository.get_session(intervention.session_id, intervention.user_id)
        if session is None or session.status != "awaiting_user":
            raise DebateOrchestrationError("Debate session is not awaiting a user challenge")
        if (
            round_two_job.session_id != session.id
            or round_two_job.user_id != session.user_id
            or round_two_job.job_type != "round_2"
            or round_two_job.status != "queued"
        ):
            raise DebateOrchestrationError("Round-two job does not match the Debate session")

        transcript = self.repository.list_messages(
            session.id,
            session.user_id,
            branch_id=session.active_branch_id,
        )
        target = next(
            (
                message
                for message in transcript
                if message.id == intervention.selected_message_id
            ),
            None,
        )
        if target is None:
            raise DebateOrchestrationError("Challenge target is not in the active Debate branch")
        if intervention.selected_text not in target.content:
            raise DebateOrchestrationError(
                "Selected challenge text is not present in its target message"
            )
        generation_id = uuid5(session.id, f"generation:{intervention.id}")
        question = DebateMessage(
            id=uuid5(session.id, f"intervention-message:{intervention.id}"),
            session_id=session.id,
            branch_id=session.active_branch_id,
            generation_id=generation_id,
            sequence_number=self._next_sequence(transcript),
            round_number=2,
            exchange_number=0,
            role="user",
            message_kind="question",
            content=intervention.question,
            metadata={
                "intervention_id": str(intervention.id),
                "selected_message_id": str(intervention.selected_message_id),
                "selected_text": intervention.selected_text,
                "mode": intervention.mode,
            },
            created_at=self._at_or_after(session.updated_at),
        )
        prepared = DebateSession.model_validate(
            {
                **session.model_dump(mode="python"),
                "active_generation_id": generation_id,
            }
        )
        queued = transition_session(
            prepared,
            "queued_round_2",
            at=self._at_or_after(session.updated_at),
        )
        return queued, question

    def _append_turn(
        self,
        session: DebateSession,
        transcript: list[DebateMessage],
        *,
        role: str,
        message_kind: str,
        round_number: int,
        exchange_number: int,
        user_intervention: str | None,
    ) -> DebateMessage:
        self._assert_generation_active(session, self._running_status(round_number))
        target_id, sequence_number, message_id, request = self._prepare_turn(
            session,
            transcript,
            role=role,
            message_kind=message_kind,
            round_number=round_number,
            exchange_number=exchange_number,
            user_intervention=user_intervention,
        )
        attempt = self._admit_attempt(
            session, message_id=message_id, sequence_number=sequence_number,
            round_number=round_number, exchange_number=exchange_number, role=role,
            message_kind=message_kind, provider=self.turn_provider,
        )
        if attempt is not None:
            self.repository.mark_provider_attempt_dispatched(attempt.id, self.clock())
        self._emit_turn_started(
            session,
            message_id=message_id,
            role=role,
            round_number=round_number,
            exchange_number=exchange_number,
            message_kind=message_kind,
            target_id=target_id,
        )
        try:
            draft = self.turn_provider.generate_turn(request)
        except Exception as exc:
            if attempt is not None:
                observed = getattr(exc, "usage", None)
                self.repository.finish_provider_attempt(attempt.id, at=self.clock(), failed=True,
                    prompt_tokens=observed.prompt_tokens if isinstance(observed, DebateTurnStreamUsage) else None,
                    completion_tokens=observed.completion_tokens if isinstance(observed, DebateTurnStreamUsage) else None,
                    total_tokens=observed.total_tokens if isinstance(observed, DebateTurnStreamUsage) else None)
            raise
        if attempt is not None:
            self.repository.finish_provider_attempt(attempt.id, at=self.clock())
        for delta_index, delta in enumerate(preview_text_chunks(draft.content), start=1):
            self._assert_generation_active(session, self._running_status(round_number))
            self._emit_turn_delta(
                session,
                message_id=message_id,
                role=role,
                delta_index=delta_index,
                delta=delta,
                source="buffered_compatibility",
            )
        return self._persist_turn_draft(
            session,
            target_id=target_id,
            sequence_number=sequence_number,
            message_id=message_id,
            role=role,
            message_kind=message_kind,
            round_number=round_number,
            exchange_number=exchange_number,
            draft=draft,
            provider_name=self.turn_provider.name,
            provider_version=self.turn_provider.version,
            stream_mode="buffered_compatibility",
        )

    async def _append_streaming_turn(
        self,
        session: DebateSession,
        transcript: list[DebateMessage],
        *,
        role: str,
        message_kind: str,
        round_number: int,
        exchange_number: int,
        user_intervention: str | None,
    ) -> tuple[DebateMessage, DebateTurnStreamUsage]:
        self._assert_generation_active(session, self._running_status(round_number))
        target_id, sequence_number, message_id, request = self._prepare_turn(
            session,
            transcript,
            role=role,
            message_kind=message_kind,
            round_number=round_number,
            exchange_number=exchange_number,
            user_intervention=user_intervention,
        )

        attempt = self._admit_attempt(
            session, message_id=message_id, sequence_number=sequence_number,
            round_number=round_number, exchange_number=exchange_number, role=role,
            message_kind=message_kind, provider=self.streaming_turn_provider,
        )
        if attempt is not None:
            self.repository.mark_provider_attempt_dispatched(attempt.id, self.clock())
        self._emit_turn_started(
            session,
            message_id=message_id,
            role=role,
            round_number=round_number,
            exchange_number=exchange_number,
            message_kind=message_kind,
            target_id=target_id,
        )

        received = ""

        async def publish_delta(event: DebateTurnStreamDelta) -> None:
            nonlocal received
            received += event.delta
            if self.checkpoint_drafts:
                self.repository.checkpoint_draft(DebateDraftCheckpoint(
                    message_id=message_id, session_id=session.id, branch_id=session.active_branch_id,
                    generation_id=session.active_generation_id, sequence_number=sequence_number,
                    round_number=round_number, exchange_number=exchange_number, role=role,
                    message_kind=message_kind, content=received, created_at=session.updated_at))
            self._assert_generation_active(session, self._running_status(round_number))
            self._emit_turn_delta(
                session,
                message_id=message_id,
                role=role,
                delta_index=event.chunk_index,
                delta=event.delta,
                source=event.source,
            )

        try:
            collected = await collect_debate_turn_stream(
                self.streaming_turn_provider, request, on_delta=publish_delta,
            )
        except Exception as exc:
            if attempt is not None:
                observed = getattr(exc, "usage", None)
                self.repository.finish_provider_attempt(attempt.id, at=self.clock(), failed=True,
                    prompt_tokens=observed.prompt_tokens if isinstance(observed, DebateTurnStreamUsage) else None,
                    completion_tokens=observed.completion_tokens if isinstance(observed, DebateTurnStreamUsage) else None,
                    total_tokens=observed.total_tokens if isinstance(observed, DebateTurnStreamUsage) else None)
            raise
        if attempt is not None:
            self.repository.finish_provider_attempt(
                attempt.id, at=self.clock(), prompt_tokens=collected.usage.prompt_tokens,
                completion_tokens=collected.usage.completion_tokens,
                total_tokens=collected.usage.total_tokens,
            )
        self._assert_generation_active(session, self._running_status(round_number))
        message = self._persist_turn_draft(
            session,
            target_id=target_id,
            sequence_number=sequence_number,
            message_id=message_id,
            role=role,
            message_kind=message_kind,
            round_number=round_number,
            exchange_number=exchange_number,
            draft=collected.draft,
            provider_name=self.streaming_turn_provider.name,
            provider_version=self.streaming_turn_provider.version,
            stream_mode="async_provider",
        )
        return message, collected.usage

    def _prepare_turn(
        self,
        session: DebateSession,
        transcript: list[DebateMessage],
        *,
        role: str,
        message_kind: str,
        round_number: int,
        exchange_number: int,
        user_intervention: str | None,
    ) -> tuple[UUID | None, int, UUID, DebateTurnRequest]:
        opponent = "bear" if role == "bull" else "bull"
        latest_opponent = next(
            (message for message in reversed(transcript) if message.role == opponent and message.is_complete),
            None,
        )
        target_id = latest_opponent.id if latest_opponent is not None else None
        sequence_number = self._next_sequence(transcript)
        message_id = self._message_id(session, sequence_number)
        request = DebateTurnRequest(
            session_id=session.id,
            branch_id=session.active_branch_id,
            generation_id=session.active_generation_id,
            ticker=session.ticker,
            role=role,
            round_number=round_number,
            exchange_number=exchange_number,
            initial_question=session.initial_question,
            user_intervention=user_intervention,
            analysis_context=session.analysis_context,
            factor_snapshot=session.factor_snapshot,
            transcript=tuple(message for message in transcript if message.is_complete),
            interrupted_context=tuple(message for message in transcript if not message.is_complete
                and message.metadata.get("interrupted") is True)[-6:],
            rebuttal_target_message_id=target_id,
            allowed_evidence_ids=session.analysis_context.allowed_evidence_ids,
            previously_used_points=tuple(
                str(message.metadata["rebuttal_point"])
                for message in transcript
                if message.metadata.get("rebuttal_point")
            )[-30:],
        )
        return target_id, sequence_number, message_id, request

    def _emit_turn_started(
        self,
        session: DebateSession,
        *,
        message_id: UUID,
        role: str,
        round_number: int,
        exchange_number: int,
        message_kind: str,
        target_id: UUID | None,
    ) -> None:
        """Publish a start only after the request has been admitted.

        Admission and Stop share the repository's session lock.  Delaying this
        transient event until admission succeeds prevents a stale ``started``
        event from appearing after a concurrent Stop has invalidated the
        generation.
        """
        self._emit(
            session.id,
            "turn.started",
            {
                "message_id": str(message_id),
                "generation_id": str(session.active_generation_id),
                "round_number": round_number,
                "exchange_number": exchange_number,
                "role": role,
                "message_kind": message_kind,
                "responds_to_message_id": str(target_id) if target_id else None,
            },
        )

    def _persist_turn_draft(
        self,
        session: DebateSession,
        *,
        target_id: UUID | None,
        sequence_number: int,
        message_id: UUID,
        role: str,
        message_kind: str,
        round_number: int,
        exchange_number: int,
        draft: DebateTurnDraft,
        provider_name: str,
        provider_version: str,
        stream_mode: str,
    ) -> DebateMessage:
        self._assert_generation_active(session, self._running_status(round_number))
        if draft.responds_to_message_id != target_id:
            raise DebateOrchestrationError("Turn provider returned the wrong rebuttal target")
        evidence_ids = self._validated_evidence_ids(
            draft.evidence_ids,
            session.analysis_context.allowed_evidence_ids,
        )
        message = DebateMessage(
            id=message_id,
            session_id=session.id,
            branch_id=session.active_branch_id,
            generation_id=session.active_generation_id,
            sequence_number=sequence_number,
            round_number=round_number,
            exchange_number=exchange_number,
            role=role,
            message_kind=message_kind,
            content=draft.content,
            confidence=draft.confidence,
            signal_strength=draft.signal_strength,
            terms=draft.terms,
            metadata={
                "provider": provider_name,
                "provider_version": provider_version,
                "stream_mode": stream_mode,
                "responds_to_message_id": str(target_id) if target_id else None,
                "rebuttal_point": draft.rebuttal_point,
                "interpretation": draft.interpretation,
                "risk_meaning": draft.risk_meaning,
            },
            created_at=self._at_or_after(session.updated_at),
        )
        citations = self._evidence_citations(message.id, evidence_ids)
        stored_message = self.repository.append_message(message, citations)
        for citation in citations:
            self._emit(
                session.id,
                "turn.citation",
                {
                    "message_id": str(message.id),
                    "generation_id": str(session.active_generation_id),
                    "evidence_id": citation.evidence_id,
                    "citation_order": citation.citation_order,
                    "support_span": citation.support_span,
                },
            )
        self._emit(
            session.id,
            "turn.completed",
            {
                "message": stored_message.model_dump(mode="json"),
                "presentation": build_debate_message_presentation(
                    stored_message,
                    citations,
                    session.analysis_context,
                ).model_dump(mode="json"),
                "generation_id": str(session.active_generation_id),
            },
        )
        return stored_message

    def _emit_turn_delta(
        self,
        session: DebateSession,
        *,
        message_id: UUID,
        role: str,
        delta_index: int,
        delta: str,
        source: str,
    ) -> None:
        self._emit(
            session.id,
            "turn.delta",
            {
                "message_id": str(message_id),
                "generation_id": str(session.active_generation_id),
                "role": role,
                "delta_index": delta_index,
                "delta": delta,
                "source": source,
            },
        )

    def _append_judge(
        self,
        session: DebateSession,
        transcript: list[DebateMessage],
        *,
        phase: str,
        round_number: int,
    ) -> DebateSession:
        self._assert_generation_active(session, self._running_status(round_number))
        request = DebateJudgeRequest(
            session_id=session.id,
            branch_id=session.active_branch_id,
            phase=phase,
            analysis_context=session.analysis_context,
            factor_snapshot=session.factor_snapshot,
            transcript=tuple(message for message in transcript if message.is_complete),
            interrupted_context=tuple(message for message in transcript if not message.is_complete
                and message.metadata.get("interrupted") is True)[-6:],
            allowed_evidence_ids=session.analysis_context.allowed_evidence_ids,
        )
        sequence_number = self._next_sequence(transcript)
        message_id = self._message_id(session, sequence_number)
        attempt = self._admit_attempt(
            session, message_id=message_id, sequence_number=sequence_number,
            round_number=round_number, exchange_number=0, role="judge",
            message_kind="summary", provider=self.judge_provider,
        )
        if attempt is not None:
            self.repository.mark_provider_attempt_dispatched(attempt.id, self.clock())
        self._emit_judge_started(
            session,
            message_id=message_id,
            round_number=round_number,
            phase=phase,
        )
        try:
            draft = self.judge_provider.generate_judgement(request)
        except Exception as exc:
            if attempt is not None:
                observed = getattr(exc, "usage", None)
                self.repository.finish_provider_attempt(attempt.id, at=self.clock(), failed=True,
                    prompt_tokens=observed.prompt_tokens if isinstance(observed, DebateTurnStreamUsage) else None,
                    completion_tokens=observed.completion_tokens if isinstance(observed, DebateTurnStreamUsage) else None,
                    total_tokens=observed.total_tokens if isinstance(observed, DebateTurnStreamUsage) else None)
            raise
        if attempt is not None:
            self.repository.finish_provider_attempt(attempt.id, at=self.clock())
        self._assert_generation_active(session, self._running_status(round_number))
        return self._persist_judge_draft(
            session,
            phase=phase,
            round_number=round_number,
            sequence_number=sequence_number,
            message_id=message_id,
            draft=draft,
            provider_name=self.judge_provider.name,
            provider_version=self.judge_provider.version,
            stream_mode="buffered_compatibility",
        )

    async def _append_streaming_judge(
        self,
        session: DebateSession,
        transcript: list[DebateMessage],
        *,
        phase: str,
        round_number: int,
    ) -> tuple[DebateSession, DebateTurnStreamUsage]:
        self._assert_generation_active(session, self._running_status(round_number))
        request = DebateJudgeRequest(
            session_id=session.id,
            branch_id=session.active_branch_id,
            phase=phase,
            analysis_context=session.analysis_context,
            factor_snapshot=session.factor_snapshot,
            transcript=tuple(message for message in transcript if message.is_complete),
            interrupted_context=tuple(message for message in transcript if not message.is_complete
                and message.metadata.get("interrupted") is True)[-6:],
            allowed_evidence_ids=session.analysis_context.allowed_evidence_ids,
        )
        sequence_number = self._next_sequence(transcript)
        message_id = self._message_id(session, sequence_number)
        attempt = self._admit_attempt(
            session, message_id=message_id, sequence_number=sequence_number,
            round_number=round_number, exchange_number=0, role="judge",
            message_kind="summary", provider=self.streaming_judge_provider,
        )
        if attempt is not None:
            self.repository.mark_provider_attempt_dispatched(attempt.id, self.clock())
        self._emit_judge_started(
            session,
            message_id=message_id,
            round_number=round_number,
            phase=phase,
        )

        received = ""

        async def publish_delta(event: DebateJudgeStreamDelta) -> None:
            nonlocal received
            received += event.delta
            if self.checkpoint_drafts:
                self.repository.checkpoint_draft(DebateDraftCheckpoint(
                    message_id=message_id, session_id=session.id, branch_id=session.active_branch_id,
                    generation_id=session.active_generation_id, sequence_number=sequence_number,
                    round_number=round_number, exchange_number=0, role="judge",
                    message_kind="summary", content=received, created_at=session.updated_at))
            self._assert_generation_active(session, self._running_status(round_number))
            self._emit(
                session.id,
                "judge.delta",
                {
                    "message_id": str(message_id),
                    "generation_id": str(session.active_generation_id),
                    "round_number": round_number,
                    "phase": phase,
                    "delta_index": event.chunk_index,
                    "delta": event.delta,
                    "source": event.source,
                },
            )

        try:
            collected = await collect_debate_judge_stream(
                self.streaming_judge_provider, request, on_delta=publish_delta,
            )
        except Exception as exc:
            if attempt is not None:
                observed = getattr(exc, "usage", None)
                self.repository.finish_provider_attempt(attempt.id, at=self.clock(), failed=True,
                    prompt_tokens=observed.prompt_tokens if isinstance(observed, DebateTurnStreamUsage) else None,
                    completion_tokens=observed.completion_tokens if isinstance(observed, DebateTurnStreamUsage) else None,
                    total_tokens=observed.total_tokens if isinstance(observed, DebateTurnStreamUsage) else None)
            raise
        if attempt is not None:
            self.repository.finish_provider_attempt(
                attempt.id, at=self.clock(), prompt_tokens=collected.usage.prompt_tokens,
                completion_tokens=collected.usage.completion_tokens,
                total_tokens=collected.usage.total_tokens,
            )
        self._assert_generation_active(session, self._running_status(round_number))
        attached = self._persist_judge_draft(
            session,
            phase=phase,
            round_number=round_number,
            sequence_number=sequence_number,
            message_id=message_id,
            draft=collected.draft,
            provider_name=self.streaming_judge_provider.name,
            provider_version=self.streaming_judge_provider.version,
            stream_mode="async_provider",
            usage=collected.usage,
        )
        return attached, collected.usage

    def _emit_judge_started(
        self,
        session: DebateSession,
        *,
        message_id: UUID,
        round_number: int,
        phase: str,
    ) -> None:
        """Publish Judge start only after the provider attempt is admitted."""
        self._emit(
            session.id,
            "judge.started",
            {
                "message_id": str(message_id),
                "generation_id": str(session.active_generation_id),
                "round_number": round_number,
                "phase": phase,
            },
        )

    def _admit_attempt(
        self, session: DebateSession, *, message_id: UUID, sequence_number: int,
        round_number: int, exchange_number: int, role: str, message_kind: str,
        provider: object,
    ) -> ProviderAttempt | None:
        """Create the request identity and empty draft in one stop-serialized write."""

        if not self.checkpoint_drafts:
            return None
        at = self.clock()
        provider_name = str(getattr(provider, "name", "unknown"))
        model_name = str(getattr(provider, "model", "") or
                         f"{provider_name}:{getattr(provider, 'version', 'unknown')}")
        attempt = ProviderAttempt(
            id=uuid4(), session_id=session.id, generation_id=session.active_generation_id,
            message_id=message_id, role=role, provider=provider_name,
            model=model_name, admitted_at=at,
        )
        checkpoint = DebateDraftCheckpoint(
            message_id=message_id, session_id=session.id, branch_id=session.active_branch_id,
            generation_id=session.active_generation_id, sequence_number=sequence_number,
            round_number=round_number, exchange_number=exchange_number, role=role,
            message_kind=message_kind, content="", created_at=at,
        )
        return self.repository.admit_provider_attempt(attempt, checkpoint)

    def _persist_judge_draft(
        self,
        session: DebateSession,
        *,
        phase: str,
        round_number: int,
        sequence_number: int,
        message_id: UUID,
        draft: DebateJudgeDraft,
        provider_name: str,
        provider_version: str,
        stream_mode: str,
        usage: DebateTurnStreamUsage | None = None,
    ) -> DebateSession:
        evidence_ids = self._validated_evidence_ids(
            draft.evidence_ids,
            session.analysis_context.allowed_evidence_ids,
        )
        message = DebateMessage(
            id=message_id,
            session_id=session.id,
            branch_id=session.active_branch_id,
            generation_id=session.active_generation_id,
            sequence_number=sequence_number,
            round_number=round_number,
            exchange_number=0,
            role="judge",
            message_kind="summary",
            content=draft.summary,
            metadata={
                "provider": provider_name,
                "provider_version": provider_version,
                "stream_mode": stream_mode,
                "usage": usage.model_dump(mode="json") if usage else None,
                "model_name": usage.model_name if usage else None,
                "phase": phase,
                "interpretation": draft.interpretation,
                "agreements": list(draft.agreements),
                "disagreements": list(draft.disagreements),
                "missing_evidence": list(draft.missing_evidence),
                "evidence_strength": draft.evidence_strength,
                "uncertainty": draft.uncertainty,
                "risk_level": draft.risk_level,
            },
            created_at=self._at_or_after(session.updated_at),
        )
        citations = self._evidence_citations(message.id, evidence_ids)
        stored_message = self.repository.append_message(message, citations)
        for citation in citations:
            self._emit(
                session.id,
                "turn.citation",
                {
                    "message_id": str(message.id),
                    "generation_id": str(session.active_generation_id),
                    "evidence_id": citation.evidence_id,
                    "citation_order": citation.citation_order,
                    "support_span": citation.support_span,
                },
            )
        self._emit(
            session.id,
            "judge.completed",
            {
                "message": stored_message.model_dump(mode="json"),
                "presentation": build_debate_message_presentation(
                    stored_message,
                    citations,
                    session.analysis_context,
                ).model_dump(mode="json"),
                "generation_id": str(session.active_generation_id),
                "phase": phase,
            },
        )
        attached = attach_judge_message(
            session,
            phase=phase,
            message_id=message.id,
            at=self._at_or_after(session.updated_at),
        )
        return self.repository.update_session(attached, expected_status=session.status,
            expected_generation_id=session.active_generation_id)

    def _record_safe_failure(
        self,
        job_id: UUID,
        session_id: UUID,
        user_id: UUID,
        provider_request_count: int,
        expected_generation_id: UUID,
    ) -> None:
        try:
            current_session = self.repository.get_session(session_id, user_id)
            if (current_session is not None
                and current_session.active_generation_id == expected_generation_id
                and current_session.status not in {
                "completed",
                "cancel_requested",
                "cancelled",
                "failed",
                "interrupted_awaiting_user",
            }):
                failed_session = transition_session(
                    current_session,
                    "failed",
                    at=self._at_or_after(current_session.updated_at),
                    safe_error_code="debate_execution_failed",
                )
                self.repository.update_session(
                    failed_session,
                    expected_status=current_session.status,
                    expected_generation_id=expected_generation_id,
                )
                self._emit(
                    failed_session.id,
                    "session.failed",
                    {
                        "status": failed_session.status,
                        "safe_error_code": failed_session.safe_error_code,
                        "generation_id": str(failed_session.active_generation_id),
                    },
                )
        except Exception:
            pass
        try:
            current_job = self.repository.get_job(job_id)
            if current_job is not None and current_job.status in {"queued", "running"}:
                failed_job = fail_job(
                    current_job,
                    at=self._at_or_after(current_job.updated_at),
                    safe_error_code="debate_execution_failed",
                    provider_request_count=provider_request_count,
                )
                self.repository.update_job(failed_job, expected_status=current_job.status)
        except Exception:
            pass

    def _settle_requested_cancellation(self, session: DebateSession) -> DebateSession:
        if session.status == "cancelled":
            return session
        if session.status != "cancel_requested":
            raise DebateOrchestrationError("Debate cancellation is not pending")

        active_job = self.repository.get_active_job(session.id, session.user_id)
        if active_job is not None and active_job.status == "running":
            return session
        if active_job is not None:
            cancelled = cancel_job(
                active_job,
                at=self._at_or_after(active_job.updated_at),
            )
            try:
                self.repository.update_job(cancelled, expected_status=active_job.status)
            except DebateConcurrencyError:
                current_job = self.repository.get_active_job(session.id, session.user_id)
                if current_job is not None and current_job.status == "running":
                    return session
                if current_job is not None:
                    raise DebateOrchestrationError("Debate job cancellation conflicted")
        return self._finalize_cancelled_session(session)

    def _finish_cancelled_execution(
        self,
        job_id: UUID,
        original_session: DebateSession,
        *,
        provider_request_count: int,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> DebateSession:
        current_job = self.repository.get_job(job_id)
        if current_job is not None and current_job.status in {"queued", "running"}:
            cancelled_job = cancel_job(
                current_job,
                at=self._at_or_after(current_job.updated_at),
                provider_request_count=provider_request_count,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
            try:
                self.repository.update_job(
                    cancelled_job,
                    expected_status=current_job.status,
                )
            except DebateConcurrencyError:
                pass

        current_session = self.repository.get_session(
            original_session.id,
            original_session.user_id,
        )
        if current_session is None:
            raise DebateOrchestrationError("Debate session not found")
        if current_session.status == "cancel_requested":
            return self._finalize_cancelled_session(current_session)
        return current_session

    def _finalize_cancelled_session(self, session: DebateSession) -> DebateSession:
        if session.status == "cancelled":
            return session
        cancelled = transition_session(
            session,
            "cancelled",
            at=self._at_or_after(session.updated_at),
        )
        try:
            cancelled = self.repository.update_session(
                cancelled,
                expected_status="cancel_requested",
                expected_generation_id=session.active_generation_id,
            )
        except DebateConcurrencyError as exc:
            current = self.repository.get_session(session.id, session.user_id)
            if current is not None and current.status == "cancelled":
                return current
            raise DebateOrchestrationError("Debate cancellation conflicted") from exc
        self._emit(
            cancelled.id,
            "session.cancelled",
            {
                "status": cancelled.status,
                "generation_id": str(cancelled.active_generation_id),
            },
        )
        return cancelled

    def _assert_generation_active(
        self,
        expected: DebateSession,
        expected_status: DebateSessionStatus,
    ) -> None:
        current = self.repository.get_session(expected.id, expected.user_id)
        if current is None:
            raise DebateOrchestrationError("Debate session not found")
        if (
            current.status != expected_status
            or current.active_branch_id != expected.active_branch_id
            or current.active_generation_id != expected.active_generation_id
        ):
            raise DebateGenerationCancelled("Debate generation is no longer active")

    def _generation_was_invalidated(self, original: DebateSession) -> bool:
        try:
            current = self.repository.get_session(original.id, original.user_id)
            return current is not None and (
                current.status in {"cancel_requested", "cancelled"}
                or current.active_generation_id != original.active_generation_id
            )
        except Exception:
            return False

    @staticmethod
    def _running_status(round_number: int) -> DebateSessionStatus:
        return "running_round_1" if round_number == 1 else "running_round_2"

    @staticmethod
    def _evidence_citations(
        message_id: UUID,
        evidence_ids: tuple[str, ...],
    ) -> tuple[DebateMessageEvidence, ...]:
        return tuple(
            DebateMessageEvidence(
                message_id=message_id,
                evidence_id=evidence_id,
                citation_order=index,
            )
            for index, evidence_id in enumerate(evidence_ids, start=1)
        )

    @staticmethod
    def _validated_evidence_ids(
        evidence_ids: tuple[str, ...],
        allowed: frozenset[str],
    ) -> tuple[str, ...]:
        if any(evidence_id not in allowed for evidence_id in evidence_ids):
            raise DebateOrchestrationError("Provider cited evidence outside the frozen snapshot")
        return tuple(dict.fromkeys(evidence_ids))

    @staticmethod
    def _next_sequence(transcript: list[DebateMessage]) -> int:
        return max((message.sequence_number for message in transcript), default=0) + 1

    @staticmethod
    def _message_id(session: DebateSession, sequence_number: int) -> UUID:
        return uuid5(
            session.id,
            f"message:{session.active_branch_id}:{sequence_number}",
        )

    def _emit(
        self,
        session_id: UUID,
        event_type: DebateEventType,
        payload: dict[str, JsonValue],
    ) -> None:
        if self.event_publisher is None:
            return
        try:
            self.event_publisher.publish(
                session_id,
                event_type,
                payload=payload,
            )
        except Exception:
            # Complete messages and session state are canonical. A transient
            # broker failure must not corrupt or block the Debate workflow.
            logger.warning("Transient Debate event publication failed", exc_info=True)

    def _at_or_after(self, minimum: datetime) -> datetime:
        candidate = self.clock()
        if candidate.tzinfo is None or candidate.utcoffset() is None:
            raise DebateOrchestrationError("Debate clock must return a timezone-aware value")
        return max(candidate, minimum)
