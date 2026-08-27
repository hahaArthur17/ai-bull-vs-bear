from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field, JsonValue, field_validator, model_validator

from app.domain.base import AwareDatetime, ImmutableDomainModel
from app.domain.factors import AnalysisContext, FactorSnapshot


DebateMode = Literal["live", "demo", "replay"]
DebateSide = Literal["bull", "bear"]
DebateSessionStatus = Literal[
    "created",
    "queued_round_1",
    "running_round_1",
    "awaiting_user",
    "queued_round_2",
    "running_round_2",
    "completed",
    "cancel_requested",
    "cancelled",
    "failed",
]
DebateRole = Literal["bull", "bear", "judge", "user", "explainer", "system"]
DebateMessageKind = Literal[
    "argument",
    "rebuttal",
    "summary",
    "question",
    "explanation",
]
InterventionMode = Literal["explain", "challenge"]


class DebateSession(ImmutableDomainModel):
    id: UUID
    user_id: UUID
    stock_id: int = Field(gt=0)
    ticker: str = Field(min_length=1, max_length=16)
    mode: DebateMode
    status: DebateSessionStatus = "created"
    opening_side: DebateSide
    initial_question: str | None = Field(default=None, max_length=500)
    active_branch_id: UUID
    active_generation_id: UUID
    analysis_context: AnalysisContext
    factor_snapshot: FactorSnapshot
    interim_judge_message_id: UUID | None = None
    final_judge_message_id: UUID | None = None
    guardrail_status: Literal["pending", "passed", "rewritten", "failed"] = "pending"
    safe_error_code: str | None = Field(default=None, max_length=80)
    created_at: AwareDatetime
    updated_at: AwareDatetime
    completed_at: AwareDatetime | None = None

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def validate_snapshot_and_terminal_state(self) -> DebateSession:
        if self.analysis_context.ticker != self.ticker:
            raise ValueError("Analysis-context ticker does not match the session")
        if self.factor_snapshot.ticker != self.ticker:
            raise ValueError("Factor-snapshot ticker does not match the session")
        if self.factor_snapshot.as_of != self.analysis_context.as_of:
            raise ValueError("Factor snapshot and analysis context must share one as-of value")
        if self.updated_at < self.created_at:
            raise ValueError("Session updated_at cannot precede created_at")
        terminal = self.status in {"completed", "cancelled", "failed"}
        if terminal != (self.completed_at is not None):
            raise ValueError("Only terminal sessions require completed_at")
        if self.status == "failed" and not self.safe_error_code:
            raise ValueError("A failed session requires a safe error code")
        if self.status != "failed" and self.safe_error_code is not None:
            raise ValueError("Only a failed session may expose a safe error code")
        return self


class DebateMessage(ImmutableDomainModel):
    id: UUID
    session_id: UUID
    branch_id: UUID
    generation_id: UUID
    sequence_number: int = Field(ge=1)
    round_number: int = Field(ge=0, le=2)
    exchange_number: int = Field(ge=0, le=3)
    role: DebateRole
    message_kind: DebateMessageKind
    content: str = Field(default="", max_length=6000)
    confidence: Literal["low", "medium", "high"] | None = None
    signal_strength: Literal["weak", "medium", "strong"] | None = None
    terms: tuple[str, ...] = Field(default=(), max_length=12)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    is_complete: bool = True
    cancelled_at: AwareDatetime | None = None
    created_at: AwareDatetime

    @model_validator(mode="after")
    def validate_role_kind_and_completion(self) -> DebateMessage:
        allowed_kinds: dict[str, set[str]] = {
            "bull": {"argument", "rebuttal"},
            "bear": {"argument", "rebuttal"},
            "judge": {"summary"},
            "user": {"question"},
            "explainer": {"explanation"},
            "system": {"summary"},
        }
        if self.message_kind not in allowed_kinds[self.role]:
            raise ValueError("Message kind is not valid for this role")
        if self.role in {"bull", "bear", "judge"} and self.round_number not in {1, 2}:
            raise ValueError("Debate-agent messages require round 1 or 2")
        if self.is_complete:
            if not self.content:
                raise ValueError("A complete message requires content")
            if self.cancelled_at is not None:
                raise ValueError("A complete message cannot be cancelled")
        elif self.cancelled_at is None:
            raise ValueError("An incomplete canonical message must be marked cancelled")
        return self


class DebateMessageEvidence(ImmutableDomainModel):
    message_id: UUID
    evidence_id: str = Field(min_length=1, max_length=240)
    citation_order: int = Field(ge=1)
    support_span: str | None = Field(default=None, max_length=500)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class DebateIntervention(ImmutableDomainModel):
    id: UUID
    session_id: UUID
    user_id: UUID
    selected_message_id: UUID
    selected_text: str = Field(min_length=1, max_length=500)
    question: str = Field(min_length=1, max_length=500)
    mode: InterventionMode
    created_at: AwareDatetime


class PlannedTurn(ImmutableDomainModel):
    stage_sequence: int = Field(ge=1)
    round_number: Literal[1, 2]
    exchange_number: int = Field(ge=0, le=3)
    role: Literal["bull", "bear", "judge"]
    message_kind: Literal["argument", "rebuttal", "summary"]
    judge_phase: Literal["interim", "final"] | None = None

    @model_validator(mode="after")
    def validate_turn_shape(self) -> PlannedTurn:
        if self.role == "judge":
            if self.message_kind != "summary" or self.judge_phase is None:
                raise ValueError("Judge turns require a summary phase")
        elif self.message_kind == "summary" or self.judge_phase is not None:
            raise ValueError("Bull/Bear turns cannot use Judge fields")
        return self


class DebateRoundPlan(ImmutableDomainModel):
    round_number: Literal[1, 2]
    job_type: Literal["round_1", "round_2"]
    opening_side: DebateSide
    turns: tuple[PlannedTurn, ...] = Field(min_length=1)


def build_round_plan(
    round_number: Literal[1, 2],
    opening_side: DebateSide,
) -> DebateRoundPlan:
    exchange_count = 3 if round_number == 1 else 2
    responding_side: DebateSide = "bear" if opening_side == "bull" else "bull"
    turns: list[PlannedTurn] = []
    for exchange_number in range(1, exchange_count + 1):
        for role in (opening_side, responding_side):
            first_opening = round_number == 1 and exchange_number == 1 and not turns
            turns.append(
                PlannedTurn(
                    stage_sequence=len(turns) + 1,
                    round_number=round_number,
                    exchange_number=exchange_number,
                    role=role,
                    message_kind="argument" if first_opening else "rebuttal",
                )
            )
    turns.append(
        PlannedTurn(
            stage_sequence=len(turns) + 1,
            round_number=round_number,
            exchange_number=0,
            role="judge",
            message_kind="summary",
            judge_phase="interim" if round_number == 1 else "final",
        )
    )
    return DebateRoundPlan(
        round_number=round_number,
        job_type="round_1" if round_number == 1 else "round_2",
        opening_side=opening_side,
        turns=tuple(turns),
    )

