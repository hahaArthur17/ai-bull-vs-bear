from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_and_stock_endpoints() -> None:
    assert client.get("/health").json()["status"] == "ok"
    stocks = client.get("/stocks").json()
    assert {stock["ticker"] for stock in stocks} == {"AAPL", "GOOG", "NVDA", "TSLA"}
    assert client.get("/stocks/AAPL/indicators").status_code == 200
    assert any(item["source_type"] == "technical" for item in client.get("/stocks/AAPL/evidence").json())


def test_watchlist_and_analysis_flow() -> None:
    headers = {"X-User-Id": "test-user"}
    response = client.post("/watchlist", json={"ticker": "NVDA"}, headers=headers)
    assert response.status_code == 201
    assert "NVDA" in response.json()["tickers"]
    analysis = client.post("/analysis/NVDA", json={}, headers=headers)
    assert analysis.status_code == 201
    payload = analysis.json()
    assert payload["bull"]["evidence_ids"]
    assert client.get(f"/analysis/{payload['analysis_id']}").status_code == 200
    assert client.get("/analysis").status_code == 200
