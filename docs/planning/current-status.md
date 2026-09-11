# Current Project Status

Last verified: 2026-09-12 (committed feature-code baseline `901cddb`; status
documents reconciled to the hosted and Live evidence below)

This file is the concise implementation baseline. Historical work and commit
evidence live in [`reports/`](reports/README.md); material incidents live in the
[`issue-log.md`](issue-log.md).

Status values are `Done`, `In progress`, `Planned`, and `Blocked`.

Important: `Done` in the baseline below means that the corresponding code
path or contract has been implemented and covered by its recorded checks. It
does not mean that the final visual design, interaction review, native-device
acceptance, current-data release, or public-demo rollout is complete. Phase 8
remains an active product/UI remediation phase.

## Current execution position

Phase 8 / WP8L.5 is after hosted interruption/Queue verification and before the
final full-model/device gates. Default-off Stop covers durable provider-attempt
accounting, before-output interruption, waiting state, persisted unconfirmed
recovery, interjection without model dispatch, explicit Continue/End, bounded
job retries, and read-only Explanation for a frozen incomplete prefix. Hosted
PostgREST/Queue, restart, ownership, idempotency and cleanup checks pass. The
2026-09-11 AAPL data preflight is current. A paced real-model run completed all
six cited Round 1 Turns, then exposed an oversized Interim Judge Prompt; the
Judge Prompt is now reduced 68.5% offline. A subsequent late-Round-2 Turn
projection also exposed insufficient request margin and is reduced from 31,127
to 16,289 characters offline. A subsequent current-SHA run completed five
paced Turns before a 334-character persisted rebuttal point exceeded the
next-request 300-character domain bound; that projection and failure-ledger
reporting are now fixed. A full two-round rerun and Expo Go remain. The ordered
remaining work and corrected boundaries are in
[`wp8l-next-steps.md`](wp8l-next-steps.md). Historical checkpoints below are dated
progress records, not the current outstanding-work list.

## Verified baseline

| Area | Status | Current state |
| --- | --- | --- |
| Mobile application | In progress | The functional Expo/React Native flow includes authentication, coverage-aware security search and Watchlist, stock research, Signals, Evidence Board, Debate, claim examination, History, and About. WP3 provides the Prototype-derived deep shell, WP4 the responsive research workspace, WP5 authoritative Debate fact/evidence projections, WP6 the chronological V2 chat, and WP7 the remaining core-screen migration. Integrated zoom/motion/accessibility review and native/physical-device acceptance remain open. |
| Backend API | Done | FastAPI exposes ranked catalog search, coverage, cached prices, indicators, macro context, evidence, watchlist, analysis, trace, token usage, and claim examination. The default-off V2 path adds Session, Message, Challenge, generation-scoped Cancellation, resumable SSE, optional durable Queue admission, and a backward-compatible server-authored fact/evidence presentation projection for canonical messages. |
| Authentication and persistence | Done | Supabase Auth, bearer-token verification, RLS, persistent watchlists, current-format analysis history, evidence, vectors, XBRL facts, price/macro caches, and the default-off V2 Debate schema/RPCs are implemented. |
| Market and evidence integrity | In progress | Distinct quote/close, current evidence, SEC facts and seven macro inputs are validated and frozen. The 2026-09-11 preflight found 115 completed daily rows through 09-10, 63 weekly rows, 13 news items, 4 filings, 155 financial facts, all seven macro series, and a positive Finnhub quote. Trading-calendar/release-lag edges remain open; this is not permanent freshness or complete statement coverage. |
| Technical and macro exploration | In progress | WP4 now renders the 1M/3M daily and 6M/1Y weekly workspace with responsive measured charts, MA overlays, RSI, MACD, volume, volatility, seven dated macro series, per-series unavailable states, and explicit provenance. The deterministic `review_fixture` passes the 320/390/768/1280 Web state matrix; native-device and product-owner visual acceptance remain required. |
| Model adapters | Done | Deterministic, Groq, and Gemini adapters share validated Bull/Bear/Judge contracts. Explanation independently defaults to deterministic and offers a bounded Groq provider. Live Turn output repeats an explicit citation contract after frozen data; both Turn and Judge inputs use bounded evidence/factor/transcript projections and an 800-Token default completion cap. A shared 61-second pacer respects the current Groq free 8K TPM envelope without Worker retries. |
| Controlled Live Acceptance | In progress | Stop, provider-attempt audit, waiting/recovery, interjection, Continue/End and incomplete-prefix Explanation have local coverage and hosted Supabase interruption verification. Current-SHA live Sessions found and fixed SSE ownership, exact transport replay, citation adherence, provider pacing and request-size bounds. The 2026-09-12 run completed five paced Turns with 13,366 reported Tokens, then exposed a persisted rebuttal-point projection mismatch before request six; `19b9d85` fixes that boundary and `901cddb` preserves failure-ledger reporting. One full twelve-attempt/two-Judge rerun and Expo Go acceptance remain open. |
| Deployment | In progress | Render and Supabase services exist and the production provider remains deterministic. `cf8b9e7` adds an explicit `APP_BUILD_SHA` value to `/health`, but it has not been deployed or used to prove the running backend revision. The project will not create an independent staging environment or require a static Web frontend release. The remaining release gate deploys the accepted SHA to the existing Render API and records smoke checks plus a reversible rollback target. |
| Automated verification | In progress | At committed feature-code baseline `901cddb`, the backend suite passes 516 tests; mobile currently passes 111 tests and TypeScript. Isolated PostgreSQL interruption/replay, hosted interruption/Queue checks, feature-enabled Web export and durable checkpoint batching pass. These checks do not establish native/device, full two-round Live AAPL, visual-owner or existing-Render release acceptance. |
| Phase 8 preservation baseline | Done | WP0 maps all required functional states to their implementation, existing automated evidence, missing manual proof, and later owner in [`phase-8-preservation-matrix.md`](phase-8-preservation-matrix.md). Representative 390/1280 Web characterization confirms the current warm UI, hidden AAPL charts, and Legacy card-style Debate; this evidence freezes regressions and is not design approval. |
| Phase 8 authentication UI | In progress | The Prototype-derived responsive single/two-panel Auth surface is implemented. Four-width Web inspection found no horizontal overflow; required/invalid state and label/description relationships are present in the Web DOM. Live-provider submission, native keyboard/screen-reader, simulator, and physical-device acceptance remain open. |
| Phase 8 Discovery and Watchlist UI | In progress | Coverage-aware search and the loaded-stock “Ready to review” summary now use the shared dark system and a responsive single/two-column layout. A local catalog-only MSFT search and four-width no-overflow check passed; persistence/reload, recovery-state, native, and product-owner acceptance remain open. |
| Native-device verification | In progress | The Android browser simulator pass is recorded, but Expo Go/native Android review, iOS review, and one physical-device pass remain open. See [`phase-8-verification-record.md`](phase-8-verification-record.md). |

The historical public verification on 2026-08-27 returned `200` from the
deployed frontend, returned a healthy production API with `provider=demo`, and
listed AAPL, GOOG, NVDA, and TSLA. It is retained as evidence of that release,
but does not close the current same-SHA, `/bundle`, freshness, or UI-acceptance
gaps described in the 2026-09-06 baseline.

## Current product limitations

These are limitations of the current implementation, not completed features:

- The deployed/mobile Debate remains one synchronous
  `POST /analysis/{ticker}` request. It returns one Bull claim, one Bear claim,
  and one Judge summary only after the full JSON response has been generated.
- A default-off V2 path now runs stateful mutual rebuttals and both rounds. With
  `DEBATE_QUEUE_ENABLED=false` it retains the synchronous deterministic preview;
  with the Queue flag enabled it atomically admits Round 1 and Round 2, returns
  `202`, and executes them in bounded background Workers. Production keeps both
  V2 flags disabled pending a deliberate production deployment smoke test and
  rollback plan; the hosted Queue migration, deterministic Worker/restart, and
  local live-provider checks are complete.
- V2 has a process-local SSE replay/heartbeat broker and the queued Worker can
  publish real async provider deltas. A feature-flagged V2 mobile screen now
  mounts the resumable client, renders Queue/retry/draft/canonical states,
  supports cancellation, and queues a selected-message Round 2 Challenge. A
  quota-controlled local Groq Round 1 produced six live Turns plus one local
  Judge, 697 ordered deltas, 11 citation links, and 6,980 recorded tokens.
  Complete messages remain durable; transient event replay is not
  cross-process.
- Default terminal Cancel remains available. Experimental Stop here is separately
  default-off and now freezes/retains an incomplete prefix in
  `interrupted_awaiting_user`, including before first output. The user can save
  an interjection without dispatching a model, explicitly Continue with a new
  generation, or End. Local pending-Stop recovery survives screen recreation;
  native kill/reopen, weak-network and hosted Queue acceptance remain open.
- V2 queued Interim/Final Judge now has an independent streamed provider and
  `judge.delta`, model/usage metadata, and completion checks. Its default remains
  deterministic. One synthetic Groq probe passed; the current-SHA full AAPL
  two-round/live-Judge/device flow remains unverified. Explanation stays separate.
- Deployed Claim Examination accepts four fixed question types. V2 accepts a
  free-form Challenge only at the Interim Judge pause. The context-bounded
  Explanation service is available through an authenticated default-off HTTP
  endpoint and its mobile panel is connected for exact terms in complete
  messages. It defaults to the credential-free deterministic provider; the
  bounded Groq provider is an explicit local/deployment selection, passed one
  local synthetic-message verification, and remains disabled in production. The
  mid-generation cancellation protocol is not yet reachable from the deployed
  screen.
- The hosted catalog now contains 7,695 searchable identities, but only the
  four curated `debate_ready` stocks have verified price, evidence, indicator,
  and Debate coverage. The other 7,691 rows remain Watchlist-only by design.
- Technical indicators, evidence types, and legacy model prompt inputs still
  use several fixed API schemas. Common `FactorProvider` contracts now build
  the V2 Session snapshot, so a future provider is additive at that boundary.
- Redis remains disabled in safe defaults and is not configured in production.
  Optional Redis/local adapters and public stock search/bundle caching now
  exist. Standard V2 requests can reuse only a public factor snapshot; custom
  questions bypass that shared cache. Per-user generation limits and the
  one-active-Debate rule and simultaneous duplicate-request lock are wired.
  The current quote remains outside the bundle response cache.
- The durable Queue is connected only to the default-off V2 Debate path. The
  public legacy `/analysis` path remains synchronous by design.
- Stock detail/charting, Evidence, Examination, Watchlist, History, About,
  Legacy Debate, and V2 Debate now live in screen modules. Shared Legacy Debate
  presentation (Claim Cards, Judge summaries, agent status, and evidence
  citations) lives in `src/components/debate/`; `App.tsx` retains app-level
  authentication, state, navigation, and API orchestration.

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

Documentation Phase 0, modular-boundary Phase 1, hosted Catalog Phase 2, Debate
persistence Phase 3, Queue/Worker Phase 5, and Redis/local Phase 6 are complete
in their recorded scopes. Phase 4 also passed its quota-controlled local Groq
streaming completion gate. Explanation now has a stable read-only mobile/API
path plus a bounded optional Groq provider. At the Interim Judge pause,
“Ask about this point” opens that educational path in a dismissible modal; only
a separate confirmation can queue Round 2. Phase 7 is complete in its linear
interaction scope. Phase 8 is not complete: the active work is the
Prototype-based dark UI migration, chart and technical-indicator review,
chat-style V2 Debate transcript with visible facts/citations, deterministic
review fixtures, data/release integrity, existing-backend release proof, and
native/physical device acceptance. WP8 has locally implemented the active-Debate recovery
interaction in `0e7c813`: the backend `409` is preserved, duplicate submissions
are protected, a nearby recovery card is shown, and the current Debate/History
actions are available. The local gate reports 370 backend and 80 mobile tests,
with typecheck and Web export passing. V2 transient proxy coverage for
reconnect/retry/cancel/failure is recorded in `8c9278c` with 15 passing tests.
Product-owner visual confirmation remains pending; Xcode/native simulator,
physical-device, and final visual acceptance are not complete. Product-owner
page checks can be performed from a concise checklist and fed back to
engineering; engineering owns reproduction, code changes, and automated
evidence. Replay, observability, resilience, and release proof follow this
remediation; message branching and arbitrary Web selection remain deferred
backlog items. See the
phase-specific work register in
[`phase-8-design-remediation.md`](phase-8-design-remediation.md).

### Phase 8 design-remediation baseline (2026-09-06)

The current implementation has substantial functional coverage, but the
product is not yet visually or operationally ready for final acceptance. The
active work register must preserve all existing feature behavior while
addressing these linked workstreams:

- migrate the application shell, navigation, cards, typography, colors, and
  motion to the Prototype HTML dark design system;
- reshape V2 Debate into a bounded chat-style transcript with Bull messages
  left, Bear messages right, and an Interim/Final neutral Judge summary in a
  centered panel rather than a stack of full-width agent boxes;
- render grounded facts and expandable citation details (source, date,
  freshness, and supporting passage) in completed Debate messages;
- add an explicit `review_fixture` mode that shows deterministic simulated
  chart/indicator/Debate states while clearly labeling them as simulated and
  never presenting them as market prices;
- align indicator calculations and availability thresholds across API and
  mobile, including partial-history behavior instead of an all-or-nothing
  chart gate;
- make refresh failures, stale caches, `/bundle` compatibility, and workflow
  exit status observable and release-blocking where appropriate; and
- run Expo Go from the accepted commit, deploy that commit to the existing
  Render API, and collect native/device plus backend health, migration, cold
  start, restart, smoke, and rollback evidence. An independent staging
  environment and static Web frontend release are outside this project scope.

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
upserts while preserving the four curated `debate_ready` records. On 2026-08-29
the coverage, search, and seed migrations were applied to hosted Supabase in
filename order after the database passed the capacity gate.

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

The catalog's stored text is 455,371 bytes. Before deployment the database was
23,727,251 bytes, safely below the 400 MB stop threshold. After deployment,
`stocks` measured 1,294,336 bytes of table data plus 4,513,792 bytes of indexes,
5,849,088 bytes total (about 5.7 MiB), below the 15 MiB budget. The whole
database measured 30,157,971 bytes. Anonymous ranked search returned MSFT for
`microsoft`, and the two-user Watchlist RLS/reconnect verifier passed all four
checks.

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
On 2026-08-29 both Debate persistence migrations were applied to hosted
Supabase. PostgREST exposes all five tables and both runtime RPCs. A disposable
two-user verifier proved owner reads across every table, hidden cross-user
reads, rejected authenticated writes and RPC calls, service-only atomic/
idempotent Session+Job and Message+citation writes, expected-status updates,
Intervention writes, and cleanup. This does not enable Queue transport or the
production V2 flags.

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

The 2026-08-29 quota-controlled local verifier then completed Round 1 through
six live `openai/gpt-oss-20b` Turns and a deterministic Judge. Seven canonical
messages, 697 ordered deltas, 11 citation links, cursor replay, canonical
reload, and 6,980 tokens passed. The reusable command caps each completion at
220 tokens, validates at 1,000 characters, and trims prior transcript inputs to
300 characters per message. Production selection remains disabled.

The mobile `DebateStreamClient` now parses fragmented SSE over an authenticated
XHR transport, maintains non-canonical draft text, replaces it only with a
complete server message, rejects sequence/delta gaps and late generations, and
reloads canonical Session/Messages at the recovery sequence advertised on a
`409`. Six Node tests cover parser, reducer, gap, late-generation filtering,
and cursor recovery behavior.
Commits: `b1ba884` and `7057628`.

Cancellation now rotates `active_generation_id` before acknowledgement,
publishes `session.cancel_requested`/`session.cancelled`, cancels queued Jobs
immediately, and makes running executors poll the canonical generation before
emitting or persisting. Both repositories reject new late-generation messages;
the Supabase transaction RPC takes a Session row lock for the same decision.
The mobile reducer clears cancelled drafts and ignores later old-generation
events. Controlled concurrency testing proves a provider completion released
after cancellation persists no message and never marks the Session failed.
Commits: `4caa46c`, `ca9cf45`, and `9f772cf`.

With Queue admission disabled, the selected HTTP preview still returns a
complete deterministic Turn before splitting it into labelled
`buffered_compatibility` chunks. With Queue admission enabled, the API returns
the Session/Job immediately and the bounded Worker selects the async Turn path.
The mounted default-off mobile V2 path understands queued, running, retry,
failed, cancelled, and terminal states and visually separates temporary drafts
from canonical complete messages.

### Phase 5 progress

The focused Queue migration enables a logged `pgmq` queue and provides
service-role-only functions for atomic Round 1/2 admission, claim, archive,
visibility-delay retry, and terminal settlement. Queue payloads contain only
versioned identifiers; protected snapshot and question content stay in the
canonical Debate tables. The migration is applied to the hosted Supabase
project and all seven functions are exposed only through the intended
server-side boundary.

The default-off API now returns `202 Accepted` for idempotent queued Round 1 and
Round 2 creation. A bounded Worker can run in the FastAPI lifespan or through
`python -m app.debate_worker_main`, resumes from already persisted turns,
classifies temporary provider failures, respects bounded `Retry-After`, safely
requeues with a visibility delay, recovers stale running jobs, and reaches a
safe terminal failure after the configured attempt limit.

Atomic repository transitions keep the Queue message and application Job
ledger consistent. Tests prove duplicate admission is idempotent, crash
redelivery does not duplicate completed messages, cancellation survives crash
recovery, retries resume from the next missing turn, and two Workers enforce
backpressure while a third submitted session remains queued. Job retry/failure
events and canonical active-job state are represented in the mobile stream
reducer. `7fddcc1` and `7be800d` mount the feature-flagged client, visible Job
state, cancellation, exact-passage Challenge form, queued Round 2, and the dark
financial-technology Debate timeline.

Phase 5 is complete in code and through the controlled hosted Supabase gate. A
fresh-client deterministic run admitted both rounds idempotently, produced the
13-message canonical transcript, recovered a running Job after visibility
retry with `read_count=2` and `attempt_count=2`, terminalized an exhausted Job,
and rejected all seven Queue RPCs for an authenticated user. Exact verifier
artifacts and their cascading Session data were removed; active and archived
Queue counts returned to zero. Production flags remain off until a deliberate
deployment smoke test and rollback plan.

The 2026-08-29 hosted preflight matched the configured Dashboard and API
project. The controlled Catalog, Debate persistence, and Queue deployments have
now passed their size, public-search, owner-RLS, client-write-rejection,
service-role, retry, and restart gates. PostgREST reports every required
surface as deployed and the preflight returns an empty migration list.

### Phase 6 progress

The Redis/local backend foundation provides TTL values, owner-scoped locks,
expiring counters, health state, strict remote timeouts, and a failure-open
local fallback. Redis URLs are excluded from settings representations and the
feature remains disabled by default. Commit `7058acd` contains this adapter
foundation.

The first hot-read slice adds a JSON response-cache boundary, hashed catalog
search keys, five-minute versioned stock-bundle keys, and `HIT`/`MISS`/
`BYPASS`/`DEGRADED` instrumentation. `GET /stocks/{ticker}/bundle` replaces the
mobile detail screen's seven API reads with one request while resolving the
optional current quote outside the cached public core. Tests prove repeated
reads avoid repository work and a cached bundle still refreshes the quote.

The second slice adds a six-hour cache for the normalized `FactorSnapshot`
used by the standard `question=null` V2 Debate. Its key hashes the exact
immutable public `AnalysisContext` and the ordered factor-provider contract, so
a provider version change creates a different entry. A custom question or
top-level context metadata always bypasses the shared cache. Tests across two
users prove only factor collection is reused: each request still creates
distinct canonical Session and Message IDs, and generated Debate text is never
cached.

The third slice adds hashed per-user admission keys, an atomic active-slot
reservation, a canonical non-terminal Session check, and a configurable
expiring generation counter. The default allows three new V2 admissions per
hour and one active Debate. Successful responses expose remaining capacity;
active conflicts return `409`, and limit exhaustion returns `429` with
`Retry-After`. Sequential queued idempotency retries reuse their deterministic
Session/Job without another count.

A fourth small slice adds an owner-scoped, TTL-bound idempotency lock around
queued `POST /debates` requests that carry a client idempotency key. Its cache
key hashes both the user and the client key. A competing request returns `409`
with `Retry-After: 1` before factor work begins; successful and failed owners
release safely, while expiry recovers abandoned locks. The lock TTL is
independently configurable and defaults to two minutes.

Redis remains coordination rather than canonical persistence. If it is
unavailable, deterministic Session/Job IDs, the service-only PostgreSQL
transaction advisory lock, and the unique `debate_jobs.idempotency_key`
constraint remain the final duplicate-admission fallback. The SQL contract
tests verify both database protections.

A fifth slice proves outage behaviour at the API boundary with every simulated
Redis operation timing out. Stock search still returns correct data and reuses
the process-local cache; queued duplicate submissions still resolve to one
canonical Session/Job and consume one admission. Both paths expose degraded
state without returning Redis errors. `GET /health/cache` reports only safe
mode, reachability, and degraded-operation counts, with an optional bounded
probe; it never returns the Redis URL, cache keys, or exception messages.

A reproducible in-process benchmark completes the sixth slice. Across 100
stock-search requests, the zero-delay profile reduced median latency from 3.787
ms uncached to 0.692 ms on a cache hit; a controlled 5 ms repository-delay
profile reduced it from 10.352 ms to 0.711 ms. Both profiles reduced repository
calls from 100 to 1. The method, p95 values, commands, and limitations are
recorded in [`project-week-15.md`](reports/project-week-15.md).

Phase 6 is complete in code and local verification. These in-process results
demonstrate the cache boundary and are not hosted Supabase/Redis measurements
or a production latency SLA.

### Phase 7 completion

The first Explanation slice adds immutable request/draft/result contracts, a
provider protocol, a credential-free deterministic provider, and a synchronous
service boundary. It accepts only an exact selection from a complete message
on the owned active branch, exposes only evidence already linked to that
message, applies financial-language guardrails, and hides provider failures.
Tests prove it leaves Session status/generation, the active Job, branch, and
canonical transcript unchanged. The authenticated, default-off HTTP boundary
now maps missing sources, invalid selections, and provider failures to safe
404, 409, and 503 responses without changing that state. Explanation now has a
separate per-user fixed-window admission limit, safe `429`/`Retry-After`
response, hashed cache key, and Redis-to-local fallback. Streaming events,
persistence, and arbitrary Web selection remain later slices. The mobile V2
screen now makes complete-message model terms accessible, validates the exact
selection locally, and opens an independent read-only Explanation panel; it
does not mutate the stream, Session, Job, generation, branch, or transcript.
V2 History now refreshes owner-scoped canonical Sessions, labels durable Final
Judge summaries, and reopens the corresponding transcript.

`EXPLANATION_PROVIDER=deterministic` remains the safe default. The independent
`groq` selection uses the existing server-only `GROQ_API_KEY`, sends only the
complete source message, exact selection/question, and that message's linked
evidence under public aliases, and rejects unknown aliases or oversized output.
Its one-request verifier is opt-in and is not run by automated tests. On
2026-08-29 it completed one local synthetic-message call through
`openai/gpt-oss-20b`: non-empty bounded output (625 characters), one linked
citation, and all request/evidence/term checks passed. The run printed neither
the generated text nor credentials and did not change production configuration.

The V2 interaction deliberately remains linear: Round 1 must reach
`awaiting_user` before a Challenge queues Round 2 on the active branch. The
selected message is a Challenge reference, not a transcript truncation point.
General message branching is deferred. If a future product requirement permits
Challenges during generation, the intended minimum design is to copy the last
complete-message prefix into a new branch with explicit provenance, rather
than introduce a general-purpose DAG.

The Phase 7 completion rule is met: the user can explain an exact term without
changing Debate state and can direct a grounded second round from the durable
Interim Judge pause. Arbitrary Web selection and generation-time branching are
deferred product enhancements, not gaps in this delivered interaction scope.

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

The following is deliberately excluded from automated verification because it
makes exactly one live Groq request; it needs both a local key and explicit
operator confirmation:

```shell
EXPLANATION_PROVIDER=groq PYTHONPATH=backend \
  backend/.venv/bin/python scripts/verify_groq_explanation.py \
  --confirm-live-quota
```

### 2026-09-09 incremental checkpoint

Offline Session/bundle consistency checking is implemented in
`scripts/verify_live_snapshot.py`; see the setup guide for input and limitations.
This does not complete server-side evidence/macro admission or live acceptance.
Reveal and streaming Judge work remains uncommitted and requires separate
integration and verification.

### 2026-09-09 live evidence admission checkpoint

Server-side live Turn admission now requires current, traceable news and filing
documents, recomputes freshness, rejects future dates, and freezes only eligible
citation IDs. Missing categories return 409 before quote lookup and Session/Job
creation. Structured financial facts and macro admission remain unfinished;
this checkpoint does not authorize or prove full Live Acceptance.

### 2026-09-09 macro admission checkpoint

Live Turn snapshots now require the seven configured daily macro series with
validated identity, provenance, chronology and age. Unavailable or inconsistent
macro context returns 409 before quote lookup and Session/Job creation.
Structured financial facts and live provider/device verification remain open.

### 2026-09-09 structured financial snapshot checkpoint

Live snapshots now load up to 200 ticker-scoped cached financial facts and freeze
up to 32 eligible SEC 10-K/10-Q observations. Selection checks SEC host/CIK/
accession path, typed periods, filing age (120 days), period age (450 days), and
storage provenance. Same-period revisions use the latest filing; conflicting
same-date values fail. Units/periods remain separate, and no ratio is inferred.
This establishes eligible context, not complete financial statement coverage.

### 2026-09-09 reveal scheduler checkpoint

The V2 client now paces English words and Unicode graphemes, keeps one visible
active bubble and prevents canonical completion from immediately replacing a
partial reveal. Explicit Show full, history/reconnect and accessibility/lifecycle
settlement are implemented. 91 mobile tests, typecheck and Web export pass.
Native verification and durable Stop/interjection remain open.

### 2026-09-09 streaming Judge checkpoint

V2 queued Interim/Final Judge now supports a separately selected asynchronous
provider and ordered `judge.delta`, validated completion, stored model/usage
metadata and job token aggregation. `DEBATE_STREAMING_JUDGE_PROVIDER` defaults
to deterministic independently of Bull/Bear. Groq Judge prose is model-generated;
structural risk/uncertainty labels remain server-authored. 424 backend tests pass.
One synthetic real-Groq probe succeeded (92 deltas, 612 tokens); it does not
establish standard AAPL or device acceptance. Durable interruption is next.

### 2026-09-09 real AAPL capture checkpoint

A controlled standard-mode capture passed all offline consistency checks using
100 cached daily rows, two eligible evidence documents and seven macro series.
Close date 2026-09-04 and quote timestamp 2026-09-08T20:00:00Z remain distinct.
One Apple RSS refresh wrote four documents; one Finnhub quote request supplied
the capture. Full filing text remains stored; the snapshot explicitly marks its
6,000-character bounded excerpt. This is input evidence, not a full model/device
session. Immediate interruption/interjection remains incomplete.


### 2026-09-09 — WP8L interruption foundation

Implemented default-off `DEBATE_INTERRUPTIONS_ENABLED`: checkpoint generated text before publishing each delta and accept an owner/generation-scoped `/debates/{id}/interrupt` request. The repository atomically rotates the generation, preserves the exact visible prefix as incomplete (including trailing whitespace), removes later messages and cancels queued jobs. Running workers acknowledge cancellation and retain observed request usage. Completed output can also be shortened when display is still catching up. Repeated identical requests are idempotent; invented prefixes and stale generations are rejected.

Validation: backend suite 434 passed (one existing Starlette/httpx deprecation warning); regression coverage includes API flag/ownership, exact prefix, late provider output, canonical completion before interruption, and repeat requests. No market or model calls in this step.

Limitations: SQL migration `20260909_debate_draft_interruption.sql` is authored but NOT applied or PostgreSQL-runtime validated. Checkpointing currently performs one synchronous persistence write per delta and needs hosted latency measurement. Client Stop here, user interjection and explicit continuation remain pending; this is not WP8L.5 acceptance. Feature stays disabled until migration and end-to-end checks pass.


### 2026-09-09 — WP8L client Stop here integration

Added default-off `EXPO_PUBLIC_DEBATE_INTERRUPTIONS_ENABLED`. While a message is revealing, Stop here freezes the last rendered prefix immediately, stops the local stream and submits that exact prefix to `/interrupt`. Failure keeps the display frozen and permits an identical retry; only a matching incomplete canonical response releases the local freeze. Reconnect, accessibility settlement, Show full and late provider completion cannot expand frozen text. Incomplete records explicitly say “Stopped here · Incomplete response” and render raw retained content without old full-text presentation sections.

Validation: mobile TypeScript check passed; 93 Node tests passed, including rendered-vs-received prefix and stale presentation regression; Expo Web export with the interruption flag enabled passed. This is build/unit verification, not browser or Expo Go device acceptance. No market/model calls or persisted environment changes.

Remaining: hosted migration/runtime verification, persistence latency, interruption before the first draft arrives, recovery of an unconfirmed stop after app termination, and user interjection/explicit continuation. The flag remains false in `.env.example`; do not claim the entire Stop here contract is complete.


### 2026-09-09 — interruption waiting state

Stop now persists `interrupted_awaiting_user` with no terminal timestamp and
publishes its own event. Terminal Cancel stays distinct and can explicitly end
the paused session. API/SSE/client types and labels recognize the waiting state;
Worker cancellation/recovery preserves it rather than treating it as a failed or
completed round. This state does not itself enable interjection or Continue.
Backend 435 tests and mobile typecheck pass; SQL runtime validation is ongoing
in isolation and the feature remains off. No live data/model calls.


### 2026-09-10 — isolated PostgreSQL and crashed Worker verification

Added `scripts/validate_debate_interruption_sql.sh` and SQL fixtures, using a
temporary local PostgreSQL 17 cluster over a Unix socket (no hosted writes).
Fixed the checkpoint RPC CASE-expression syntax found by execution. First and
repeat migration application, role/RLS isolation, foreign keys, prefix retention,
idempotence and checkpoint pruning pass. The runner supports PG_BIN discovery
and a TMPDIR containing spaces. Worker tests: 12 passed, including Stop followed
by process crash and lease redelivery; the old job is cancelled while the waiting
session and incomplete prefix survive. Per-message audit loss was confirmed and
is being addressed separately by the provider-attempt ledger, not declared fixed
by this migration test. Hosted PostgREST/Queue validation remains separate.


### 2026-09-10 — persisted unconfirmed Stop recovery

The mobile client now persists account/session-scoped pending Stop targets and
visible-message IDs before sending the network request, after freezing locally.
Reopening checks storage before starting SSE or displaying received text. It
restores only the saved visible prefix/history; exact incomplete canonical
confirmation clears the matching pending request. Logout/account changes clear
that account's pending records; stale confirmations cannot remove newer keys.
Empty prefixes, Unicode code-point bounds, corrupt/legacy records and prototype
keys are covered. Frozen drafts are labelled as unconfirmed Stop and cannot Show
full. A remote interruption event reloads the shortened canonical transcript.
Mobile tests: 105 passed; TypeScript passed; Expo Web export passed before the
final label-only refinement. Native kill/reopen is still user-operated acceptance.
No new external data/model calls and no hosted flags changed.

### 2026-09-10 — stream failure accounting

Rejected completed output retains its observed usage; interrupted streams close
the provider iterator and retain unknown usage when no report arrived. Twelve
stream contract tests pass. Provider-attempt persistence and explicit continuation
are being integrated separately; this checkpoint does not certify them.
