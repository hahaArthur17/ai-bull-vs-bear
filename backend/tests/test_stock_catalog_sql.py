from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_SQL = (REPOSITORY_ROOT / "backend/supabase/schema.sql").read_text(encoding="utf-8")
MIGRATION_SQL = (
    REPOSITORY_ROOT
    / "backend/supabase/migrations/20260827_stock_catalog_coverage.sql"
).read_text(encoding="utf-8")
SEARCH_MIGRATION_SQL = (
    REPOSITORY_ROOT
    / "backend/supabase/migrations/20260827_stock_catalog_search.sql"
).read_text(encoding="utf-8")


def test_catalog_schema_has_identity_coverage_and_nullable_classification() -> None:
    for sql in (SCHEMA_SQL, MIGRATION_SQL):
        assert "sec_cik" in sql
        assert "country" in sql
        assert "aliases text[]" in sql
        assert "search_text" in sql
        assert "is_active" in sql
        assert "coverage_status" in sql
        assert "coverage_updated_at" in sql
        assert all(
            status in sql
            for status in ("catalog_only", "price_cached", "evidence_ready", "debate_ready")
        )

    assert "sector text," in SCHEMA_SQL
    assert "alter column sector drop not null" in MIGRATION_SQL


def test_catalog_schema_has_search_indexes_and_public_read_policy() -> None:
    for sql in (SCHEMA_SQL, MIGRATION_SQL):
        assert "create extension if not exists pg_trgm" in sql
        assert "stocks_ticker_lower_idx" in sql
        assert "stocks_active_coverage_idx" in sql
        assert "stocks_search_text_trgm_idx" in sql
        assert "alter table public.stocks enable row level security" in sql
        assert '"Public stock catalog is readable"' in sql


def test_catalog_migration_preserves_demo_debate_coverage() -> None:
    assert "coverage_status = 'debate_ready'" in MIGRATION_SQL
    assert all(ticker in MIGRATION_SQL for ticker in ("AAPL", "GOOG", "NVDA", "TSLA"))
    assert "stocks_sec_cik_positive" in MIGRATION_SQL
    assert "stocks_coverage_status_allowed" in MIGRATION_SQL


def test_catalog_search_function_is_ranked_bounded_and_public_read_only() -> None:
    for sql in (SCHEMA_SQL, SEARCH_MIGRATION_SQL):
        assert "function public.search_stock_catalog" in sql
        assert "least(greatest(coalesce(result_limit, 20), 1), 25)" in sql
        assert "when lower(stock.ticker) = normalized.query then 0" in sql
        assert "when lower(stock.ticker) like normalized.query || '%' then 1" in sql
        assert "length(normalized.query) >= 3" in sql
        assert "stock.search_text like '%' || normalized.query || '%'" in sql
        assert "chr(37) || chr(95) || chr(92)" in sql
        assert "stable" in sql
        assert "set search_path = ''" in sql
        assert "grant execute" in sql
        assert "anon, authenticated" in sql
