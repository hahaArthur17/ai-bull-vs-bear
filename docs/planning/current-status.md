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
| Automated verification | Done | 78 backend tests and the mobile TypeScript check pass. The only backend warning is the existing Starlette/httpx test-client deprecation. |
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
  fixed schemas. Existing technical, macro, news, filing, and financial-fact
  data are present, but there is no common `FactorProvider` extension contract.
- Redis is not configured. The current quote cache is process-local and other
  persistent cached data is read from Supabase.
- No durable message queue is connected to the analysis request path.
- Most mobile UI and navigation logic remains in one large `App.tsx`, making a
  consistent financial-technology visual redesign harder to maintain.

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
and first coding task are canonical in
[`portfolio-implementation-plan.md`](portfolio-implementation-plan.md).

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
```
