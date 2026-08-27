import json
from pathlib import Path

import pytest

from app.services.stock_catalog_seed import CatalogSeedError, render_catalog_seed_sql


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_PATH = (
    REPOSITORY_ROOT / "data/catalog/sec-company-tickers-exchange-2026-08-27.json"
)


def snapshot(*stocks: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "source": {
            "url": "https://www.sec.gov/files/company_tickers_exchange.json",
            "retrieved_on": "2026-08-27",
            "sha256": "a" * 64,
        },
        "stocks": list(stocks),
    }


def stock(ticker: str, company_name: str, cik: int = 1) -> dict[str, object]:
    return {
        "sec_cik": cik,
        "ticker": ticker,
        "company_name": company_name,
        "exchange": "NASDAQ",
    }


def test_render_catalog_seed_escapes_names_and_preserves_coverage_fields() -> None:
    sql = render_catalog_seed_sql(snapshot(stock("OREL", "O'Reilly Media")))

    assert "O''Reilly Media" in sql
    assert "on conflict (ticker) do update set" in sql
    assert "existing.coverage_status = 'debate_ready'" in sql
    assert "sector =" not in sql
    assert "country =" not in sql
    assert "aliases =" not in sql
    assert "coverage_status = excluded.coverage_status" not in sql
    assert "coverage_updated_at = excluded.coverage_updated_at" not in sql


def test_render_catalog_seed_chunks_large_inserts() -> None:
    sql = render_catalog_seed_sql(
        snapshot(stock("AAA", "First"), stock("BBB", "Second", 2)),
        chunk_size=1,
    )

    assert sql.count("insert into public.stocks as existing") == 2
    assert sql.startswith("-- Generated stock identity seed")
    assert sql.endswith("commit;\n")


@pytest.mark.parametrize(
    "invalid_snapshot",
    [
        {"schema_version": 2},
        snapshot(stock("bbb", "Not normalized")),
        snapshot(stock("BBB", "Second"), stock("AAA", "First", 2)),
        snapshot(stock("AAA", "First"), stock("AAA", "Duplicate", 2)),
    ],
)
def test_render_catalog_seed_rejects_unsafe_snapshots(invalid_snapshot: object) -> None:
    with pytest.raises(CatalogSeedError):
        render_catalog_seed_sql(invalid_snapshot)


def test_render_catalog_seed_accepts_checked_in_snapshot() -> None:
    catalog = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    sql = render_catalog_seed_sql(catalog)

    assert "-- Normalized rows: 7695" in sql
    assert ", 'AAPL'," in sql
    assert ", 'GOOG'," in sql
    assert ", 'NVDA'," in sql
    assert ", 'TSLA'," in sql
    assert sql.count("insert into public.stocks as existing") == 16
