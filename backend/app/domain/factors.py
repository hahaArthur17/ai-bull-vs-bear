from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pydantic import Field, JsonValue, field_serializer, field_validator, model_validator

from app.domain.base import AwareDatetime, ImmutableDomainModel


FactorCategory = Literal["technical", "macro", "company", "fundamental", "other"]
FactorDirection = Literal["supportive", "cautionary", "mixed", "neutral", "unknown"]
FactorConfidence = Literal["low", "medium", "high"]
FactorSourceType = Literal[
    "evidence",
    "price",
    "macro",
    "financial_fact",
    "other",
    "quote",
]


class FactorFreshness(ImmutableDomainModel):
    status: Literal["current", "stale", "unknown"] = "unknown"
    age_days: int | None = Field(default=None, ge=0)
    max_age_days: int | None = Field(default=None, ge=0)
    evaluated_at: str | None = Field(default=None, max_length=40)


class AnalysisPricePoint(ImmutableDomainModel):
    date: str = Field(min_length=1, max_length=40)
    open: float = Field(ge=0)
    high: float = Field(ge=0)
    low: float = Field(ge=0)
    close: float = Field(ge=0)
    volume: int = Field(ge=0)
    source: str | None = Field(default=None, max_length=80)
    is_stale: bool | None = None


class AnalysisMarketQuote(ImmutableDomainModel):
    """One accepted provider quote, kept separate from completed closes."""

    ticker: str = Field(min_length=1, max_length=16)
    close: float = Field(gt=0)
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    previous_close: float = Field(gt=0)
    as_of: AwareDatetime
    retrieved_at: AwareDatetime
    source: Literal["finnhub_quote"]
    freshness: FactorFreshness = Field(default_factory=FactorFreshness)
    market_session: Literal["pre_market", "regular", "after_hours", "closed", "unknown"] = "unknown"

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def validate_quote(self) -> AnalysisMarketQuote:
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close):
            raise ValueError("Quote contains an inconsistent OHLC range")
        if self.retrieved_at < self.as_of:
            raise ValueError("Quote retrieval cannot precede its provider timestamp")
        return self


class AnalysisEvidenceItem(ImmutableDomainModel):
    id: str = Field(min_length=1, max_length=240)
    ticker: str = Field(min_length=1, max_length=16)
    source_type: Literal["news", "filing", "technical"]
    title: str = Field(min_length=1, max_length=500)
    url: str | None = Field(default=None, max_length=2048)
    published_at: str | None = Field(default=None, max_length=40)
    excerpt: str = Field(min_length=1, max_length=6000)
    freshness: FactorFreshness = Field(default_factory=FactorFreshness)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        return value.upper()

class AnalysisMacroObservation(ImmutableDomainModel):
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    source: str = Field(min_length=1, max_length=80)
    unit: str = Field(min_length=1, max_length=80)
    observation_date: str = Field(min_length=1, max_length=40)
    value: float
    retrieved_at: str = Field(min_length=1, max_length=40)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class AnalysisFinancialFact(ImmutableDomainModel):
    id: str = Field(min_length=1, max_length=240)
    ticker: str = Field(min_length=1, max_length=16)
    taxonomy: str = Field(min_length=1, max_length=80)
    concept: str = Field(min_length=1, max_length=200)
    label: str = Field(min_length=1, max_length=300)
    value: float
    unit: str = Field(min_length=1, max_length=80)
    period_start: str = Field(min_length=1, max_length=40)
    period_end: str = Field(min_length=1, max_length=40)
    filed_at: str = Field(min_length=1, max_length=40)
    form: str = Field(min_length=1, max_length=40)
    accession_number: str = Field(min_length=1, max_length=80)
    source_url: str = Field(min_length=1, max_length=2048)
    fiscal_year: int | None = None
    fiscal_period: str | None = Field(default=None, max_length=40)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        return value.upper()


class AnalysisContext(ImmutableDomainModel):
    """Immutable inputs shared by factor providers for one analysis snapshot."""

    ticker: str = Field(min_length=1, max_length=16)
    as_of: str = Field(min_length=1, max_length=40)
    captured_at: AwareDatetime | None = None
    latest_completed_close_date: str | None = Field(default=None, max_length=40)
    market_quote: AnalysisMarketQuote | None = None
    prices: tuple[AnalysisPricePoint, ...] = ()
    evidence: tuple[AnalysisEvidenceItem, ...] = ()
    macro_context: tuple[AnalysisMacroObservation, ...] = ()
    financial_facts: tuple[AnalysisFinancialFact, ...] = ()
    question: str | None = Field(default=None, max_length=500)
    allowed_evidence_ids: frozenset[str] = frozenset()
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        return value.upper()

    @field_serializer("allowed_evidence_ids")
    def serialize_allowed_evidence_ids(self, value: frozenset[str]) -> list[str]:
        return sorted(value)

    @model_validator(mode="after")
    def validate_ticker_scoped_inputs(self) -> AnalysisContext:
        if any(item.ticker != self.ticker for item in self.evidence):
            raise ValueError("Evidence ticker does not match the analysis context")
        if any(item.ticker != self.ticker for item in self.financial_facts):
            raise ValueError("Financial-fact ticker does not match the analysis context")
        if self.market_quote is not None and self.market_quote.ticker != self.ticker:
            raise ValueError("Market quote ticker does not match the analysis context")
        if (
            self.latest_completed_close_date is not None
            and self.prices
            and self.latest_completed_close_date != self.prices[-1].date
        ):
            raise ValueError("Latest completed close date must match the final price row")
        evidence_ids = {item.id for item in self.evidence}
        if evidence_ids and not self.allowed_evidence_ids <= evidence_ids:
            raise ValueError("Allowed evidence IDs must exist in the context snapshot")
        return self


class FactorSourceReference(ImmutableDomainModel):
    source_type: FactorSourceType
    source_id: str = Field(min_length=1, max_length=240)
    url: str | None = Field(default=None, max_length=2048)
    as_of: str | None = Field(default=None, max_length=40)


class FactorObservation(ImmutableDomainModel):
    """Versioned, provider-neutral observation used by future Debate turns."""

    id: str = Field(min_length=1, max_length=240)
    ticker: str = Field(min_length=1, max_length=16)
    factor_key: str = Field(
        min_length=3,
        max_length=120,
        pattern=r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$",
    )
    category: FactorCategory
    provider: str = Field(
        min_length=2,
        max_length=80,
        pattern=r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$",
    )
    label: str = Field(min_length=1, max_length=160)
    as_of: str = Field(min_length=1, max_length=40)
    value: JsonValue
    unit: str | None = Field(default=None, max_length=80)
    interpretation: str = Field(min_length=1, max_length=1200)
    direction: FactorDirection = "unknown"
    confidence: FactorConfidence = "low"
    freshness: FactorFreshness = Field(default_factory=FactorFreshness)
    source_refs: tuple[FactorSourceReference, ...] = ()
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    provider_version: str = Field(min_length=1, max_length=40)

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        return value.upper()


class FactorProviderFailure(ImmutableDomainModel):
    provider: str = Field(min_length=2, max_length=80)
    provider_version: str = Field(min_length=1, max_length=40)
    required: bool
    code: Literal["collection_failed", "invalid_output"]
    detail: str = Field(min_length=1, max_length=240)


class FactorSnapshot(ImmutableDomainModel):
    schema_version: Literal["factor-snapshot.v1"] = "factor-snapshot.v1"
    ticker: str = Field(min_length=1, max_length=16)
    as_of: str = Field(min_length=1, max_length=40)
    observations: tuple[FactorObservation, ...] = ()
    provider_failures: tuple[FactorProviderFailure, ...] = ()
    missing_categories: tuple[FactorCategory, ...] = ()

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        return value.upper()


@runtime_checkable
class FactorProvider(Protocol):
    """Additive extension point for one normalized factor source."""

    name: str
    version: str
    required: bool

    def collect(self, context: AnalysisContext) -> list[FactorObservation]:
        ...
