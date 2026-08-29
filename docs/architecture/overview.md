# Architecture overview

Last reviewed: 2026-08-29

This document distinguishes the implemented baseline from the accepted target.
The detailed phase order and acceptance criteria live in the canonical
[`portfolio-implementation-plan.md`](../planning/portfolio-implementation-plan.md).

## Implemented baseline

The project is organized as a small monorepo:

    apps/mobile  ->  FastAPI  ->  DemoStore or Supabase
                         |
                         +-> indicators
                         +-> evidence retrieval
                         +-> Bull / Bear / Judge / Guardrail workflow

## Implemented runtime modes

### Demo mode

Demo mode is the default. The API creates deterministic cached OHLCV data and
serves curated evidence for AAPL, GOOG, NVDA, and TSLA. It keeps the mobile
flow reproducible and does not require credentials.

### Persistence mode

Supabase `schema.sql` defines the tables, pgvector storage, grants, and row-level
security policies needed for persistent watchlists, analyses, agent outputs,
evidence, price/macro caches, structured financial facts, and token usage. The
deployed production API uses Supabase; `DemoStore` remains the credential-free
local/test fallback.

### Model-provider mode

The analysis service uses the deterministic provider by default and can select
Groq or Gemini through ANALYSIS_PROVIDER. The provider adapters return a
validated Bull/Bear/Judge JSON draft, filter evidence IDs to the retrieved
corpus, record token usage, and pass all user-facing text through the guardrail
policy before it reaches the user.

### Phase 1 factor foundation

The backend now has immutable, database-independent factor contracts, a
validating `FactorRegistry`, and a `TechnicalFactorProvider` that normalizes the
existing indicator calculation. Macro, news, filing, and structured
financial-fact adapters now use the same snapshot contract. A test-only provider
proves additive registration. The default-off V2 preview now freezes these
current inputs into each Debate Session without changing the legacy synchronous
API response.

Database and Queue changes follow
[`ADR-0001`](decisions/0001-staged-supabase-schema-and-queue.md); no hosted DDL
is changed during the initial factor work.

### Phase 1 Debate domain foundation

The database-independent domain layer now validates Debate sessions, ordered
messages, citations, user interventions, jobs, identifier-only Queue payloads,
and versioned stream events. Deterministic plans encode six Bull/Bear turns plus
an interim Judge in round one and four rebuttal turns plus a final Judge in
round two. One state-transition service owns all legal session changes.

Repository and turn/Judge provider protocols are implemented. Phase 3 adds the
local V2 API and repository adapters described below; Phase 5 now connects the
optional Queue/Worker transport described below.

The mobile boundary has also started moving out of the original single-file
implementation. Shared design tokens and base UI components are centralized,
and Watchlist, History, and About are standalone screens. This refactor retains
the existing appearance and behaviour; the financial-technology redesign
remains Phase 8 work.

### Phase 2 catalog foundation

The repository contains a reviewed, versioned SEC ticker/exchange snapshot and
deterministic generators for both the snapshot and its Supabase seed. Catalog
DDL adds CIK, nullable classification, aliases/search text, explicit coverage,
search indexes, a ranked search RPC, and public-read RLS. The generated seed
contains 7,695 catalog identities and preserves the four curated
`debate_ready` rows on conflict.

`DemoStore` searches the checked-in snapshot. `SupabaseStore` uses Supabase as
the authoritative catalog when available and falls back to that snapshot only
on repository failure. Search results are bounded to 25 and never query the SEC
or a market-data provider at runtime. Successful empty Supabase results remain
authoritative rather than being replaced with demo rows.

Coverage gates allow any known catalog identity to be saved to Watchlist while
returning no prices, quote, evidence, technical analysis, or Debate for
`catalog_only` rows. The mobile client performs debounced API search, displays
coverage, and opens a catalog identity page without loading a stock-data bundle.

The migrations were applied to the hosted project on 2026-08-29. The 7,695-row
Catalog passed its 15 MiB relation budget, anonymous ranked search, and the
existing two-user Watchlist RLS/reconnect verifier; Phase 2 is complete.

### Phase 3 Debate persistence foundation

Repository migrations now define the five canonical V2 Debate tables and
service-only transaction functions. The application job ledger is deliberately
separate from the Phase 5 Queue transport. Authenticated users receive owner-scoped
read policies only; the API/Worker will write through a server-only secret.

Both the credential-free in-memory adapter and the Supabase adapter implement
`DebateUnitOfWork`. Session/Job creation and Message/citation insertion are
atomic and idempotent, while updates use expected-status filters plus shared
domain validation. The five tables and two transaction RPCs were deployed on
2026-08-29. A disposable two-user hosted verifier passed owner isolation,
authenticated write rejection, service-only writes, idempotency, state updates,
and cleanup. The separate Queue transport was subsequently deployed and
verified while runtime feature flags remained default-off.

The deterministic orchestration runtime now executes the existing plans through
the repository and credential-free Turn/Judge provider. Stable message IDs,
expected-status writes, and provider-input validation make completed jobs and
Challenges idempotent; safe failure preserves the canonical partial transcript.

`DEBATE_WORKFLOW_V2=false` is now the explicit default. When deliberately
enabled, authenticated Session, Message, and Challenge routes run the complete
deterministic two-round workflow synchronously and return canonical completed
messages with citations. The preview is hidden from OpenAPI and returns `404`
while disabled. The legacy `/analysis` path is unchanged.

This is an integration seam, not the final transport: it returns `201` only
after the deterministic stage finishes and labels responses
`synchronous_preview`.

Phase 4 now adds a bounded process-local event broker and authenticated SSE
preview. The orchestrator publishes ordered lifecycle, buffered text, citation,
Judge, and terminal events; complete messages remain canonical. SSE supports
sequence cursors, `Last-Event-ID`, heartbeats, owner isolation, and an explicit
canonical-message reload response when the transient cursor is too old.
Buffered deltas are labelled and are not represented as live model tokens.

The next Phase 4 layer now exists behind that transport: an async per-Turn
Provider protocol emits whitespace-preserving ordered deltas followed by one
validated completion. A whole-draft adapter keeps existing providers usable
without blocking the event loop, while a zero-token deterministic async
provider exercises the native contract. The async orchestrator publishes each
arriving delta, accounts for Turn token usage, and writes a message only after
the complete text, finish reason, output bound, rebuttal target, and evidence
IDs validate. Interrupted streams leave no incomplete canonical message.

The first live implementation uses Groq `AsyncGroq` with a current
`openai/gpt-oss-20b` default. It streams plain user-facing prose; evidence IDs,
rebuttal targets, confidence/signal metadata, risk meaning, citation validation,
and financial guardrails remain server-owned. This avoids exposing partial JSON
and respects Groq's current incompatibility between Structured Outputs and
streaming. Selection is independent and defaults to deterministic.

A quota-controlled local run on 2026-08-29 exercised that adapter through the
real Queue/Worker orchestration boundary: six live Turns plus a deterministic
Judge produced seven canonical messages, 697 ordered delta events, 11 valid
citation links, safe cursor replay/canonical reload, and 6,980 recorded tokens.
The verifier bounds each completion to 220 tokens and trims transport-only
transcript excerpts; production selection remains disabled.

The first Phase 7 Explanation boundary is intentionally separate from Debate
orchestration. An `ExplanationService` reads an owned Session and one complete
active-branch message, requires an exact source selection, limits evidence to
that message's canonical citation links, applies financial-language
guardrails, and returns a panel result through an injected provider. It does
not create a Job, append a message, rotate a generation, or transition Session
state. Its authenticated default-off HTTP boundary is now wired and is
independently admission-limited to 12 requests per user per 3,600-second window
by default, using a hashed `rate:explain` cache key and a safe local fallback.
The mobile client now has the typed authenticated request
boundary. Complete-message term chips now open a separate, read-only panel;
Explanation deliberately does not enter the event stream or canonical
transcript. V2 History reloads owner-scoped canonical Sessions, labels completed
Round 2 entries with their durable Final Judge, and reopens their transcript.
The Explanation provider selection is independent and defaults to deterministic.
The explicit Groq implementation sends only the source message, selected text,
question, and message-linked evidence under server-owned aliases; its one-call
local verifier remains opt-in and production stays deterministic.

The mobile layer now has an authenticated XHR SSE transport and reducer. Deltas
remain temporary by message/generation, a completion replaces them with the
canonical message, gaps trigger a canonical reload, and expired cursors resume
from the server-advertised latest sequence. The default-off V2 screen mounts
this integration boundary. Cancellation rotates the Session generation,
clears matching mobile drafts, ignores late old-generation events, and checks
status/generation again inside the atomic complete-message write. Queued Jobs
cancel immediately; an executing Job settles when it observes the invalidated
generation.

Phase 5 adds a logged Supabase Queue migration, atomic Round 1/2 enqueue RPCs,
identifier-only transport messages, bounded lifespan and standalone Workers,
and async `202 Accepted` admission. Visibility timeout, retry classification,
bounded `Retry-After`, completed-turn resume, terminal failure, cancellation
recovery, and two-Worker backpressure are covered by automated tests. The
mobile reducer also understands queued/running/retry/failed Job events.

A default-off V2 screen now mounts live mobile/Web consumption, shows transient
drafts separately from canonical messages, renders Job/retry/failure states,
exposes generation-scoped cancellation, and queues Round 2 from an exact
passage selected in a complete message. The same screen also has a separate
read-only Explanation panel; cross-process transient-event reconnect remains
later work. Redis cache/coordination is
complete in code and local verification. The
catalog, Debate, and Queue migrations were applied to hosted Supabase on
2026-08-29; a disposable two-round Queue run passed idempotency, retry,
restart, exhaustion, authorization, and cleanup gates. Production still keeps
V2 and Queue flags disabled pending a deliberate rollout.

### Phase 6 public response-cache foundation

The optional cache boundary now has Redis and process-local adapters for TTL
values, owner locks, and expiring counters. Strict Redis timeouts and a
failure-open local fallback keep canonical repository reads available. Redis is
disabled by default and is never the source of truth.

`GET /stocks` caches bounded catalog results under hashed normalized-query
keys for 30 minutes. `GET /stocks/{ticker}/bundle` replaces seven mobile detail
reads with one response and caches its public core for five minutes. The current
quote is resolved outside that bundle cache. Both endpoints expose
`X-Cache-Status`.

The standard V2 Debate path now hashes its exact immutable public
`AnalysisContext` plus the ordered factor-provider names, versions, required
flags, and expected categories. It can reuse the resulting `FactorSnapshot` for
six hours. Eligibility requires `question=null` and empty top-level context metadata.
Arbitrary questions always bypass the shared cache, and canonical Sessions,
Messages, Jobs, history, and generated agent text remain per-user repository
records.

The admission boundary now hashes user IDs before constructing Redis/local
keys, atomically reserves one active slot, checks canonical non-terminal
Sessions, and increments a configurable expiring per-user counter before factor
or model work. The default is three new V2 generations per hour and one active
Debate. A cache TTL cannot bypass the canonical Session check. Sequential
queued idempotency replays are recognized from their deterministic
Session/Job records and do not consume another slot. A simultaneous
duplicate-request lock uses Redis when available and deterministic database
uniqueness as the outage fallback.

## Implemented single-response data flow

1. The mobile client requests supported stocks and the user's watchlist.
2. Stock detail requests cached OHLCV, calculated indicators, and evidence.
3. An analysis run retrieves and ranks evidence for the user's question.
4. Technical, news, and filing context is aggregated into Bull and Bear claims.
5. The Judge produces a neutral summary with uncertainty and risk level.
6. Guardrails check language and the API returns claims, citations, trace, and
   token usage.
7. Cross-examination requests use the claim ID to return focused explanations
   and the relevant evidence.

## Accepted portfolio target

The next milestone remains a modular monolith but adds clear domain and process
boundaries:

```text
Expo client -> FastAPI API -> Supabase canonical data
                    |             `-> durable Debate Queue
                    |-> Redis cache, rate limits, idempotency locks
                    `-> bounded Worker -> Factor Registry
                                       -> Bull/Bear/Judge/Explainer
                                       -> streamed Debate events
```

The free deployment initially runs the API and bounded Queue consumer in the
same FastAPI service. The Worker also receives a standalone entry point so the
consumer can move to separate compute later without changing the Debate domain
or provider contracts.

Target responsibilities:

- `FactorProvider` adapters normalize the existing technical, macro, news,
  filing, and financial-fact inputs. No new live factor source is part of this
  milestone.
- Supabase remains the source of truth for sessions, jobs, complete messages,
  citations, interventions, history, and immutable snapshots.
- Supabase Queues now provides the implemented, default-off transport for
  durable admission, retry, visibility timeout, and backpressure for Debate
  stages; its hosted migration and deterministic lifecycle verification pass.
- Redis accelerates hot reads, rate limits expensive work, and coordinates
  duplicate-request locks. It is not the canonical Queue or history store.
- Authenticated SSE-formatted events stream the active turn. Complete validated
  messages are persisted so a reconnect can recover without storing every token.
- Catalog search is independent of market-data providers. A stock can be
  watchlist-only while full Debate remains restricted to `debate_ready` symbols.

## Target Debate flow

1. Create an authenticated session and immutable factor/evidence snapshot.
2. Enqueue a round-one stage and return `202 Accepted`.
3. The Worker produces six mutually aware Bull/Bear messages and an interim
   Judge summary while the client receives streamed events.
4. Persist each completed message and pause at `awaiting_user`.
5. An explanation request leaves the session state unchanged; a Challenge
   creates an intervention and queues Round 2 on the active linear branch.
6. Enqueue round two, produce four grounded messages and a final Judge summary,
   then mark the session complete.
7. Retry/redelivery resumes from the next missing planned turn, and Redis plus
   database uniqueness prevents duplicate submissions and outputs.
