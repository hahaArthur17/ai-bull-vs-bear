import pytest
from pydantic import ValidationError

from app.domain.factors import (
    AnalysisContext,
    AnalysisPricePoint,
    FactorObservation,
    FactorProvider,
    FactorSourceReference,
)


def build_context() -> AnalysisContext:
    return AnalysisContext(
        ticker="aapl",
        as_of="2026-08-26",
        prices=(
            AnalysisPricePoint(
                date="2026-08-26",
                open=225.0,
                high=229.0,
                low=224.5,
                close=228.0,
                volume=48_000_000,
                source="daily_market_cache",
                is_stale=False,
            ),
        ),
        allowed_evidence_ids=frozenset({"technical-aapl-001"}),
    )


def build_observation() -> FactorObservation:
    return FactorObservation(
        id="technical-indicators:aapl:2026-08-26",
        ticker="aapl",
        factor_key="technical.rsi",
        category="technical",
        provider="technical-indicators",
        label="Relative Strength Index",
        as_of="2026-08-26",
        value=52.4,
        unit="index points",
        interpretation="RSI is descriptive context and does not predict a future price.",
        direction="neutral",
        confidence="medium",
        source_refs=(
            FactorSourceReference(
                source_type="price",
                source_id="daily-market-cache:aapl:2026-08-26",
                as_of="2026-08-26",
            ),
        ),
        metadata={"window": 14},
        provider_version="1",
    )


def test_factor_contract_normalizes_and_serializes_json_safe_values() -> None:
    context = build_context()
    observation = build_observation()

    assert context.ticker == "AAPL"
    assert observation.ticker == "AAPL"
    assert FactorObservation.model_validate_json(observation.model_dump_json()) == observation


def test_factor_contract_is_immutable_and_forbids_provider_specific_fields() -> None:
    observation = build_observation()

    with pytest.raises(ValidationError, match="frozen"):
        observation.confidence = "high"  # type: ignore[misc]

    with pytest.raises(ValidationError, match="extra_forbidden"):
        FactorObservation.model_validate(
            {**observation.model_dump(mode="json"), "sentiment_score": 0.8}
        )


@pytest.mark.parametrize("factor_key", ["RSI", "technical RSI", "technical/rsi"])
def test_factor_contract_rejects_unstable_factor_keys(factor_key: str) -> None:
    with pytest.raises(ValidationError):
        FactorObservation.model_validate(
            {**build_observation().model_dump(mode="json"), "factor_key": factor_key}
        )


def test_factor_provider_is_a_structural_extension_contract() -> None:
    class MockFactorProvider:
        name = "mock-sentiment"
        version = "test-v1"
        required = False

        def collect(self, context: AnalysisContext) -> list[FactorObservation]:
            return [
                build_observation().model_copy(
                    update={
                        "id": f"mock-sentiment:{context.ticker}:{context.as_of}",
                        "ticker": context.ticker,
                        "factor_key": "other.mock-sentiment",
                        "category": "other",
                        "provider": self.name,
                        "provider_version": self.version,
                    }
                )
            ]

    assert isinstance(MockFactorProvider(), FactorProvider)
    assert MockFactorProvider().collect(build_context())[0].provider == "mock-sentiment"

