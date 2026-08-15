# Weekly Roadmap and Progress Log

This file is the project memory for weekly planning. Before starting a new
week, review the current status, move unfinished items forward, and record the
result at the end of the week.

Status values: `Done`, `In progress`, `Planned`, and `Blocked`.

## Current snapshot

Last reviewed: 2026-08-15

| Area | Status | Notes |
| --- | --- | --- |
| Mobile MVP | Done | Expo flow covers watchlist, stock detail, evidence, debate, claim examination, history, and about screens. |
| Backend MVP | Done | FastAPI routes, deterministic demo store, indicators, evidence retrieval, analysis trace, and token ledger are implemented. |
| Safety | Done | Financial-advice guardrails and the educational disclaimer are applied. |
| Automated checks | Done | 37 backend unit/API tests, mobile typecheck, and GitHub Actions CI pass. |
| Real LLM provider | Done | Groq is configured locally and a live structured analysis completed successfully; Gemini remains an optional fallback. |
| Supabase | In progress | Auth/session handling and backend persistence are implemented; two-user RLS and restart verification remain. |
| Live market/evidence data | In progress | RSS/SEC/vector and price-cache code are complete; selected SEC and Alpha Vantage cache population remain. |
| Mobile verification | In progress | Dependencies and lockfile are present and typecheck passes; simulator and physical-device testing remain. |
| Deployment | Planned | Backend hosting, mobile build, monitoring, and release checklist remain. |

## Week 1 — Product definition and repository foundation

Status: Done

- Define MVP scope and user stories.
- Research stock, news, and SEC filing data sources.
- Create the initial prototype and monorepo structure.
- Create the GitHub Project board and task cards.
- Establish the educational-only financial safety boundary.

Evidence:

- `prototype.html`
- `docs/planning/mvp-scope.md`
- `docs/planning/user-stories.md`
- `docs/planning/data-source-research.md`

## Week 2 — Demo backend and mobile experience

Status: Done

- Build the FastAPI service and API contract.
- Add deterministic stock prices and evidence for AAPL, GOOG, NVDA, and TSLA.
- Calculate RSI, MACD, moving averages, volatility, and volume-spike signals.
- Build the Expo mobile flow for watchlist, detail, evidence, debate, history,
  and cross-examination.
- Add safety guardrails, trace output, token usage, tests, CI, and architecture
  documentation.

Evidence:

- `backend/app/main.py`
- `backend/app/services/analysis.py`
- `apps/mobile/App.tsx`
- `backend/tests/`
- `.github/workflows/ci.yml`

## Week 3 — Real service integration

Status: In progress

- [x] Add Groq and Gemini provider adapters.
- [x] Validate structured Bull/Bear/Judge responses.
- [x] Filter model citations to retrieved evidence IDs.
- [x] Preserve safety guardrails and provider token accounting.
- [x] Create and configure one real model API key.
- [x] Run a live model analysis and record the verification result.
- [x] Create a dedicated Supabase project for AI Bull vs Bear.
- [x] Apply `backend/supabase/schema.sql`.
- [x] Enable Supabase Auth and connect persistent watchlists/analysis history.

Live verification is carried into Week 4: two real test users must still prove
cross-user RLS isolation and persistence across a backend restart.

Completion rule: a real provider analysis succeeds locally, and Supabase stores
and returns data for an authenticated user without exposing secrets.

## Week 4 — Live evidence and persistence

Status: In progress

Operating checklist: [`week-4-todo.md`](week-4-todo.md)

- [x] Connect one production-safe daily market price source with caching.
- [x] Ingest news through an approved RSS source.
- [x] Ingest SEC EDGAR filing metadata and extract selected filing sections.
- [x] Store evidence documents/chunks in Supabase.
- [x] Add embedding generation and pgvector retrieval.
- [x] Complete stale-cache and provider-failure handling across live data sources.
- [x] Add tests with mocked provider responses; do not call paid APIs in CI.

Progress recorded on 2026-08-15:

- Supabase authentication, mobile bearer-token forwarding, persistent
  watchlists/history, RLS policies, live RSS/SEC ingestion, evidence upserts,
  chunk storage, database-local vectors, and vector retrieval were implemented
  in the 2026-08-13 commit series.
- `4af130d` extracts Risk Factors and Management's Discussion and Analysis from
  filing HTML while rejecting short table-of-contents matches.
- `04d66c1` adds a declared SEC client with request spacing and retry handling
  for 429, network, and temporary server failures.
- `3ead176` stores selected sections when available and retains explicit
  metadata-only evidence when an individual filing cannot be fetched.
- `e00c33d` falls back to deterministic evidence when vector retrieval is empty
  or unavailable.
- `a34ab9b`, `170a4a0`, and `461c64b` add Alpha Vantage daily parsing, batch
  Supabase upserts, stale-cache provenance, and deterministic price fallback.
- `82880ff` displays live-cache, demo-fallback, and stale status in stock detail.
- A live read-only check found four supported stocks, six evidence documents
  (two news and four filing records), six chunks, and six populated vectors.
- Backend verification passes 37 tests; mobile `npm run typecheck` passes.

Remaining before Week 4 completion:

- Configure a server-side Supabase secret and compliant `SEC_USER_AGENT`, then
  rerun ingestion so existing filing records contain selected sections.
- Verify authentication, restart persistence, and RLS isolation with two real
  test users.
- Configure an Alpha Vantage key and server-side Supabase secret, then populate
  the currently empty `stock_prices` cache.

Completion rule: the evidence board can distinguish cached/demo evidence from
live evidence and every generated claim links to retrievable source metadata.

## Week 5 — Mobile verification and release preparation

Status: Planned

- [x] Install mobile dependencies and commit the generated lockfile.
- [ ] Run Expo diagnostics; TypeScript typecheck already passes.
- Test iOS/Android simulator and at least one physical device.
- Add loading, empty, timeout, offline, and provider-error states.
- Deploy the backend and configure production CORS/environment variables.
- Add monitoring, privacy notes, demo script, and final release checklist.

Completion rule: a fresh clone can follow the README, run the app, complete the
main analysis flow, and recover cleanly from expected service failures.

## Weekly update procedure

At the start of each week:

1. Read this file, `README.md`, and the latest GitHub Project status.
2. Select only the next unfinished weekly section unless priorities changed.
3. Move unresolved work forward and state why.

During the week:

1. Keep secrets only in local `.env` files or the deployment platform's secret
   manager.
2. Make one focused commit per small change; avoid combining unrelated files.
3. Update tests and documentation in their own focused commits when practical.

At the end of each week:

1. Update the current snapshot and week status.
2. Record completed work, remaining work, blockers, and verification evidence.
3. Sync the GitHub Project board with the repository state.

## Decision log

- 2026-08-06: Use deterministic demo data first so development does not depend
  on credentials or unstable free APIs.
- 2026-08-06: Keep the product educational; do not output personalised
  buy/sell/hold recommendations.
- 2026-08-12: Support Groq and Gemini behind the same structured analysis
  contract; demo remains the safe fallback.
- 2026-08-12: Use small, focused commits for each meaningful change.
- 2026-08-12: Select Groq as the first live provider; a real
  `llama-3.3-70b-versatile` analysis completed with validated evidence IDs and
  provider token usage.
- 2026-08-12: Create a dedicated Supabase project, apply the ten-table schema,
  and use explicit minimum Data API grants because automatic table exposure is
  disabled.
- 2026-08-15: Prefer bounded SEC narrative sections over filing metadata-only
  evidence; keep metadata as an explicit fallback when a filing is unavailable.
- 2026-08-15: Treat the repository and passing tests as the implementation
  source of truth when the GitHub Project board has not yet been synchronized.
- 2026-08-15: Use Alpha Vantage compact daily data as a four-call batch into
  Supabase; never spend the 25-call free quota during normal API requests.
