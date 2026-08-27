from app.domain.factors import (
    AnalysisEvidenceItem,
    AnalysisFinancialFact,
    AnalysisMacroObservation,
    AnalysisPricePoint,
)
from app.providers.current_factors import build_current_factor_registry
from app.services.analysis_context import build_analysis_context


def build_current_context():
    return build_analysis_context(
        "AAPL",
        as_of="2026-08-26",
        prices=(
            AnalysisPricePoint(
                date="2026-08-25",
                open=100,
                high=103,
                low=99,
                close=102,
                volume=1_000,
                source="daily_market_cache",
                is_stale=False,
            ),
            AnalysisPricePoint(
                date="2026-08-26",
                open=102,
                high=105,
                low=101,
                close=104,
                volume=1_600,
                source="daily_market_cache",
                is_stale=False,
            ),
        ),
        evidence=(
            AnalysisEvidenceItem(
                id="news-aapl-1",
                ticker="AAPL",
                source_type="news",
                title="Current company announcement",
                url="https://example.com/news",
                published_at="2026-08-25",
                excerpt="A dated announcement with company context.",
                freshness={"status": "current", "age_days": 1, "max_age_days": 7},
            ),
            AnalysisEvidenceItem(
                id="filing-aapl-1",
                ticker="AAPL",
                source_type="filing",
                title="Quarterly risk disclosure",
                url="https://www.sec.gov/example",
                published_at="2026-07-31",
                excerpt="A dated filing excerpt describing material risks.",
                freshness={"status": "current", "age_days": 26, "max_age_days": 120},
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
                ticker="AAPL",
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
    )


def test_current_registry_collects_every_existing_factor_category() -> None:
    registry = build_current_factor_registry()

    snapshot = registry.collect(build_current_context())

    assert registry.provider_names == (
        "technical-indicators",
        "macro-context",
        "news-evidence",
        "filing-evidence",
        "financial-facts",
    )
    assert len(snapshot.observations) == 9
    assert {item.category for item in snapshot.observations} == {
        "technical",
        "macro",
        "company",
        "fundamental",
    }
    assert snapshot.missing_categories == ()
    assert len({item.id for item in snapshot.observations}) == 9


def test_macro_provider_preserves_source_date_and_non_causation_boundary() -> None:
    snapshot = build_current_factor_registry().collect(build_current_context())
    factor = next(item for item in snapshot.observations if item.provider == "macro-context")

    assert factor.factor_key == "macro.vix"
    assert factor.as_of == "2026-08-25"
    assert factor.value == 17.25
    assert factor.direction == "neutral"
    assert "does not establish why the stock moved" in factor.interpretation
    assert factor.source_refs[0].source_type == "macro"


def test_evidence_providers_preserve_freshness_without_inventing_sentiment() -> None:
    snapshot = build_current_factor_registry().collect(build_current_context())
    news = next(item for item in snapshot.observations if item.provider == "news-evidence")
    filing = next(item for item in snapshot.observations if item.provider == "filing-evidence")

    assert news.source_refs[0].source_id == "news-aapl-1"
    assert news.freshness.status == "current"
    assert news.direction == "unknown"
    assert "does not infer sentiment" in news.interpretation
    assert filing.source_refs[0].source_id == "filing-aapl-1"
    assert filing.freshness.max_age_days == 120
    assert filing.direction == "unknown"


def test_financial_fact_provider_preserves_period_unit_and_filing_reference() -> None:
    snapshot = build_current_factor_registry().collect(build_current_context())
    factor = next(item for item in snapshot.observations if item.provider == "financial-facts")

    assert factor.factor_key.startswith("fundamental.us-gaap.revenuefromcontract")
    assert factor.value == 94_000_000_000
    assert factor.unit == "USD"
    assert factor.direction == "unknown"
    assert factor.metadata["period_end"] == "2026-06-30"
    assert factor.source_refs[0].source_type == "financial_fact"


def test_absent_optional_sources_are_visible_as_missing_categories_not_failures() -> None:
    full_context = build_current_context()
    prices_only = build_analysis_context(
        "AAPL",
        as_of=full_context.as_of,
        prices=full_context.prices,
    )

    snapshot = build_current_factor_registry().collect(prices_only)

    assert len(snapshot.observations) == 5
    assert snapshot.missing_categories == ("macro", "company", "fundamental")
    assert snapshot.provider_failures == ()

