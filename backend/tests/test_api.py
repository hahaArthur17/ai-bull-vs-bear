import pytest
from fastapi.testclient import TestClient

from app.main import app, settings
from app.schemas import MarketQuote
from app.services.analysis import AnalysisService
from app.services.cache import LocalCacheBackend, ResilientCacheBackend
from app.services.demo_store import DemoStore
from app.services.response_cache import JsonResponseCache
from test_cache_backend import BrokenBackend


client = TestClient(app)
settings.auth_mode = "demo"


@pytest.fixture(autouse=True)
def demo_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    repository = DemoStore()
    monkeypatch.setattr("app.main.store", repository)
    monkeypatch.setattr("app.main.analysis_service", AnalysisService(repository))


def test_health_and_stock_endpoints() -> None:
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/health/cache").json() == {
        "status": "ok",
        "mode": "local",
        "redis_configured": False,
        "redis_reachable": None,
        "degraded_operations": 0,
    }
    stocks = client.get("/stocks").json()
    assert {stock["ticker"] for stock in stocks} == {"AAPL", "GOOG", "NVDA", "TSLA"}
    assert client.get("/stocks/AAPL/indicators").status_code == 200
    assert client.get("/stocks/AAPL/quote").json() is None
    assert any(item["source_type"] == "technical" for item in client.get("/stocks/AAPL/evidence").json())
    assert client.get("/stocks/AAPL/price-history").json() == []
    assert client.get("/macro/series").json() == []
    assert client.get("/macro/series/vix").json() == []


def test_stock_search_survives_redis_outage_and_exposes_degraded_health(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import main

    class CountingStore(DemoStore):
        calls = 0

        def list_stocks(self, query: str | None = None, limit: int = 20):
            self.calls += 1
            return super().list_stocks(query, limit)

    repository = CountingStore()
    backend = ResilientCacheBackend(
        BrokenBackend(),
        fallback=LocalCacheBackend(),
    )
    cache = JsonResponseCache(backend, enabled=True)
    monkeypatch.setattr(main, "store", repository)
    monkeypatch.setattr(main, "cache_backend", backend)
    monkeypatch.setattr(main, "response_cache", cache)

    first = client.get("/stocks", params={"q": "aapl"})
    repeated = client.get("/stocks", params={"q": "aapl"})
    health = client.get("/health/cache", params={"probe": "true"})

    assert first.status_code == repeated.status_code == 200
    assert first.json() == repeated.json()
    assert [stock["ticker"] for stock in repeated.json()] == ["AAPL"]
    assert first.headers["x-cache-status"] == "DEGRADED"
    assert repeated.headers["x-cache-status"] == "DEGRADED"
    assert repository.calls == 1
    assert cache.metrics.snapshot()["DEGRADED"] == 2
    assert health.status_code == 200
    assert health.json() == {
        "status": "degraded",
        "mode": "degraded",
        "redis_configured": True,
        "redis_reachable": False,
        "degraded_operations": 4,
    }


def test_catalog_search_is_limited_and_performs_no_external_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import main

    def fail_external_request(*args: object, **kwargs: object) -> None:
        raise AssertionError("Catalog search must not make an external HTTP request")

    monkeypatch.setattr("httpx.get", fail_external_request)
    repository = DemoStore()
    monkeypatch.setattr(main, "store", repository)
    monkeypatch.setattr(main, "analysis_service", AnalysisService(repository))

    response = client.get("/stocks", params={"q": "microsoft", "limit": 3})

    assert response.status_code == 200
    assert [stock["ticker"] for stock in response.json()] == ["MSFT"]
    assert response.json()[0]["coverage_status"] == "catalog_only"
    assert client.get("/stocks", params={"q": "a", "limit": 26}).status_code == 422


def test_catalog_search_cache_avoids_repeat_repository_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import main

    class CountingStore(DemoStore):
        calls = 0

        def list_stocks(self, query: str | None = None, limit: int = 20):
            self.calls += 1
            return super().list_stocks(query, limit)

    repository = CountingStore()
    cache = JsonResponseCache(
        ResilientCacheBackend(LocalCacheBackend()),
        enabled=True,
    )
    monkeypatch.setattr(main, "store", repository)
    monkeypatch.setattr(main, "response_cache", cache)

    first = client.get("/stocks", params={"q": "apple", "limit": 5})
    second = client.get("/stocks", params={"q": "apple", "limit": 5})

    assert first.headers["x-cache-status"] == "MISS"
    assert second.headers["x-cache-status"] == "HIT"
    assert first.json() == second.json()
    assert repository.calls == 1


def test_stock_bundle_cache_replaces_seven_mobile_reads_with_one_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import main

    class CountingStore(DemoStore):
        price_calls = 0

        def get_prices(self, ticker: str):
            self.price_calls += 1
            return super().get_prices(ticker)

    repository = CountingStore()
    cache = JsonResponseCache(
        ResilientCacheBackend(LocalCacheBackend()),
        enabled=True,
    )
    quotes = iter(
        [
            MarketQuote(
                ticker="AAPL",
                close=210.0,
                open=208.0,
                high=211.0,
                low=207.0,
                previous_close=209.0,
                as_of="2026-08-28T01:00:00Z",
                source="finnhub_quote",
            ),
            MarketQuote(
                ticker="AAPL",
                close=211.0,
                open=208.0,
                high=212.0,
                low=207.0,
                previous_close=209.0,
                as_of="2026-08-28T01:01:00Z",
                source="finnhub_quote",
            ),
        ]
    )
    monkeypatch.setattr(main, "store", repository)
    monkeypatch.setattr(main, "response_cache", cache)
    monkeypatch.setattr(main, "get_quote", lambda _ticker: next(quotes))

    first = client.get("/stocks/AAPL/bundle")
    second = client.get("/stocks/AAPL/bundle")

    assert first.status_code == 200
    assert first.headers["x-cache-status"] == "MISS"
    assert second.headers["x-cache-status"] == "HIT"
    assert repository.price_calls == 1
    assert first.json()["stock"]["ticker"] == "AAPL"
    assert first.json()["quote"]["close"] == 210.0
    assert second.json()["quote"]["close"] == 211.0
    assert first.json()["prices"] == second.json()["prices"]
    assert "indicators" in first.json()
    assert client.get("/stocks/MSFT/bundle").status_code == 409


def test_catalog_only_stock_can_be_saved_to_watchlist() -> None:
    headers = {"X-User-Id": "catalog-watchlist-user"}

    add_response = client.post("/watchlist", json={"ticker": "MSFT"}, headers=headers)

    assert add_response.status_code == 201
    assert add_response.json()["tickers"] == ["MSFT"]
    assert client.delete("/watchlist/MSFT", headers=headers).json()["tickers"] == []


def test_catalog_only_stock_exposes_identity_without_synthetic_coverage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import main

    class FailIfCalledQuoteCache:
        def get(self, ticker: str) -> dict[str, object]:
            raise AssertionError(f"Quote provider must not be called for {ticker}")

    monkeypatch.setattr(main, "quote_cache", FailIfCalledQuoteCache())

    stock = client.get("/stocks/MSFT")
    coverage = client.get("/stocks/MSFT/coverage")

    assert stock.status_code == 200
    assert stock.json()["coverage_status"] == "catalog_only"
    assert coverage.json() == {
        "ticker": "MSFT",
        "coverage_status": "catalog_only",
        "has_price_data": False,
        "has_evidence": False,
        "can_debate": False,
    }
    assert client.get("/stocks/MSFT/prices").json() == []
    assert client.get("/stocks/MSFT/price-history").json() == []
    assert client.get("/stocks/MSFT/quote").json() is None
    assert client.get("/stocks/MSFT/evidence").json() == []
    assert client.get("/stocks/MSFT/indicators").status_code == 409

    debate = client.post(
        "/analysis/MSFT",
        json={"question": None},
        headers={"X-User-Id": "catalog-user"},
    )
    assert debate.status_code == 409
    assert "Debate-ready" in debate.json()["detail"]


def test_unknown_stock_coverage_returns_not_found() -> None:
    assert client.get("/stocks/NOTREAL/coverage").status_code == 404


def test_quote_endpoint_returns_the_cached_quote(monkeypatch: pytest.MonkeyPatch) -> None:
    from app import main

    class FakeQuoteCache:
        def get(self, ticker: str) -> dict[str, object]:
            return {
                "ticker": ticker,
                "close": 316.83,
                "open": 310.14,
                "high": 319.28,
                "low": 309.60,
                "previous_close": 310.03,
                "as_of": "2026-08-19T20:00:00+00:00",
                "source": "finnhub_quote",
            }

    monkeypatch.setattr(main, "quote_cache", FakeQuoteCache())

    response = client.get("/stocks/AAPL/quote")

    assert response.status_code == 200
    assert response.json()["close"] == 316.83


def test_macro_context_endpoint_groups_cached_observations(monkeypatch: pytest.MonkeyPatch) -> None:
    from app import main

    class MacroStore(DemoStore):
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
            assert limit == 30
            return [
                {
                    "series_code": "vix",
                    "observation_date": "2026-08-20",
                    "value": 17.25,
                    "retrieved_at": "2026-08-21T00:00:00+00:00",
                }
            ]

    monkeypatch.setattr(main, "store", MacroStore())

    response = client.get("/macro/context?limit=30")

    assert response.status_code == 200
    assert response.json() == [
        {
            "series": {
                "code": "vix",
                "name": "CBOE Volatility Index",
                "source": "fred",
                "unit": "index points",
                "frequency": "daily",
                "metadata": {},
            },
            "observations": [
                {
                    "series_code": "vix",
                    "observation_date": "2026-08-20",
                    "value": 17.25,
                    "metadata": {},
                    "retrieved_at": "2026-08-21T00:00:00+00:00",
                }
            ],
        }
    ]


def test_watchlist_and_analysis_flow() -> None:
    headers = {"X-User-Id": "test-user"}
    response = client.post("/watchlist", json={"ticker": "NVDA"}, headers=headers)
    assert response.status_code == 201
    assert "NVDA" in response.json()["tickers"]
    analysis = client.post("/analysis/NVDA", json={}, headers=headers)
    assert analysis.status_code == 201
    payload = analysis.json()
    assert payload["bull"]["evidence_ids"]
    assert client.get(f"/analysis/{payload['analysis_id']}", headers=headers).status_code == 200
    assert client.get("/analysis", headers=headers).status_code == 200


def test_supabase_auth_mode_rejects_missing_bearer_token() -> None:
    previous_mode = settings.auth_mode
    settings.auth_mode = "supabase"
    try:
        response = client.get("/watchlist")
    finally:
        settings.auth_mode = previous_mode

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}


def test_unexpected_error_includes_cors_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    class FailingHistoryStore(DemoStore):
        def list_analyses(self, user_id: str, access_token: str | None = None) -> list[object]:
            raise RuntimeError("test-only unexpected failure")

    monkeypatch.setattr("app.main.store", FailingHistoryStore())
    error_client = TestClient(app, raise_server_exceptions=False)
    origin = "http://localhost:8081"

    response = error_client.get("/analysis", headers={"Origin": origin})

    assert response.status_code == 500
    assert response.headers["access-control-allow-origin"] == origin
