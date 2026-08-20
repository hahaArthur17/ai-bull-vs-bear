import json

import httpx
import pytest

from app.services.market_data import (
    AlphaVantageClient,
    FinnhubClient,
    FinnhubQuoteClient,
    MarketDataError,
    QuoteCache,
    SupabasePriceWriter,
    ingest_live_prices,
    ingest_weekly_price_history,
    parse_alpha_vantage_daily,
    parse_alpha_vantage_weekly,
    parse_finnhub_daily,
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


def weekly_payload() -> dict[str, object]:
    return {
        "Meta Data": {"2. Symbol": "AAPL"},
        "Weekly Time Series": {
            "2026-08-14": {
                "1. open": "220.1000",
                "2. high": "224.5000",
                "3. low": "219.0000",
                "4. close": "223.7500",
                "5. volume": "250123456",
            },
            "2026-08-07": {
                "1. open": "218.0000",
                "2. high": "221.0000",
                "3. low": "217.5000",
                "4. close": "220.0000",
                "5. volume": "248123456",
            },
        },
    }


def test_parse_alpha_vantage_weekly_keeps_its_frequency_separate() -> None:
    prices = parse_alpha_vantage_weekly(weekly_payload())

    assert [point["date"] for point in prices] == ["2026-08-07", "2026-08-14"]
    assert prices[-1]["close"] == 223.75


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


def test_alpha_vantage_client_requests_weekly_series() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["function"] == "TIME_SERIES_WEEKLY"
        assert "outputsize" not in request.url.params
        return httpx.Response(200, json=weekly_payload())

    client = AlphaVantageClient("test-key", client=httpx.Client(transport=httpx.MockTransport(handler)))

    assert client.fetch_weekly("aapl")[-1]["date"] == "2026-08-14"


def finnhub_daily_payload() -> dict[str, object]:
    return {
        "c": [220.0, 223.75],
        "h": [221.0, 224.5],
        "l": [217.5, 219.0],
        "o": [218.0, 220.1],
        "s": "ok",
        "t": [1786579200, 1786665600],
        "v": [48_123_456, 50_123_456],
    }


def test_parse_finnhub_daily_normalizes_candle_arrays() -> None:
    prices = parse_finnhub_daily(finnhub_daily_payload())

    assert [point["date"] for point in prices] == ["2026-08-13", "2026-08-14"]
    assert prices[-1]["close"] == 223.75
    assert prices[-1]["volume"] == 50_123_456


def test_finnhub_client_requests_daily_candles() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "finnhub.io"
        assert request.url.path == "/api/v1/stock/candle"
        assert request.url.params["symbol"] == "AAPL"
        assert request.url.params["resolution"] == "D"
        assert request.url.params["token"] == "test-key"
        return httpx.Response(200, json=finnhub_daily_payload())

    client = FinnhubClient("test-key", client=httpx.Client(transport=httpx.MockTransport(handler)))

    prices = client.fetch_daily("aapl")

    assert prices[-1]["date"] == "2026-08-14"


def test_finnhub_no_data_response_is_safe() -> None:
    with pytest.raises(MarketDataError, match="no daily price series"):
        parse_finnhub_daily({"s": "no_data"})


def test_finnhub_quote_client_normalizes_latest_quote() -> None:
    payload = {
        "c": 316.83,
        "d": 6.8,
        "dp": 2.1933,
        "h": 319.2799,
        "l": 309.6,
        "o": 310.14,
        "pc": 310.03,
        "t": 1_787_169_600,
    }
    client = FinnhubQuoteClient(
        "test-key",
        client=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))),
    )

    quote = client.fetch_quote("aapl")

    assert quote == {
        "ticker": "AAPL",
        "close": 316.83,
        "open": 310.14,
        "high": 319.2799,
        "low": 309.6,
        "previous_close": 310.03,
        "as_of": "2026-08-19T20:00:00+00:00",
        "source": "finnhub_quote",
    }


def test_quote_cache_avoids_repeat_provider_calls_until_expiry() -> None:
    class FakeProvider:
        def __init__(self) -> None:
            self.calls = 0

        def fetch_quote(self, ticker: str) -> dict[str, object]:
            self.calls += 1
            return {"ticker": ticker, "close": 316.83}

    now = [0.0]
    provider = FakeProvider()
    cache = QuoteCache(provider, ttl_seconds=60, clock=lambda: now[0])  # type: ignore[arg-type]

    assert cache.get("aapl")["close"] == 316.83
    assert cache.get("AAPL")["close"] == 316.83
    now[0] = 60.0
    cache.get("AAPL")

    assert provider.calls == 2


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


def test_supabase_price_writer_upserts_labelled_weekly_history() -> None:
    written_rows: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        table = request.url.path.rsplit("/", 1)[-1]
        if table == "stocks":
            return httpx.Response(200, json=[{"id": 7}])
        if table == "stock_price_history":
            written_rows.extend(json.loads(request.content))
            return httpx.Response(201)
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    writer = SupabasePriceWriter(
        "https://example.supabase.co",
        "secret-key",
        httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert writer.upsert_weekly_prices("AAPL", parse_alpha_vantage_weekly(weekly_payload())) == 2
    assert written_rows[-1]["frequency"] == "weekly"
    assert written_rows[-1]["source"] == "alpha_vantage_weekly"


def test_weekly_ingestion_has_a_separate_single_ticker_path() -> None:
    class FakeProvider:
        def fetch_weekly(self, ticker: str, limit: int) -> list[dict[str, object]]:
            assert ticker == "AAPL"
            assert limit == 60
            return parse_alpha_vantage_weekly(weekly_payload())

    class FakeWriter:
        def upsert_weekly_prices(self, ticker: str, prices: list[dict[str, object]]) -> int:
            assert ticker == "AAPL"
            return len(prices)

    assert ingest_weekly_price_history(FakeProvider(), FakeWriter()) == {  # type: ignore[arg-type]
        "updated": {"AAPL": 2},
        "failed": [],
    }


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
