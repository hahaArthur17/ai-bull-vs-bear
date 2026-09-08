# Current Project Status

Last verified: 2026-09-08

This file is the concise implementation baseline. Historical work and commit
evidence live in [`reports/`](reports/README.md); material incidents live in the
[`issue-log.md`](issue-log.md).

Status values are `Done`, `In progress`, `Planned`, and `Blocked`.

Important: `Done` in the baseline below means that the corresponding code
path or contract has been implemented and covered by its recorded checks. It
does not mean that the final visual design, interaction review, native-device
acceptance, current-data release, or public-demo rollout is complete. Phase 8
remains an active product/UI remediation phase.

## Verified baseline

| Area | Status | Current state |
| --- | --- | --- |
| Mobile application | In progress | The functional Expo/React Native flow includes authentication, coverage-aware security search and Watchlist, stock research, Signals, Evidence Board, Debate, claim examination, History, and About. WP3 provides the Prototype-derived deep shell, WP4 the responsive research workspace, WP5 authoritative Debate fact/evidence projections, WP6 the chronological V2 chat, and WP7 the remaining core-screen migration. Integrated zoom/motion/accessibility review and native/physical-device acceptance remain open. |
| Backend API | Done | FastAPI exposes ranked catalog search, coverage, cached prices, indicators, macro context, evidence, watchlist, analysis, trace, token usage, and claim examination. The default-off V2 path adds Session, Message, Challenge, generation-scoped Cancellation, resumable SSE, optional durable Queue admission, and a backward-compatible server-authored fact/evidence presentation projection for canonical messages. |
| Authentication and persistence | Done | Supabase Auth, bearer-token verification, RLS, persistent watchlists, current-format analysis history, evidence, vectors, XBRL facts, price/macro caches, and the default-off V2 Debate schema/RPCs are implemented. |
| Market and evidence integrity | In progress | WP1 now validates strictly ordered, unique, completed positive closes; requires explicit provenance and 50 records for a complete technical view; reads the newest 100 Supabase rows; and makes failed or non-advancing daily refreshes exit nonzero. The actual hosted AAPL cache has not been refreshed or re-verified in this code-only package, so public-data integrity remains open. |
| Technical and macro exploration | In progress | WP4 now renders the 1M/3M daily and 6M/1Y weekly workspace with responsive measured charts, MA overlays, RSI, MACD, volume, volatility, seven dated macro series, per-series unavailable states, and explicit provenance. The deterministic `review_fixture` passes the 320/390/768/1280 Web state matrix; native-device and product-owner visual acceptance remain required. |
| Model adapters | Done | Deterministic, Groq, and Gemini adapters share a validated single-response Bull/Bear/Judge contract. Explanation independently defaults to deterministic and offers a bounded Groq provider behind explicit configuration; its one-request local verifier passed on 2026-08-29. The default-off async Groq Turn stream also passed one quota-controlled live Round 1. |
| Deployment | In progress | Render and Supabase services exist and the production provider remains deterministic, but the hosted frontend/backend are not yet proven to be the same release: the public API does not expose the current `/bundle` contract, and a staging deployment from one shared SHA plus smoke-test/rollback evidence is still required. |
| Automated verification | In progress | The 2026-09-08 WP8 baseline has 369 passing backend tests and 66 passing mobile tests; TypeScript, Expo Web export, and `git diff --check` also pass. WP4 browser evidence covers 320/390/768/1280 research charts and the data-state matrix; WP5/WP6 cover authoritative facts and the full V2 conversation; WP7 adds responsive Auth, Watchlist, Evidence, Examination, History, About, and Legacy verification. Reduced-motion transcript scrolling is implemented and unit-verified; browser preference, native simulator, physical-device, 200% zoom, staging, and current-data acceptance remain open. |
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
path plus a bounded optional Groq provider. Phase 7 is complete in its linear
interaction scope. Phase 8 is not complete: the active work is the
Prototype-based dark UI migration, chart and technical-indicator review,
chat-style V2 Debate transcript with visible facts/citations, deterministic
review fixtures, data/release integrity, staging proof, and native/physical
device acceptance. WP8 also has an open active-Debate recovery interaction:
the backend correctly returns `409` when the test user already has an
`awaiting_user` Debate, but the frontend feedback is distant from the Debate
action and offers no open-existing-Debate/History action. Product-owner page
checks can be performed from a concise checklist and fed back to engineering;
engineering owns reproduction, code changes, and automated evidence. Replay,
observability, resilience, and release proof follow this remediation; message
branching and arbitrary Web selection remain deferred backlog items. See the
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
- deploy frontend and backend from one SHA to staging, then collect visual,
  responsive, accessibility, native-simulator, physical-device, and rollback
  evidence before public-demo promotion.

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
