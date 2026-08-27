from datetime import datetime, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.domain.agents import (
    DebateJudgeDraft,
    DebateJudgeRequest,
    DebateTurnDraft,
    DebateTurnRequest,
)
from app.domain.debate import DebateMessage
from app.domain.factors import FactorSnapshot
from app.providers.debate_agents import DebateJudgeProvider, DebateTurnProvider
from app.services.analysis_context import build_analysis_context


NOW = datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc)
SESSION_ID = UUID("00000000-0000-4000-8000-000000000040")
BRANCH_ID = UUID("00000000-0000-4000-8000-000000000041")
GENERATION_ID = UUID("00000000-0000-4000-8000-000000000042")
BULL_MESSAGE_ID = UUID("00000000-0000-4000-8000-000000000043")


def build_context_and_snapshot():
    context = build_analysis_context("AAPL", as_of="2026-08-26")
    snapshot = FactorSnapshot(ticker="AAPL", as_of=context.as_of)
    return context, snapshot


def build_bull_message() -> DebateMessage:
    return DebateMessage(
        id=BULL_MESSAGE_ID,
        session_id=SESSION_ID,
        branch_id=BRANCH_ID,
        generation_id=GENERATION_ID,
        sequence_number=1,
        round_number=1,
        exchange_number=1,
        role="bull",
        message_kind="argument",
        content="A constructive but uncertain interpretation.",
        created_at=NOW,
    )


def test_turn_request_requires_the_latest_opponent_as_rebuttal_target() -> None:
    context, snapshot = build_context_and_snapshot()
    message = build_bull_message()

    request = DebateTurnRequest(
        session_id=SESSION_ID,
        branch_id=BRANCH_ID,
        generation_id=GENERATION_ID,
        ticker="AAPL",
        role="bear",
        round_number=1,
        exchange_number=1,
        analysis_context=context,
        factor_snapshot=snapshot,
        transcript=(message,),
        rebuttal_target_message_id=message.id,
    )

    assert request.rebuttal_target_message_id == BULL_MESSAGE_ID
    with pytest.raises(ValidationError, match="latest opponent"):
        DebateTurnRequest.model_validate(
            {**request.model_dump(mode="python"), "rebuttal_target_message_id": None}
        )


def test_first_opening_turn_does_not_invent_a_rebuttal_target() -> None:
    context, snapshot = build_context_and_snapshot()

    request = DebateTurnRequest(
        session_id=SESSION_ID,
        branch_id=BRANCH_ID,
        generation_id=GENERATION_ID,
        ticker="AAPL",
        role="bull",
        round_number=1,
        exchange_number=1,
        analysis_context=context,
        factor_snapshot=snapshot,
    )

    assert request.rebuttal_target_message_id is None


def test_turn_draft_requires_rebuttal_target_and_point_together() -> None:
    with pytest.raises(ValidationError, match="supplied together"):
        DebateTurnDraft(
            content="A rebuttal without its explicit target is invalid.",
            responds_to_message_id=BULL_MESSAGE_ID,
            confidence="low",
            signal_strength="weak",
            risk_meaning="Uncertainty remains.",
        )


def test_final_judge_requires_round_two_in_the_transcript() -> None:
    context, snapshot = build_context_and_snapshot()

    with pytest.raises(ValidationError, match="round-two"):
        DebateJudgeRequest(
            session_id=SESSION_ID,
            branch_id=BRANCH_ID,
            phase="final",
            analysis_context=context,
            factor_snapshot=snapshot,
            transcript=(build_bull_message(),),
        )


def test_turn_and_judge_providers_are_structural_contracts() -> None:
    class ContractProvider:
        name = "contract-provider"
        version = "test-v1"

        def generate_turn(self, request: DebateTurnRequest) -> DebateTurnDraft:
            return DebateTurnDraft(
                content="Bounded educational argument.",
                confidence="low",
                signal_strength="weak",
                risk_meaning="The interpretation may change with new evidence.",
            )

        def generate_judgement(self, request: DebateJudgeRequest) -> DebateJudgeDraft:
            return DebateJudgeDraft(
                summary="The evidence remains mixed.",
                evidence_strength="weak",
                uncertainty="Important information remains unavailable.",
                risk_level="medium",
            )

    provider = ContractProvider()
    assert isinstance(provider, DebateTurnProvider)
    assert isinstance(provider, DebateJudgeProvider)

