from __future__ import annotations

import pytest

from app.domain.factors import AnalysisContext, AnalysisPricePoint, FactorObservation
from app.providers.technical_factors import TechnicalFactorProvider
from app.services.factor_registry import FactorRegistry, FactorRegistryError
from app.services.indicators import calculate_indicators


def build_context(*, is_stale: bool = False) -> AnalysisContext:
    prices = (
        AnalysisPricePoint(
            date="2026-08-25",
            open=100,
            high=103,
            low=99,
            close=102,
            volume=1_000,
            source="daily_market_cache",
            is_stale=is_stale,
        ),
        AnalysisPricePoint(
            date="2026-08-26",
            open=102,
            high=105,
            low=101,
            close=104,
            volume=1_600,
            source="daily_market_cache",
            is_stale=is_stale,
        ),
    )
    return AnalysisContext(ticker="AAPL", as_of="2026-08-26", prices=prices)


def test_technical_provider_wraps_the_existing_indicator_calculation() -> None:
    context = build_context()

    observations = TechnicalFactorProvider().collect(context)
    expected = calculate_indicators(
        context.ticker,
        [point.model_dump(mode="python") for point in context.prices],
    )
    by_key = {item.factor_key: item for item in observations}

    assert set(by_key) == {
        "technical.rsi",
        "technical.macd",
        "technical.moving-averages",
        "technical.volatility",
        "technical.volume-spike",
    }
    assert by_key["technical.rsi"].value == expected["rsi"]
    assert by_key["technical.macd"].value == {
        "macd": expected["macd"],
        "signal": expected["macd_signal"],
    }
    assert by_key["technical.volatility"].value == expected["volatility"]
    assert all(item.freshness.status == "current" for item in observations)
    assert all(item.source_refs[0].source_type == "price" for item in observations)


def test_registry_builds_an_immutable_snapshot_and_records_missing_categories() -> None:
    registry = FactorRegistry(
        [TechnicalFactorProvider()],
        expected_categories=("technical", "macro", "company"),
    )

    snapshot = registry.collect(build_context(is_stale=True))

    assert snapshot.schema_version == "factor-snapshot.v1"
    assert snapshot.ticker == "AAPL"
    assert len(snapshot.observations) == 5
    assert snapshot.missing_categories == ("macro", "company")
    assert all(item.freshness.status == "stale" for item in snapshot.observations)
    assert FactorObservation.model_validate(snapshot.observations[0])


def test_optional_provider_failure_is_recorded_without_losing_valid_factors() -> None:
    class FailingOptionalProvider:
        name = "optional-failure"
        version = "test-v1"
        required = False

        def collect(self, context: AnalysisContext) -> list[FactorObservation]:
            raise RuntimeError("provider detail that must not enter the snapshot")

    registry = FactorRegistry([TechnicalFactorProvider(), FailingOptionalProvider()])

    snapshot = registry.collect(build_context())

    assert len(snapshot.observations) == 5
    assert snapshot.provider_failures[0].provider == "optional-failure"
    assert snapshot.provider_failures[0].code == "collection_failed"
    assert "provider detail" not in snapshot.provider_failures[0].detail


def test_required_provider_failure_stops_collection_with_a_safe_error() -> None:
    with pytest.raises(FactorRegistryError, match="technical-indicators"):
        FactorRegistry([TechnicalFactorProvider()]).collect(
            AnalysisContext(ticker="AAPL", as_of="2026-08-26")
        )

