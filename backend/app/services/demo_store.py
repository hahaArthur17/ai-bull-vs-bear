from __future__ import annotations

import random
from datetime import date, timedelta
from threading import Lock


STOCKS: list[dict[str, str]] = [
    {"ticker": "AAPL", "company_name": "Apple Inc.", "exchange": "NASDAQ", "sector": "Technology"},
    {"ticker": "GOOG", "company_name": "Alphabet Inc.", "exchange": "NASDAQ", "sector": "Communication Services"},
    {"ticker": "NVDA", "company_name": "NVIDIA Corporation", "exchange": "NASDAQ", "sector": "Technology"},
    {"ticker": "TSLA", "company_name": "Tesla, Inc.", "exchange": "NASDAQ", "sector": "Consumer Discretionary"},
]


class DemoStore:
    """Small deterministic repository used when Supabase is not configured."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._prices = {stock["ticker"]: self._build_prices(stock["ticker"]) for stock in STOCKS}
        self._evidence = self._build_evidence()
        self._watchlists: dict[str, set[str]] = {"demo-user": {"AAPL"}}
        self._analyses: dict[str, dict[str, object]] = {}

    @staticmethod
    def _build_prices(ticker: str) -> list[dict[str, object]]:
        bases = {"AAPL": 192.0, "GOOG": 176.0, "NVDA": 118.0, "TSLA": 242.0}
        drifts = {"AAPL": 0.45, "GOOG": 0.2, "NVDA": 1.1, "TSLA": -0.35}
        rng = random.Random(sum(ord(char) for char in ticker))
        price = bases[ticker]
        points: list[dict[str, object]] = []
        current = date(2026, 1, 2)
        for index in range(55):
            noise = rng.uniform(-2.1, 2.1)
            open_price = max(1.0, price + rng.uniform(-1.2, 1.2))
            close = max(1.0, price + drifts[ticker] + noise)
            high = max(open_price, close) + rng.uniform(0.3, 2.0)
            low = min(open_price, close) - rng.uniform(0.3, 2.0)
            volume = int(18_000_000 + rng.uniform(-4_000_000, 7_000_000))
            if index in {18, 41}:
                volume *= 2
            points.append(
                {
                    "date": current.isoformat(),
                    "open": round(open_price, 2),
                    "high": round(high, 2),
                    "low": round(max(0.1, low), 2),
                    "close": round(close, 2),
                    "volume": volume,
                }
            )
            price = close
            current += timedelta(days=1)
        return points

    @staticmethod
    def _build_evidence() -> dict[str, list[dict[str, object]]]:
        return {
            "AAPL": [
                {
                    "id": "NEWS-003",
                    "ticker": "AAPL",
                    "source_type": "news",
                    "title": "Services revenue beats the prior-year quarter",
                    "url": "https://example.com/demo/news/aapl-services",
                    "published_at": "2026-01-18",
                    "excerpt": "A cached demo headline and summary provide positive business context for the analysis.",
                    "metadata": {"source": "demo RSS feed"},
                },
                {
                    "id": "10-K-RISK",
                    "ticker": "AAPL",
                    "source_type": "filing",
                    "title": "Competition and supply constraints remain material risks",
                    "url": "https://example.com/demo/sec/aapl-risk-factors",
                    "published_at": "2026-01-12",
                    "excerpt": "Selected demo risk-factor text highlights competition, supply constraints, and execution uncertainty.",
                    "metadata": {"source": "SEC demo excerpt"},
                },
            ],
            "GOOG": [
                {
                    "id": "NEWS-GOOG-001",
                    "ticker": "GOOG",
                    "source_type": "news",
                    "title": "Cloud growth remains a key discussion point",
                    "url": "https://example.com/demo/news/goog-cloud",
                    "published_at": "2026-01-15",
                    "excerpt": "The demo corpus contains a mixed update on cloud growth and advertising demand.",
                    "metadata": {"source": "demo RSS feed"},
                },
                {
                    "id": "10-K-GOOG-001",
                    "ticker": "GOOG",
                    "source_type": "filing",
                    "title": "Regulatory and infrastructure investment risks",
                    "url": "https://example.com/demo/sec/goog-risk-factors",
                    "published_at": "2026-01-10",
                    "excerpt": "The selected filing excerpt describes regulatory scrutiny and infrastructure cost uncertainty.",
                    "metadata": {"source": "SEC demo excerpt"},
                },
            ],
            "NVDA": [
                {
                    "id": "NEWS-NVDA-001",
                    "ticker": "NVDA",
                    "source_type": "news",
                    "title": "AI infrastructure demand remains a major theme",
                    "url": "https://example.com/demo/news/nvda-demand",
                    "published_at": "2026-01-22",
                    "excerpt": "The demo evidence points to strong demand discussion while noting supply and concentration risks.",
                    "metadata": {"source": "demo RSS feed"},
                },
                {
                    "id": "10-K-NVDA-001",
                    "ticker": "NVDA",
                    "source_type": "filing",
                    "title": "Customer concentration and supply chain uncertainty",
                    "url": "https://example.com/demo/sec/nvda-risk-factors",
                    "published_at": "2026-01-09",
                    "excerpt": "The selected filing excerpt covers customer concentration, supply chain, and product-cycle risks.",
                    "metadata": {"source": "SEC demo excerpt"},
                },
            ],
            "TSLA": [
                {
                    "id": "NEWS-TSLA-001",
                    "ticker": "TSLA",
                    "source_type": "news",
                    "title": "Delivery expectations remain closely watched",
                    "url": "https://example.com/demo/news/tsla-deliveries",
                    "published_at": "2026-01-20",
                    "excerpt": "The demo news context includes delivery expectations and changing competitive dynamics.",
                    "metadata": {"source": "demo RSS feed"},
                },
                {
                    "id": "10-K-TSLA-001",
                    "ticker": "TSLA",
                    "source_type": "filing",
                    "title": "Competition, pricing, and execution risks",
                    "url": "https://example.com/demo/sec/tsla-risk-factors",
                    "published_at": "2026-01-08",
                    "excerpt": "The selected filing excerpt highlights competition, pricing pressure, and execution uncertainty.",
                    "metadata": {"source": "SEC demo excerpt"},
                },
            ],
        }

    def list_stocks(self, query: str | None = None) -> list[dict[str, str]]:
        if not query:
            return [stock.copy() for stock in STOCKS]
        normalized = query.strip().lower()
        return [
            stock.copy()
            for stock in STOCKS
            if normalized in stock["ticker"].lower() or normalized in stock["company_name"].lower()
        ]

    def get_stock(self, ticker: str) -> dict[str, str] | None:
        normalized = ticker.upper()
        return next((stock.copy() for stock in STOCKS if stock["ticker"] == normalized), None)

    def get_prices(self, ticker: str) -> list[dict[str, object]]:
        return [point.copy() for point in self._prices.get(ticker.upper(), [])]

    def get_macro_series(self) -> list[dict[str, object]]:
        return []

    def get_macro_observations(self, series_code: str, limit: int = 400) -> list[dict[str, object]]:
        return []

    def get_evidence(self, ticker: str) -> list[dict[str, object]]:
        normalized = ticker.upper()
        technical = [
            {
                "id": f"technical-{normalized.lower()}-001",
                "ticker": normalized,
                "source_type": "technical",
                "title": "Price and moving-average signal",
                "url": None,
                "published_at": None,
                "excerpt": "Calculated from the cached OHLCV series; this signal is descriptive and not a prediction.",
                "metadata": {"source": "Technical Agent"},
            },
            {
                "id": f"technical-{normalized.lower()}-004",
                "ticker": normalized,
                "source_type": "technical",
                "title": "Volatility and volume context",
                "url": None,
                "published_at": None,
                "excerpt": "Calculated volatility and volume context add uncertainty to the interpretation.",
                "metadata": {"source": "Technical Agent"},
            },
        ]
        return technical + [item.copy() for item in self._evidence.get(normalized, [])]

    def get_watchlist(self, user_id: str, access_token: str | None = None) -> list[str]:
        with self._lock:
            return sorted(self._watchlists.setdefault(user_id, set()))

    def add_watchlist(
        self,
        user_id: str,
        ticker: str,
        access_token: str | None = None,
    ) -> list[str]:
        with self._lock:
            self._watchlists.setdefault(user_id, set()).add(ticker.upper())
            return sorted(self._watchlists[user_id])

    def remove_watchlist(
        self,
        user_id: str,
        ticker: str,
        access_token: str | None = None,
    ) -> list[str]:
        with self._lock:
            self._watchlists.setdefault(user_id, set()).discard(ticker.upper())
            return sorted(self._watchlists[user_id])

    def save_analysis(
        self,
        user_id: str,
        analysis_id: str,
        response: object,
        access_token: str | None = None,
    ) -> None:
        with self._lock:
            self._analyses.setdefault(user_id, {})[analysis_id] = response

    def get_analysis(
        self,
        user_id: str,
        analysis_id: str,
        access_token: str | None = None,
    ) -> object | None:
        return self._analyses.get(user_id, {}).get(analysis_id)

    def list_analyses(self, user_id: str, access_token: str | None = None) -> list[object]:
        return list(self._analyses.get(user_id, {}).values())
