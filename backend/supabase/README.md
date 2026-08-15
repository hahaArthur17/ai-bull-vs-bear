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

The evidence schema separates canonical chunks from provider-specific
embeddings. `local-hash-v1` is the deterministic offline baseline; real Gemini,
Qwen, BGE, or other profiles belong in `chunk_embeddings` and must never be
compared across profiles. SEC XBRL values belong in `financial_facts` so period,
unit, and arithmetic semantics are not lost in vectorized text.
