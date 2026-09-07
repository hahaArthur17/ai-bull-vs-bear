from __future__ import annotations

from typing import Annotated, Literal, TypeAlias
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.base import ImmutableDomainModel
from app.domain.debate import DebateMessage
from app.domain.factors import AnalysisContext, FactorSnapshot


BoundedPoint = Annotated[str, Field(min_length=1, max_length=300)]
BoundedTerm = Annotated[str, Field(min_length=1, max_length=100)]


class DebateTurnRequest(ImmutableDomainModel):
    session_id: UUID
    branch_id: UUID
    generation_id: UUID
    ticker: str = Field(min_length=1, max_length=16)
    role: Literal["bull", "bear"]
    round_number: Literal[1, 2]
    exchange_number: int = Field(ge=1, le=3)
    initial_question: str | None = Field(default=None, max_length=500)
    user_intervention: str | None = Field(default=None, max_length=500)
    analysis_context: AnalysisContext
    factor_snapshot: FactorSnapshot
    transcript: tuple[DebateMessage, ...] = ()
    rebuttal_target_message_id: UUID | None = None
    allowed_evidence_ids: frozenset[str] = frozenset()
    previously_used_points: tuple[BoundedPoint, ...] = Field(default=(), max_length=30)
    max_output_chars: int = Field(default=1600, ge=300, le=4000)

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def validate_grounding_and_rebuttal_target(self) -> DebateTurnRequest:
        normalized_ticker = self.ticker.upper()
        if self.analysis_context.ticker != normalized_ticker:
            raise ValueError("Analysis-context ticker does not match the turn request")
        if self.factor_snapshot.ticker != normalized_ticker:
            raise ValueError("Factor-snapshot ticker does not match the turn request")
        if self.factor_snapshot.as_of != self.analysis_context.as_of:
            raise ValueError("Turn request snapshots must share one as-of value")
        if not self.allowed_evidence_ids <= self.analysis_context.allowed_evidence_ids:
            raise ValueError("Turn request contains evidence outside the immutable context")
        if any(
            message.session_id != self.session_id or message.branch_id != self.branch_id
            for message in self.transcript
        ):
            raise ValueError("Transcript messages must belong to the requested session branch")
        if any(not message.is_complete for message in self.transcript):
            raise ValueError("Only complete canonical messages may enter a turn request")

        opponent = "bear" if self.role == "bull" else "bull"
        latest_opponent = next(
            (message for message in reversed(self.transcript) if message.role == opponent),
            None,
        )
        if latest_opponent is None:
            if self.rebuttal_target_message_id is not None:
                raise ValueError("A rebuttal target must reference a prior opponent message")
        elif self.rebuttal_target_message_id != latest_opponent.id:
            raise ValueError("The latest opponent message must be the rebuttal target")
        return self


class DebateTurnDraft(ImmutableDomainModel):
    content: str = Field(min_length=1, max_length=4000)
    interpretation: str | None = Field(default=None, min_length=1, max_length=1200)
    evidence_ids: tuple[str, ...] = Field(default=(), max_length=12)
    responds_to_message_id: UUID | None = None
    rebuttal_point: str | None = Field(default=None, max_length=500)
    confidence: Literal["low", "medium", "high"]
    signal_strength: Literal["weak", "medium", "strong"]
    risk_meaning: str = Field(min_length=1, max_length=1200)
    terms: tuple[BoundedTerm, ...] = Field(default=(), max_length=12)

    @model_validator(mode="after")
    def validate_rebuttal_fields(self) -> DebateTurnDraft:
        if (self.responds_to_message_id is None) != (self.rebuttal_point is None):
            raise ValueError("A rebuttal target and rebuttal point must be supplied together")
        return self


class DebateTurnStreamDelta(BaseModel):
    """One provider-emitted text fragment with whitespace preserved exactly."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=False,
        allow_inf_nan=False,
    )

    kind: Literal["delta"] = "delta"
    chunk_index: int = Field(ge=1)
    delta: str = Field(min_length=1, max_length=1200)
    source: Literal[
        "live_provider",
        "buffered_compatibility",
        "deterministic",
    ]


class DebateTurnStreamUsage(ImmutableDomainModel):
    model_name: str = Field(min_length=1, max_length=160)
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_token_total(self) -> DebateTurnStreamUsage:
        if self.total_tokens != self.prompt_tokens + self.completion_tokens:
            raise ValueError("Stream token total must equal prompt plus completion tokens")
        return self


class DebateTurnStreamCompleted(ImmutableDomainModel):
    kind: Literal["completed"] = "completed"
    draft: DebateTurnDraft
    finish_reason: Literal["stop", "length", "content_filter"] = "stop"
    usage: DebateTurnStreamUsage


DebateTurnStreamEvent: TypeAlias = DebateTurnStreamDelta | DebateTurnStreamCompleted


class DebateJudgeRequest(ImmutableDomainModel):
    session_id: UUID
    branch_id: UUID
    phase: Literal["interim", "final"]
    analysis_context: AnalysisContext
    factor_snapshot: FactorSnapshot
    transcript: tuple[DebateMessage, ...] = Field(min_length=1)
    allowed_evidence_ids: frozenset[str] = frozenset()

    @model_validator(mode="after")
    def validate_transcript(self) -> DebateJudgeRequest:
        if self.factor_snapshot.ticker != self.analysis_context.ticker:
            raise ValueError("Judge request snapshots must use the same ticker")
        if self.factor_snapshot.as_of != self.analysis_context.as_of:
            raise ValueError("Judge request snapshots must share one as-of value")
        if any(
            message.session_id != self.session_id
            or message.branch_id != self.branch_id
            or not message.is_complete
            for message in self.transcript
        ):
            raise ValueError("Judge transcript must contain complete messages from one branch")
        if self.phase == "interim" and not any(
            message.round_number == 1 for message in self.transcript
        ):
            raise ValueError("Interim Judge requires round-one messages")
        if self.phase == "final" and not any(
            message.round_number == 2 for message in self.transcript
        ):
            raise ValueError("Final Judge requires round-two messages")
        if not self.allowed_evidence_ids <= self.analysis_context.allowed_evidence_ids:
            raise ValueError("Judge request contains evidence outside the immutable context")
        return self


class DebateJudgeDraft(ImmutableDomainModel):
    summary: str = Field(min_length=1, max_length=4000)
    interpretation: str | None = Field(default=None, min_length=1, max_length=1200)
    agreements: tuple[BoundedPoint, ...] = Field(default=(), max_length=12)
    disagreements: tuple[BoundedPoint, ...] = Field(default=(), max_length=12)
    missing_evidence: tuple[BoundedPoint, ...] = Field(default=(), max_length=12)
    evidence_ids: tuple[str, ...] = Field(default=(), max_length=20)
    evidence_strength: Literal["weak", "medium", "strong"]
    uncertainty: str = Field(min_length=1, max_length=1200)
    risk_level: Literal["low", "medium", "high"]
