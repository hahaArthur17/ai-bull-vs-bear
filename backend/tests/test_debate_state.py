from datetime import timedelta
from uuid import UUID

import pytest

from app.services.debate_state import (
    DebateTransitionError,
    allowed_session_transitions,
    attach_judge_message,
    transition_session,
)
from test_debate_domain import NOW, build_session


INTERIM_JUDGE_ID = UUID("00000000-0000-4000-8000-000000000020")
FINAL_JUDGE_ID = UUID("00000000-0000-4000-8000-000000000021")


def advance_full_debate():
    session = build_session()
    session = transition_session(session, "queued_round_1", at=NOW + timedelta(seconds=1))
    session = transition_session(session, "running_round_1", at=NOW + timedelta(seconds=2))
    session = attach_judge_message(
        session,
        phase="interim",
        message_id=INTERIM_JUDGE_ID,
        at=NOW + timedelta(seconds=3),
    )
    session = transition_session(session, "awaiting_user", at=NOW + timedelta(seconds=4))
    session = transition_session(session, "queued_round_2", at=NOW + timedelta(seconds=5))
    session = transition_session(session, "running_round_2", at=NOW + timedelta(seconds=6))
    session = attach_judge_message(
        session,
        phase="final",
        message_id=FINAL_JUDGE_ID,
        at=NOW + timedelta(seconds=7),
    )
    return transition_session(session, "completed", at=NOW + timedelta(seconds=8))


def test_full_two_round_state_path_requires_both_judges() -> None:
    completed = advance_full_debate()

    assert completed.status == "completed"
    assert completed.interim_judge_message_id == INTERIM_JUDGE_ID
    assert completed.final_judge_message_id == FINAL_JUDGE_ID
    assert completed.completed_at == NOW + timedelta(seconds=8)


def test_round_one_cannot_pause_before_interim_judge() -> None:
    session = transition_session(
        build_session(),
        "queued_round_1",
        at=NOW + timedelta(seconds=1),
    )
    session = transition_session(session, "running_round_1", at=NOW + timedelta(seconds=2))

    with pytest.raises(DebateTransitionError, match="interim Judge"):
        transition_session(session, "awaiting_user", at=NOW + timedelta(seconds=3))


def test_session_cannot_skip_round_states() -> None:
    with pytest.raises(DebateTransitionError, match="created -> running_round_1"):
        transition_session(
            build_session(),
            "running_round_1",
            at=NOW + timedelta(seconds=1),
        )


def test_cancel_request_is_explicit_and_terminal() -> None:
    session = transition_session(
        build_session(),
        "queued_round_1",
        at=NOW + timedelta(seconds=1),
    )
    session = transition_session(
        session,
        "cancel_requested",
        at=NOW + timedelta(seconds=2),
    )
    cancelled = transition_session(
        session,
        "cancelled",
        at=NOW + timedelta(seconds=3),
    )

    assert cancelled.status == "cancelled"
    assert cancelled.completed_at == NOW + timedelta(seconds=3)
    assert allowed_session_transitions("cancelled") == frozenset()


def test_failed_transition_exposes_only_a_safe_error_code() -> None:
    with pytest.raises(DebateTransitionError, match="safe error code"):
        transition_session(build_session(), "failed", at=NOW + timedelta(seconds=1))

    failed = transition_session(
        build_session(),
        "failed",
        at=NOW + timedelta(seconds=1),
        safe_error_code="provider_unavailable",
    )

    assert failed.safe_error_code == "provider_unavailable"
    assert failed.completed_at == NOW + timedelta(seconds=1)


def test_transitions_reject_non_monotonic_timestamps() -> None:
    with pytest.raises(DebateTransitionError, match="cannot precede"):
        transition_session(
            build_session(),
            "queued_round_1",
            at=NOW - timedelta(seconds=1),
        )

