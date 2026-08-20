from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import Lock
from time import monotonic, sleep
from typing import Callable, Protocol

import httpx

from app.services.supabase_headers import service_headers


DEFAULT_PRICE_TICKERS = ("AAPL",)


class MarketDataError(RuntimeError):
    pass


class PriceCacheError(RuntimeError):
    pass


class DailyPriceProvider(Protocol):
    def fetch_daily(self, ticker: str, limit: int = 100) -> list[dict[str, object]]: ...


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


def parse_finnhub_daily(payload: dict[str, object], limit: int = 100) -> list[dict[str, object]]:
    if limit < 1:
        raise ValueError("limit must be at least 1")
    status = payload.get("s")
    if payload.get("error") or status in ("no_data", "error"):
        raise MarketDataError("Finnhub returned no daily price series")
    try:
        timestamps = payload["t"]
        opens = payload["o"]
        highs = payload["h"]
        lows = payload["l"]
        closes = payload["c"]
        volumes = payload["v"]
        series = (timestamps, opens, highs, lows, closes, volumes)
        if not all(isinstance(values, list) for values in series):
            raise TypeError("Candle fields must be arrays")
        if not timestamps or len({len(values) for values in series}) != 1:
            raise ValueError("Candle fields have incompatible lengths")
        prices = [
            {
                "date": datetime.fromtimestamp(int(timestamp), tz=timezone.utc).date().isoformat(),
                "open": float(open_price),
                "high": float(high),
                "low": float(low),
                "close": float(close),
                "volume": int(volume),
            }
            for timestamp, open_price, high, low, close, volume in zip(
                timestamps, opens, highs, lows, closes, volumes, strict=True
            )
        ]
    except (KeyError, TypeError, ValueError, OverflowError, OSError) as exc:
        raise MarketDataError("Finnhub returned an invalid daily price series") from exc
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


class FinnhubClient:
    def __init__(
        self,
        api_key: str,
        *,
        client: httpx.Client | None = None,
        timeout: float = 10.0,
    ) -> None:
        if not api_key.strip():
            raise ValueError("FINNHUB_API_KEY is required")
        self.api_key = api_key.strip()
        self.client = client
        self.timeout = timeout

    def fetch_daily(self, ticker: str, limit: int = 100) -> list[dict[str, object]]:
        if limit < 1:
            raise ValueError("limit must be at least 1")
        # Two calendar days per desired daily candle covers weekends and market holidays.
        today = datetime.now(timezone.utc).date()
        start = today - timedelta(days=max(30, limit * 2))
        requester = self.client.get if self.client is not None else httpx.get
        try:
            response = requester(
                "https://finnhub.io/api/v1/stock/candle",
                params={
                    "symbol": ticker.upper(),
                    "resolution": "D",
                    "from": int(datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc).timestamp()),
                    "to": int(datetime.combine(today, datetime.max.time(), tzinfo=timezone.utc).timestamp()),
                    "token": self.api_key,
                },
                timeout=self.timeout,
            )
        except httpx.RequestError as exc:
            raise MarketDataError("Finnhub is unavailable") from exc
        if response.status_code >= 500:
            raise MarketDataError("Finnhub is unavailable")
        if response.status_code >= 400:
            raise MarketDataError("Finnhub rejected the request")
        try:
            payload = response.json()
        except ValueError as exc:
            raise MarketDataError("Finnhub returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise MarketDataError("Finnhub returned invalid JSON")
        return parse_finnhub_daily(payload, limit=limit)


class FinnhubQuoteClient:
    """Fetch the latest AAPL quote; the API layer applies a short in-memory cache."""

    def __init__(
        self,
        api_key: str,
        *,
        client: httpx.Client | None = None,
        timeout: float = 10.0,
    ) -> None:
        if not api_key.strip():
            raise ValueError("FINNHUB_API_KEY is required")
        self.api_key = api_key.strip()
        self.client = client
        self.timeout = timeout

    def fetch_quote(self, ticker: str) -> dict[str, object]:
        requester = self.client.get if self.client is not None else httpx.get
        try:
            response = requester(
                "https://finnhub.io/api/v1/quote",
                params={"symbol": ticker.upper(), "token": self.api_key},
                timeout=self.timeout,
            )
        except httpx.RequestError as exc:
            raise MarketDataError("Finnhub is unavailable") from exc
        if response.status_code >= 500:
            raise MarketDataError("Finnhub is unavailable")
        if response.status_code >= 400:
            raise MarketDataError("Finnhub rejected the request")
        try:
            payload = response.json()
            close = float(payload["c"])
            as_of = int(payload["t"])
            if close <= 0 or as_of <= 0:
                raise ValueError("Quote has no market value")
            return {
                "ticker": ticker.upper(),
                "close": close,
                "open": float(payload["o"]),
                "high": float(payload["h"]),
                "low": float(payload["l"]),
                "previous_close": float(payload["pc"]),
                "as_of": datetime.fromtimestamp(as_of, tz=timezone.utc).isoformat(),
                "source": "finnhub_quote",
            }
        except (KeyError, TypeError, ValueError, OverflowError, OSError) as exc:
            raise MarketDataError("Finnhub returned an invalid quote") from exc


class QuoteCache:
    def __init__(
        self,
        provider: FinnhubQuoteClient,
        *,
        ttl_seconds: float = 60.0,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self.provider = provider
        self.ttl_seconds = ttl_seconds
        self.clock = clock
        self._cache: dict[str, tuple[float, dict[str, object]]] = {}
        self._lock = Lock()

    def get(self, ticker: str) -> dict[str, object]:
        normalized = ticker.upper()
        now = self.clock()
        with self._lock:
            cached = self._cache.get(normalized)
            if cached and cached[0] > now:
                return cached[1].copy()
        quote = self.provider.fetch_quote(normalized)
        with self._lock:
            self._cache[normalized] = (self.clock() + self.ttl_seconds, quote.copy())
        return quote


class SupabasePriceWriter:
    def __init__(
        self,
        supabase_url: str,
        secret_key: str,
        client: httpx.Client | None = None,
    ) -> None:
        self.rest_url = f"{supabase_url.rstrip('/')}/rest/v1"
        self.secret_key = secret_key
        self.client = client

    def _request(self, method: str, table: str, **kwargs: object) -> httpx.Response:
        requester = self.client.request if self.client is not None else httpx.request
        headers = service_headers(
            self.secret_key,
            str(kwargs.pop("prefer", "return=representation")),
        )
        try:
            response = requester(
                method,
                f"{self.rest_url}/{table}",
                headers=headers,
                timeout=15.0,
                **kwargs,
            )
        except httpx.RequestError as exc:
            raise PriceCacheError("Supabase price cache is unavailable") from exc
        if response.status_code >= 400:
            raise PriceCacheError(
                f"Supabase price cache request failed with status {response.status_code}"
            )
        return response

    def _stock_id(self, ticker: str) -> int:
        response = self._request(
            "GET",
            "stocks",
            params={"select": "id", "ticker": f"eq.{ticker.upper()}", "limit": "1"},
        )
        rows = response.json()
        if not rows:
            raise PriceCacheError(f"Stock {ticker.upper()} is not seeded in Supabase")
        return int(rows[0]["id"])

    def upsert_prices(self, ticker: str, prices: list[dict[str, object]]) -> int:
        if not prices:
            return 0
        stock_id = self._stock_id(ticker)
        rows = [
            {
                "stock_id": stock_id,
                "trading_date": point["date"],
                "open": point["open"],
                "high": point["high"],
                "low": point["low"],
                "close": point["close"],
                "volume": point["volume"],
            }
            for point in prices
        ]
        self._request(
            "POST",
            "stock_prices",
            params={"on_conflict": "stock_id,trading_date"},
            json=rows,
            prefer="resolution=merge-duplicates,return=minimal",
        )
        return len(rows)


def ingest_live_prices(
    provider: DailyPriceProvider,
    writer: SupabasePriceWriter,
    tickers: tuple[str, ...] = DEFAULT_PRICE_TICKERS,
    max_provider_calls: int = 3,
) -> dict[str, object]:
    if max_provider_calls < 1:
        raise ValueError("max_provider_calls must be at least 1")
    updated: dict[str, int] = {}
    failed: list[str] = []
    selected_tickers = tickers[:max_provider_calls]
    skipped = list(tickers[max_provider_calls:])
    for ticker in selected_tickers:
        try:
            prices = provider.fetch_daily(ticker)
            updated[ticker] = writer.upsert_prices(ticker, prices)
        except (MarketDataError, PriceCacheError):
            failed.append(ticker)
    return {"updated": updated, "failed": failed, "skipped": skipped}
