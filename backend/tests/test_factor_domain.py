import pytest
from pydantic import ValidationError

from app.domain.factors import (
    AnalysisContext,
    AnalysisEvidenceItem,
    AnalysisFinancialFact,
    AnalysisMacroObservation,
    AnalysisPricePoint,
    FactorObservation,
    FactorProvider,
    FactorSourceReference,
)
from app.services.analysis_context import build_analysis_context


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


def test_analysis_context_normalizes_existing_typed_source_inputs() -> None:
    context = build_analysis_context(
        "aapl",
        as_of="2026-08-26",
        prices=build_context().prices,
        evidence=(
            AnalysisEvidenceItem(
                id="news-aapl-1",
                ticker="aapl",
                source_type="news",
                title="Company update",
                published_at="2026-08-25",
                excerpt="A dated company update used only as context.",
                freshness={"status": "current", "age_days": 1, "max_age_days": 7},
            ),
        ),
        macro_context=(
            AnalysisMacroObservation(
                code="vix",
                name="CBOE Volatility Index",
                source="fred",
                unit="index points",
                observation_date="2026-08-25",
                value=17.25,
                retrieved_at="2026-08-26T00:00:00+00:00",
            ),
        ),
        financial_facts=(
            AnalysisFinancialFact(
                id="fact-aapl-revenue-2026-q2",
                ticker="aapl",
                taxonomy="us-gaap",
                concept="RevenueFromContractWithCustomerExcludingAssessedTax",
                label="Revenue",
                value=94_000_000_000,
                unit="USD",
                period_start="2026-04-01",
                period_end="2026-06-30",
                filed_at="2026-07-31",
                form="10-Q",
                accession_number="0000320193-26-000001",
                source_url="https://www.sec.gov/example",
                fiscal_year=2026,
                fiscal_period="Q2",
            ),
        ),
        question="What context is available?",
    )

    assert context.ticker == "AAPL"
    assert context.allowed_evidence_ids == frozenset({"news-aapl-1"})
    assert context.evidence[0].freshness.status == "current"
    assert context.macro_context[0].value == 17.25
    assert context.financial_facts[0].unit == "USD"
    assert AnalysisContext.model_validate_json(context.model_dump_json()) == context


def test_analysis_context_rejects_cross_ticker_inputs() -> None:
    with pytest.raises(ValidationError, match="Evidence ticker"):
        AnalysisContext(
            ticker="AAPL",
            as_of="2026-08-26",
            evidence=(
                AnalysisEvidenceItem(
                    id="news-goog-1",
                    ticker="GOOG",
                    source_type="news",
                    title="Wrong company",
                    excerpt="This item must not enter an AAPL snapshot.",
                ),
            ),
        )


def test_analysis_context_serializes_allowed_evidence_ids_canonically() -> None:
    context = AnalysisContext(
        ticker="AAPL",
        as_of="2026-08-27",
        allowed_evidence_ids=frozenset({"evidence-z", "evidence-a"}),
    )

    assert context.model_dump(mode="json")["allowed_evidence_ids"] == [
        "evidence-a",
        "evidence-z",
    ]
