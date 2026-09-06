from __future__ import annotations

import json
from pathlib import Path
import random
from datetime import date, timedelta
from threading import Lock


STOCKS: list[dict[str, object]] = [
    {
        "ticker": "AAPL",
        "company_name": "Apple Inc.",
        "exchange": "NASDAQ",
        "sector": "Technology",
        "sec_cik": 320193,
        "country": "US",
        "aliases": ["apple"],
        "is_active": True,
        "coverage_status": "debate_ready",
        "coverage_updated_at": "2026-08-27T00:00:00Z",
    },
    {
        "ticker": "GOOG",
        "company_name": "Alphabet Inc.",
        "exchange": "NASDAQ",
        "sector": "Communication Services",
        "sec_cik": 1652044,
        "country": "US",
        "aliases": ["alphabet", "google"],
        "is_active": True,
        "coverage_status": "debate_ready",
        "coverage_updated_at": "2026-08-27T00:00:00Z",
    },
    {
        "ticker": "NVDA",
        "company_name": "NVIDIA Corporation",
        "exchange": "NASDAQ",
        "sector": "Technology",
        "sec_cik": 1045810,
        "country": "US",
        "aliases": ["nvidia"],
        "is_active": True,
        "coverage_status": "debate_ready",
        "coverage_updated_at": "2026-08-27T00:00:00Z",
    },
    {
        "ticker": "TSLA",
        "company_name": "Tesla, Inc.",
        "exchange": "NASDAQ",
        "sector": "Consumer Discretionary",
        "sec_cik": 1318605,
        "country": "US",
        "aliases": ["tesla"],
        "is_active": True,
        "coverage_status": "debate_ready",
        "coverage_updated_at": "2026-08-27T00:00:00Z",
    },
]


class DemoStore:
    """Small deterministic repository used when Supabase is not configured."""

    def __init__(self, catalog_path: str | Path | None = None) -> None:
        self._lock = Lock()
        self._stocks = self._build_stock_catalog(catalog_path)
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

    @staticmethod
    def _build_stock_catalog(catalog_path: str | Path | None) -> list[dict[str, object]]:
        resolved_path = DemoStore._resolve_catalog_path(catalog_path)
        catalog = {str(stock["ticker"]): stock.copy() for stock in STOCKS}
        if resolved_path is None:
            return sorted(catalog.values(), key=lambda stock: str(stock["ticker"]))

        try:
            snapshot = json.loads(resolved_path.read_text(encoding="utf-8"))
            source = snapshot["source"]
            rows = snapshot["stocks"]
            retrieved_on = str(source["retrieved_on"])
        except (KeyError, OSError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid stock catalog snapshot: {resolved_path}") from exc
        if not isinstance(rows, list):
            raise ValueError(f"Invalid stock catalog rows: {resolved_path}")

        for row in rows:
            if not isinstance(row, dict):
                raise ValueError(f"Invalid stock catalog row: {resolved_path}")
            ticker = str(row.get("ticker", "")).upper()
            if not ticker:
                raise ValueError(f"Stock catalog row is missing a ticker: {resolved_path}")
            if ticker in catalog:
                continue
            catalog[ticker] = {
                "ticker": ticker,
                "company_name": str(row["company_name"]),
                "exchange": str(row["exchange"]),
                "sector": None,
                "sec_cik": int(row["sec_cik"]),
                "country": None,
                "aliases": [],
                "is_active": True,
                "coverage_status": "catalog_only",
                "coverage_updated_at": f"{retrieved_on}T00:00:00Z",
            }
        return sorted(catalog.values(), key=lambda stock: str(stock["ticker"]))

    @staticmethod
    def _resolve_catalog_path(catalog_path: str | Path | None) -> Path | None:
        if catalog_path is not None:
            path = Path(catalog_path)
            if not path.is_file():
                raise ValueError(f"Stock catalog snapshot does not exist: {path}")
            return path
        filename = "sec-company-tickers-exchange-2026-08-27.json"
        candidates = (
            Path(__file__).resolve().parents[3] / "data/catalog" / filename,
            Path(__file__).resolve().parents[2] / "data/catalog" / filename,
        )
        return next((path for path in candidates if path.is_file()), None)

    def list_stocks(
        self,
        query: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, object]]:
        bounded_limit = max(1, min(limit, 25))
        normalized = (query or "").strip().lower()
        if not normalized:
            return [
                stock.copy()
                for stock in self._stocks
                if stock["coverage_status"] == "debate_ready"
            ][:bounded_limit]

        ranked: list[tuple[int, str, dict[str, object]]] = []
        for stock in self._stocks:
            ticker = str(stock["ticker"]).lower()
            company_name = str(stock["company_name"]).lower()
            aliases = [str(alias).lower() for alias in stock.get("aliases", [])]
            rank: int | None = None
            if ticker == normalized:
                rank = 0
            elif ticker.startswith(normalized):
                rank = 1
            elif normalized in aliases:
                rank = 2
            elif len(normalized) >= 2 and company_name.startswith(normalized):
                rank = 3
            elif len(normalized) >= 2 and any(alias.startswith(normalized) for alias in aliases):
                rank = 4
            elif len(normalized) >= 3 and normalized in " ".join(
                [ticker, company_name, *aliases]
            ):
                rank = 5
            if rank is not None:
                ranked.append((rank, ticker, stock))
        ranked.sort(key=lambda match: (match[0], match[1]))
        return [stock.copy() for _, _, stock in ranked[:bounded_limit]]

    def get_stock(self, ticker: str) -> dict[str, object] | None:
        normalized = ticker.upper()
        return next((stock.copy() for stock in self._stocks if stock["ticker"] == normalized), None)

    def get_stock_record_id(
        self,
        ticker: str,
        access_token: str | None = None,
    ) -> int:
        normalized = ticker.upper()
        for record_id, stock in enumerate(self._stocks, start=1):
            if stock["ticker"] == normalized:
                return record_id
        raise ValueError(f"Stock {normalized} is not in the catalog")

    def get_prices(self, ticker: str) -> list[dict[str, object]]:
        return [point.copy() for point in self._prices.get(ticker.upper(), [])]

    def get_price_history(self, ticker: str, frequency: str = "weekly") -> list[dict[str, object]]:
        return []

    def review_fixture_status(self, ticker: str) -> dict[str, object]:
        """Expose a stable disabled shape without conflating demo and review data."""

        return {"enabled": False, "scenario": None, "notice": None}

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
