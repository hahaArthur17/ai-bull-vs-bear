from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Stock(BaseModel):
    ticker: str
    company_name: str
    exchange: str
    sector: str


class PricePoint(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class TechnicalIndicators(BaseModel):
    ticker: str
    as_of: str
    rsi: float
    macd: float
    macd_signal: float
    moving_average_20: float
    moving_average_50: float
    volatility: float
    volume_spike: bool
    signal_summary: str


class EvidenceItem(BaseModel):
    id: str
    ticker: str
    source_type: Literal["news", "filing", "technical"]
    title: str
    url: str | None = None
    published_at: str | None = None
    excerpt: str
    metadata: dict[str, str] = Field(default_factory=dict)


class WatchlistRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=10)


class WatchlistResponse(BaseModel):
    user_id: str
    tickers: list[str]


class AnalysisRequest(BaseModel):
    question: str | None = Field(default=None, max_length=500)


class Claim(BaseModel):
    id: str
    agent: Literal["bull", "bear"]
    text: str
    evidence_ids: list[str]
    signal_strength: Literal["weak", "medium", "strong"]
    confidence: Literal["low", "medium", "high"]
    risk_meaning: str
    terms: list[str] = Field(default_factory=list)


class JudgeSummary(BaseModel):
    summary: str
    evidence_strength: Literal["weak", "medium", "strong"]
    uncertainty: str
    risk_level: Literal["low", "medium", "high"]


class TraceStep(BaseModel):
    step: str
    status: Literal["completed", "skipped", "failed"]
    detail: str


class TokenUsage(BaseModel):
    model_name: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class AnalysisResponse(BaseModel):
    analysis_id: str
    ticker: str
    created_at: str
    question: str | None = None
    indicators: TechnicalIndicators
    judge: JudgeSummary
    bull: Claim
    bear: Claim
    evidence: list[EvidenceItem]
    disclaimer: str
    guardrail_status: Literal["passed", "rewritten"]
    trace: list[TraceStep]
    token_usage: TokenUsage


QuestionType = Literal[
    "explain_term",
    "evidence_support",
    "signal_strength",
    "risk_meaning",
]


class ExaminationRequest(BaseModel):
    question_type: QuestionType


class ExaminationResponse(BaseModel):
    claim_id: str
    question_type: QuestionType
    answer: str
    evidence: list[EvidenceItem]
    disclaimer: str

