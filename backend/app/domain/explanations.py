from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.domain.base import ImmutableDomainModel
from app.domain.debate import DebateMessage
from app.domain.factors import AnalysisContext, FactorSnapshot


ExplanationTerm = Annotated[str, Field(min_length=1, max_length=100)]


class ExplanationAgentRequest(ImmutableDomainModel):
    """One exact selection grounded in an immutable Debate snapshot."""

    session_id: UUID
    branch_id: UUID
    ticker: str = Field(min_length=1, max_length=16)
    source_message: DebateMessage
    selected_text: str = Field(min_length=1, max_length=500)
    question: str = Field(min_length=1, max_length=500)
    analysis_context: AnalysisContext
    factor_snapshot: FactorSnapshot
    allowed_evidence_ids: frozenset[str] = frozenset()

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        return value.upper()

    @field_validator("selected_text", "question")
    @classmethod
    def normalize_user_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Explanation text cannot be blank")
        return normalized

    @model_validator(mode="after")
    def validate_bounded_source(self) -> ExplanationAgentRequest:
        if (
            self.source_message.session_id != self.session_id
            or self.source_message.branch_id != self.branch_id
        ):
            raise ValueError("Explanation source must belong to the selected branch")
        is_interrupted_prefix = (
            not self.source_message.is_complete
            and self.source_message.metadata.get("interrupted") is True
        )
        if not self.source_message.is_complete and not is_interrupted_prefix:
            raise ValueError(
                "Explanation source must be complete or an interrupted prefix"
            )
        if self.selected_text not in self.source_message.content:
            raise ValueError("Selected text must occur in the source message")
        if self.analysis_context.ticker != self.ticker:
            raise ValueError("Explanation context ticker does not match the request")
        if self.factor_snapshot.ticker != self.ticker:
            raise ValueError("Explanation factor ticker does not match the request")
        if self.factor_snapshot.as_of != self.analysis_context.as_of:
            raise ValueError("Explanation snapshots must share one as-of value")
        if not self.allowed_evidence_ids <= self.analysis_context.allowed_evidence_ids:
            raise ValueError("Explanation evidence must stay inside the frozen context")
        return self


class ExplanationDraft(ImmutableDomainModel):
    content: str = Field(min_length=1, max_length=2400)
    evidence_ids: tuple[str, ...] = Field(default=(), max_length=12)
    terms: tuple[ExplanationTerm, ...] = Field(default=(), max_length=12)


class ExplanationResult(ImmutableDomainModel):
    session_id: UUID
    source_message_id: UUID
    selected_text: str = Field(min_length=1, max_length=500)
    question: str = Field(min_length=1, max_length=500)
    content: str = Field(min_length=1, max_length=3000)
    evidence_ids: tuple[str, ...] = Field(default=(), max_length=12)
    terms: tuple[ExplanationTerm, ...] = Field(default=(), max_length=12)
    provider_name: str = Field(min_length=1, max_length=80)
    provider_version: str = Field(min_length=1, max_length=80)
    guardrail_status: Literal["passed", "rewritten"]
