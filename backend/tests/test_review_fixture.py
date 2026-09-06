from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.services.analysis import AnalysisService
from app.services.cache import LocalCacheBackend, ResilientCacheBackend
from app.services.response_cache import JsonResponseCache
from app.services.review_fixture_store import REVIEW_FIXTURE_NOTICE, ReviewFixtureStore


def test_review_fixture_settings_are_local_only_and_override_dotenv_provider_flags() -> None:
    settings = Settings(
        app_data_mode="review_fixture",
        environment="development",
        auth_mode="supabase",
        persistence_mode="supabase",
        analysis_provider="groq",
        explanation_provider="groq",
        debate_streaming_provider="groq",
        debate_queue_enabled=True,
        redis_enabled=True,
        redis_url="redis://example.test",
    )

    assert settings.is_review_fixture
    assert settings.auth_mode == "demo"
    assert settings.persistence_mode == "demo"
    assert settings.analysis_provider == "demo"
    assert settings.explanation_provider == "deterministic"
    assert settings.debate_streaming_provider == "deterministic"
    assert settings.debate_workflow_v2 is True
    assert settings.debate_queue_enabled is False
    assert settings.redis_enabled is False
    assert settings.redis_url is None


def test_review_fixture_is_rejected_outside_local_or_test_environment() -> None:
    with pytest.raises(ValueError, match="allowed only in local development or test"):
        Settings(app_data_mode="review_fixture", environment="production")

    production = Settings(
        _env_file=None,
        app_data_mode="standard",
        environment="production",
        auth_mode="demo",
        persistence_mode="demo",
    )
    assert production.is_review_fixture is False
    assert production.app_data_mode == "standard"


def test_review_fixture_scenarios_and_macro_series_are_deterministic() -> None:
    first = ReviewFixtureStore()
    second = ReviewFixtureStore()

    assert first.get_prices("AAPL") == second.get_prices("AAPL")
    assert first.review_fixture_status("AAPL") == {
        "enabled": True,
        "scenario": "fresh",
        "notice": REVIEW_FIXTURE_NOTICE,
    }
    assert first.review_fixture_status("GOOG")["scenario"] == "stale"
    assert len(first.get_prices("NVDA")) == 19
    assert first.get_prices("TSLA") == []
    assert first.get_stock("MSFT")["coverage_status"] == "catalog_only"

    series = first.get_macro_series()
    assert len(series) == 7
    assert {item["code"] for item in series} == {
        "sp500",
        "vix",
        "effective_fed_funds_rate",
        "treasury_2y_yield",
        "treasury_10y_yield",
        "treasury_30y_yield",
        "wti_spot",
    }
    assert all(item["metadata"]["simulated"] is True for item in series)
    assert len(first.get_macro_observations("vix", limit=400)) == 77
    assert first.get_macro_observations("vix", limit=7) == second.get_macro_observations("vix", limit=7)


def test_review_fixture_analysis_and_api_never_use_external_clients(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_external(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("review_fixture must not make an outbound request")

    monkeypatch.setattr(httpx, "get", fail_external)
    monkeypatch.setattr(httpx, "request", fail_external)

    from app import main

    fixture = ReviewFixtureStore()
    fixture_settings = Settings(app_data_mode="review_fixture", environment="test")
    monkeypatch.setattr(main, "settings", fixture_settings)
    monkeypatch.setattr(main, "store", fixture)
    monkeypatch.setattr(main, "analysis_service", AnalysisService(fixture, fixture_settings))
    monkeypatch.setattr(
        main,
        "response_cache",
        JsonResponseCache(ResilientCacheBackend(LocalCacheBackend()), enabled=False),
    )
    monkeypatch.setattr(main, "quote_cache", None)
    client = TestClient(main.app)

    bundle = client.get("/stocks/AAPL/bundle")
    assert bundle.status_code == 200
    payload = bundle.json()
    assert payload["quote"] is None
    assert client.get("/health").json()["data_mode"] == "review_fixture"
    assert payload["prices"][-1]["source"] == "review_fixture"
    assert payload["indicators"]["history"]["provenance"] == "review_fixture"
    assert len(payload["macro_context"]) == 7
    assert all(
        context["series"]["metadata"]["simulated"] is True
        for context in payload["macro_context"]
    )

    analysis = AnalysisService(fixture, fixture_settings).create("AAPL")
    assert analysis.snapshot.price.source == "review_fixture"
    assert len(analysis.snapshot.macro_context) == 7
    assert {item.source_type for item in analysis.evidence} == {"technical", "news", "filing"}
    assert all(
        "review fixture" in str(item.metadata.get("source", "")).lower()
        for item in analysis.evidence
    )
    assert all(item.freshness.status == "current" for item in analysis.evidence if item.source_type != "technical")

    debate = client.post(
        "/debates",
        json={"ticker": "AAPL", "opening_side": "bull"},
        headers={"X-User-Id": "fixture-v2-test"},
    )
    assert debate.status_code == 201
    debate_payload = debate.json()
    assert debate_payload["execution_mode"] == "synchronous_preview"
    assert len(debate_payload["messages"]) == 7
    citations = [
        citation
        for message in debate_payload["messages"]
        for citation in message["citations"]
    ]
    assert citations
    assert all(
        citation["evidence_id"].startswith("review-aapl-")
        for citation in citations
    )

    assert client.get("/stocks/MSFT/bundle").status_code == 409
    goog = client.get("/stocks/GOOG/bundle").json()
    assert goog["prices"][-1]["is_stale"] is True
    assert goog["indicators"]["history"]["provenance"] == "review_fixture"
    nvda = client.get("/stocks/NVDA/bundle").json()
    assert nvda["indicators"]["history"]["record_count"] == 19
    assert nvda["indicators"]["history"]["complete_view"] is False
    tsla = client.get("/stocks/TSLA/bundle").json()
    assert tsla["data_mode"] == "review_fixture"
    assert tsla["prices"] == []
    assert client.get("/stocks/TSLA/bundle").status_code == 200
    assert client.get("/stocks/TSLA/indicators").json()["history"]["provenance"] == "unavailable"


def test_review_fixture_store_does_not_construct_or_use_http_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_client_request(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("review_fixture must not use an httpx Client")

    monkeypatch.setattr(httpx.Client, "request", fail_client_request)
    fixture = ReviewFixtureStore()

    assert fixture.get_prices("AAPL")
    assert len(fixture.get_macro_series()) == 7
