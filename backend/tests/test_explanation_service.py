from uuid import UUID

import pytest

from app.domain.explanations import ExplanationDraft
from app.domain.factors import AnalysisContext, FactorSnapshot
from app.providers.deterministic_debate import DeterministicDebateProvider
from app.providers.explanation import DeterministicExplanationProvider
from app.repositories.memory_debate_repository import InMemoryDebateRepository
from app.services.debate_preview import DebatePreviewService
from app.services.explanation import (
    ExplanationNotFound,
    ExplanationProviderError,
    ExplanationService,
    ExplanationValidationError,
)
from app.services.guardrails import DISCLAIMER


USER_ID = UUID("00000000-0000-4000-8000-000000000701")


def build_completed_round_one():
    repository = InMemoryDebateRepository()
    provider = DeterministicDebateProvider()
    preview = DebatePreviewService(repository, provider, provider)
    context = AnalysisContext.model_validate(
        {
            "ticker": "AAPL",
            "as_of": "2026-08-29T12:00:00+00:00",
            "evidence": [
                {
                    "id": "explanation-evidence-1",
                    "ticker": "AAPL",
                    "source_type": "filing",
                    "title": "Bounded explanation fixture",
                    "published_at": "2026-08-29",
                    "excerpt": "A dated fixture used only for explanation tests.",
                }
            ],
            "allowed_evidence_ids": ["explanation-evidence-1"],
        }
    )
    session, job = preview.create_and_execute_round_one(
        user_id=USER_ID,
        stock_id=1,
        ticker="AAPL",
        opening_side="bull",
        question=None,
        analysis_context=context,
        factor_snapshot=FactorSnapshot(ticker="AAPL", as_of=context.as_of),
    )
    messages = repository.list_messages(
        session.id,
        USER_ID,
        branch_id=session.active_branch_id,
    )
    return repository, session, repository.get_job(job.id), messages


def test_explanation_is_grounded_without_mutating_debate_state() -> None:
    repository, session, job_before, messages_before = build_completed_round_one()
    target = messages_before[0]
    service = ExplanationService(repository, DeterministicExplanationProvider())

    result = service.explain(
        session_id=session.id,
        user_id=USER_ID,
        source_message_id=target.id,
        selected_text="frozen snapshot",
        question="What does this mean here?",
    )

    assert result.session_id == session.id
    assert result.source_message_id == target.id
    assert result.selected_text == "frozen snapshot"
    assert result.evidence_ids == ("explanation-evidence-1",)
    assert result.provider_name == "deterministic-explainer"
    assert result.guardrail_status == "passed"
    assert result.content.endswith(DISCLAIMER)
    assert repository.get_session(session.id, USER_ID) == session
    assert repository.get_job(job_before.id) == job_before
    assert repository.list_messages(
        session.id,
        USER_ID,
        branch_id=session.active_branch_id,
    ) == messages_before


def test_explanation_requires_owned_active_branch_message_and_exact_text() -> None:
    repository, session, _, messages = build_completed_round_one()
    service = ExplanationService(repository, DeterministicExplanationProvider())

    with pytest.raises(ExplanationNotFound):
        service.explain(
            session_id=session.id,
            user_id=UUID("00000000-0000-4000-8000-000000000702"),
            source_message_id=messages[0].id,
            selected_text="frozen snapshot",
            question="What does this mean here?",
        )
    with pytest.raises(ExplanationValidationError, match="Selected text"):
        service.explain(
            session_id=session.id,
            user_id=USER_ID,
            source_message_id=messages[0].id,
            selected_text="text that is not present",
            question="What does this mean here?",
        )


def test_explanation_rejects_provider_evidence_outside_selected_message() -> None:
    class InvalidEvidenceProvider(DeterministicExplanationProvider):
        def generate_explanation(self, request):
            return ExplanationDraft(
                content="A bounded explanation.",
                evidence_ids=("invented-evidence",),
            )

    repository, session, _, messages = build_completed_round_one()
    service = ExplanationService(repository, InvalidEvidenceProvider())

    with pytest.raises(ExplanationValidationError, match="outside"):
        service.explain(
            session_id=session.id,
            user_id=USER_ID,
            source_message_id=messages[0].id,
            selected_text="frozen snapshot",
            question="What does this mean here?",
        )


def test_explanation_hides_provider_failure_details() -> None:
    class FailingProvider(DeterministicExplanationProvider):
        def generate_explanation(self, request):
            raise RuntimeError("private provider response and request identifier")

    repository, session, _, messages = build_completed_round_one()
    service = ExplanationService(repository, FailingProvider())

    with pytest.raises(ExplanationProviderError) as error:
        service.explain(
            session_id=session.id,
            user_id=USER_ID,
            source_message_id=messages[0].id,
            selected_text="frozen snapshot",
            question="What does this mean here?",
        )

    assert str(error.value) == "Explanation provider failed safely"
    assert "private provider" not in str(error.value)


def test_explanation_applies_financial_language_guardrails() -> None:
    repository, session, _, messages = build_completed_round_one()
    service = ExplanationService(repository, DeterministicExplanationProvider())

    result = service.explain(
        session_id=session.id,
        user_id=USER_ID,
        source_message_id=messages[0].id,
        selected_text="frozen snapshot",
        question="Does this mean you should buy the stock?",
    )

    assert result.guardrail_status == "rewritten"
    assert "you should buy" not in result.content.lower()
    assert result.content.endswith(DISCLAIMER)
