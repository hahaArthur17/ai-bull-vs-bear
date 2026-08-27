from __future__ import annotations

from datetime import date
import re

from app.services.stock_catalog import CATALOG_SCHEMA_VERSION, MAX_CATALOG_ROWS


_CANONICAL_EXCHANGES = {"CBOE", "NASDAQ", "NYSE"}
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_TICKER_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9.-]{0,9}$")


class CatalogSeedError(ValueError):
    """Raised when a catalog snapshot is unsafe to render as seed SQL."""


def render_catalog_seed_sql(
    snapshot: object,
    *,
    chunk_size: int = 500,
) -> str:
    """Render an idempotent Supabase seed without changing coverage metadata."""

    retrieved_on, source_url, source_sha256, stocks = _validate_snapshot(snapshot)
    if isinstance(chunk_size, bool) or not isinstance(chunk_size, int) or chunk_size < 1:
        raise CatalogSeedError("chunk_size must be a positive integer")

    lines = [
        "-- Generated stock identity seed. Do not edit rows by hand.",
        f"-- Source: {source_url}",
        f"-- Retrieved: {retrieved_on}",
        f"-- Raw source SHA-256: {source_sha256}",
        f"-- Normalized rows: {len(stocks)}",
        "",
        "begin;",
        "",
    ]
    coverage_timestamp = f"{retrieved_on}T00:00:00Z"
    for start in range(0, len(stocks), chunk_size):
        chunk = stocks[start : start + chunk_size]
        lines.extend(
            [
                "insert into public.stocks as existing (",
                "  sec_cik, ticker, company_name, exchange, search_text,",
                "  is_active, coverage_status, coverage_updated_at",
                ")",
                "values",
            ]
        )
        for index, stock in enumerate(chunk):
            ticker = str(stock["ticker"])
            company_name = str(stock["company_name"])
            values = (
                f"  ({stock['sec_cik']}, {_sql_text(ticker)}, {_sql_text(company_name)}, "
                f"{_sql_text(str(stock['exchange']))}, "
                f"{_sql_text(f'{ticker} {company_name}'.lower())}, true, "
                f"'catalog_only', {_sql_text(coverage_timestamp)}::timestamptz)"
            )
            lines.append(values + ("," if index < len(chunk) - 1 else ""))
        lines.extend(
            [
                "on conflict (ticker) do update set",
                "  sec_cik = excluded.sec_cik,",
                "  company_name = case",
                "    when existing.coverage_status = 'debate_ready' then existing.company_name",
                "    else excluded.company_name",
                "  end,",
                "  exchange = case",
                "    when existing.coverage_status = 'debate_ready' then existing.exchange",
                "    else excluded.exchange",
                "  end,",
                "  search_text = case",
                "    when existing.coverage_status = 'debate_ready' then lower(concat_ws(",
                "      ' ',",
                "      existing.ticker,",
                "      existing.company_name,",
                "      array_to_string(existing.aliases, ' ')",
                "    ))",
                "    else excluded.search_text",
                "  end;",
                "",
            ]
        )
    lines.extend(["commit;", ""])
    return "\n".join(lines)


def _validate_snapshot(
    snapshot: object,
) -> tuple[str, str, str, list[dict[str, object]]]:
    if not isinstance(snapshot, dict) or snapshot.get("schema_version") != CATALOG_SCHEMA_VERSION:
        raise CatalogSeedError("Unsupported catalog snapshot schema")
    source = snapshot.get("source")
    stocks = snapshot.get("stocks")
    if not isinstance(source, dict) or not isinstance(stocks, list):
        raise CatalogSeedError("Catalog snapshot is missing source or stock rows")
    if not stocks or len(stocks) > MAX_CATALOG_ROWS:
        raise CatalogSeedError("Catalog snapshot row count is outside the safety bound")

    retrieved_on = source.get("retrieved_on")
    source_url = source.get("url")
    source_sha256 = source.get("sha256")
    try:
        date.fromisoformat(retrieved_on)
    except (TypeError, ValueError) as exc:
        raise CatalogSeedError("Snapshot retrieval date is invalid") from exc
    if not isinstance(source_url, str) or not source_url.startswith("https://www.sec.gov/"):
        raise CatalogSeedError("Snapshot source URL is not an SEC HTTPS URL")
    if not isinstance(source_sha256, str) or not _SHA256_PATTERN.fullmatch(source_sha256):
        raise CatalogSeedError("Snapshot source SHA-256 is invalid")

    validated: list[dict[str, object]] = []
    seen: set[str] = set()
    previous_ticker = ""
    for index, stock in enumerate(stocks):
        if not isinstance(stock, dict):
            raise CatalogSeedError(f"Catalog row {index} is not an object")
        cik = stock.get("sec_cik")
        ticker = stock.get("ticker")
        company_name = stock.get("company_name")
        exchange = stock.get("exchange")
        if isinstance(cik, bool) or not isinstance(cik, int) or cik <= 0:
            raise CatalogSeedError(f"Catalog row {index} has an invalid CIK")
        if not isinstance(ticker, str) or not _TICKER_PATTERN.fullmatch(ticker):
            raise CatalogSeedError(f"Catalog row {index} has an invalid normalized ticker")
        if ticker in seen or ticker < previous_ticker:
            raise CatalogSeedError("Catalog tickers must be sorted and unique")
        if not isinstance(company_name, str) or not company_name or "\x00" in company_name:
            raise CatalogSeedError(f"Catalog row {index} has an invalid company name")
        if exchange not in _CANONICAL_EXCHANGES:
            raise CatalogSeedError(f"Catalog row {index} has an unsupported exchange")
        seen.add(ticker)
        previous_ticker = ticker
        validated.append(stock)
    return retrieved_on, source_url, source_sha256, validated


def _sql_text(value: str) -> str:
    if "\x00" in value:
        raise CatalogSeedError("SQL text cannot contain a null byte")
    return "'" + value.replace("'", "''") + "'"
