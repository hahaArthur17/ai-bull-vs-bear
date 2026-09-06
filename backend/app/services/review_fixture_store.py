"""Explicit, local-only data for deterministic UI review.

This provider is intentionally separate from DemoStore. Its values are not a
fallback for live data and every price/evidence item carries review-fixture
provenance so a client can label it as simulated.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

from app.services.demo_store import DemoStore
from app.services.macro_data import DEFAULT_MACRO_SERIES


REVIEW_FIXTURE_NOTICE = "SIMULATED DATA · LOCAL UI REVIEW · NOT A MARKET PRICE"
ReviewScenario = Literal["fresh", "stale", "insufficient", "unavailable", "catalog_only"]


def _business_days(start: date, count: int) -> list[date]:
    days: list[date] = []
    current = start
    while len(days) < count:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


def _price_series(
    *, start: date, count: int, base: float, drift: float, stale: bool
) -> list[dict[str, object]]:
    """Generate fixed, valid OHLCV records without time or network inputs."""

    points: list[dict[str, object]] = []
    for index, trading_date in enumerate(_business_days(start, count)):
        wave = ((index * 7) % 9 - 4) * 0.31
        close = round(base + index * drift + wave, 2)
        open_price = round(close - ((index % 3) - 1) * 0.42, 2)
        high = round(max(open_price, close) + 0.86, 2)
        low = round(min(open_price, close) - 0.79, 2)
        points.append(
            {
                "date": trading_date.isoformat(),
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": 16_000_000 + (index % 11) * 510_000,
                "source": "review_fixture",
                "is_stale": stale,
            }
        )
    return points


def _weekly_series(*, base: float, drift: float, stale: bool) -> list[dict[str, object]]:
    points: list[dict[str, object]] = []
    for index in range(60):
        trading_date = date(2024, 1, 5) + timedelta(days=index * 7)
        wave = ((index * 5) % 7 - 3) * 0.52
        close = round(base + index * drift + wave, 2)
        open_price = round(close - 0.65, 2)
        points.append(
            {
                "date": trading_date.isoformat(),
                "open": open_price,
                "high": round(max(open_price, close) + 1.3, 2),
                "low": round(min(open_price, close) - 1.1, 2),
                "close": close,
                "volume": 80_000_000 + (index % 8) * 1_000_000,
                "frequency": "weekly",
                "source": "review_fixture",
                "retrieved_at": "2025-03-01T00:00:00Z",
                "is_stale": stale,
            }
        )
    return points


def _macro_series() -> list[dict[str, object]]:
    return [
        {
            "code": definition.code,
            "name": definition.name,
            "source": definition.source,
            "unit": definition.unit,
            "frequency": definition.frequency,
            "metadata": {
                "provider_series_id": definition.provider_series_id,
                "source": "review_fixture",
                "simulated": True,
            },
        }
        for definition in DEFAULT_MACRO_SERIES
    ]


def _macro_observations(series_code: str, *, index: int, limit: int) -> list[dict[str, object]]:
    # Each series is deterministic but visually distinct. Values are fixed in
    # the past so the fixture never depends on the current clock.
    bases = {
        "sp500": 4_720.0,
        "vix": 18.0,
        "effective_fed_funds_rate": 4.35,
        "treasury_2y_yield": 4.10,
        "treasury_10y_yield": 4.25,
        "treasury_30y_yield": 4.50,
        "wti_spot": 76.0,
    }
    drifts = {
        "sp500": 13.0,
        "vix": -0.08,
        "effective_fed_funds_rate": -0.01,
        "treasury_2y_yield": -0.008,
        "treasury_10y_yield": -0.004,
        "treasury_30y_yield": 0.002,
        "wti_spot": 0.18,
    }
    if series_code not in bases:
        return []
    rows: list[dict[str, object]] = []
    for point_index in range(77):
        observation_date = date(2025, 1, 2) + timedelta(days=point_index)
        value = bases[series_code] + point_index * drifts[series_code]
        value += ((point_index * (index + 3)) % 7 - 3) * 0.04
        rows.append(
            {
                "series_code": series_code,
                "observation_date": observation_date.isoformat(),
                "value": round(value, 4),
                "metadata": {"source": "review_fixture", "simulated": True},
                "retrieved_at": "2025-04-02T00:00:00Z",
            }
        )
    return rows[-max(1, min(limit, len(rows))):]


class ReviewFixtureStore(DemoStore):
    """A stable scenario matrix used only when APP_DATA_MODE=review_fixture."""

    _scenarios: dict[str, ReviewScenario] = {
        "AAPL": "fresh",
        "GOOG": "stale",
        "NVDA": "insufficient",
        "TSLA": "unavailable",
        "MSFT": "catalog_only",
    }

    def __init__(self) -> None:
        super().__init__()
        self._prices = {
            "AAPL": _price_series(start=date(2025, 1, 2), count=55, base=184.0, drift=0.44, stale=False),
            "GOOG": _price_series(start=date(2025, 1, 2), count=55, base=171.0, drift=-0.18, stale=True),
            "NVDA": _price_series(start=date(2025, 1, 2), count=19, base=116.0, drift=0.75, stale=False),
            "TSLA": [],
        }
        self._weekly_prices = {
            "AAPL": _weekly_series(base=164.0, drift=0.72, stale=False),
            "GOOG": _weekly_series(base=180.0, drift=-0.22, stale=True),
            "NVDA": _weekly_series(base=91.0, drift=1.1, stale=False),
            "TSLA": [],
        }
        self._macro_series = _macro_series()
        self._macro_observations = {
            str(series["code"]): _macro_observations(
                str(series["code"]), index=index, limit=90
            )
            for index, series in enumerate(self._macro_series)
        }
        for stock in self._stocks:
            ticker = str(stock["ticker"])
            if ticker in {"NVDA", "TSLA"}:
                stock["coverage_status"] = "price_cached"
        self._evidence = {
            ticker: self._fixture_evidence(ticker)
            for ticker in ("AAPL", "GOOG", "NVDA")
        }

    @staticmethod
    def _fixture_evidence(ticker: str) -> list[dict[str, object]]:
        return [
            {
                "id": f"review-{ticker.lower()}-news-001",
                "ticker": ticker,
                "source_type": "news",
                "title": f"{ticker} review-fixture company context",
                "url": None,
                "published_at": "2025-03-17",
                "excerpt": "Simulated dated company context for local interface review; it is not a real news item.",
                "metadata": {"source": "Review fixture (simulated)"},
                "freshness": {
                    "status": "current",
                    "age_days": 2,
                    "max_age_days": 7,
                    "evaluated_at": "2025-03-19T00:00:00Z",
                },
            },
            {
                "id": f"review-{ticker.lower()}-filing-001",
                "ticker": ticker,
                "source_type": "filing",
                "title": f"{ticker} review-fixture risk context",
                "url": None,
                "published_at": "2025-02-18",
                "excerpt": "Simulated filing-style risk context for local interface review; it is not a real filing.",
                "metadata": {"source": "Review fixture (simulated)"},
                "freshness": {
                    "status": "current",
                    "age_days": 29,
                    "max_age_days": 120,
                    "evaluated_at": "2025-03-19T00:00:00Z",
                },
            },
        ]

    def review_fixture_status(self, ticker: str) -> dict[str, object]:
        return {
            "enabled": True,
            "scenario": self._scenarios.get(ticker.upper()),
            "notice": REVIEW_FIXTURE_NOTICE,
        }

    def get_price_history(self, ticker: str, frequency: str = "weekly") -> list[dict[str, object]]:
        if frequency != "weekly":
            return []
        return [point.copy() for point in self._weekly_prices.get(ticker.upper(), [])]

    def get_macro_series(self) -> list[dict[str, object]]:
        return [series.copy() for series in self._macro_series]

    def get_macro_observations(self, series_code: str, limit: int = 400) -> list[dict[str, object]]:
        rows = self._macro_observations.get(series_code.lower(), [])
        bounded_limit = max(1, min(limit, 1000))
        return [row.copy() for row in rows[-bounded_limit:]]

    def get_evidence(self, ticker: str) -> list[dict[str, object]]:
        normalized = ticker.upper()
        if normalized not in self._prices or not self._prices[normalized]:
            return []
        technical = [
            {
                "id": f"review-{normalized.lower()}-technical-001",
                "ticker": normalized,
                "source_type": "technical",
                "title": "Review-fixture technical signal",
                "url": None,
                "published_at": None,
                "excerpt": "Calculated from simulated OHLCV values for local interface review only.",
                "metadata": {"source": "Review fixture (simulated)"},
            }
        ]
        return technical + [item.copy() for item in self._evidence.get(normalized, [])]
