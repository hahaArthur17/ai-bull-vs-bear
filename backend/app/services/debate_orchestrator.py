from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import logging
from uuid import UUID, uuid5

from pydantic import JsonValue

from app.domain.agents import DebateJudgeRequest, DebateTurnRequest
from app.domain.debate import (
    DebateIntervention,
    DebateMessage,
    DebateMessageEvidence,
    DebateSession,
    build_round_plan,
)
from app.domain.events import DebateEventType
from app.domain.jobs import DebateJob
from app.providers.debate_agents import DebateJudgeProvider, DebateTurnProvider
from app.repositories.debate_repository import DebateUnitOfWork
from app.services.debate_job_state import complete_job, fail_job, start_job
from app.services.debate_event_broker import DebateEventPublisher
from app.services.debate_state import attach_judge_message, transition_session


logger = logging.getLogger(__name__)


class DebateOrchestrationError(RuntimeError):
    """Safe workflow failure that does not expose provider or persistence data."""


class DebateOrchestrator:
    def __init__(
        self,
        repository: DebateUnitOfWork,
        turn_provider: DebateTurnProvider,
        judge_provider: DebateJudgeProvider,
        *,
        event_publisher: DebateEventPublisher | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.repository = repository
        self.turn_provider = turn_provider
        self.judge_provider = judge_provider
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
            finished_session = transition_session(
                running_session,
                target_status,
                at=self._at_or_after(running_session.updated_at),
            )
            finished_session = self.repository.update_session(
                finished_session,
                expected_status=running_status,
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
        except Exception as exc:
            self._record_safe_failure(job.id, session.id, session.user_id, provider_request_count)
            raise DebateOrchestrationError("Debate job execution failed") from exc

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
        if not any(message.id == intervention.selected_message_id for message in transcript):
            raise DebateOrchestrationError("Challenge target is not in the active Debate branch")
        generation_id = expected_generation_id
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
        self.repository.create_intervention(intervention)
        self.repository.append_message(question)
        self.repository.create_job(round_two_job)
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
        return self.repository.update_session(queued, expected_status="awaiting_user")

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
        opponent = "bear" if role == "bull" else "bull"
        latest_opponent = next(
            (message for message in reversed(transcript) if message.role == opponent),
            None,
        )
        target_id = latest_opponent.id if latest_opponent is not None else None
        sequence_number = self._next_sequence(transcript)
        message_id = self._message_id(session, sequence_number)
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
            transcript=tuple(transcript),
            rebuttal_target_message_id=target_id,
            allowed_evidence_ids=session.analysis_context.allowed_evidence_ids,
            previously_used_points=tuple(
                str(message.metadata["rebuttal_point"])
                for message in transcript
                if message.metadata.get("rebuttal_point")
            )[-30:],
        )
        draft = self.turn_provider.generate_turn(request)
        if draft.responds_to_message_id != target_id:
            raise DebateOrchestrationError("Turn provider returned the wrong rebuttal target")
        evidence_ids = self._validated_evidence_ids(
            draft.evidence_ids,
            session.analysis_context.allowed_evidence_ids,
        )
        for delta_index, delta in enumerate(self._buffered_deltas(draft.content), start=1):
            self._emit(
                session.id,
                "turn.delta",
                {
                    "message_id": str(message_id),
                    "generation_id": str(session.active_generation_id),
                    "role": role,
                    "delta_index": delta_index,
                    "delta": delta,
                    "source": "buffered_preview",
                },
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
                "provider": self.turn_provider.name,
                "provider_version": self.turn_provider.version,
                "responds_to_message_id": str(target_id) if target_id else None,
                "rebuttal_point": draft.rebuttal_point,
                "risk_meaning": draft.risk_meaning,
            },
            created_at=self._at_or_after(session.updated_at),
        )
        citations = tuple(
            DebateMessageEvidence(
                message_id=message.id,
                evidence_id=evidence_id,
                citation_order=index,
            )
            for index, evidence_id in enumerate(evidence_ids, start=1)
        )
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
                },
            )
        self._emit(
            session.id,
            "turn.completed",
            {
                "message": stored_message.model_dump(mode="json"),
                "generation_id": str(session.active_generation_id),
            },
        )
        return stored_message

    def _append_judge(
        self,
        session: DebateSession,
        transcript: list[DebateMessage],
        *,
        phase: str,
        round_number: int,
    ) -> DebateSession:
        request = DebateJudgeRequest(
            session_id=session.id,
            branch_id=session.active_branch_id,
            phase=phase,
            analysis_context=session.analysis_context,
            factor_snapshot=session.factor_snapshot,
            transcript=tuple(transcript),
            allowed_evidence_ids=session.analysis_context.allowed_evidence_ids,
        )
        sequence_number = self._next_sequence(transcript)
        message_id = self._message_id(session, sequence_number)
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
        draft = self.judge_provider.generate_judgement(request)
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
                "provider": self.judge_provider.name,
                "provider_version": self.judge_provider.version,
                "phase": phase,
                "agreements": list(draft.agreements),
                "disagreements": list(draft.disagreements),
                "missing_evidence": list(draft.missing_evidence),
                "evidence_strength": draft.evidence_strength,
                "uncertainty": draft.uncertainty,
                "risk_level": draft.risk_level,
            },
            created_at=self._at_or_after(session.updated_at),
        )
        citations = tuple(
            DebateMessageEvidence(
                message_id=message.id,
                evidence_id=evidence_id,
                citation_order=index,
            )
            for index, evidence_id in enumerate(evidence_ids, start=1)
        )
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
                },
            )
        self._emit(
            session.id,
            "judge.completed",
            {
                "message": stored_message.model_dump(mode="json"),
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
        return self.repository.update_session(attached, expected_status=session.status)

    def _record_safe_failure(
        self,
        job_id: UUID,
        session_id: UUID,
        user_id: UUID,
        provider_request_count: int,
    ) -> None:
        try:
            current_session = self.repository.get_session(session_id, user_id)
            if current_session is not None and current_session.status not in {
                "completed",
                "cancelled",
                "failed",
            }:
                failed_session = transition_session(
                    current_session,
                    "failed",
                    at=self._at_or_after(current_session.updated_at),
                    safe_error_code="debate_execution_failed",
                )
                self.repository.update_session(
                    failed_session,
                    expected_status=current_session.status,
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

    @staticmethod
    def _buffered_deltas(content: str, *, max_characters: int = 96) -> tuple[str, ...]:
        if max_characters < 1:
            raise ValueError("Buffered Debate delta size must be positive")
        # DebateEvent strips outer whitespace as part of its domain safety
        # configuration. Keep whitespace inside frames so concatenation remains
        # byte-for-byte equivalent to the canonical complete message.
        chunks: list[str] = []
        start = 0
        while start < len(content):
            end = min(start + max_characters, len(content))
            while end < len(content) and (
                content[end].isspace() or content[end - 1].isspace()
            ):
                end += 1
            chunks.append(content[start:end])
            start = end
        return tuple(chunks)

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
