# Current Project Status

Last verified: 2026-08-27

This file is the concise implementation baseline. Historical work and commit
evidence live in [`reports/`](reports/README.md); material incidents live in the
[`issue-log.md`](issue-log.md).

Status values are `Done`, `In progress`, `Planned`, and `Blocked`.

## Verified baseline

| Area | Status | Current state |
| --- | --- | --- |
| Mobile application | Done | Expo/React Native flow includes authentication, watchlist, stock detail, Signals, Evidence Board, Debate, claim examination, History, and About. |
| Backend API | Done | FastAPI exposes stocks, cached prices, indicators, macro context, evidence, watchlist, analysis, trace, token usage, and claim examination. |
| Authentication and persistence | Done | Supabase Auth, bearer-token verification, RLS, persistent watchlists, current-format analysis history, evidence, vectors, XBRL facts, price caches, and macro caches are implemented. |
| Market and evidence integrity | Done | AAPL uses a verified completed-close cache, current-source freshness rules, immutable evidence/macro snapshots, and dated citations. Missing current news lowers confidence instead of being silently replaced by demo narrative evidence. |
| Technical and macro exploration | Done | 1M/3M daily and 6M/1Y weekly price views, MA overlays, RSI, MACD, volume, volatility, and seven dated macro series are available. |
| Model adapters | Done | Deterministic, Groq, and Gemini adapters share a validated single-response Bull/Bear/Judge contract. A real provider was verified locally. |
| Deployment | Done | Render Free serves the static Expo Web site and one FastAPI web service; Supabase Free provides Auth and persistent data. Production deliberately uses the deterministic provider. |
| Automated verification | Done | 123 backend tests, the mobile TypeScript check, and Expo Web export pass. The only backend warning is the existing Starlette/httpx test-client deprecation. |
| Native-device verification | In progress | Expo checks and Web export pass; physical iOS/Android testing remains. |

Public verification on 2026-08-27 returned `200` from the deployed frontend,
returned a healthy production API with `provider=demo`, and listed AAPL, GOOG,
NVDA, and TSLA.

## Current product limitations

These are limitations of the current implementation, not completed features:

- Debate is one synchronous `POST /analysis/{ticker}` request. It returns one
  Bull claim, one Bear claim, and one Judge summary only after the full JSON
  response has been generated.
- Bull and Bear do not receive each other's prior statements, so the current
  result is a side-by-side analysis rather than a stateful rebuttal.
- There is no SSE/WebSocket stream, durable debate job queue, worker lifecycle,
  cancellation protocol, or reconnect/resume cursor.
- Claim examination accepts four fixed question types. It does not accept an
  arbitrary selected term, a free-form question, or a user interruption that
  redirects the debate.
- Search filters the four already-loaded supported stocks in the client. The
  API accepts a query parameter, but the production repository still exposes
  the same four-symbol catalog.
- Watchlist persistence works for seeded stocks only. A catalog-only stock
  cannot yet be saved with an explicit data-coverage state.
- Technical indicators, evidence types, and model prompt inputs use several
  fixed schemas in the current API. Common `FactorProvider` contracts and
  adapters now exist, but they are not yet connected to the V2 Debate runtime.
- Redis is not configured. The current quote cache is process-local and other
  persistent cached data is read from Supabase.
- No durable message queue is connected to the analysis request path.
- Stock detail, charting, Debate, Evidence, and Examination UI still live in a
  large `App.tsx`; the shared theme/components and three low-coupling screens
  are now extracted, but the remaining UI needs incremental modularization.

## Accepted product direction

The next portfolio milestone is a demonstrable engineering system, not a claim
of production-scale market-traffic capacity. It will:

- keep the zero-cost deployment boundary and the existing data sources;
- add extension points for future factors without integrating new live factor
  sources now;
- implement a real durable message queue for debate jobs;
- use Redis for cache, rate limiting, and idempotency rather than canonical
  persistence;
- turn Debate into a streamed, persisted, multi-turn session in which each side
  rebuts the other;
- pause after a neutral Judge summary for a user question and run a second
  debate round;
- separate term explanation from debate interruption;
- support zero-cost local/server-side stock catalog search and watchlist-only
  symbols while keeping full Debate limited to verified supported stocks; and
- redesign the UI around reusable finance/technology design tokens and
  components.

The complete target architecture, product rules, phase order, acceptance tests,
and current coding entry point are canonical in
[`portfolio-implementation-plan.md`](portfolio-implementation-plan.md).

Documentation Phase 0 and modular-boundary Phase 1 are complete. The active
development phase is Phase 2: add a bounded local/Supabase stock catalog,
coverage-aware search, and watchlist-only symbols without spending market-data
provider quota.

### Phase 1 completion evidence

The synchronous analysis contract now has explicit characterization tests.
Immutable `AnalysisContext`/`FactorObservation` contracts, a validating
`FactorRegistry`, and the first `TechnicalFactorProvider` are implemented. A
test-only mock sentiment provider proves that registration adds a new factor
without changing the registry or existing technical provider. These components
are a foundation for the V2 Debate and do not change the current API response.

Typed snapshot inputs and adapters now cover all current categories: technical
indicators, dated macro background, news, filings, and structured financial
facts. Macro text retains a non-causation boundary; evidence adapters preserve
freshness without inferring sentiment; financial facts preserve units, periods,
and filing references. Missing optional categories remain explicit rather than
being replaced with synthetic data.

Database-independent Debate contracts now define sessions, complete/cancelled
messages, citations, explain/challenge interventions, jobs, identifier-only
Queue payloads, and versioned stream events. A single state service validates
the full two-round path, Judge prerequisites, cancellation, failure, and
terminal states. Turn-provider inputs require the latest opponent message as
the rebuttal target. Repository protocols define the future Supabase boundary
without claiming that persistence or Queue adapters already exist.

The mobile baseline now imports shared colour/spacing/radius tokens and shared
UI primitives. Watchlist, History, and About are separate screen modules;
`App.tsx` fell from 1365 to 1091 lines without a visual or navigation rewrite.
The completion gate passed with 123 backend tests, mobile TypeScript, and Expo
Web export.

Supabase DDL remains unchanged by design. The accepted
[`ADR-0001`](../architecture/decisions/0001-staged-supabase-schema-and-queue.md)
assigns catalog changes to Phase 2, Debate business tables to Phase 3, and the
`pgmq` Queue migration to Phase 5.

## Boundaries that remain in force

- Educational explanations only; no personalised allocations, trading
  execution, buy/sell/hold instruction, guaranteed outcome, or price target.
- A dated factor or headline provides context, not proof that it caused a stock
  move.
- Normal UI/API reads use cached data and do not spend market-data provider
  requests.
- Secrets stay server-side or in the deployment secret manager and never enter
  the mobile bundle, queue payloads, logs, reports, or Redis values.
- The free deployment demonstrates architecture and graceful backpressure; it
  does not promise high availability, horizontal scale, or a production SLA.

## Current verification commands

```shell
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests -q
cd apps/mobile && npm run typecheck
cd apps/mobile && npm run build:web
```
