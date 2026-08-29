from __future__ import annotations

from uuid import UUID

from app.domain.explanations import ExplanationAgentRequest, ExplanationResult
from app.providers.explanation import ExplanationProvider
from app.repositories.debate_repository import DebateSessionRepository
from app.services.guardrails import apply_guardrails


class ExplanationError(RuntimeError):
    """Safe base error for a rejected or unavailable explanation."""


class ExplanationNotFound(ExplanationError):
    """The owned Session or selected complete message does not exist."""


class ExplanationValidationError(ExplanationError):
    """The selected passage or provider output escaped its bounded context."""


class ExplanationProviderError(ExplanationError):
    """The provider failed without exposing private upstream detail."""


class ExplanationService:
    """Generate a panel result without mutating Debate state or transcript."""

    def __init__(
        self,
        repository: DebateSessionRepository,
        provider: ExplanationProvider,
    ) -> None:
        self.repository = repository
        self.provider = provider

    def explain(
        self,
        *,
        session_id: UUID,
        user_id: UUID,
        source_message_id: UUID,
        selected_text: str,
        question: str,
    ) -> ExplanationResult:
        session = self.repository.get_session(session_id, user_id)
        if session is None:
            raise ExplanationNotFound("Debate explanation source was not found")
        messages = self.repository.list_messages(
            session.id,
            user_id,
            branch_id=session.active_branch_id,
        )
        source = next(
            (message for message in messages if message.id == source_message_id),
            None,
        )
        if source is None or not source.is_complete:
            raise ExplanationNotFound("Debate explanation source was not found")
        citations = self.repository.list_message_evidence(source.id, user_id)
        allowed_evidence_ids = frozenset(
            citation.evidence_id
            for citation in citations
            if citation.evidence_id in session.analysis_context.allowed_evidence_ids
        )
        try:
            request = ExplanationAgentRequest(
                session_id=session.id,
                branch_id=session.active_branch_id,
                ticker=session.ticker,
                source_message=source,
                selected_text=selected_text,
                question=question,
                analysis_context=session.analysis_context,
                factor_snapshot=session.factor_snapshot,
                allowed_evidence_ids=allowed_evidence_ids,
            )
        except ValueError as exc:
            raise ExplanationValidationError(str(exc)) from exc

        try:
            draft = self.provider.generate_explanation(request)
        except Exception as exc:
            raise ExplanationProviderError("Explanation provider failed safely") from exc
        if any(
            evidence_id not in request.allowed_evidence_ids
            for evidence_id in draft.evidence_ids
        ):
            raise ExplanationValidationError(
                "Explanation cited evidence outside the selected message"
            )
        evidence_ids = tuple(dict.fromkeys(draft.evidence_ids))
        safe_content, guardrail_status, _ = apply_guardrails(draft.content)
        return ExplanationResult(
            session_id=session.id,
            source_message_id=source.id,
            selected_text=request.selected_text,
            question=request.question,
            content=safe_content,
            evidence_ids=evidence_ids,
            terms=draft.terms,
            provider_name=self.provider.name,
            provider_version=self.provider.version,
            guardrail_status=guardrail_status,
        )
