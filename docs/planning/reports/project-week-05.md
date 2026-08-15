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

## GitHub Project sync

The board was synchronized after implementation:

- moved JWT authentication, RSS ingestion, SEC ingestion, embeddings, and live
  price caching subtasks from Todo to Done;
- kept the two top-level issues `#3` and `#6` In Progress because their live
  credential acceptance checks are still incomplete;
- kept two-user RLS verification in Todo; and
- created `#11` embedding benchmark, `#12` hybrid retrieval/reranking, `#13`
  live XBRL/price population, and `#14` layout-aware table/chart ingestion.

Final board counts: 5 Todo, 2 In Progress, and 13 Done.

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

- Backend: 41 tests pass after source-aware chunking and XBRL ingestion.
- Live Supabase migration: `local-hash-v1 | 1536 | active | 6 embeddings`.
- Live anonymous `match_evidence_chunks` request returned three NVDA vector
  results after the schema migration.
- Live `financial_facts` table and read policy exist; the table is empty pending
  credentialed ingestion.
- Supabase Dashboard login was already active, so no user login was needed.

## Exact blockers

- `SUPABASE_SECRET_KEY` is not present locally, so backend ingestion cannot
  write refreshed SEC sections, XBRL facts, or Alpha Vantage prices.
- `SEC_USER_AGENT` lacks a real monitored contact email. Do not send automated
  SEC traffic using the committed placeholder.
- `ALPHA_VANTAGE_API_KEY` is absent.
- Two existing RLS users are visible in Supabase, but their passwords are not in
  the local environment. Dashboard can send recovery email but cannot reveal a
  password. Fill the four `SUPABASE_RLS_*` variables, then run
  `PYTHONPATH=backend python scripts/verify_supabase_rls.py`.
- Simulator and physical-device verification still require an available device
  or simulator session.

## Next three tasks

1. Configure only the missing project/test credentials in the ignored `.env`,
   run RLS verification, and populate SEC/XBRL and price caches.
2. Create a small finance retrieval benchmark with gold chunks, cells, units,
   periods, and calculations; add the first real 1,024-dimensional profile.
3. Add lexical retrieval/rank fusion and expose structured financial facts to
   the analysis pipeline before beginning multimodal PDF/chart work.

## Handoff links

- `docs/architecture/vectorization-strategy.md`
- `docs/setup/live-services.md`
- `docs/database/schema-plan.md`
- `../week-4-todo.md`
