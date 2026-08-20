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
    source: Literal["daily_market_cache", "demo_fallback"] = "demo_fallback"
    is_stale: bool = True


class PriceHistoryPoint(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    frequency: Literal["weekly"]
    source: Literal["alpha_vantage_weekly"]
    retrieved_at: str


class MarketQuote(BaseModel):
    ticker: str
    close: float
    open: float
    high: float
    low: float
    previous_close: float
    as_of: str
    source: Literal["finnhub_quote"]


class MacroSeries(BaseModel):
    code: str
    name: str
    source: Literal["fred", "eia", "treasury", "fomc", "cme"]
    unit: str
    frequency: str
    metadata: dict[str, object] = Field(default_factory=dict)


class MacroObservation(BaseModel):
    series_code: str
    observation_date: str
    value: float
    metadata: dict[str, object] = Field(default_factory=dict)
    retrieved_at: str


class MacroSeriesContext(BaseModel):
    series: MacroSeries
    observations: list[MacroObservation]


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


class EvidenceFreshness(BaseModel):
    status: Literal["current", "stale", "unknown"] = "unknown"
    age_days: int | None = None
    max_age_days: int | None = None
    evaluated_at: str | None = None


class EvidenceItem(BaseModel):
    id: str
    ticker: str
    source_type: Literal["news", "filing", "technical"]
    title: str
    url: str | None = None
    published_at: str | None = None
    excerpt: str
    metadata: dict[str, object] = Field(default_factory=dict)
    freshness: EvidenceFreshness = Field(default_factory=EvidenceFreshness)


class PriceSnapshot(BaseModel):
    as_of: str
    close: float
    source: Literal["daily_market_cache", "demo_fallback"]
    is_stale: bool


class EvidenceSnapshot(BaseModel):
    id: str
    source_type: Literal["news", "filing", "technical"]
    published_at: str | None = None
    freshness: EvidenceFreshness


class MacroContextSnapshot(BaseModel):
    code: str
    name: str
    source: Literal["fred", "eia", "treasury", "fomc", "cme"]
    unit: str
    observation_date: str
    value: float
    retrieved_at: str


class AnalysisSnapshot(BaseModel):
    retrieved_at: str
    price: PriceSnapshot
    retrieved_evidence_count: int
    included_evidence_ids: list[str]
    evidence: list[EvidenceSnapshot] = Field(default_factory=list)
    macro_context: list[MacroContextSnapshot] = Field(default_factory=list)
    excluded_external_evidence_count: int
    missing_current_evidence: list[Literal["news", "filing"]] = Field(default_factory=list)


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
    snapshot: AnalysisSnapshot
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
