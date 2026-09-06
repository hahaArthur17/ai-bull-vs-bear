from __future__ import annotations

from typing import Literal, TypeAlias

from pydantic import BaseModel, Field


CoverageStatus: TypeAlias = Literal[
    "catalog_only",
    "price_cached",
    "evidence_ready",
    "debate_ready",
]


class Stock(BaseModel):
    ticker: str
    company_name: str
    exchange: str
    sector: str | None = None
    sec_cik: int | None = None
    country: str | None = None
    aliases: list[str] = Field(default_factory=list)
    is_active: bool = True
    coverage_status: CoverageStatus = "catalog_only"
    coverage_updated_at: str | None = None


class StockCoverage(BaseModel):
    ticker: str
    coverage_status: CoverageStatus
    has_price_data: bool
    has_evidence: bool
    can_debate: bool


class PricePoint(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    source: Literal["daily_market_cache", "demo_fallback", "review_fixture"] = "demo_fallback"
    is_stale: bool = True


class PriceHistoryPoint(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    frequency: Literal["weekly"]
    source: Literal["alpha_vantage_weekly", "review_fixture"]
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


class IndicatorAvailability(BaseModel):
    price_line: bool = False
    price_change: bool = False
    moving_average_20: bool = False
    moving_average_50: bool = False
    rsi: bool = False
    macd: bool = False
    macd_signal: bool = False
    volume: bool = False
    volatility: bool = False


class TechnicalHistoryStatus(BaseModel):
    provenance: Literal["live_fresh", "live_stale", "review_fixture", "unavailable"] = "unavailable"
    record_count: int = 0
    completed_close_count: int = 0
    required_for_complete: int = 50
    is_ordered: bool = False
    has_unique_dates: bool = False
    has_valid_closes: bool = False
    has_valid_ohlcv: bool = False
    has_only_completed_closes: bool = False
    is_valid: bool = False
    complete_view: bool = False
    explanation: str = "Daily history has not been assessed."


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
    availability: IndicatorAvailability = Field(default_factory=IndicatorAvailability)
    history: TechnicalHistoryStatus = Field(default_factory=TechnicalHistoryStatus)


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


class StockBundle(BaseModel):
    stock: Stock
    data_mode: Literal["standard", "review_fixture"] = "standard"
    prices: list[PricePoint]
    weekly_history: list[PriceHistoryPoint]
    quote: MarketQuote | None
    indicators: TechnicalIndicators
    evidence: list[EvidenceItem]
    macro_context: list[MacroSeriesContext]


class PriceSnapshot(BaseModel):
    as_of: str
    close: float
    source: Literal["daily_market_cache", "demo_fallback", "review_fixture"]
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
