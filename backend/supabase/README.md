# Supabase setup

1. Create a Supabase project at https://supabase.com/dashboard.
2. Open SQL Editor and run `schema.sql`.
3. Run every file in `migrations/` in filename order. Migrations are idempotent
   and are also required after pulling new database work into an existing
   project.
4. Enable Email or OAuth authentication under Authentication.
5. Copy the project URL and anon key into a local `.env` file.
6. Keep `ANALYSIS_PROVIDER=demo` until the provider adapter is configured.

The current backend intentionally uses the deterministic DemoStore so the
application is usable before Supabase credentials are available. The SQL schema
and environment variables are prepared for the persistence/authentication
milestone.

The Phase 2 stock catalog uses three migrations. Apply them in filename order:

1. `20260827_stock_catalog_coverage.sql`
2. `20260827_stock_catalog_search.sql`
3. `20260827_stock_catalog_seed.sql`

Before applying them to Supabase Free, verify the database is below 400 MB as
documented in [`live-services.md`](../../docs/setup/live-services.md). Afterward,
verify that `public.stocks`, including indexes, is no more than 15 MiB and rerun
public-read plus two-user Watchlist RLS checks.

The generated seed uses 16 bounded upsert statements inside one transaction and
preserves existing coverage, sector, country, and aliases on conflict. Do not
edit its generated rows manually; regenerate it from the reviewed artifact
under `data/catalog`.

Phase 3 adds two V2 Debate migrations after the catalog files:

1. `20260827_v2_debate_persistence.sql`
2. `20260827_v2_debate_persistence_rpc.sql`

The first creates the five canonical relations, constraints, indexes, grants,
and owner-read RLS. The second adds service-only transaction boundaries for the
initial Session+Job pair and a complete Message+citations write. Neither file
enables Supabase Queue transport. Apply them to a hosted project only after the
catalog capacity gate, then verify two-user read isolation, rejected client
writes, and service-role creation/update before marking Phase 3 persistence
deployed.

The evidence schema separates canonical chunks from provider-specific
embeddings. `local-hash-v1` is the deterministic offline baseline; real Gemini,
Qwen, BGE, or other profiles belong in `chunk_embeddings` and must never be
compared across profiles. SEC XBRL values belong in `financial_facts` so period,
unit, and arithmetic semantics are not lost in vectorized text.
