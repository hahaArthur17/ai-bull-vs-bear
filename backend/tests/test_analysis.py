from app.services.analysis import AnalysisService
from app.services.demo_store import DemoStore


def test_analysis_contains_bull_bear_evidence_and_trace() -> None:
    service = AnalysisService(DemoStore())
    response = service.create("AAPL")
    assert response.ticker == "AAPL"
    assert response.bull.evidence_ids
    assert response.bear.evidence_ids
    assert {item.id for item in response.evidence} >= set(response.bull.evidence_ids + response.bear.evidence_ids)
    assert response.snapshot.price.as_of == response.indicators.as_of
    assert response.snapshot.price.source == "demo_fallback"
    assert response.snapshot.missing_current_evidence == ["news", "filing"]
    assert response.question == (
        f"What available evidence may relate to the AAPL close on {response.snapshot.price.as_of}? "
        "Distinguish contemporaneous context from proven causation."
    )
    assert len(response.trace) == 9
    examined = service.examine(response.bull.id, "evidence_support")
    assert examined.evidence


def test_analysis_history_is_isolated_by_user() -> None:
    service = AnalysisService(DemoStore())
    response = service.create("AAPL", user_id="user-a")

    assert service.get(response.analysis_id, user_id="user-a") == response
    assert service.get(response.analysis_id, user_id="user-b") is None


class FreshnessStore(DemoStore):
    def search_evidence(self, ticker: str, query: str) -> list[dict[str, object]]:
        return [
            {
                "id": "technical-aapl-001",
                "ticker": ticker,
                "source_type": "technical",
                "title": "Verified technical context",
                "excerpt": "Calculated from the cached series.",
            },
            {
                "id": "current-news",
                "ticker": ticker,
                "source_type": "news",
                "title": "Current AAPL context",
                "excerpt": "Published during the current analysis window.",
                "freshness": {"status": "current", "age_days": 1, "max_age_days": 7},
            },
            {
                "id": "stale-news",
                "ticker": ticker,
                "source_type": "news",
                "title": "Old AAPL context",
                "excerpt": "This should not be used for a current-price Debate.",
                "freshness": {"status": "stale", "age_days": 30, "max_age_days": 7},
            },
        ]


def test_analysis_excludes_stale_external_evidence() -> None:
    response = AnalysisService(FreshnessStore()).create("AAPL")

    assert {item.id for item in response.evidence} == {"technical-aapl-001", "current-news"}
    evidence_trace = next(step for step in response.trace if step.step == "evidence_aggregator")
    assert "Excluded 1 stale or undated external document" in evidence_trace.detail
    assert response.snapshot.retrieved_evidence_count == 3
    assert response.snapshot.included_evidence_ids == ["technical-aapl-001", "current-news"]
    assert [(item.id, item.freshness.status) for item in response.snapshot.evidence] == [
        ("technical-aapl-001", "unknown"),
        ("current-news", "current"),
    ]
    assert response.snapshot.excluded_external_evidence_count == 1
    assert response.snapshot.missing_current_evidence == ["filing"]


def test_analysis_discloses_when_no_current_external_evidence_exists() -> None:
    response = AnalysisService(DemoStore()).create("AAPL")

    assert "No current company news was available" in response.judge.uncertainty
    assert response.judge.evidence_strength == "weak"
    assert response.bull.signal_strength == "weak"
    assert response.bull.confidence == "low"


class FilingOnlyStore(DemoStore):
    def get_evidence(self, ticker: str) -> list[dict[str, object]]:
        return [
            {
                "id": "technical-aapl-001",
                "ticker": ticker,
                "source_type": "technical",
                "title": "Verified technical context",
                "excerpt": "Calculated from the cached series.",
            },
            {
                "id": "current-filing",
                "ticker": ticker,
                "source_type": "filing",
                "title": "Current quarterly filing",
                "published_at": "2026-07-31T10:00:00+00:00",
                "excerpt": "A filing dated within the filing freshness window.",
                "freshness": {"status": "current", "age_days": 21, "max_age_days": 120},
            },
        ]

    def search_evidence(self, ticker: str, query: str) -> list[dict[str, object]]:
        return self.get_evidence(ticker)


def test_analysis_downgrades_filing_only_context_without_current_news() -> None:
    response = AnalysisService(FilingOnlyStore()).create("AAPL")

    assert response.snapshot.missing_current_evidence == ["news"]
    assert response.judge.evidence_strength == "weak"
    assert response.bear.confidence == "low"
    assert "any filing is long-horizon context" in response.judge.uncertainty


class MacroSnapshotStore(DemoStore):
    def get_macro_series(self) -> list[dict[str, object]]:
        return [
            {
                "code": "vix",
                "name": "CBOE Volatility Index",
                "source": "fred",
                "unit": "index points",
                "frequency": "daily",
            }
        ]

    def get_macro_observations(self, series_code: str, limit: int = 400) -> list[dict[str, object]]:
        assert series_code == "vix"
        assert limit == 10
        return [
            {
                "series_code": "vix",
                "observation_date": "2000-01-03",
                "value": 24.5,
                "retrieved_at": "2026-08-21T00:00:00+00:00",
            },
            {
                "series_code": "vix",
                "observation_date": "9999-12-31",
                "value": 99.0,
                "retrieved_at": "2026-08-21T00:00:00+00:00",
            },
        ]


def test_analysis_freezes_macro_context_known_at_the_close() -> None:
    response = AnalysisService(MacroSnapshotStore()).create("AAPL")

    assert [(item.code, item.observation_date, item.value) for item in response.snapshot.macro_context] == [
        ("vix", "2000-01-03", 24.5)
    ]
    assert "CBOE Volatility Index (2000-01-03)" in response.bull.text
    assert "does not establish why this stock moved" in response.bull.text
    assert "CBOE Volatility Index (2000-01-03)" in response.bear.text
    macro_trace = next(step for step in response.trace if step.step == "macro_context_agent")
    assert "dated on or before the close" in macro_trace.detail


class SourceCoverageStore(DemoStore):
    def search_evidence(self, ticker: str, query: str) -> list[dict[str, object]]:
        return [
            {
                "id": "technical-aapl-001",
                "ticker": ticker,
                "source_type": "technical",
                "title": "Verified technical context",
                "excerpt": "Calculated from the cached series.",
            }
        ]

    def get_evidence(self, ticker: str) -> list[dict[str, object]]:
        return SourceCoverageStore.search_evidence(self, ticker, "") + [
            {
                "id": "current-news",
                "ticker": ticker,
                "source_type": "news",
                "title": "Current company announcement",
                "published_at": "2026-08-20T10:00:00+00:00",
                "excerpt": "An announcement dated within the news freshness window.",
                "freshness": {"status": "current", "age_days": 1, "max_age_days": 7},
            },
            {
                "id": "current-filing",
                "ticker": ticker,
                "source_type": "filing",
                "title": "Current quarterly filing",
                "published_at": "2026-07-31T10:00:00+00:00",
                "excerpt": "A filing dated within the filing freshness window.",
                "freshness": {"status": "current", "age_days": 21, "max_age_days": 120},
            },
        ]


def test_analysis_supplements_relevant_retrieval_with_current_source_coverage() -> None:
    response = AnalysisService(SourceCoverageStore()).create("AAPL")

    assert {item.id for item in response.evidence} == {
        "technical-aapl-001",
        "current-news",
        "current-filing",
    }
    assert response.snapshot.retrieved_evidence_count == 3
    assert response.snapshot.missing_current_evidence == []
    evidence_trace = next(step for step in response.trace if step.step == "evidence_aggregator")
    assert "Added 2 source-coverage document" in evidence_trace.detail


class ExternalOnlySearchStore(SourceCoverageStore):
    def search_evidence(self, ticker: str, query: str) -> list[dict[str, object]]:
        return [
            item
            for item in super().get_evidence(ticker)
            if item["source_type"] == "filing"
        ]


def test_analysis_restores_technical_context_when_vector_search_omits_it() -> None:
    response = AnalysisService(ExternalOnlySearchStore()).create("AAPL")

    assert any(item.source_type == "technical" for item in response.evidence)
    assert {item.id for item in response.evidence} >= set(
        response.bull.evidence_ids + response.bear.evidence_ids
    )
