from app.domain.agents import DebateJudgeRequest, DebateTurnRequest
from app.providers.deterministic_debate import DeterministicDebateProvider
from app.providers.debate_agents import DebateJudgeProvider, DebateTurnProvider
from test_debate_agent_contract import (
    BRANCH_ID,
    GENERATION_ID,
    SESSION_ID,
    build_bull_message,
    build_context_and_snapshot,
)


def test_deterministic_provider_uses_latest_opponent_and_allowed_evidence_only() -> None:
    context, snapshot = build_context_and_snapshot()
    bull = build_bull_message()
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
        transcript=(bull,),
        rebuttal_target_message_id=bull.id,
        allowed_evidence_ids=context.allowed_evidence_ids,
    )

    provider = DeterministicDebateProvider()
    draft = provider.generate_turn(request)

    assert isinstance(provider, DebateTurnProvider)
    assert draft.responds_to_message_id == bull.id
    assert "latest Bull message" in draft.content
    assert set(draft.evidence_ids) <= context.allowed_evidence_ids
    assert all(term in draft.content for term in draft.terms)


def test_deterministic_judge_reports_phase_and_shared_snapshot_boundary() -> None:
    context, snapshot = build_context_and_snapshot()
    provider = DeterministicDebateProvider()
    draft = provider.generate_judgement(
        DebateJudgeRequest(
            session_id=SESSION_ID,
            branch_id=BRANCH_ID,
            phase="interim",
            analysis_context=context,
            factor_snapshot=snapshot,
            transcript=(build_bull_message(),),
            allowed_evidence_ids=context.allowed_evidence_ids,
        )
    )

    assert isinstance(provider, DebateJudgeProvider)
    assert draft.summary.startswith("Interim Judge summary")
    assert "not proof of causation" in draft.summary
    assert set(draft.evidence_ids) <= context.allowed_evidence_ids
