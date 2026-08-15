# Weekly Roadmap and Progress Log

This file is the project memory for weekly planning. Before starting a new
week, review the current status, move unfinished items forward, and record the
result at the end of the week.

Detailed, append-only records now live in [`reports/`](reports/README.md) so
this roadmap remains a short index instead of growing without bound.

Status values: `Done`, `In progress`, `Planned`, and `Blocked`.

## Current snapshot

Last reviewed: 2026-08-16

| Area | Status | Notes |
| --- | --- | --- |
| Mobile MVP | Done | Expo flow covers watchlist, stock detail, evidence, debate, claim examination, history, and about screens. |
| Backend MVP | Done | FastAPI routes, deterministic demo store, indicators, evidence retrieval, analysis trace, and token ledger are implemented. |
| Safety | Done | Financial-advice guardrails and the educational disclaimer are applied. |
| Automated checks | Done | 44 backend unit/API tests, mobile typecheck, production Web export, and GitHub Actions CI pass. |
| Real LLM provider | Done | Groq is configured locally and a live structured analysis completed successfully; Gemini remains an optional fallback. |
| Supabase | Done | Auth/session handling, persistence, current backend key, two-user RLS isolation, restart persistence, vectors, and XBRL facts are live. |
| Live market/evidence data | In progress | Live RSS/SEC/vector/XBRL data is populated; Alpha Vantage remains optional because price reads have a tested demo fallback. |
| Mobile verification | In progress | SDK dependencies, typecheck, Expo Doctor, and Web export pass; simulator and physical-device testing remain. |
| Deployment | Done | Render Free API and static Expo Web site are live; production auth, CORS, zero-token analysis, and persistence smoke tests pass. |

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

Status: Done

- [x] Add Groq and Gemini provider adapters.
- [x] Validate structured Bull/Bear/Judge responses.
- [x] Filter model citations to retrieved evidence IDs.
- [x] Preserve safety guardrails and provider token accounting.
- [x] Create and configure one real model API key.
- [x] Run a live model analysis and record the verification result.
- [x] Create a dedicated Supabase project for AI Bull vs Bear.
- [x] Apply `backend/supabase/schema.sql`.
- [x] Enable Supabase Auth and connect persistent watchlists/analysis history.

Live verification was completed in Week 5: two disposable test users proved
owner access, cross-user RLS isolation, and persistence across reconnects.

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
- A later 2026-08-15 continuation separated chunks from versioned embedding
  profiles, added source-aware contextual chunking, and added typed SEC XBRL
  facts. Both database migrations are live; backend verification now passes 41
  tests. See [`reports/project-week-05.md`](reports/project-week-05.md).

Remaining live-data enhancement:

- Optionally configure a free Alpha Vantage key and populate the price cache.
  This is not a deployment or presentation blocker because empty/unavailable
  price caches use the tested deterministic fallback.

Completion rule: the evidence board can distinguish cached/demo evidence from
live evidence and every generated claim links to retrievable source metadata.

## Week 5 — Mobile verification and release preparation

Status: In progress

- [x] Install mobile dependencies and commit the generated lockfile.
- [x] Run TypeScript typecheck and Expo diagnostics.
- [x] Export a production Web bundle with Metro.
- [ ] Test iOS/Android simulator and at least one physical device.
- [x] Add loading, empty, timeout, offline, and provider-error states.
- [x] Deploy the backend and configure production CORS/environment variables.
- [ ] Add monitoring, privacy notes, demo script, and final release checklist.

Progress recorded on 2026-08-15:

- `d110fe6` aligns React Native and AsyncStorage with Expo SDK 52; Expo Doctor
  passes all 18 checks.
- `02f109a` adds a configurable 15-second API timeout and clear messages for
  offline, expired-session, and temporary live-service failures.
- `2bd291a` replaces the stock-detail infinite-loading failure path with a
  recoverable error screen and retry action.
- TypeScript typecheck and a clean temporary Web export both pass.
- `54f180f` adds a zero-cost Render Blueprint, slim FastAPI Docker image, and
  static Expo Web deployment. The Web export is 616 KB and the measured API
  process peak RSS is about 53.4 MiB against 512 MB of free RAM.
- `a0e153b` reduces live price refreshes to AAPL, NVDA, and TSLA, caps each
  invocation at three provider calls, and disables batch retries.
- Production deployment deliberately uses deterministic analysis so Groq and
  Gemini consumption is zero and cannot interrupt the presentation.
- The `ai-bull-vs-bear-zero-cost` Blueprint is live at
  <https://ai-bull-vs-bear.onrender.com>, backed by the Free API at
  <https://ai-bull-vs-bear-api.onrender.com>. Render shows the API as Free and
  the Hobby workspace has a `$0` monthly spend limit.
- Live acceptance passes Supabase login, four-stock retrieval, eight AAPL
  evidence items, zero-token analysis persistence, and frontend-origin CORS.
- `npm audit --omit=dev` reports 23 transitive Expo/Metro findings (10 moderate,
  12 high, 1 critical). Its automated fix requires a major Expo 52-to-57
  migration, so the dependency upgrade needs a dedicated compatibility task;
  do not run `npm audit fix --force` on the current SDK line.

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
2. Add a report under `reports/` with completed work, remaining work, blockers,
   verification evidence, and handoff links.
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
- 2026-08-15: Use Alpha Vantage compact daily data as a cached batch into
  Supabase; never spend the 25-call free quota during normal API requests.
- 2026-08-15: Keep Expo SDK 52 dependencies aligned and defer the audit-driven
  Expo 57 major upgrade to a dedicated migration with simulator regression.
- 2026-08-15: Separate canonical chunks from provider-specific embedding
  profiles; vectors from different profiles are never compared.
- 2026-08-15: Store financial values with SEC XBRL period/unit provenance and
  use vector search only for discovery, not numerical arithmetic.
- 2026-08-16: Enforce a zero-spend deployment boundary: Render Free plus
  Supabase Free, no payment method or automatic upgrades, three price calls per
  daily batch, and deterministic production analysis.
