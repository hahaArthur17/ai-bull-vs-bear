# Project Week 5 Report — Retrieval Architecture and Release Checks

Reporting date: 2026-08-15  
Status: In progress

## Goal

Make the evidence layer safe to evolve across news, filings, tables, images,
and multiple embedding providers while preserving a clear handoff record.

## Completed work

- Pushed the previous 60 local commits to `origin/main`.
- Researched pgvector/Supabase constraints, Gemini, Qwen/DashScope, BGE-M3,
  MTEB, contextual/parent-child retrieval, SEC XBRL, Docling, TAT-QA, FinQA,
  and practical GitHub/Reddit/YouTube experience.
- Documented the presentation-ready architecture in
  `docs/architecture/vectorization-strategy.md` (`665872e`).
- Added versioned `embedding_profiles` and mixed-dimension
  `chunk_embeddings`, including dimension validation, local-profile syncing,
  a generic real-vector RPC, and a partial HNSW index (`a536cd6`).
- Applied that migration to the live Supabase project. Six existing embeddings
  now belong to `local-hash-v1`, 1,536 dimensions, and public RPC retrieval
  still succeeds.
- Replaced one-size word windows in ingestion with source-aware contextual
  chunks. News carries ticker/date/title context; filings preserve form,
  reporting period, and section path (`a68b9db`).
- Added the typed `financial_facts` schema and applied it live (`01e3cc5`).
- Added bounded SEC `companyfacts` parsing/upsert for common revenue, earnings,
  balance-sheet, cash-flow, share, and EPS concepts (`8afa884`).
- Added four ignored-env inputs and a repeatable two-user RLS verifier
  (`0bcf0c2`).
- Updated schema and live-service documentation (`41bd77e`, `e86c515`).
- Created a dedicated current-format Supabase backend key and stored it only in
  the ignored local `.env`; no credential value entered Git or this report.
- Reset the two existing disposable Auth users to random local-only passwords
  and passed owner access, cross-user read/write isolation, and reconnect
  persistence checks.
- Added current `sb_secret_...` request-header compatibility (`6a59abf`) and
  restored the live `service_role` SQL privileges required by backend ingestion
  (`d489330`).
- Replaced the partial evidence ID index with a PostgREST-compatible unique
  index (`8f7bb76`). Repeated live ingestion now succeeds idempotently.
- Refreshed live RSS/SEC evidence to 20 documents and 107 contextual chunks,
  and populated 611 typed SEC XBRL facts.
- Prefilled the Alpha Vantage free-key form with the project identity and
  monitored contact. Submission is intentionally paused at the terms-acceptance
  button.

## 2026-08-16 continuation

- Stored the supplied Apify user ID/token and Finnhub key only in the ignored
  local `.env`; no credential values were added to source control.
- Declared `APIFY_USER_ID`, `APIFY_API_TOKEN`, and `FINNHUB_API_KEY` in the
  backend settings and non-secret environment template, and documented the
  provider boundary (`f6ccd8b`).
- Verified the Apify token against the authenticated user endpoint and the
  Finnhub key with one AAPL quote request; both checks passed.
- Apify still needs a concrete Actor or saved Task plus an output contract
  before implementation. Finnhub can be evaluated as a direct price-provider
  fallback in a later focused change.
- Because the credentials were supplied through chat, rotate both provider
  tokens before production deployment and update only the ignored `.env`.

## GitHub Project sync

The board was synchronized after implementation:

- moved JWT authentication, RSS ingestion, SEC ingestion, embeddings, and live
  price caching subtasks from Todo to Done;
- kept the two top-level issues `#3` and `#6` In Progress because their live
  credential acceptance checks are still incomplete;
- kept two-user RLS verification in Todo; and
- created `#11` embedding benchmark, `#12` hybrid retrieval/reranking, `#13`
  live XBRL/price population, and `#14` layout-aware table/chart ingestion.

Initial sync counts were 5 Todo, 2 In Progress, and 13 Done. After the live
credential work, `#3` was verified, moved to Done, and closed; `#13` was moved
to In Progress with a non-secret live-count update; and the RLS verification
draft card was moved to Done. Current counts: 3 Todo, 2 In Progress, and 15
Done.

## Main technical decisions

- The current 1,536-dimensional vector is `local-hash-v1`, an offline plumbing
  baseline, not a semantic model.
- Do not force Gemini, Qwen, BGE, and other models into one vector space. A
  canonical chunk can have multiple profile-specific vectors; query and stored
  vectors must share a profile.
- Start production evaluation around 768–1,536 dimensions. Test BGE-M3 and
  Qwen/DashScope at 1,024, Gemini at 768 and 1,536, then select by finance-corpus
  Recall@K, nDCG/MRR, citation precision, numeric exact match, latency, and cost.
- News uses paragraph/heading-aware contextual chunks. Filing narrative uses
  section-aware children with parent document context.
- Tables keep headers, periods, units, cells, footnotes, and source locations.
  Vectors discover relevant evidence; structured XBRL/SQL performs arithmetic.
- Use dense + lexical + metadata retrieval, rank fusion, and reranking rather
  than dense-only search.

## Verification

- Backend: 43 tests pass, including current and legacy Supabase key headers.
- Live Supabase migration: `local-hash-v1 | 1536 | active | 6 embeddings`.
- Live anonymous `match_evidence_chunks` request returned three NVDA vector
  results after the schema migration.
- Two-user RLS verification passes all four acceptance checks.
- The current-format backend key successfully reaches both Supabase Auth Admin
  and the Data API without being sent as an invalid Bearer JWT.
- Live Supabase contains 20 evidence documents, 107 contextual chunks, and 611
  structured financial facts after two idempotent ingestion runs.
- Supabase Dashboard login was already active, so no user login was needed.

## Exact blockers

- `ALPHA_VANTAGE_API_KEY` is the only remaining credential gap. The application
  form is complete, but pressing **Get Free API Key** constitutes acceptance of
  Alpha Vantage's Terms of Service and Privacy Policy, so the user must perform
  that final confirmation. The returned key can then be stored locally and the
  price cache populated without any further code change.
- Simulator and physical-device verification still require an available device
  or simulator session.

## Next three tasks

1. Confirm the Alpha Vantage free-key terms, save the returned key in the
   ignored `.env`, and run the four-ticker price-cache refresh.
2. Create a small finance retrieval benchmark with gold chunks, cells, units,
   periods, and calculations; add the first real 1,024-dimensional profile.
3. Add lexical retrieval/rank fusion and expose structured financial facts to
   the analysis pipeline before beginning multimodal PDF/chart work.

## Handoff links

- `docs/architecture/vectorization-strategy.md`
- `docs/setup/live-services.md`
- `docs/database/schema-plan.md`
- `../week-4-todo.md`
