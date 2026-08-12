# Weekly Roadmap and Progress Log

This file is the project memory for weekly planning. Before starting a new
week, review the current status, move unfinished items forward, and record the
result at the end of the week.

Status values: `Done`, `In progress`, `Planned`, and `Blocked`.

## Current snapshot

Last reviewed: 2026-08-12

| Area | Status | Notes |
| --- | --- | --- |
| Mobile MVP | Done | Expo flow covers watchlist, stock detail, evidence, debate, claim examination, history, and about screens. |
| Backend MVP | Done | FastAPI routes, deterministic demo store, indicators, evidence retrieval, analysis trace, and token ledger are implemented. |
| Safety | Done | Financial-advice guardrails and the educational disclaimer are applied. |
| Automated checks | Done | Backend unit/API tests and GitHub Actions CI are present. |
| Real LLM provider | Done | Groq is configured locally and a live structured analysis completed successfully; Gemini remains an optional fallback. |
| Supabase | In progress | Database schema and RLS policies exist; a dedicated project, schema deployment, Auth, and backend persistence remain. |
| Live market/evidence data | Planned | RSS ingestion utility exists; production feeds, SEC EDGAR ingestion, and scheduled refresh remain. |
| Mobile verification | Planned | Dependency installation, typecheck, and device testing remain. |
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
- [ ] Create a dedicated Supabase project for AI Bull vs Bear.
- [ ] Apply `backend/supabase/schema.sql`.
- [ ] Enable Supabase Auth and connect persistent watchlists/analysis history.

Completion rule: a real provider analysis succeeds locally, and Supabase stores
and returns data for an authenticated user without exposing secrets.

## Week 4 — Live evidence and persistence

Status: Planned

- Connect at least one production-safe market price source with caching.
- Ingest news through an approved RSS or API source.
- Ingest SEC EDGAR filing metadata and selected filing sections.
- Store evidence documents/chunks in Supabase.
- Add embedding generation and pgvector retrieval.
- Add retry, rate-limit, stale-cache, and provider-failure handling.
- Add tests with mocked provider responses; do not call paid APIs in CI.

Completion rule: the evidence board can distinguish cached/demo evidence from
live evidence and every generated claim links to retrievable source metadata.

## Week 5 — Mobile verification and release preparation

Status: Planned

- Install mobile dependencies and commit the generated lockfile.
- Run TypeScript typecheck and Expo diagnostics.
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
