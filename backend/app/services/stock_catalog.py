from __future__ import annotations

from datetime import date
import re


SEC_CATALOG_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
CATALOG_SCHEMA_VERSION = 1
CATALOG_TRANSFORMATION_VERSION = "sec-exchange-v1"
MAX_CATALOG_ROWS = 10_000

_EXPECTED_FIELDS = ["cik", "name", "ticker", "exchange"]
_EXCHANGE_NAMES = {
    "CBOE": "CBOE",
    "Nasdaq": "NASDAQ",
    "NYSE": "NYSE",
}
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_TICKER_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9.-]{0,9}$")


class CatalogSnapshotError(ValueError):
    """Raised when an SEC catalog input cannot produce a safe snapshot."""


def build_catalog_snapshot(
    payload: object,
    *,
    retrieved_on: str,
    source_sha256: str,
    max_rows: int = MAX_CATALOG_ROWS,
) -> dict[str, object]:
    """Normalize one downloaded SEC ticker/exchange file deterministically.

    The function has no network or database side effects. Runtime stock search
    reads its generated artifact instead of calling the SEC.
    """

    _validate_snapshot_metadata(retrieved_on, source_sha256, max_rows)
    if not isinstance(payload, dict):
        raise CatalogSnapshotError("SEC catalog payload must be a JSON object")
    if payload.get("fields") != _EXPECTED_FIELDS:
        raise CatalogSnapshotError("SEC catalog fields do not match the expected schema")
    rows = payload.get("data")
    if not isinstance(rows, list):
        raise CatalogSnapshotError("SEC catalog data must be a list")

    stocks: list[dict[str, object]] = []
    tickers: set[str] = set()
    excluded_rows = 0
    for index, row in enumerate(rows):
        if not isinstance(row, list) or len(row) != len(_EXPECTED_FIELDS):
            raise CatalogSnapshotError(f"SEC catalog row {index} has an invalid shape")
        cik, company_name, ticker, exchange = row
        if exchange not in _EXCHANGE_NAMES:
            excluded_rows += 1
            continue
        if isinstance(cik, bool) or not isinstance(cik, int) or cik <= 0:
            raise CatalogSnapshotError(f"SEC catalog row {index} has an invalid CIK")
        if not isinstance(company_name, str) or not company_name.strip():
            raise CatalogSnapshotError(f"SEC catalog row {index} has an invalid company name")
        if not isinstance(ticker, str):
            raise CatalogSnapshotError(f"SEC catalog row {index} has an invalid ticker")

        normalized_ticker = ticker.strip().upper()
        if not _TICKER_PATTERN.fullmatch(normalized_ticker):
            raise CatalogSnapshotError(
                f"SEC catalog row {index} has unsupported ticker {normalized_ticker!r}"
            )
        if normalized_ticker in tickers:
            raise CatalogSnapshotError(f"Duplicate normalized ticker {normalized_ticker}")
        tickers.add(normalized_ticker)
        stocks.append(
            {
                "sec_cik": cik,
                "ticker": normalized_ticker,
                "company_name": " ".join(company_name.split()),
                "exchange": _EXCHANGE_NAMES[exchange],
            }
        )
        if len(stocks) > max_rows:
            raise CatalogSnapshotError(
                f"Normalized catalog exceeds the {max_rows} row safety limit"
            )

    if not stocks:
        raise CatalogSnapshotError("SEC catalog produced no supported exchange rows")
    stocks.sort(key=lambda stock: str(stock["ticker"]))
    return {
        "schema_version": CATALOG_SCHEMA_VERSION,
        "source": {
            "url": SEC_CATALOG_URL,
            "retrieved_on": retrieved_on,
            "sha256": source_sha256,
            "raw_row_count": len(rows),
        },
        "transformation": {
            "version": CATALOG_TRANSFORMATION_VERSION,
            "allowed_source_exchanges": sorted(_EXCHANGE_NAMES),
            "max_rows": max_rows,
            "excluded_row_count": excluded_rows,
        },
        "stocks": stocks,
    }


def _validate_snapshot_metadata(
    retrieved_on: str,
    source_sha256: str,
    max_rows: int,
) -> None:
    try:
        date.fromisoformat(retrieved_on)
    except (TypeError, ValueError) as exc:
        raise CatalogSnapshotError("retrieved_on must be an ISO date") from exc
    if not isinstance(source_sha256, str) or not _SHA256_PATTERN.fullmatch(source_sha256):
        raise CatalogSnapshotError("source_sha256 must be a lowercase SHA-256 digest")
    if isinstance(max_rows, bool) or not isinstance(max_rows, int) or max_rows < 1:
        raise CatalogSnapshotError("max_rows must be a positive integer")
