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
    assert len(response.trace) == 8
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
    assert "Excluded 1 stale or undated external document" in response.trace[3].detail
    assert response.snapshot.retrieved_evidence_count == 3
    assert response.snapshot.included_evidence_ids == ["technical-aapl-001", "current-news"]
    assert response.snapshot.excluded_external_evidence_count == 1
    assert response.snapshot.missing_current_evidence == ["filing"]


def test_analysis_discloses_when_no_current_external_evidence_exists() -> None:
    response = AnalysisService(DemoStore()).create("AAPL")

    assert "No current company news or filing was available" in response.judge.uncertainty
