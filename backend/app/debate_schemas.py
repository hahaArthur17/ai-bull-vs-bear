from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.domain.debate import (
    DebateMessage,
    DebateMessageEvidence,
    DebateSession,
    DebateSide,
)
from app.domain.factors import FactorFreshness
from app.domain.jobs import DebateJob


class DebateCreateRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=16)
    question: str | None = Field(default=None, max_length=500)
    opening_side: DebateSide = "bull"
    idempotency_key: str | None = Field(
        default=None,
        min_length=8,
        max_length=80,
        pattern=r"^[A-Za-z0-9_-]+$",
    )

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("Ticker cannot be blank")
        return normalized

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class DebateChallengeRequest(BaseModel):
    selected_message_id: UUID
    selected_text: str = Field(min_length=1, max_length=500)
    question: str = Field(min_length=1, max_length=500)
    idempotency_key: str | None = Field(
        default=None,
        min_length=8,
        max_length=80,
        pattern=r"^[A-Za-z0-9_-]+$",
    )

    @field_validator("selected_text", "question")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Text cannot be blank")
        return normalized


class DebateExplanationRequest(BaseModel):
    message_id: UUID
    selected_text: str = Field(min_length=1, max_length=500)
    question: str = Field(min_length=1, max_length=500)

    @field_validator("selected_text", "question")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Text cannot be blank")
        return normalized


class DebateInterruptRequest(BaseModel):
    generation_id: UUID
    message_id: UUID
    visible_prefix: str = Field(max_length=6000)


class DebateCancelRequest(BaseModel):
    generation_id: UUID


class DebateEvidencePresentation(BaseModel):
    evidence_id: str
    evidence_type: Literal["news", "filing", "technical"] | None = None
    title: str | None = None
    fact: str | None = None
    source: str | None = None
    date: str | None = None
    freshness: FactorFreshness = Field(default_factory=FactorFreshness)
    support_span: str | None = None
    source_destination: str | None = None
    missing_metadata: tuple[
        Literal["evidence_type", "title", "fact", "source", "date", "support_span", "source_destination"],
        ...,
    ] = ()


class DebateMessagePresentation(BaseModel):
    argument: str
    facts_used: tuple[DebateEvidencePresentation, ...] = ()
    interpretation: str | None = None
    uncertainty: str | None = None


class DebateMessageRecord(BaseModel):
    message: DebateMessage
    citations: tuple[DebateMessageEvidence, ...] = ()
    # Optional keeps old serialized records and event payloads parseable. The
    # canonical detail/message APIs always populate this server-side.
    presentation: DebateMessagePresentation | None = None


class DebateSessionDetail(BaseModel):
    session: DebateSession
    messages: tuple[DebateMessageRecord, ...] = ()
    job: DebateJob | None = None
    execution_mode: Literal["synchronous_preview", "queued"] = "synchronous_preview"


class DebateMutationResponse(DebateSessionDetail):
    job_id: UUID
