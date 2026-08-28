from __future__ import annotations

from collections.abc import Mapping
from typing import Literal
from uuid import UUID, uuid5

from app.domain.base import AwareDatetime
from app.domain.debate import DebateSession, DebateSessionStatus


class DebateTransitionError(ValueError):
    """Raised when a caller attempts an invalid Debate state change."""


ALLOWED_SESSION_TRANSITIONS: Mapping[
    DebateSessionStatus,
    frozenset[DebateSessionStatus],
] = {
    "created": frozenset({"queued_round_1", "cancel_requested", "failed"}),
    "queued_round_1": frozenset({"running_round_1", "cancel_requested", "failed"}),
    "running_round_1": frozenset({"awaiting_user", "cancel_requested", "failed"}),
    "awaiting_user": frozenset({"queued_round_2", "cancel_requested", "failed"}),
    "queued_round_2": frozenset({"running_round_2", "cancel_requested", "failed"}),
    "running_round_2": frozenset({"completed", "cancel_requested", "failed"}),
    "cancel_requested": frozenset({"cancelled", "failed"}),
    "completed": frozenset(),
    "cancelled": frozenset(),
    "failed": frozenset(),
}


def allowed_session_transitions(
    status: DebateSessionStatus,
) -> frozenset[DebateSessionStatus]:
    return ALLOWED_SESSION_TRANSITIONS[status]


def transition_session(
    session: DebateSession,
    target: DebateSessionStatus,
    *,
    at: AwareDatetime,
    safe_error_code: str | None = None,
) -> DebateSession:
    if target not in ALLOWED_SESSION_TRANSITIONS[session.status]:
        raise DebateTransitionError(
            f"Invalid Debate session transition: {session.status} -> {target}"
        )
    if at < session.updated_at:
        raise DebateTransitionError("Transition time cannot precede the current session state")
    if target == "awaiting_user" and session.interim_judge_message_id is None:
        raise DebateTransitionError("Round one requires an interim Judge before awaiting user")
    if target == "completed" and session.final_judge_message_id is None:
        raise DebateTransitionError("Round two requires a final Judge before completion")
    if target == "failed" and not safe_error_code:
        raise DebateTransitionError("A failed transition requires a safe error code")
    if target != "failed" and safe_error_code is not None:
        raise DebateTransitionError("A safe error code is valid only for a failed transition")

    payload = session.model_dump(mode="python")
    payload.update(
        status=target,
        updated_at=at,
        completed_at=at if target in {"completed", "cancelled", "failed"} else None,
        safe_error_code=safe_error_code,
    )
    return DebateSession.model_validate(payload)


def request_session_cancellation(
    session: DebateSession,
    *,
    at: AwareDatetime,
) -> tuple[DebateSession, UUID]:
    """Invalidate the active generation before cancellation is acknowledged.

    Rotating the generation makes provider output already in flight stale. The
    former generation is returned so event consumers can discard its drafts.
    """

    if session.status in {"completed", "cancelled", "failed"}:
        raise DebateTransitionError("A terminal Debate session cannot be cancelled")
    if session.status == "cancel_requested":
        raise DebateTransitionError("Debate cancellation is already requested")

    cancelled_generation_id = session.active_generation_id
    invalidated = DebateSession.model_validate(
        {
            **session.model_dump(mode="python"),
            "active_generation_id": uuid5(
                session.id,
                f"cancel:{cancelled_generation_id}",
            ),
        }
    )
    requested = transition_session(invalidated, "cancel_requested", at=at)
    return requested, cancelled_generation_id


def attach_judge_message(
    session: DebateSession,
    *,
    phase: Literal["interim", "final"],
    message_id: UUID,
    at: AwareDatetime,
) -> DebateSession:
    required_status = "running_round_1" if phase == "interim" else "running_round_2"
    if session.status != required_status:
        raise DebateTransitionError(
            f"Cannot attach {phase} Judge message while session is {session.status}"
        )
    if at < session.updated_at:
        raise DebateTransitionError("Judge message time cannot precede the current session state")
    field_name = (
        "interim_judge_message_id" if phase == "interim" else "final_judge_message_id"
    )
    if getattr(session, field_name) is not None:
        raise DebateTransitionError(f"The {phase} Judge message is already attached")

    payload = session.model_dump(mode="python")
    payload[field_name] = message_id
    payload["updated_at"] = at
    return DebateSession.model_validate(payload)
