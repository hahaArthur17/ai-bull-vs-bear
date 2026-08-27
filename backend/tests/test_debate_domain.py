from datetime import datetime, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.domain.debate import (
    DebateIntervention,
    DebateMessage,
    DebateSession,
    build_round_plan,
)
from app.domain.factors import FactorSnapshot
from app.services.analysis_context import build_analysis_context


NOW = datetime(2026, 8, 27, 10, 0, tzinfo=timezone.utc)
SESSION_ID = UUID("00000000-0000-4000-8000-000000000001")
USER_ID = UUID("00000000-0000-4000-8000-000000000002")
BRANCH_ID = UUID("00000000-0000-4000-8000-000000000003")
GENERATION_ID = UUID("00000000-0000-4000-8000-000000000004")


def build_session() -> DebateSession:
    context = build_analysis_context("AAPL", as_of="2026-08-26")
    return DebateSession(
        id=SESSION_ID,
        user_id=USER_ID,
        stock_id=1,
        ticker="aapl",
        mode="demo",
        opening_side="bull",
        active_branch_id=BRANCH_ID,
        active_generation_id=GENERATION_ID,
        analysis_context=context,
        factor_snapshot=FactorSnapshot(ticker="AAPL", as_of=context.as_of),
        created_at=NOW,
        updated_at=NOW,
    )


def test_round_one_has_three_exchanges_and_an_interim_judge() -> None:
    plan = build_round_plan(1, "bull")

    assert len(plan.turns) == 7
    assert [turn.role for turn in plan.turns] == [
        "bull",
        "bear",
        "bull",
        "bear",
        "bull",
        "bear",
        "judge",
    ]
    assert plan.turns[0].message_kind == "argument"
    assert all(turn.message_kind == "rebuttal" for turn in plan.turns[1:6])
    assert plan.turns[-1].judge_phase == "interim"


def test_round_two_has_two_rebuttal_exchanges_and_a_final_judge() -> None:
    plan = build_round_plan(2, "bear")

    assert len(plan.turns) == 5
    assert [turn.role for turn in plan.turns] == [
        "bear",
        "bull",
        "bear",
        "bull",
        "judge",
    ]
    assert all(turn.message_kind == "rebuttal" for turn in plan.turns[:4])
    assert plan.turns[-1].judge_phase == "final"


def test_session_rejects_a_snapshot_for_another_ticker() -> None:
    session = build_session()

    with pytest.raises(ValidationError, match="Factor-snapshot ticker"):
        DebateSession.model_validate(
            {
                **session.model_dump(mode="python"),
                "factor_snapshot": FactorSnapshot(ticker="GOOG", as_of="2026-08-26"),
            }
        )


def test_complete_and_cancelled_messages_have_distinct_invariants() -> None:
    complete = DebateMessage(
        id=UUID("00000000-0000-4000-8000-000000000010"),
        session_id=SESSION_ID,
        branch_id=BRANCH_ID,
        generation_id=GENERATION_ID,
        sequence_number=1,
        round_number=1,
        exchange_number=1,
        role="bull",
        message_kind="argument",
        content="A bounded argument with explicit uncertainty.",
        is_complete=True,
        created_at=NOW,
    )

    assert complete.is_complete is True
    with pytest.raises(ValidationError, match="marked cancelled"):
        DebateMessage.model_validate(
            {**complete.model_dump(mode="python"), "content": "", "is_complete": False}
        )


def test_message_role_cannot_use_another_roles_kind() -> None:
    with pytest.raises(ValidationError, match="not valid for this role"):
        DebateMessage(
            id=UUID("00000000-0000-4000-8000-000000000011"),
            session_id=SESSION_ID,
            branch_id=BRANCH_ID,
            generation_id=GENERATION_ID,
            sequence_number=1,
            round_number=1,
            exchange_number=1,
            role="judge",
            message_kind="rebuttal",
            content="Invalid role-kind pair.",
            created_at=NOW,
        )


def test_intervention_modes_share_a_bounded_user_input_contract() -> None:
    intervention = DebateIntervention(
        id=UUID("00000000-0000-4000-8000-000000000012"),
        session_id=SESSION_ID,
        user_id=USER_ID,
        selected_message_id=UUID("00000000-0000-4000-8000-000000000010"),
        selected_text="moving average",
        question="What does this term mean in this argument?",
        mode="explain",
        created_at=NOW,
    )

    assert intervention.mode == "explain"
    with pytest.raises(ValidationError):
        DebateIntervention.model_validate(
            {**intervention.model_dump(mode="python"), "selected_text": "x" * 501}
        )
