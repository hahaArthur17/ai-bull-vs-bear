from datetime import timedelta
from uuid import UUID, uuid4

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
from test_debate_domain import NOW
from test_memory_debate_repository import build_message, store_running_round_one


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


def test_deterministic_explanation_accepts_a_long_exact_passage() -> None:
    repository, session, _, messages = build_completed_round_one()
    target = messages[0]
    selected_text = target.content[:140]
    assert len(selected_text) > 100

    result = ExplanationService(
        repository,
        DeterministicExplanationProvider(),
    ).explain(
        session_id=session.id,
        user_id=USER_ID,
        source_message_id=target.id,
        selected_text=selected_text,
        question="Can you explain this point in plain language?",
    )

    assert result.selected_text == selected_text
    assert result.terms == ()
    assert "Can you explain this point" in result.content


def test_interrupted_prefix_explanation_is_read_only_and_has_no_citations() -> None:
    repository = InMemoryDebateRepository()
    running = store_running_round_one(repository)
    draft = build_message(content="Visible unfinished prefix with bounded context")
    repository.checkpoint_draft(draft)
    stopped = repository.interrupt_generation(
        running.id,
        running.user_id,
        running.active_generation_id,
        draft.id,
        "Visible unfinished prefix",
        NOW + timedelta(seconds=5),
    )
    messages_before = repository.list_messages(
        stopped.id,
        stopped.user_id,
        branch_id=stopped.active_branch_id,
    )

    result = ExplanationService(
        repository,
        DeterministicExplanationProvider(),
    ).explain(
        session_id=stopped.id,
        user_id=stopped.user_id,
        source_message_id=messages_before[0].id,
        selected_text="unfinished prefix",
        question="What can this partial point mean without assuming its conclusion?",
    )

    assert "interrupted Bull prefix" in result.content
    assert result.evidence_ids == ()
    assert repository.get_session(stopped.id, stopped.user_id) == stopped
    assert repository.list_messages(
        stopped.id,
        stopped.user_id,
        branch_id=stopped.active_branch_id,
    ) == messages_before


def test_explanation_rejects_empty_or_unmarked_incomplete_sources() -> None:
    repository = InMemoryDebateRepository()
    running = store_running_round_one(repository)
    stopped = repository.interrupt_before_output_generation(
        running.id,
        running.user_id,
        running.active_generation_id,
        NOW + timedelta(seconds=5),
    )
    empty_source = repository.list_messages(
        stopped.id,
        stopped.user_id,
        branch_id=stopped.active_branch_id,
    )[0]
    service = ExplanationService(repository, DeterministicExplanationProvider())

    with pytest.raises(ExplanationNotFound):
        service.explain(
            session_id=stopped.id,
            user_id=stopped.user_id,
            source_message_id=empty_source.id,
            selected_text="invented",
            question="What does this mean?",
        )

    unmarked = empty_source.model_copy(
        update={
            "id": uuid4(),
            "content": "Unmarked incomplete content",
            "metadata": {},
        }
    )
    repository._messages[unmarked.id] = unmarked
    with pytest.raises(ExplanationNotFound):
        service.explain(
            session_id=stopped.id,
            user_id=stopped.user_id,
            source_message_id=unmarked.id,
            selected_text="incomplete content",
            question="What does this mean?",
        )


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
