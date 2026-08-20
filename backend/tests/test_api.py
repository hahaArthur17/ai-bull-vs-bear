import pytest
from fastapi.testclient import TestClient
import pytest

from app.main import app, settings
from app.services.analysis import AnalysisService
from app.services.demo_store import DemoStore


client = TestClient(app)
settings.auth_mode = "demo"


@pytest.fixture(autouse=True)
def demo_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    repository = DemoStore()
    monkeypatch.setattr("app.main.store", repository)
    monkeypatch.setattr("app.main.analysis_service", AnalysisService(repository))


def test_health_and_stock_endpoints() -> None:
    assert client.get("/health").json()["status"] == "ok"
    stocks = client.get("/stocks").json()
    assert {stock["ticker"] for stock in stocks} == {"AAPL", "GOOG", "NVDA", "TSLA"}
    assert client.get("/stocks/AAPL/indicators").status_code == 200
    assert client.get("/stocks/AAPL/quote").json() is None
    assert any(item["source_type"] == "technical" for item in client.get("/stocks/AAPL/evidence").json())
    assert client.get("/stocks/AAPL/price-history").json() == []
    assert client.get("/macro/series").json() == []
    assert client.get("/macro/series/vix").json() == []


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
