# Current Project Status

Last verified: 2026-08-28

This file is the concise implementation baseline. Historical work and commit
evidence live in [`reports/`](reports/README.md); material incidents live in the
[`issue-log.md`](issue-log.md).

Status values are `Done`, `In progress`, `Planned`, and `Blocked`.

## Verified baseline

| Area | Status | Current state |
| --- | --- | --- |
| Mobile application | Done | Expo/React Native flow includes authentication, coverage-aware security search and Watchlist, stock detail, Signals, Evidence Board, Debate, claim examination, History, and About. |
| Backend API | Done | FastAPI exposes ranked catalog search, coverage, cached prices, indicators, macro context, evidence, watchlist, analysis, trace, token usage, and claim examination. A default-off V2 preview adds Session, Message, Challenge, and resumable SSE event routes. |
| Authentication and persistence | Done | Supabase Auth, bearer-token verification, RLS, persistent watchlists, current-format analysis history, evidence, vectors, XBRL facts, price caches, and macro caches are implemented. |
| Market and evidence integrity | Done | AAPL uses a verified completed-close cache, current-source freshness rules, immutable evidence/macro snapshots, and dated citations. Missing current news lowers confidence instead of being silently replaced by demo narrative evidence. |
| Technical and macro exploration | Done | 1M/3M daily and 6M/1Y weekly price views, MA overlays, RSI, MACD, volume, volatility, and seven dated macro series are available. |
| Model adapters | Done | Deterministic, Groq, and Gemini adapters share a validated single-response Bull/Bear/Judge contract. Phase 4 also has a default-off, mock-verified async Groq Turn stream. |
| Deployment | Done | Render Free serves the static Expo Web site and one FastAPI web service; Supabase Free provides Auth and persistent data. Production deliberately uses the deterministic provider. |
| Automated verification | Done | 233 backend tests, 5 mobile stream tests, the mobile TypeScript check, and Expo Web export pass. The only backend warning is the existing Starlette/httpx test-client deprecation. |
| Native-device verification | In progress | Expo checks and Web export pass; physical iOS/Android testing remains. |

Public verification on 2026-08-27 returned `200` from the deployed frontend,
returned a healthy production API with `provider=demo`, and listed AAPL, GOOG,
NVDA, and TSLA.

## Current product limitations

These are limitations of the current implementation, not completed features:

- The deployed/mobile Debate remains one synchronous
  `POST /analysis/{ticker}` request. It returns one Bull claim, one Bear claim,
  and one Judge summary only after the full JSON response has been generated.
- A default-off V2 API preview now runs stateful mutual rebuttals and both
  rounds, but it is synchronous, deterministic, not connected to the mobile UI,
  and deliberately disabled in production.
- V2 has a process-local SSE replay/heartbeat preview, but POST execution is
  still synchronous and its HTTP deltas are buffered from a completed
  deterministic draft rather than streamed live from a model. A real async
  Groq Turn provider and a resumable mobile stream-client module now exist
  behind explicit boundaries, but neither is selected by the API or current
  Debate screen. There is no durable job queue, Worker lifecycle, cancellation
  protocol, or cross-process cursor.
- Deployed Claim Examination accepts four fixed question types. V2 accepts a
  free-form Challenge only at the Interim Judge pause; arbitrary term
  explanation and mid-generation interruption are not implemented.
- The 7,695-row catalog, ranked search function, and coverage columns are
  implemented in repository migrations but have not yet been applied to the
  hosted Supabase project. Hosted production therefore still exposes its
  previously deployed four-stock data until that controlled migration.
- Technical indicators, evidence types, and legacy model prompt inputs still
  use several fixed API schemas. Common `FactorProvider` contracts now build
  the V2 Session snapshot, so a future provider is additive at that boundary.
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

Documentation Phase 0 and modular-boundary Phase 1 are complete. Phase 2
behaviour is implemented and verified locally; its remaining gate is the
controlled hosted Supabase migration, size measurement, and RLS verification.

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

Phase 1 left Supabase DDL unchanged by design. The accepted
[`ADR-0001`](../architecture/decisions/0001-staged-supabase-schema-and-queue.md)
assigns catalog changes to Phase 2, Debate business tables to Phase 3, and the
`pgmq` Queue migration to Phase 5.

### Phase 2 progress

[`ADR-0002`](../architecture/decisions/0002-sec-static-stock-catalog.md) selects a
bounded, checked-in SEC ticker/exchange snapshot as the stock identity catalog.
It will be refreshed manually rather than queried during search, so search has
no runtime SEC or market-data cost. Country and sector are not inferred from the
source; imported non-demo symbols begin as `catalog_only`.

The reviewed 2026-08-27 snapshot contains 7,695 Nasdaq, NYSE, and CBOE tickers
from 10,388 SEC associations and records the raw source checksum. Snapshot
generation validates source shape, duplicate tickers, provenance, and the
10,000-row safety bound.

Repository DDL now adds nullable classification fields, CIK, aliases/search
text, four explicit coverage states, indexed search, ranked search RPC, and
public-read RLS. A generated migration seeds all 7,695 rows in 16 bounded
upserts while preserving the four curated `debate_ready` records. The migrations
have not yet been applied to the hosted Supabase project.

`DemoStore` searches the versioned snapshot without external calls.
`SupabaseStore` treats successful Supabase results—including an empty result—as
authoritative, calls the ranked catalog RPC, and falls back to the same
versioned snapshot only when the repository is unavailable. Search is limited
to 25 results and tested to perform zero external SEC or market-data requests.

The API exposes explicit coverage and prevents unsupported work: a
`catalog_only` identity can be opened and saved to Watchlist; prices/history are
empty, quote is null, evidence is empty, indicators and analysis are rejected,
and no synthetic analysis is substituted. The mobile UI debounces server
search, labels Watchlist-only results, and renders an identity/coverage page
without requesting the stock bundle.

The catalog's stored text is 455,371 bytes. Its table and indexes are estimated
at 3.9–6.9 MiB, with a conservative 15 MiB deployment budget—3% of the current
500 MB Supabase Free database quota. The feature remains in scope. Deployment
must stop if the existing database is already above 400 MB or the measured
catalog relation exceeds 15 MiB after migration.

### Phase 3 completion

The repository now has a separate V2 Debate persistence migration for
`debate_sessions`, `debate_messages`, `debate_message_evidence`,
`debate_interventions`, and the application `debate_jobs` ledger. It includes
allowed-state and lifecycle constraints, cross-table owner foreign keys,
idempotent message/job keys, Worker query indexes, explicit grants, and RLS on
all five tables. Authenticated clients can read only their own Debate records;
writes require the server-only service role.

Two service-only Postgres functions provide transaction boundaries for the
operations that cannot safely be split across REST calls: creating the initial
Session+Job pair and appending one complete message with its citations. They do
not enable or call the durable Queue; that remains Phase 5.

`InMemoryDebateRepository` and `SupabaseDebateRepository` implement the same
database-independent unit-of-work contract. Tests cover atomic/idempotent
writes, optimistic session/job states, immutable snapshots, citation sequence
conflicts, owner-scoped reads, safe remote failures, and current versus legacy
Supabase secret headers.

The deterministic provider and `DebateOrchestrator` now execute and persist the
complete Phase 3 path: six mutually aware Round 1 messages, Interim Judge,
`awaiting_user`, one idempotent user Challenge, four Round 2 messages, Final
Judge, and terminal Session/Job state. Every rebuttal request is tested against
the latest opponent message. Provider failure preserves completed messages,
records attempted provider calls, and exposes only `debate_execution_failed`.
Re-executing a completed Job or resubmitting the same domain Challenge causes
no duplicate provider work.

`DEBATE_WORKFLOW_V2=false` is now wired through local/test/example/Render
configuration. When explicitly enabled, authenticated `POST /debates`, Session
list/detail, Message list, and Challenge endpoints use the canonical
repositories and deterministic orchestrator. Round 1 returns seven complete
messages in `awaiting_user`; Challenge persists the user question and returns a
13-message completed Session after Round 2. Responses explicitly say
`synchronous_preview`; disabled routes return `404` and remain absent from
OpenAPI. Coverage gates, owner isolation, invalid selections, and unchanged
legacy `/analysis` behavior are covered at API level.

Phase 3 is complete in code with commits `3c921b6`, `e0635e0`, and `6f6d0d7`.
The Debate migrations are checked in but not applied to hosted Supabase. They
must not be described as live persistence until the Phase 2 catalog preflight
and the new Debate RLS/service-role verification are completed.

### Phase 4 progress

A bounded `InMemoryDebateEventBroker` now assigns monotonic per-Session
sequences, retains at most 256 events for each of 128 recent Sessions, supports
blocking wait and cursor replay, and emits unbuffered heartbeat control frames.
The orchestrator publishes Job, Turn, buffered delta, citation, Judge, safe
failure, and terminal Session events without making this transient path
canonical or allowing its failure to block persisted work.

The default-off authenticated SSE endpoint enforces Session ownership, supports
`after_sequence` and `Last-Event-ID`, closes on the current stage terminal event,
and returns `409` when a cursor has fallen behind the bounded buffer. Tests
reconstruct complete messages from ordered deltas, verify sensitive provider
failures never enter events, and cover heartbeat, owner isolation, resume, and
canonical-reload behavior. Commits: `03627b5`, `cfac90d`, and `82e2374`.

The async per-Turn contract now preserves exact delta whitespace, requires
contiguous chunk indexes and one normal completion, records validated usage,
and rejects truncated, inconsistent, over-length, wrongly targeted, or
out-of-snapshot results. `WholeDraftTurnStreamAdapter` keeps blocking legacy
providers off the event-loop thread, while
`DeterministicStreamingDebateProvider` exercises the native async protocol with
zero tokens. The async orchestrator publishes deltas immediately, aggregates
Turn token usage into the Job, and persists only after stream collection and
validation. An interrupted stream leaves temporary deltas plus a safe failure,
but no incomplete canonical message. Commits: `5209db1`, `cfc5dfa`, and
`149a7ed`.

The first real adapter now uses Groq's async Chat Completions stream with
`openai/gpt-oss-20b`. It sends bounded plain prose rather than streamed JSON,
maps public `[E1]` aliases to frozen server-side evidence IDs, withholds a
cross-chunk guardrail window, rejects missing/invalid citations and abnormal
finishes, and owns confidence/signal/risk metadata on the server. Selection is
independent through `DEBATE_STREAMING_PROVIDER`, which defaults to
`deterministic`; all automated tests use a fake client and consumed no quota.
Commits: `77c33c4` and `a6529c3`.

The mobile `DebateStreamClient` now parses fragmented SSE over an authenticated
XHR transport, maintains non-canonical draft text, replaces it only with a
complete server message, rejects sequence/delta gaps and late generations, and
reloads canonical Session/Messages at the recovery sequence advertised on a
`409`. Five Node tests cover parser, reducer, gap, late-generation filtering,
and cursor recovery behavior.
Commits: `b1ba884` and `7057628`.

The selected HTTP preview still returns a complete deterministic Turn before
splitting it into labelled `buffered_compatibility` chunks. The client module is
not mounted in `App.tsx`, because the current POST does not return a Session ID
until generation has already finished. Cancellation and a durable Queue/Worker
start path remain the next integration boundaries.

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
(cd apps/mobile && npm run typecheck)
(cd apps/mobile && npm run test:stream)
(cd apps/mobile && npm run build:web)
```
