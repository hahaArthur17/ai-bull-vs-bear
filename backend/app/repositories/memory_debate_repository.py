from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import TypeVar
from uuid import UUID, uuid4, uuid5

from app.domain.base import ImmutableDomainModel
from app.domain.debate import (
    DebateIntervention,
    DebateDraftCheckpoint,
    DebateMessage,
    DebateMessageEvidence,
    DebateSession,
    DebateSessionStatus,
    ProviderAttempt,
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
from app.services.debate_job_state import fail_job, requeue_job
from app.services.debate_state import transition_session


DomainModel = TypeVar("DomainModel", bound=ImmutableDomainModel)


@dataclass
class _QueueEnvelope:
    message: DebateQueueMessage
    enqueued_at: datetime
    visible_at: datetime
    read_count: int = 0


def _clone(model: DomainModel) -> DomainModel:
    """Return a deep validated copy so nested mutable JSON cannot leak state."""

    return type(model).model_validate(model.model_dump(mode="python"))


class InMemoryDebateRepository:
    """Deterministic Phase 3 repository with production-equivalent invariants.

    This adapter is the credential-free execution/test implementation. Supabase
    remains the target canonical store; both adapters share the same domain
    protocols and optimistic status checks.
    """

    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self._sessions: dict[UUID, DebateSession] = {}
        self._messages: dict[UUID, DebateMessage] = {}
        self._drafts: dict[UUID, DebateDraftCheckpoint] = {}
        self._provider_attempts: dict[UUID, ProviderAttempt] = {}
        self._message_keys: dict[tuple[UUID, UUID, int], UUID] = {}
        self._citations: dict[UUID, tuple[DebateMessageEvidence, ...]] = {}
        self._interventions: dict[UUID, DebateIntervention] = {}
        self._jobs: dict[UUID, DebateJob] = {}
        self._job_keys: dict[str, UUID] = {}
        self._queue_messages: dict[int, _QueueEnvelope] = {}
        self._archived_queue_messages: dict[int, _QueueEnvelope] = {}
        self._next_queue_message_id = 1
        self._clock = clock or (lambda: datetime.now(timezone.utc))
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
        expected_generation_id: UUID | None = None,
    ) -> DebateSession:
        with self._lock:
            current = self._sessions.get(session.id)
            if current is None:
                raise DebateRepositoryError("Debate session not found")
            if (current.status != expected_status or (expected_generation_id is not None
                    and current.active_generation_id != expected_generation_id)):
                raise DebateConcurrencyError("Debate session status changed concurrently")
            try:
                validate_session_update(current, session)
            except DebatePersistenceValidationError as exc:
                raise DebateRepositoryError(str(exc)) from exc
            self._sessions[session.id] = _clone(session)
            if session.status in {"completed", "cancelled", "failed"}:
                self._drafts = {key: value for key, value in self._drafts.items()
                                if value.session_id != session.id}
            return _clone(session)

    def checkpoint_draft(self, message: DebateDraftCheckpoint | DebateMessage) -> None:
        with self._lock:
            if isinstance(message, DebateMessage):
                payload = message.model_dump(mode="python")
                payload["message_id"] = payload.pop("id")
                message = DebateDraftCheckpoint.model_validate({
                    name: value for name, value in payload.items()
                    if name in DebateDraftCheckpoint.model_fields
                })
            session = self._sessions.get(message.session_id)
            if session is None:
                raise DebateConcurrencyError("Draft session unavailable")
            if message.role not in {"bull", "bear", "judge"}:
                raise DebateConcurrencyError("Only agent output can be checkpointed")
            if (message.generation_id != session.active_generation_id
                    or message.branch_id != session.active_branch_id
                    or session.status not in {"running_round_1", "running_round_2"}):
                raise DebateConcurrencyError("Draft generation is no longer active")
            if any(
                canonical.session_id == session.id
                and canonical.branch_id == session.active_branch_id
                and canonical.sequence_number == message.sequence_number
                and canonical.id != message.message_id
                for canonical in self._messages.values()
            ):
                raise DebateConcurrencyError("Draft sequence is already canonical")
            previous = self._drafts.get(message.message_id)
            if previous and (previous.branch_id != message.branch_id
                    or previous.generation_id != message.generation_id
                    or previous.sequence_number != message.sequence_number
                    or not message.content.startswith(previous.content)):
                raise DebateConcurrencyError("Draft prefix changed")
            self._drafts[message.message_id] = _clone(message)

    def admit_provider_attempt(self, attempt: ProviderAttempt,
                               checkpoint: DebateDraftCheckpoint) -> ProviderAttempt:
        with self._lock:
            session = self._sessions.get(attempt.session_id)
            previous = self._provider_attempts.get(attempt.id)
            if previous is not None:
                # Admission is an idempotent request boundary.  Dispatch and
                # settlement mutate the ledger after admission, so retries
                # carry the original immutable identity while the stored row
                # may already be dispatched or finished.
                if (
                    attempt.outcome != "admitted"
                    or attempt.usage_status != "unknown"
                    or attempt.dispatched_at is not None
                    or attempt.finished_at is not None
                    or any(value is not None for value in (
                        attempt.prompt_tokens, attempt.completion_tokens, attempt.total_tokens,
                    ))
                    or checkpoint.content != ""
                    or previous.session_id != attempt.session_id
                    or previous.generation_id != attempt.generation_id
                    or previous.message_id != attempt.message_id
                    or previous.role != attempt.role
                    or previous.provider != attempt.provider
                    or previous.model != attempt.model
                    or previous.admitted_at != attempt.admitted_at
                ):
                    raise DebateConcurrencyError("Provider attempt already exists")
                if (
                    checkpoint.message_id != previous.message_id
                    or checkpoint.session_id != previous.session_id
                    or checkpoint.generation_id != previous.generation_id
                    or checkpoint.role != previous.role
                    or session is None
                    or checkpoint.branch_id != session.active_branch_id
                ):
                    raise DebateConcurrencyError("Provider checkpoint identifier conflict")
                # Stop prunes the checkpoint but intentionally retains the
                # provider ledger.  An exact admission retry can therefore
                # settle safely after the generation has been rotated.
                existing_checkpoint = self._drafts.get(checkpoint.message_id)
                if existing_checkpoint is not None and (
                    existing_checkpoint.session_id != attempt.session_id
                    or existing_checkpoint.generation_id != attempt.generation_id
                    or existing_checkpoint.branch_id != checkpoint.branch_id
                    or existing_checkpoint.sequence_number != checkpoint.sequence_number
                ):
                    raise DebateConcurrencyError("Provider checkpoint identifier conflict")
                return _clone(previous)
            expected_round = (
                1 if session is not None and session.status == "running_round_1"
                else 2 if session is not None and session.status == "running_round_2"
                else None
            )
            if (session is None or session.active_generation_id != attempt.generation_id
                    or session.active_branch_id != checkpoint.branch_id
                    or checkpoint.message_id != attempt.message_id
                    or checkpoint.session_id != attempt.session_id
                    or checkpoint.generation_id != attempt.generation_id
                    or checkpoint.role != attempt.role
                    or checkpoint.content != ""
                    or checkpoint.round_number != expected_round
                    or (
                        checkpoint.role == "judge"
                        and (checkpoint.exchange_number != 0 or checkpoint.message_kind != "summary")
                    )
                    or (
                        checkpoint.role in {"bull", "bear"}
                        and (
                            checkpoint.exchange_number not in {1, 2, 3}
                            or checkpoint.message_kind not in {"argument", "rebuttal"}
                        )
                    )
                    or session.status not in {"running_round_1", "running_round_2"}):
                raise DebateConcurrencyError("Provider attempt generation is no longer active")
            if any(
                message.id == attempt.message_id
                or (
                    message.session_id == session.id
                    and message.branch_id == session.active_branch_id
                    and message.sequence_number == checkpoint.sequence_number
                )
                for message in self._messages.values()
            ) or any(
                draft.session_id == session.id
                and draft.branch_id == session.active_branch_id
                and draft.sequence_number == checkpoint.sequence_number
                and draft.message_id != checkpoint.message_id
                for draft in self._drafts.values()
            ):
                raise DebateConcurrencyError("Provider attempt message is already reserved")
            existing_checkpoint = self._drafts.get(checkpoint.message_id)
            if existing_checkpoint is not None and (
                existing_checkpoint.session_id != session.id
                or existing_checkpoint.generation_id != attempt.generation_id
                or existing_checkpoint.branch_id != checkpoint.branch_id
                or existing_checkpoint.sequence_number != checkpoint.sequence_number
                or existing_checkpoint.content != ""
            ):
                raise DebateConcurrencyError("Provider checkpoint identifier conflict")
            self._provider_attempts[attempt.id] = _clone(attempt)
            self._drafts[checkpoint.message_id] = _clone(checkpoint)
            return _clone(attempt)

    def mark_provider_attempt_dispatched(self, attempt_id: UUID, at: datetime) -> ProviderAttempt:
        with self._lock:
            attempt = self._provider_attempts.get(attempt_id)
            if attempt is None or attempt.outcome != "admitted":
                raise DebateConcurrencyError("Provider attempt is not dispatchable")
            updated = attempt.model_copy(update={"outcome": "dispatched", "dispatched_at": at})
            self._provider_attempts[attempt_id] = updated
            return _clone(updated)

    def finish_provider_attempt(self, attempt_id: UUID, *, at: datetime,
                                prompt_tokens: int | None = None,
                                completion_tokens: int | None = None,
                                total_tokens: int | None = None,
                                failed: bool = False) -> ProviderAttempt:
        with self._lock:
            attempt = self._provider_attempts.get(attempt_id)
            if attempt is None or attempt.outcome not in {"dispatched", "completed", "failed"}:
                raise DebateConcurrencyError("Provider attempt is not finishable")
            reported = all(value is not None for value in (prompt_tokens, completion_tokens, total_tokens))
            # A late usage callback may arrive after the attempt was marked
            # complete/failed. Preserve the first terminal outcome and any
            # already reported usage; an absent or partial report remains
            # unknown instead of becoming synthetic zeroes.
            if attempt.outcome == "failed":
                outcome = "failed"
            elif attempt.outcome == "completed":
                outcome = "completed"
            else:
                outcome = "failed" if failed else "completed"
            if reported and attempt.usage_status == "unknown":
                usage_update = {
                    "usage_status": "reported",
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                }
            elif attempt.usage_status == "reported":
                usage_update = {
                    "usage_status": attempt.usage_status,
                    "prompt_tokens": attempt.prompt_tokens,
                    "completion_tokens": attempt.completion_tokens,
                    "total_tokens": attempt.total_tokens,
                }
            else:
                usage_update = {
                    "usage_status": "unknown",
                    "prompt_tokens": None,
                    "completion_tokens": None,
                    "total_tokens": None,
                }
            # The first terminal callback owns the finish timestamp. A late
            # usage callback is a settlement update and must be idempotent.
            finished_at = attempt.finished_at if attempt.finished_at is not None else at
            updated = attempt.model_copy(update={
                "outcome": outcome,
                "finished_at": finished_at,
                **usage_update,
            })
            updated = ProviderAttempt.model_validate(updated)
            self._provider_attempts[attempt_id] = updated
            return _clone(updated)

    def list_provider_attempts(self, session_id: UUID, user_id: UUID) -> list[ProviderAttempt]:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None or session.user_id != user_id:
                return []
            return [_clone(value) for value in sorted(self._provider_attempts.values(),
                key=lambda item: (item.admitted_at, str(item.id))) if value.session_id == session_id]

    def interrupt_generation(self, session_id: UUID, user_id: UUID, generation_id: UUID,
                             message_id: UUID, visible_prefix: str, at: datetime) -> DebateSession:
        with self._lock:
            session = self._sessions.get(session_id)
            target = self._messages.get(message_id) or self._drafts.get(message_id)
            if session is None or session.user_id != user_id or target is None:
                raise DebateConcurrencyError("Interruption target unavailable")
            if target.session_id != session_id or target.branch_id != session.active_branch_id:
                raise DebateConcurrencyError("Interruption target unavailable")
            if (session.status == "interrupted_awaiting_user" and target.generation_id == generation_id
                    and not target.is_complete and target.metadata.get("interrupted") is True
                    and target.content == visible_prefix):
                return _clone(session)
            if (session.active_generation_id != generation_id or target.generation_id != generation_id
                    or session.status in {"cancelled", "cancel_requested", "failed", "interrupted_awaiting_user"}
                    or target.role not in {"bull", "bear", "judge"}
                    or not target.content.startswith(visible_prefix)):
                raise DebateConcurrencyError("Interruption prefix or generation is invalid")
            at = max(at, session.updated_at)
            target_payload = target.model_dump()
            if "message_id" in target_payload:
                target_payload["id"] = target_payload.pop("message_id")
            partial = DebateMessage.model_validate({**target_payload, "content": visible_prefix,
                "is_complete": False, "cancelled_at": at, "confidence": None,
                "signal_strength": None, "terms": [], "metadata": {"interrupted": True}})
            for key, message in list(self._messages.items()):
                if (message.session_id == session_id and message.branch_id == session.active_branch_id
                        and message.sequence_number >= target.sequence_number):
                    self._messages.pop(key)
                    self._interventions = {i: value for i, value in self._interventions.items()
                                           if value.selected_message_id != key}
                    self._citations.pop(key, None)
                    self._message_keys.pop((session_id, message.branch_id, message.sequence_number), None)
            self._messages[message_id] = partial
            self._message_keys[(session_id, target.branch_id, target.sequence_number)] = message_id
            self._citations[message_id] = ()
            self._drafts = {key: value for key, value in self._drafts.items() if value.session_id != session_id}
            for key, job in list(self._jobs.items()):
                if job.session_id == session_id and job.status == "queued":
                    stamp = max(at, job.updated_at)
                    self._jobs[key] = _clone(job.model_copy(update={"status": "cancelled", "finished_at": stamp, "updated_at": stamp}))
            retained = {key for key in self._messages if key != message_id}
            cancelled = DebateSession.model_validate({**session.model_dump(), "status": "interrupted_awaiting_user",
                "active_generation_id": uuid4(), "updated_at": at, "completed_at": None,
                "interim_judge_message_id": session.interim_judge_message_id if session.interim_judge_message_id in retained else None,
                "final_judge_message_id": None})
            self._sessions[session_id] = cancelled
            return _clone(cancelled)

    def interrupt_before_output_generation(
        self,
        session_id: UUID,
        user_id: UUID,
        generation_id: UUID,
        at: datetime,
    ) -> DebateSession:
        """Freeze a generation before any agent text has become visible.

        This operation deliberately lives under the same repository lock as
        ``admit_provider_attempt`` and canonical message appends.  A caller
        therefore observes either an empty provider admission or its first
        output, never an intermediate state.  The empty canonical anchor uses
        the requested generation as its stable id so a retry can return the
        already-frozen session without manufacturing another message.
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None or session.user_id != user_id:
                raise DebateConcurrencyError("Before-output interruption target unavailable")

            existing = self._messages.get(generation_id)
            if existing is not None:
                if existing.session_id != session_id:
                    raise DebateConcurrencyError("Before-output anchor identifier collision")
                if (
                    session.status == "interrupted_awaiting_user"
                    and existing.generation_id == generation_id
                    and existing.branch_id == session.active_branch_id
                    and existing.role in {"bull", "bear", "judge"}
                    and existing.content == ""
                    and not existing.is_complete
                    and existing.metadata.get("interrupted") is True
                    and existing.metadata.get("before_output") is True
                ):
                    return _clone(session)
                raise DebateConcurrencyError("Before-output anchor identifier already exists")

            existing_draft = self._drafts.get(generation_id)
            if existing_draft is not None and (
                existing_draft.session_id != session_id
                or existing_draft.generation_id != generation_id
            ):
                raise DebateConcurrencyError("Before-output anchor identifier collision")

            allowed_statuses = {
                "queued_round_1", "queued_round_2",
                "running_round_1", "running_round_2",
            }
            if session.status not in allowed_statuses:
                raise DebateConcurrencyError("Debate generation is not waiting before output")
            if session.active_generation_id != generation_id:
                raise DebateConcurrencyError("Debate generation changed before interruption")

            if any(
                message.session_id == session_id
                and message.branch_id == session.active_branch_id
                and message.generation_id == generation_id
                and message.role in {"bull", "bear", "judge"}
                and message.content != ""
                for message in self._messages.values()
            ):
                raise DebateConcurrencyError("Debate generation has already produced output")
            if any(
                draft.session_id == session_id
                and draft.branch_id == session.active_branch_id
                and draft.generation_id == generation_id
                and draft.content != ""
                for draft in self._drafts.values()
            ):
                raise DebateConcurrencyError("Debate generation has already produced output")

            at = max(at, session.updated_at)
            round_number = 1 if session.status.endswith("_round_1") else 2
            # Both rounds begin with the configured opening side.  At this
            # point a generation has no agent output, so exchange one is the
            # only valid anchor shape.
            anchor = DebateMessage(
                id=generation_id,
                session_id=session_id,
                branch_id=session.active_branch_id,
                generation_id=generation_id,
                sequence_number=max(
                    (message.sequence_number for message in self._messages.values()
                     if message.session_id == session_id
                     and message.branch_id == session.active_branch_id),
                    default=0,
                ) + 1,
                round_number=round_number,
                exchange_number=1,
                role=session.opening_side,
                message_kind="argument",
                content="",
                metadata={"interrupted": True, "before_output": True},
                is_complete=False,
                cancelled_at=at,
                created_at=at,
            )
            unique_key = (session_id, session.active_branch_id, anchor.sequence_number)
            if unique_key in self._message_keys:
                raise DebateConcurrencyError("Before-output anchor sequence changed")
            self._messages[generation_id] = _clone(anchor)
            self._message_keys[unique_key] = generation_id
            self._citations[generation_id] = ()

            # A queued delivery can be cancelled immediately.  A running
            # worker observes the rotated generation and settles its job when
            # its provider call returns; it is intentionally left running here.
            for key, job in list(self._jobs.items()):
                if job.session_id == session_id and job.status == "queued":
                    stamp = max(at, job.updated_at)
                    self._jobs[key] = _clone(job.model_copy(update={
                        "status": "cancelled", "finished_at": stamp, "updated_at": stamp,
                    }))

            self._drafts = {
                key: value for key, value in self._drafts.items()
                if value.session_id != session_id
            }
            stopped = DebateSession.model_validate({
                **session.model_dump(),
                "status": "interrupted_awaiting_user",
                "active_generation_id": uuid5(session.id, f"before-output:{generation_id}"),
                "updated_at": at,
                "completed_at": None,
                "final_judge_message_id": None,
            })
            self._sessions[session_id] = stopped
            return _clone(stopped)

    def record_interjection(self, point: DebateMessage) -> DebateMessage:
        from app.services.debate_interruption import interruption_target
        with self._lock:
            session = self._sessions.get(point.session_id)
            if session is None:
                raise DebateConcurrencyError("Debate is not waiting at this interruption")
            # A network retry may arrive after Continue or End has won the
            # state race.  The exact idempotent write must still return the
            # existing point, while a reused identifier with changed content
            # remains a conflict.
            previous = self._messages.get(point.id)
            if previous is not None:
                if (
                    previous.session_id == point.session_id
                    and previous.branch_id == point.branch_id
                    and previous.generation_id == point.generation_id
                    and previous.role == point.role
                    and previous.message_kind == point.message_kind
                    and previous.content == point.content
                    and previous.metadata == point.metadata
                ):
                    return _clone(previous)
                raise DebateConcurrencyError("Interjection key conflicts")
            if (session.status != "interrupted_awaiting_user"
                    or session.active_generation_id != point.generation_id
                    or session.active_branch_id != point.branch_id):
                raise DebateConcurrencyError("Debate is not waiting at this interruption")
            transcript = self.list_messages(session.id, session.user_id, branch_id=session.active_branch_id)
            target = interruption_target(transcript)
            if (point.role != "user" or point.message_kind != "question"
                    or point.metadata.get("interjection") is not True
                    or point.metadata.get("interrupted_message_id") != str(target.id)
                    or not 1 <= len(point.content.strip()) <= 500):
                raise DebateConcurrencyError("Invalid interjection target")
            if sum(m.metadata.get("interjection") is True for m in transcript) >= 6:
                raise DebateConcurrencyError("Interjection limit reached")
            if point.sequence_number != max((m.sequence_number for m in transcript), default=0) + 1:
                raise DebateConcurrencyError("Interjection sequence changed")
            stored = self.append_message(point)
            self._sessions[session.id] = _clone(session.model_copy(update={
                "updated_at": max(session.updated_at, point.created_at)}))
            return stored

    def continue_interrupted(self, session: DebateSession, job: DebateJob, message: DebateQueueMessage,
                             *, expected_generation_id: UUID, interjection_id: UUID,
                             ) -> tuple[DebateSession, DebateJob]:
        from app.services.debate_interruption import CONTINUATION_MAX_AGE, prepare_continuation
        with self._lock:
            current = self._sessions.get(session.id)
            if current is None or current.user_id != session.user_id:
                raise DebateConcurrencyError("Session unavailable")
            existing = self._jobs.get(job.id)
            if existing is not None:
                if existing.session_id != session.id or existing.idempotency_key != job.idempotency_key:
                    raise DebateConcurrencyError("Continue key conflicts")
                return _clone(current), _clone(existing)
            transcript = self.list_messages(current.id, current.user_id, branch_id=current.active_branch_id)
            expected, expected_job, expected_message = prepare_continuation(current, transcript,
                expected_generation_id=expected_generation_id, interjection_id=interjection_id,
                idempotency_key=job.idempotency_key.rsplit(":", 1)[-1], at=session.updated_at)
            captured_at = current.created_at
            if current.analysis_context.captured_at:
                captured_at = min(captured_at, current.analysis_context.captured_at)
            now = self._queue_now()
            if now < captured_at or now - captured_at > CONTINUATION_MAX_AGE:
                raise DebateConcurrencyError("Frozen discussion expired; start a new debate")
            if (expected != session or expected_job != job or expected_message != message
                    or job.idempotency_key in self._job_keys):
                raise DebateConcurrencyError("Continue payload conflicts")
            self._validate_one_active_job(job)
            validate_session_update(current, session)
            queue_id = self._next_queue_message_id
            queued_job = _clone(job.model_copy(update={"queue_message_id": queue_id}))
            stamp = self._queue_now()
            self._sessions[session.id] = _clone(session)
            self._jobs[job.id] = queued_job
            self._job_keys[job.idempotency_key] = job.id
            self._queue_messages[queue_id] = _QueueEnvelope(message=_clone(message), enqueued_at=stamp, visible_at=stamp)
            self._next_queue_message_id += 1
            return _clone(session), _clone(queued_job)

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
            self._validate_new_message(session, message)
            unique_key = (message.session_id, message.branch_id, message.sequence_number)
            if unique_key in self._message_keys:
                raise DebateConcurrencyError("Debate message sequence already exists")
            self._drafts.pop(message.id, None)
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
            self._validate_one_active_job(job)
            self._jobs[job.id] = _clone(job)
            self._job_keys[job.idempotency_key] = job.id
            return _clone(job)

    def get_job(self, job_id: UUID) -> DebateJob | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return _clone(job) if job is not None else None

    def get_active_job(self, session_id: UUID, user_id: UUID) -> DebateJob | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None or session.user_id != user_id:
                return None
            active = [
                job
                for job in self._jobs.values()
                if job.session_id == session_id and job.status in {"queued", "running"}
            ]
            if len(active) > 1:
                raise DebateRepositoryError("Debate session has multiple active jobs")
            return _clone(active[0]) if active else None

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
            self._validate_one_active_job(job)
            self._sessions[session.id] = _clone(session)
            self._jobs[job.id] = _clone(job)
            self._job_keys[job.idempotency_key] = job.id
            return _clone(session), _clone(job)

    def create_session_with_job_and_enqueue(
        self,
        session: DebateSession,
        job: DebateJob,
        message: DebateQueueMessage,
    ) -> tuple[DebateSession, DebateJob]:
        with self._lock:
            self._validate_queue_admission(session, job, message)
            existing_session = self._sessions.get(session.id)
            existing_job = self._jobs.get(job.id)
            if existing_session is not None or existing_job is not None:
                if existing_session is None or existing_job is None:
                    raise DebateConcurrencyError("Queued Debate admission is incomplete")
                queue_message_id = existing_job.queue_message_id
                envelope = (
                    self._queue_messages.get(queue_message_id or 0)
                    or self._archived_queue_messages.get(queue_message_id or 0)
                )
                expected_job = DebateJob.model_validate(
                    {
                        **job.model_dump(mode="python"),
                        "queue_message_id": queue_message_id,
                    }
                )
                if (
                    existing_session == session
                    and existing_job == expected_job
                    and envelope is not None
                    and envelope.message == message
                ):
                    return _clone(existing_session), _clone(existing_job)
                raise DebateConcurrencyError("Queued Debate admission already exists")
            if job.idempotency_key in self._job_keys:
                raise DebateConcurrencyError("Debate job idempotency key already exists")
            self._validate_one_active_job(job)

            queue_message_id = self._next_queue_message_id
            queued_job = DebateJob.model_validate(
                {
                    **job.model_dump(mode="python"),
                    "queue_message_id": queue_message_id,
                }
            )
            enqueued_at = self._queue_now()
            envelope = _QueueEnvelope(
                message=_clone(message),
                enqueued_at=enqueued_at,
                visible_at=enqueued_at,
            )
            self._sessions[session.id] = _clone(session)
            self._jobs[job.id] = _clone(queued_job)
            self._job_keys[job.idempotency_key] = job.id
            self._queue_messages[queue_message_id] = envelope
            self._next_queue_message_id += 1
            return _clone(session), _clone(queued_job)

    def create_round_two_with_job_and_enqueue(
        self,
        intervention: DebateIntervention,
        question: DebateMessage,
        session: DebateSession,
        job: DebateJob,
        message: DebateQueueMessage,
    ) -> tuple[DebateSession, DebateJob]:
        with self._lock:
            existing_job = self._jobs.get(job.id)
            if existing_job is not None:
                queue_message_id = existing_job.queue_message_id
                envelope = (
                    self._queue_messages.get(queue_message_id or 0)
                    or self._archived_queue_messages.get(queue_message_id or 0)
                )
                expected_job = DebateJob.model_validate(
                    {
                        **job.model_dump(mode="python"),
                        "queue_message_id": queue_message_id,
                    }
                )
                if (
                    self._sessions.get(session.id) == session
                    and self._interventions.get(intervention.id) == intervention
                    and self._messages.get(question.id) == question
                    and existing_job == expected_job
                    and envelope is not None
                    and envelope.message == message
                ):
                    return _clone(session), _clone(existing_job)
                raise DebateConcurrencyError("Queued Round 2 admission already exists")

            current = self._sessions.get(session.id)
            if current is None or current.user_id != intervention.user_id:
                raise DebateRepositoryError("Debate session not found")
            self._validate_round_two_admission(
                current,
                intervention,
                question,
                session,
                job,
                message,
            )
            if intervention.id in self._interventions or question.id in self._messages:
                raise DebateConcurrencyError("Round 2 challenge identifiers already exist")
            if job.idempotency_key in self._job_keys:
                raise DebateConcurrencyError("Debate job idempotency key already exists")
            self._validate_one_active_job(job)
            unique_key = (question.session_id, question.branch_id, question.sequence_number)
            if unique_key in self._message_keys:
                raise DebateConcurrencyError("Debate message sequence already exists")

            queue_message_id = self._next_queue_message_id
            queued_job = DebateJob.model_validate(
                {
                    **job.model_dump(mode="python"),
                    "queue_message_id": queue_message_id,
                }
            )
            enqueued_at = self._queue_now()
            self._interventions[intervention.id] = _clone(intervention)
            self._messages[question.id] = _clone(question)
            self._message_keys[unique_key] = question.id
            self._citations[question.id] = ()
            self._sessions[session.id] = _clone(session)
            self._jobs[job.id] = _clone(queued_job)
            self._job_keys[job.idempotency_key] = job.id
            self._queue_messages[queue_message_id] = _QueueEnvelope(
                message=_clone(message),
                enqueued_at=enqueued_at,
                visible_at=enqueued_at,
            )
            self._next_queue_message_id += 1
            return _clone(session), _clone(queued_job)

    def claim_job(
        self,
        *,
        visibility_timeout_seconds: int,
    ) -> ClaimedDebateQueueMessage | None:
        if not 30 <= visibility_timeout_seconds <= 3600:
            raise DebateRepositoryError("Queue visibility timeout is outside safe bounds")
        with self._lock:
            now = self._queue_now()
            available = [
                (queue_message_id, envelope)
                for queue_message_id, envelope in self._queue_messages.items()
                if envelope.visible_at <= now
            ]
            if not available:
                return None
            queue_message_id, envelope = min(available, key=lambda item: item[0])
            envelope.read_count += 1
            envelope.visible_at = now + timedelta(seconds=visibility_timeout_seconds)
            return ClaimedDebateQueueMessage(
                queue_message_id=queue_message_id,
                read_count=envelope.read_count,
                enqueued_at=envelope.enqueued_at,
                visibility_deadline=envelope.visible_at,
                payload=_clone(envelope.message),
            )

    def archive_job_message(self, queue_message_id: int) -> bool:
        with self._lock:
            envelope = self._queue_messages.pop(queue_message_id, None)
            if envelope is None:
                return queue_message_id in self._archived_queue_messages
            self._archived_queue_messages[queue_message_id] = envelope
            return True

    def retry_job_message(self, queue_message_id: int, *, delay_seconds: int) -> bool:
        if not 0 <= delay_seconds <= 3600:
            raise DebateRepositoryError("Queue retry delay is outside safe bounds")
        with self._lock:
            envelope = self._queue_messages.get(queue_message_id)
            if envelope is None:
                return False
            envelope.visible_at = self._queue_now() + timedelta(seconds=delay_seconds)
            return True

    def requeue_running_job(
        self,
        job_id: UUID,
        *,
        expected_attempt_count: int,
        provider_request_count: int = 0,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> tuple[DebateSession, DebateJob]:
        with self._lock:
            job, session = self._running_retry_records(
                job_id,
                expected_attempt_count=expected_attempt_count,
                require_exhausted=False,
            )
            at = max(self._queue_now(), job.updated_at, session.updated_at)
            retried_job = requeue_job(
                job,
                at=at,
                provider_request_count=provider_request_count,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
            queued_status = "queued_round_1" if job.job_type == "round_1" else "queued_round_2"
            retried_session = transition_session(session, queued_status, at=at)
            # A retry regenerates the first incomplete provider turn.  Its
            # checkpoint is provider output from the failed attempt and must
            # not be mistaken for an append-only prefix of the new attempt.
            # Keep the provider-attempt ledger itself for billing/audit.
            self._drafts = {
                key: value for key, value in self._drafts.items()
                if value.session_id != session.id
            }
            self._jobs[job.id] = _clone(retried_job)
            self._sessions[session.id] = _clone(retried_session)
            return _clone(retried_session), _clone(retried_job)

    def fail_exhausted_job(
        self,
        job_id: UUID,
        *,
        expected_attempt_count: int,
    ) -> tuple[DebateSession, DebateJob]:
        with self._lock:
            job, session = self._running_retry_records(
                job_id,
                expected_attempt_count=expected_attempt_count,
                require_exhausted=True,
            )
            at = max(self._queue_now(), job.updated_at, session.updated_at)
            failed_job = fail_job(
                job,
                at=at,
                safe_error_code="debate_retry_exhausted",
                provider_request_count=job.provider_request_count,
            )
            failed_session = transition_session(
                session,
                "failed",
                at=at,
                safe_error_code="debate_retry_exhausted",
            )
            self._jobs[job.id] = _clone(failed_job)
            self._sessions[session.id] = _clone(failed_session)
            return _clone(failed_session), _clone(failed_job)

    def _running_retry_records(
        self,
        job_id: UUID,
        *,
        expected_attempt_count: int,
        require_exhausted: bool,
    ) -> tuple[DebateJob, DebateSession]:
        job = self._jobs.get(job_id)
        if (
            job is None
            or job.status != "running"
            or job.attempt_count != expected_attempt_count
            or job.job_type not in {"round_1", "round_2"}
        ):
            raise DebateConcurrencyError("Running Debate retry state changed concurrently")
        exhausted = job.attempt_count >= job.max_attempts
        if exhausted != require_exhausted:
            raise DebateConcurrencyError("Debate retry budget does not match the requested action")
        session = self._sessions.get(job.session_id)
        running_status = (
            "running_round_1" if job.job_type == "round_1" else "running_round_2"
        )
        if session is None or session.user_id != job.user_id or session.status != running_status:
            raise DebateConcurrencyError("Debate Session is not running the claimed Job")
        return job, session

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

    @staticmethod
    def _validate_new_message(session: DebateSession, message: DebateMessage) -> None:
        if message.branch_id != session.active_branch_id:
            raise DebateConcurrencyError("Debate message branch is no longer active")
        if session.status in {"cancel_requested", "cancelled", "completed", "failed"}:
            raise DebateConcurrencyError("Debate session no longer accepts messages")
        if message.role != "user" and message.generation_id != session.active_generation_id:
            raise DebateConcurrencyError("Debate message generation is no longer active")
        if message.role in {"bull", "bear", "judge"}:
            expected_status = (
                "running_round_1" if message.round_number == 1 else "running_round_2"
            )
            if session.status != expected_status:
                raise DebateConcurrencyError("Debate session is not running this message round")

    def _validate_one_active_job(self, job: DebateJob) -> None:
        if job.status not in {"queued", "running"}:
            return
        if any(
            existing.session_id == job.session_id
            and existing.status in {"queued", "running"}
            and existing.id != job.id
            for existing in self._jobs.values()
        ):
            raise DebateConcurrencyError("Debate session already has an active job")

    @staticmethod
    def _validate_queue_admission(
        session: DebateSession,
        job: DebateJob,
        message: DebateQueueMessage,
    ) -> None:
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

    def _validate_round_two_admission(
        self,
        current: DebateSession,
        intervention: DebateIntervention,
        question: DebateMessage,
        session: DebateSession,
        job: DebateJob,
        message: DebateQueueMessage,
    ) -> None:
        if current.status != "awaiting_user" or session.status != "queued_round_2":
            raise DebateConcurrencyError("Debate session is not awaiting Round 2 admission")
        try:
            validate_session_update(current, session)
        except DebatePersistenceValidationError as exc:
            raise DebateRepositoryError(str(exc)) from exc
        target = self._messages.get(intervention.selected_message_id)
        if (
            intervention.session_id != current.id
            or intervention.user_id != current.user_id
            or intervention.mode != "challenge"
            or target is None
            or target.session_id != current.id
            or target.branch_id != current.active_branch_id
            or intervention.selected_text not in target.content
        ):
            raise DebateRepositoryError("Round 2 intervention does not match its target")
        self._validate_new_message(current, question)
        expected_sequence = 1 + max(
            (
                existing.sequence_number
                for existing in self._messages.values()
                if existing.session_id == current.id
                and existing.branch_id == current.active_branch_id
            ),
            default=0,
        )
        if (
            question.role != "user"
            or question.message_kind != "question"
            or question.round_number != 2
            or question.exchange_number != 0
            or question.sequence_number != expected_sequence
            or question.generation_id != session.active_generation_id
            or question.content != intervention.question
            or question.metadata.get("intervention_id") != str(intervention.id)
            or question.metadata.get("selected_message_id")
            != str(intervention.selected_message_id)
            or question.metadata.get("selected_text") != intervention.selected_text
            or question.metadata.get("mode") != "challenge"
        ):
            raise DebateRepositoryError("Round 2 question does not match its intervention")
        self._validate_queue_admission(session, job, message)
        if job.job_type != "round_2":
            raise DebateRepositoryError("Round 2 admission requires a Round 2 Job")

    def _queue_now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise DebateRepositoryError("Queue clock must return a timezone-aware value")
        return now
