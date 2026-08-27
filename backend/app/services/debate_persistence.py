from __future__ import annotations

from app.domain.debate import DebateSession
from app.domain.jobs import DebateJob, DebateJobStatus
from app.services.debate_state import allowed_session_transitions


class DebatePersistenceValidationError(ValueError):
    """A canonical record update violates immutable or lifecycle state."""


ALLOWED_JOB_TRANSITIONS: dict[DebateJobStatus, frozenset[DebateJobStatus]] = {
    "queued": frozenset({"running", "failed", "cancelled"}),
    "running": frozenset({"completed", "failed", "cancelled"}),
    "completed": frozenset(),
    "failed": frozenset(),
    "cancelled": frozenset(),
}


def validate_session_update(current: DebateSession, updated: DebateSession) -> None:
    immutable_fields = (
        "id",
        "user_id",
        "stock_id",
        "ticker",
        "mode",
        "opening_side",
        "initial_question",
        "analysis_context",
        "factor_snapshot",
        "created_at",
    )
    if any(getattr(current, field) != getattr(updated, field) for field in immutable_fields):
        raise DebatePersistenceValidationError("Immutable Debate session fields cannot change")
    if updated.updated_at < current.updated_at:
        raise DebatePersistenceValidationError("Debate session update time cannot move backwards")
    if updated.status != current.status:
        if updated.status not in allowed_session_transitions(current.status):
            raise DebatePersistenceValidationError("Invalid Debate session status transition")
        if updated.status == "awaiting_user" and updated.interim_judge_message_id is None:
            raise DebatePersistenceValidationError("Round one requires an interim Judge")
        if updated.status == "completed" and updated.final_judge_message_id is None:
            raise DebatePersistenceValidationError("Round two requires a final Judge")


def validate_job_update(current: DebateJob, updated: DebateJob) -> None:
    immutable_fields = (
        "id",
        "session_id",
        "user_id",
        "job_type",
        "idempotency_key",
        "max_attempts",
        "available_at",
        "created_at",
    )
    if any(getattr(current, field) != getattr(updated, field) for field in immutable_fields):
        raise DebatePersistenceValidationError("Immutable Debate job fields cannot change")
    if updated.updated_at < current.updated_at:
        raise DebatePersistenceValidationError("Debate job update time cannot move backwards")
    if (
        updated.status != current.status
        and updated.status not in ALLOWED_JOB_TRANSITIONS[current.status]
    ):
        raise DebatePersistenceValidationError("Invalid Debate job status transition")
