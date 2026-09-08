from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import BaseModel

from app.domain.factors import (
    AnalysisContext,
    AnalysisEvidenceItem,
    AnalysisFinancialFact,
    AnalysisMacroObservation,
    AnalysisMarketQuote,
    AnalysisPricePoint,
)


def _mapping(value: object) -> Mapping[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="python")
    if isinstance(value, Mapping):
        return value
    raise TypeError("Analysis context inputs must be mappings or Pydantic models")


def build_analysis_context(
    ticker: str,
    *,
    as_of: str,
    prices: Iterable[object] = (),
    evidence: Iterable[object] = (),
    macro_context: Iterable[object] = (),
    financial_facts: Iterable[object] = (),
    question: str | None = None,
    captured_at: object | None = None,
    market_quote: object | None = None,
) -> AnalysisContext:
    """Normalize already-selected current inputs into one immutable snapshot.

    The caller remains responsible for retrieval and freshness selection. This
    factory performs no network or database reads, so the same inputs can be
    used in deterministic tests, queued jobs, and replay fixtures.
    """

    normalized_prices = tuple(
        AnalysisPricePoint.model_validate(_mapping(item)) for item in prices
    )
    normalized_evidence = tuple(
        AnalysisEvidenceItem.model_validate(_mapping(item)) for item in evidence
    )
    normalized_macro = tuple(
        AnalysisMacroObservation.model_validate(_mapping(item))
        for item in macro_context
    )
    normalized_facts = tuple(
        AnalysisFinancialFact.model_validate(_mapping(item))
        for item in financial_facts
    )
    return AnalysisContext(
        ticker=ticker,
        as_of=as_of,
        captured_at=captured_at,
        latest_completed_close_date=normalized_prices[-1].date if normalized_prices else None,
        market_quote=(
            AnalysisMarketQuote.model_validate(_mapping(market_quote))
            if market_quote is not None
            else None
        ),
        prices=normalized_prices,
        evidence=normalized_evidence,
        macro_context=normalized_macro,
        financial_facts=normalized_facts,
        question=question,
        allowed_evidence_ids=frozenset(item.id for item in normalized_evidence),
    )
