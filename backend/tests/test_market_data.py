import httpx
import pytest

from app.services.market_data import (
    AlphaVantageClient,
    MarketDataError,
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
