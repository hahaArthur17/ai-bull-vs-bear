import pytest
from app.services.analysis import AnalysisService
from app.services.demo_store import DemoStore
from app.services.model_provider import ProviderClaim


@pytest.mark.parametrize("citations", [[], ["invented"], ["real", "invented"]])
def test_bb003_unsupported_provider_claim_is_withheld_without_fabricated_links(citations) -> None:
    claim, rewritten = AnalysisService._claim_from_provider(
        "bull",
        ProviderClaim(
            text="Revenue doubled last quarter.",
            evidence_ids=citations,
            risk_meaning="New results may differ.",
            confidence="high",
        ),
        {"real"},
    )
    assert "Revenue doubled" not in claim.text
    assert claim.evidence_ids == []
    assert claim.confidence == "low" and claim.signal_strength == "weak"
    assert rewritten


def test_bb003_valid_source_membership_is_preserved_without_adding_other_sources() -> None:
    claim, rewritten = AnalysisService._claim_from_provider(
        "bear",
        ProviderClaim(
            text="A conditional interpretation",
            evidence_ids=["real", "real"],
            risk_meaning="Uncertainty remains.",
        ),
        {"real", "unrelated"},
    )
    assert claim.evidence_ids == ["real"]
    assert not rewritten


def test_analysis_contains_bull_bear_evidence_and_trace() -> None:
    service = AnalysisService(DemoStore())
    response = service.create("AAPL")
    assert response.ticker == "AAPL"
    assert response.bull.evidence_ids
    assert response.bear.evidence_ids
    assert {item.id for item in response.evidence} >= set(
        response.bull.evidence_ids + response.bear.evidence_ids
    )
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

    assert [
        (item.code, item.observation_date, item.value) for item in response.snapshot.macro_context
    ] == [("vix", "2000-01-03", 24.5)]
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
        return [item for item in super().get_evidence(ticker) if item["source_type"] == "filing"]


def test_analysis_restores_technical_context_when_vector_search_omits_it() -> None:
    response = AnalysisService(ExternalOnlySearchStore()).create("AAPL")

    assert any(item.source_type == "technical" for item in response.evidence)
    assert {item.id for item in response.evidence} >= set(
        response.bull.evidence_ids + response.bear.evidence_ids
    )


@pytest.mark.parametrize(
    "generation_fails,cleanup_fails", [(False, False), (True, False), (True, True), (False, True)]
)
def test_analysis_releases_provider_connections_without_masking_generation_errors(
    monkeypatch: pytest.MonkeyPatch,
    generation_fails: bool,
    cleanup_fails: bool,
) -> None:
    from app.config import Settings
    from app.schemas import TokenUsage
    from app.services.model_provider import ProviderError, ProviderResult, parse_provider_payload

    closed = []

    class RequestProvider:
        def generate(self, *args: object) -> ProviderResult:
            if generation_fails:
                raise ProviderError("Controlled generation failure")
            return ProviderResult(
                draft=parse_provider_payload("""{
                  "bull": {"text":"A conditional reading", "risk_meaning":"Evidence is limited"},
                  "bear": {"text":"Another conditional reading", "risk_meaning":"New risks may emerge"},
                  "judge": {"summary":"Evidence is mixed", "uncertainty":"You should buy this stock"}
                }"""),
                token_usage=TokenUsage(
                    model_name="test", prompt_tokens=0, completion_tokens=0, total_tokens=0
                ),
            )

        def close(self) -> None:
            closed.append(True)
            if cleanup_fails:
                raise RuntimeError("Controlled cleanup failure")

    monkeypatch.setattr(
        "app.services.analysis.build_analysis_provider", lambda settings: RequestProvider()
    )
    service = AnalysisService(DemoStore(), Settings(analysis_provider="test"))
    if generation_fails:
        with pytest.raises(ProviderError, match="Controlled generation failure"):
            service.create("AAPL")
        assert not service.store.list_analyses("demo-user")
    else:
        result = service.create("AAPL")
        assert "you should buy" not in result.judge.uncertainty.lower()
        assert result.guardrail_status == "rewritten"
    assert closed == [True]
