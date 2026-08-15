from __future__ import annotations

from time import sleep
from typing import Callable

import httpx


class MarketDataError(RuntimeError):
    pass


def parse_alpha_vantage_daily(
    payload: dict[str, object],
    limit: int = 100,
) -> list[dict[str, object]]:
    if limit < 1:
        raise ValueError("limit must be at least 1")
    if payload.get("Note") or payload.get("Information"):
        raise MarketDataError("Alpha Vantage request limit reached")
    if payload.get("Error Message"):
        raise MarketDataError("Alpha Vantage rejected the ticker")
    raw_series = payload.get("Time Series (Daily)")
    if not isinstance(raw_series, dict):
        raise MarketDataError("Alpha Vantage returned no daily price series")

    prices: list[dict[str, object]] = []
    try:
        for trading_date, raw_point in raw_series.items():
            if not isinstance(raw_point, dict):
                raise TypeError("Daily price point must be an object")
            prices.append(
                {
                    "date": str(trading_date),
                    "open": float(raw_point["1. open"]),
                    "high": float(raw_point["2. high"]),
                    "low": float(raw_point["3. low"]),
                    "close": float(raw_point["4. close"]),
                    "volume": int(raw_point["5. volume"]),
                }
            )
    except (KeyError, TypeError, ValueError) as exc:
        raise MarketDataError("Alpha Vantage returned an invalid daily price series") from exc
    prices.sort(key=lambda point: str(point["date"]))
    return prices[-limit:]


class AlphaVantageClient:
    def __init__(
        self,
        api_key: str,
        *,
        client: httpx.Client | None = None,
        timeout: float = 10.0,
        max_attempts: int = 3,
        sleeper: Callable[[float], None] = sleep,
    ) -> None:
        if not api_key.strip():
            raise ValueError("ALPHA_VANTAGE_API_KEY is required")
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self.api_key = api_key.strip()
        self.client = client
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.sleeper = sleeper

    def fetch_daily(self, ticker: str, limit: int = 100) -> list[dict[str, object]]:
        requester = self.client.get if self.client is not None else httpx.get
        params = {
            "function": "TIME_SERIES_DAILY",
            "symbol": ticker.upper(),
            "outputsize": "compact",
            "apikey": self.api_key,
        }
        for attempt in range(self.max_attempts):
            try:
                response = requester(
                    "https://www.alphavantage.co/query",
                    params=params,
                    timeout=self.timeout,
                )
            except httpx.RequestError as exc:
                if attempt + 1 == self.max_attempts:
                    raise MarketDataError("Alpha Vantage is unavailable") from exc
                self.sleeper(0.5 * (2**attempt))
                continue
            if response.status_code >= 500:
                if attempt + 1 == self.max_attempts:
                    raise MarketDataError("Alpha Vantage is unavailable")
                self.sleeper(0.5 * (2**attempt))
                continue
            if response.status_code >= 400:
                raise MarketDataError("Alpha Vantage rejected the request")
            try:
                payload = response.json()
            except ValueError as exc:
                raise MarketDataError("Alpha Vantage returned invalid JSON") from exc
            if not isinstance(payload, dict):
                raise MarketDataError("Alpha Vantage returned invalid JSON")
            return parse_alpha_vantage_daily(payload, limit=limit)
        raise MarketDataError("Alpha Vantage request attempts exhausted")
