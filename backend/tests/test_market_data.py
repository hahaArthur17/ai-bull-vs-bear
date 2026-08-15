import json

import httpx
import pytest

from app.services.market_data import (
    AlphaVantageClient,
    MarketDataError,
    SupabasePriceWriter,
    ingest_live_prices,
    parse_alpha_vantage_daily,
)


def daily_payload() -> dict[str, object]:
    return {
        "Meta Data": {"2. Symbol": "AAPL"},
        "Time Series (Daily)": {
            "2026-08-14": {
                "1. open": "220.1000",
                "2. high": "224.5000",
                "3. low": "219.0000",
                "4. close": "223.7500",
                "5. volume": "50123456",
            },
            "2026-08-13": {
                "1. open": "218.0000",
                "2. high": "221.0000",
                "3. low": "217.5000",
                "4. close": "220.0000",
                "5. volume": "48123456",
            },
        },
    }


def test_parse_alpha_vantage_daily_normalizes_oldest_to_newest() -> None:
    prices = parse_alpha_vantage_daily(daily_payload())

    assert [point["date"] for point in prices] == ["2026-08-13", "2026-08-14"]
    assert prices[-1]["close"] == 223.75
    assert prices[-1]["volume"] == 50_123_456


def test_alpha_vantage_client_retries_temporary_server_failure() -> None:
    attempts = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        assert request.url.params["function"] == "TIME_SERIES_DAILY"
        assert request.url.params["outputsize"] == "compact"
        if attempts == 1:
            return httpx.Response(503)
        return httpx.Response(200, json=daily_payload())

    client = AlphaVantageClient(
        "test-key",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleeper=delays.append,
    )

    prices = client.fetch_daily("aapl")

    assert prices[-1]["date"] == "2026-08-14"
    assert attempts == 2
    assert delays == [0.5]


def test_alpha_vantage_rate_limit_response_is_safe() -> None:
    client = AlphaVantageClient(
        "test-key",
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json={"Note": "limit details"})
            )
        ),
    )

    with pytest.raises(MarketDataError, match="request limit reached"):
        client.fetch_daily("AAPL")


def test_supabase_price_writer_upserts_daily_cache() -> None:
    written_rows: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["apikey"] == "secret-key"
        table = request.url.path.rsplit("/", 1)[-1]
        if table == "stocks":
            return httpx.Response(200, json=[{"id": 7}])
        if table == "stock_prices":
            written_rows.extend(json.loads(request.content))
            return httpx.Response(201)
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    writer = SupabasePriceWriter(
        "https://example.supabase.co",
        "secret-key",
        httpx.Client(transport=httpx.MockTransport(handler)),
    )
    prices = parse_alpha_vantage_daily(daily_payload())

    count = writer.upsert_prices("AAPL", prices)

    assert count == 2
    assert written_rows[0]["stock_id"] == 7
    assert written_rows[-1]["trading_date"] == "2026-08-14"


def test_live_price_ingestion_preserves_other_tickers_after_provider_failure() -> None:
    class FakeProvider:
        def fetch_daily(self, ticker: str) -> list[dict[str, object]]:
            if ticker == "GOOG":
                raise MarketDataError("temporary failure")
            return parse_alpha_vantage_daily(daily_payload(), limit=1)

    class FakeWriter:
        def __init__(self) -> None:
            self.tickers: list[str] = []

        def upsert_prices(self, ticker: str, prices: list[dict[str, object]]) -> int:
            self.tickers.append(ticker)
            return len(prices)

    writer = FakeWriter()

    result = ingest_live_prices(  # type: ignore[arg-type]
        FakeProvider(),  # type: ignore[arg-type]
        writer,  # type: ignore[arg-type]
        tickers=("AAPL", "GOOG", "NVDA"),
    )

    assert result == {
        "updated": {"AAPL": 1, "NVDA": 1},
        "failed": ["GOOG"],
        "skipped": [],
    }
    assert writer.tickers == ["AAPL", "NVDA"]


def test_live_price_ingestion_enforces_provider_call_budget() -> None:
    class FakeProvider:
        def __init__(self) -> None:
            self.tickers: list[str] = []

        def fetch_daily(self, ticker: str) -> list[dict[str, object]]:
            self.tickers.append(ticker)
            return parse_alpha_vantage_daily(daily_payload(), limit=1)

    class FakeWriter:
        def upsert_prices(self, ticker: str, prices: list[dict[str, object]]) -> int:
            return len(prices)

    provider = FakeProvider()
    result = ingest_live_prices(  # type: ignore[arg-type]
        provider,  # type: ignore[arg-type]
        FakeWriter(),  # type: ignore[arg-type]
        tickers=("AAPL", "GOOG", "NVDA", "TSLA"),
        max_provider_calls=2,
    )

    assert provider.tickers == ["AAPL", "GOOG"]
    assert result["skipped"] == ["NVDA", "TSLA"]
