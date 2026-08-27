from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator


FactorCategory = Literal["technical", "macro", "company", "fundamental", "other"]
FactorDirection = Literal["supportive", "cautionary", "mixed", "neutral", "unknown"]
FactorConfidence = Literal["low", "medium", "high"]
FactorSourceType = Literal[
    "evidence",
    "price",
    "macro",
    "financial_fact",
    "other",
]


class ImmutableDomainModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        allow_inf_nan=False,
    )


class AnalysisPricePoint(ImmutableDomainModel):
    date: str = Field(min_length=1, max_length=40)
    open: float = Field(ge=0)
    high: float = Field(ge=0)
    low: float = Field(ge=0)
    close: float = Field(ge=0)
    volume: int = Field(ge=0)
    source: str | None = Field(default=None, max_length=80)
    is_stale: bool | None = None


class AnalysisContext(ImmutableDomainModel):
    """Immutable inputs shared by factor providers for one analysis snapshot."""

    ticker: str = Field(min_length=1, max_length=16)
    as_of: str = Field(min_length=1, max_length=40)
    prices: tuple[AnalysisPricePoint, ...] = ()
    question: str | None = Field(default=None, max_length=500)
    allowed_evidence_ids: frozenset[str] = frozenset()
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        return value.upper()


class FactorFreshness(ImmutableDomainModel):
    status: Literal["current", "stale", "unknown"] = "unknown"
    age_days: int | None = Field(default=None, ge=0)
    max_age_days: int | None = Field(default=None, ge=0)
    evaluated_at: str | None = Field(default=None, max_length=40)


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


@runtime_checkable
class FactorProvider(Protocol):
    """Additive extension point for one normalized factor source."""

    name: str
    version: str
    required: bool

    def collect(self, context: AnalysisContext) -> list[FactorObservation]:
        ...

