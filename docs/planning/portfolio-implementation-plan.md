# Portfolio Implementation Plan

Last reviewed: 2026-08-29

Status: Active

Purpose: Canonical plan for the next development milestone

This is the only active implementation checklist for the portfolio milestone.
It translates the accepted product discussion into concrete architecture,
contracts, sequencing, tests, and completion criteria. Read
[`current-status.md`](current-status.md) first so planned behaviour is not
mistaken for implemented behaviour.

## 1. Portfolio objective

Build a demonstrable, technically honest system that proves the project can:

- orchestrate a stateful, evidence-grounded Bull/Bear debate;
- stream progress and generated text to the user;
- queue long-running AI work with durable retry and backpressure;
- use Redis for measurable cache, rate-limiting, and idempotency benefits;
- accept user explanations and debate interventions;
- search a zero-cost stock catalog independently of market-data API calls;
- keep the current factor set while allowing future factors to be added behind
  a stable extension contract; and
- present the experience with a coherent financial-technology design system.

The milestone demonstrates engineering knowledge and a complete workflow. It
does not claim production-scale availability during a real market event.

## 2. Scope and non-goals

### In scope

- Existing AAPL, GOOG, NVDA, and TSLA data and current live/cache providers.
- A common factor contract wrapping current technical, macro, news, filing, and
  financial-fact inputs.
- A durable Supabase Queue for Debate stage jobs.
- A Redis-compatible remote cache for hot reads, rate limits, and locks.
- Persisted Debate sessions, messages, citations, jobs, and interventions.
- Three Bull/Bear exchanges in round one, an interim Judge summary, a user
  question, two exchanges in round two, and a final Judge summary.
- Server-to-client streaming with reconnect-safe completed messages.
- An Explanation Agent for selected terms and passages.
- A clear distinction between explanation, intervention, and cancellation.
- A searchable symbol catalog with explicit data-coverage status.
- Live AI and deterministic/replayed demonstration modes using the same client
  event contract.
- Observability and failure tests that make Queue and Redis behaviour visible.

### Not in scope

- Integrating additional live factor, sentiment, analyst, options, social, or
  alternative-data providers in this milestone.
- Real-time trading data, order execution, portfolios, price targets, or
  personalised financial advice.
- Kafka, RabbitMQ, Celery, Kubernetes, microservices, multi-region failover, or
  horizontal autoscaling for their own sake.
- Promising a production SLA or unlimited peak traffic on free services.
- Supporting a full live Debate for every searchable symbol.
- Replacing the existing immutable evidence/freshness contract.

## 3. Accepted product decisions

These decisions are defaults. Change them only with an explicit product reason
and update this document in the same commit.

### 3.1 Debate length

Round one contains three exchanges and six agent messages:

1. Bull opening argument.
2. Bear rebuttal and risk case.
3. Bull counterargument addressing Bear.
4. Bear counterargument addressing Bull.
5. Bull closing position without introducing unsupported evidence.
6. Bear closing position without introducing unsupported evidence.
7. Neutral interim Judge summary.

Round two begins only after a user question and contains two exchanges:

1. Bull answer to the user question.
2. Bear rebuttal to Bull and the user question.
3. Bull counterargument.
4. Bear closing response.
5. Neutral final Judge summary.

The fixed order keeps tests and classroom demonstrations deterministic. Store
`opening_side` so a future version can alternate the opening side without
changing the message model.

### 3.2 Explanation versus intervention

- **Explain** opens or updates an explanation panel. It does not change the
  Debate state and does not cancel a generation.
- **Challenge the debate** records a user intervention. It requests cancellation
  of any active turn, closes the current branch at the last complete message,
  and starts the user-question round from that durable point.
- **Cancel** ends the session and does not start a new branch.

Provider cancellation is best effort. The UI must stop showing cancelled
generation events immediately, while late provider chunks are discarded by
`generation_id` even if the provider has already consumed tokens.

### 3.3 Search and coverage

- Symbol discovery and company-name lookup use a local/Supabase catalog and do
  not call Alpha Vantage, Finnhub, SEC, or an LLM.
- A catalog symbol can be added to a watchlist even when it has no cached market
  data.
- Only `debate_ready` symbols can start a live Debate.
- The initial full-Debate set remains AAPL, GOOG, NVDA, and TSLA, subject to the
  existing freshness and cache rules.
- The UI never substitutes a synthetic price for an unsupported catalog symbol.

### 3.4 Demonstration modes

- **Live AI** uses the real Queue, Worker, provider adapter, persistence, SSE,
  and Redis path.
- **Demo Replay** emits a sanitized, versioned saved Debate through the same
  event contract with controlled delays. It must be visibly labelled replay.
- Deterministic local tests use the same state machine and event types without
  spending provider calls.

## 4. Target architecture

Keep a modular monolith. Separate modules and process entry points, but do not
split repositories or services before deployment needs justify it.

```text
Expo Web / React Native
  |-- stock search, watchlist, detail reads --------------------------|
  |-- POST debate / intervention / explanation -------------------|  |
  |-- authenticated streamed events <----------------------------|  |
                                                                  |  |
FastAPI modular application                                      |  |
  |-- Catalog API ------------------------------------------------|--|
  |-- Debate API -> Job Producer -> Supabase Queue                |
  |-- Stream API <-> in-process event broker                      |
  |-- Worker consumer -> Debate Orchestrator                      |
  |                         |-- Factor Registry                   |
  |                         |-- Bull/Bear/Judge/Explainer         |
  |                         |-- Guardrails and citation checks    |
  |                         `-- Groq/Gemini/Demo providers        |
  |                                                              |
  |-- Redis adapter: cache, rate limits, idempotency locks -------|
  `-- Supabase repository: canonical sessions, messages, jobs,
      watchlists, snapshots, citations, history, and Auth/RLS
```

### 4.1 Deployment shape

For the zero-cost portfolio deployment:

- Render Static Site continues to serve the Expo Web export.
- One Render Free FastAPI service exposes HTTP/SSE and starts a bounded Worker
  consumer in the application lifespan.
- The Worker implementation also has a standalone command entry point so it
  can move to an independent worker later without changing orchestration code.
- Supabase remains canonical persistence and hosts the durable queue.
- Upstash Redis or another Redis-compatible free service is optional by
  configuration; the app retains safe local/database fallbacks.

The same-process Worker is an explicit free-deployment compromise, not a claim
that the queue increases CPU capacity. It demonstrates durable admission,
retry, recovery, and separation of producer/consumer responsibilities.

### 4.2 Required module boundaries

Target backend modules:

```text
backend/app/
  api/
    stocks.py
    debates.py
    streams.py
    explanations.py
  domain/
    factors.py
    debate.py
    events.py
    jobs.py
  services/
    factor_registry.py
    debate_orchestrator.py
    debate_worker.py
    event_stream.py
    explanation.py
    cache.py
    rate_limit.py
  repositories/
    debate_repository.py
    catalog_repository.py
    queue_repository.py
  providers/
    analysis_model.py
    demo_model.py
    groq_model.py
    gemini_model.py
```

This is a target boundary, not a requirement to move every existing file in one
commit. Refactor incrementally while current tests remain green.

Target mobile modules:

```text
apps/mobile/src/
  screens/
  components/
    finance/
    debate/
    feedback/
  features/
    stocks/
    watchlist/
    debate/
    explanations/
  theme/
    tokens.ts
    typography.ts
    components.ts
  api/
    client.ts
    debateStream.ts
```

## 5. Factor extensibility design

No new live source is added in this milestone. The goal is to make future
sources additive rather than invasive.

### 5.1 Domain contract

```text
FactorObservation
  id                    stable within an analysis snapshot
  ticker
  factor_key            e.g. technical.rsi, macro.vix, filing.risk
  category              technical | macro | company | fundamental | other
  provider              stable provider/adapter identifier
  label
  as_of
  value                 typed JSON-compatible value
  unit                  optional
  interpretation        descriptive, non-predictive text
  direction             supportive | cautionary | mixed | neutral | unknown
  confidence            low | medium | high
  freshness             existing freshness structure
  source_refs           evidence IDs or structured source references
  metadata              provider-specific, bounded JSON
  provider_version
```

`category` stays broad and stable. `factor_key` and `provider` are extensible
strings; do not add a database enum or CHECK constraint for every future factor.

### 5.2 Provider contract

```python
class FactorProvider(Protocol):
    name: str
    version: str

    def collect(self, context: AnalysisContext) -> list[FactorObservation]:
        ...
```

`FactorRegistry.collect(context)` calls registered providers, validates their
outputs, records provider-specific failures, and returns one immutable factor
snapshot. Debate prompts consume only this normalized snapshot.

Initial adapters wrap existing behaviour:

- `TechnicalFactorProvider`
- `MacroFactorProvider`
- `NewsFactorProvider`
- `FilingFactorProvider`
- `FinancialFactsProvider`

The existing typed indicator endpoints remain available for chart rendering.
The generic factor contract is the orchestration boundary, not a reason to
replace useful typed UI responses with unstructured JSON.

### 5.3 Factor failure rules

- One optional provider failure does not fail the complete collection.
- Missing categories are recorded in the immutable session snapshot.
- Freshness is evaluated before Debate generation.
- A provider cannot invent evidence IDs or claim causation.
- Numerical questions use structured facts and explicit units/periods.
- The same stored factor snapshot is reused for all turns in one Debate branch;
  later ingestion never rewrites a completed session.

### 5.4 Extension proof

Add a test-only `MockSentimentFactorProvider`. Registering it must make the
factor available to the orchestrator without changing the orchestrator, model
provider interface, session repository, or existing provider implementations.
This is the acceptance proof for future extensibility; no real sentiment source
is added.

## 6. Stock catalog and watchlist design

### 6.1 Catalog fields

Extend the stock catalog with:

```text
ticker
company_name
exchange
sector
country
aliases/search_text
is_active
coverage_status
coverage_updated_at
```

Allowed initial `coverage_status` values:

- `catalog_only`
- `price_cached`
- `evidence_ready`
- `debate_ready`

Coverage is capability metadata, not a statement that data is current. Existing
per-response source and freshness fields remain authoritative.

### 6.2 Search behaviour

- Enhance `GET /stocks?q=<query>&limit=<n>` to search ticker, company name, and
  normalized aliases in the local/Supabase catalog.
- Debounce the mobile request and require a small minimum query length for
  company-name search; exact ticker search can execute immediately.
- Limit results and rank exact ticker, ticker prefix, company prefix, then
  substring matches.
- Cache normalized search results, but make catalog search correct without
  Redis.
- Do not call a market-data provider from the search request path.

### 6.3 Watchlist behaviour

- Any catalog stock can be added or removed.
- A catalog-only row opens a profile/coverage screen rather than a fake Signals
  page.
- The primary Debate action is enabled only for `debate_ready`.
- Search results and watchlist rows display coverage explicitly.

### 6.4 Initial catalog size

Start with a checked-in or migration-seeded, bounded US-symbol catalog suitable
for the classroom demonstration. Record its source and update date. Do not add
an automated live symbol-provider dependency merely to enlarge the list.

## 7. Debate domain and persistence

### 7.1 Session states

```text
created
queued_round_1
running_round_1
awaiting_user
queued_round_2
running_round_2
completed
cancel_requested
cancelled
failed
```

State transitions are validated in one domain service. API routes, Worker code,
and UI code must not independently invent transitions.

### 7.2 New tables

#### `debate_sessions`

- id
- user_id
- stock_id
- mode: `live`, `demo`, or `replay`
- status
- opening_side
- initial_question
- active_branch
- active_generation_id
- factor_snapshot JSONB
- price/evidence snapshot JSONB or a versioned reference to the existing
  immutable snapshot
- interim_judge JSONB
- final_judge JSONB
- guardrail_status
- error_code, containing a safe classification only
- created_at, updated_at, completed_at

#### `debate_jobs`

- id
- session_id
- user_id
- job_type: `round_1`, `round_2`, `explanation`, or `replay`
- status: `queued`, `running`, `completed`, `failed`, or `cancelled`
- idempotency_key, unique
- queue_message_id
- attempt_count
- max_attempts
- available_at
- started_at, finished_at
- safe_error_code
- provider_request_count
- prompt_tokens, completion_tokens, total_tokens

#### `debate_messages`

- id
- session_id
- branch_id
- generation_id
- sequence_number
- round_number
- exchange_number
- role: `bull`, `bear`, `judge`, `user`, `explainer`, or `system`
- message_kind: `argument`, `rebuttal`, `summary`, `question`, or `explanation`
- content
- confidence/signal metadata where relevant
- is_complete
- cancelled_at
- created_at
- unique `(session_id, branch_id, sequence_number)`

#### `debate_message_evidence`

- message_id
- evidence_document_id or immutable external evidence ID
- citation_order
- optional quoted/support span metadata
- unique `(message_id, evidence reference)`

#### `debate_interventions`

- id
- session_id
- user_id
- selected_message_id
- selected_text or selected term, length-bounded
- question
- mode: `explain` or `challenge`
- created_at

Apply RLS so users read and create records only for their sessions. The Worker
uses a server-only secret to claim jobs and write generated outputs. Never put a
user JWT, provider key, raw authorization header, or server secret in a queue
message.

### 7.3 Legacy compatibility

- Keep current `/analysis` endpoints and stored current-format analyses during
  migration.
- Add the new Debate API alongside the old path behind
  `DEBATE_WORKFLOW_V2` until acceptance tests pass.
- Do not fabricate new multi-turn messages for legacy single-response analyses.
- History can label legacy items as `single_analysis` and new items as
  `multi_turn_debate`.
- Remove the old UI path only in a focused, reversible commit after the new
  workflow passes local and deployed smoke tests.

## 8. Agent orchestration contract

Every Bull/Bear turn receives:

- the immutable price, evidence, macro, and factor snapshot;
- the initial question and current user intervention, if any;
- all complete prior messages in the active branch;
- the immediately preceding opponent statement highlighted as the rebuttal
  target;
- allowed evidence IDs and citation rules;
- previously used core points so the model avoids repetition;
- turn role, round, exchange, and maximum output length; and
- guardrail, uncertainty, and non-causation instructions.

Every Bull/Bear turn must:

- directly address at least one material point from the opponent when a prior
  opponent message exists;
- distinguish evidence from interpretation;
- cite only allowed evidence IDs;
- state uncertainty;
- avoid buy/sell/hold and personalized advice; and
- stay within a bounded output length suitable for streaming and classroom
  viewing.

The Judge receives the same immutable snapshot plus the complete branch
transcript. It must summarize agreements, strongest disagreements, evidence
quality, missing evidence, and uncertainty without declaring a winning trade.

The Explainer receives only the selected term/passage, its containing message,
the minimal relevant evidence, and the educational boundary. It does not alter
the Debate transcript unless the user separately chooses `challenge`.

Use one underlying model with role-specific prompts when appropriate. Describe
the result accurately as stateful multi-agent orchestration, not independently
trained autonomous models.

## 9. Streaming contract

### 9.1 Transport

Use authenticated HTTP streaming from FastAPI. The first implementation uses
SSE-formatted events consumed through `fetch` so the bearer token can remain in
the header. Hide platform differences behind a `DebateStreamClient`; do not
scatter parsing logic across screens.

### 9.2 Event envelope

Every event uses a versioned envelope:

```json
{
  "version": 1,
  "event_id": "uuid-or-monotonic-id",
  "session_id": "uuid",
  "sequence": 12,
  "type": "turn.delta",
  "timestamp": "ISO-8601",
  "payload": {}
}
```

Required event types:

- `session.created`
- `job.queued`
- `job.started`
- `job.retry_scheduled`
- `job.failed`
- `turn.started`
- `turn.delta`
- `turn.citation`
- `turn.completed`
- `judge.started`
- `judge.completed`
- `session.awaiting_user`
- `explanation.started`
- `explanation.delta`
- `explanation.completed`
- `session.cancel_requested`
- `session.cancelled`
- `session.completed`
- `session.failed`
- `heartbeat`

### 9.3 Persistence and reconnect

- Do not write every token to Supabase or Redis.
- Buffer deltas for the connected client and persist the complete validated
  message at turn completion.
- A reconnect first loads the canonical session and complete messages, then
  attaches to new events.
- Send a heartbeat on a bounded interval so proxies and clients can identify a
  dead stream.
- If the Worker dies mid-turn, the incomplete generation is discarded and the
  idempotent job resumes from the next missing planned turn after queue
  redelivery.
- `generation_id` prevents late chunks from a cancelled/retried turn from being
  rendered or persisted as current output.

## 10. Queue design

Use Supabase Queues/`pgmq` as the durable broker. One queue message represents
one bounded stage, not one token or one agent message.

### 10.1 Job types

- `round_1`: six Bull/Bear messages plus interim Judge.
- `round_2`: four Bull/Bear messages plus final Judge.
- `explanation`: one selected-term/passage explanation when asynchronous
  processing is useful.
- `replay`: optional controlled event playback; this may remain local to the
  API if queueing adds no demonstrable value.

### 10.2 Queue message payload

```json
{
  "schema_version": 1,
  "job_id": "uuid",
  "session_id": "uuid",
  "job_type": "round_1",
  "trace_id": "safe-random-id",
  "enqueued_at": "ISO-8601"
}
```

The payload contains identifiers only. The Worker reloads protected content
from Supabase after it claims the message.

### 10.3 Producer rules

- Validate authentication, coverage, input length, and rate limit first.
- Create the session/job and enqueue through one database RPC/transaction where
  possible so an orphan job or orphan session is not created.
- Generate a deterministic idempotency key before enqueueing.
- Return `202 Accepted` with session ID, job ID, state, and approximate queue
  position; do not hold the initial request open for model completion.

### 10.4 Consumer rules

- Default global live-generation concurrency is one on the free deployment;
  make the limit configurable with an upper demo cap of two.
- Claim with a visibility timeout longer than the measured maximum stage time;
  begin with 15 minutes and revise from observed duration.
- Reload the session and planned turns before every attempt.
- Skip already completed turns, making whole-stage redelivery idempotent.
- Respect provider `Retry-After` where available.
- Ack/archive only after durable stage completion.
- Retry temporary network, 429, and 5xx failures with bounded backoff.
- Mark permanent validation/safety failures without retry.
- After three failed attempts, mark the job/session failed with a safe error
  code and preserve the job for diagnostics.
- Recover stale `running` job rows on startup using queue visibility and the
  database ledger rather than assuming in-memory tasks survived.

### 10.5 Queue acceptance evidence

Tests and a manual demonstration must prove:

- several submissions remain queued while only the configured concurrency runs;
- a claimed job reappears after a simulated Worker crash/visibility timeout;
- redelivery does not duplicate messages or token-ledger records;
- temporary provider failure retries and then succeeds;
- a permanent failure reaches a visible terminal state; and
- queue state survives an API process restart.

## 11. Redis design

Redis is an optimization and coordination layer. Supabase remains canonical.

### 11.1 Adapter

Define a small `CacheBackend`/`CoordinationBackend` contract with:

- `get`, `set`, `delete`
- `acquire_lock`, `release_lock`
- atomic increment with expiry
- optional health/metrics information

Implement Redis and local fallback adapters. Set strict network timeouts so a
cache outage does not stall the API.

### 11.2 Initial keys and TTLs

| Key pattern | Purpose | Initial TTL |
| --- | --- | ---: |
| `cache:stock-search:v1:{query_hash}` | Normalized catalog result | 30 minutes |
| `cache:stock-bundle:v1:{ticker}:{data_version}` | Hot stock detail reads | 5 minutes |
| `cache:standard-debate:v1:{snapshot_hash}` | Reusable standard-question factor snapshot only | 6 hours |
| `lock:debate:v1:{idempotency_hash}` | Duplicate job prevention | 20 minutes |
| `active-debate:v1:{user_hash}` | One active live debate per user | 20 minutes, renewed while active |
| `rate:debate:v1:{user_hash}:{window}` | Live Debate admission | window length |
| `rate:explain:v1:{user_hash}:{window}` | Explanation admission | window length |

Hash normalized values; never place a raw free-form question, email address,
access token, or user financial information in a Redis key.

### 11.3 Initial portfolio limits

- One active live Debate per user.
- Three newly generated live Debates per user per hour.
- Thirty explanation requests per user per hour.
- Replay and cached-result viewing do not consume the live-generation limit.
- Limits are configuration, not hard-coded product facts.

### 11.4 Cache correctness

- A stock bundle key includes a data version or latest cache timestamp.
- A standard Debate cache key includes the immutable snapshot hash.
- Do not share/cache arbitrary user questions across users.
- Do not cache canonical Sessions, Messages, Jobs, history, or generated Debate
  text at this shared boundary.
- On Redis failure, stock/search reads fall through to Supabase.
- Database unique constraints remain the final idempotency guard.
- If Redis rate limiting is unavailable, use a bounded in-process fallback and
  record degraded status; do not expose a raw Redis error to the user.

### 11.5 Redis acceptance evidence

- Return/log `HIT`, `MISS`, `BYPASS`, and `DEGRADED` without leaking key data.
- Compare repeated request latency and repository/provider call counts with
  cache enabled and disabled.
- Prove duplicate clicks create one canonical Debate job.
- Prove the API still returns correct data when Redis is unavailable.
- Do not use Redis as the only store for jobs, sessions, messages, or history.

## 12. API target

Keep the current API stable while adding:

```text
GET    /stocks?q=&limit=
GET    /stocks/{ticker}/coverage

POST   /debates
GET    /debates
GET    /debates/{session_id}
GET    /debates/{session_id}/messages
GET    /debates/{session_id}/events
POST   /debates/{session_id}/explanations
POST   /debates/{session_id}/interventions
POST   /debates/{session_id}/cancel
```

### `POST /debates`

Request:

```json
{
  "ticker": "AAPL",
  "question": null,
  "mode": "live",
  "idempotency_key": "client-generated-uuid"
}
```

Response: `202 Accepted`

```json
{
  "session_id": "uuid",
  "job_id": "uuid",
  "status": "queued_round_1",
  "queue_position": 1,
  "stream_path": "/debates/uuid/events"
}
```

### Explanation request

```json
{
  "message_id": "uuid",
  "selected_text": "moving average",
  "question": "What does this mean here?"
}
```

### Intervention request

```json
{
  "message_id": "uuid",
  "question": "Does the filing risk outweigh the momentum argument?"
}
```

All user text is length-bounded, normalized, authenticated, and treated as
untrusted input. Evidence text is also untrusted prompt content; delimit it and
prohibit embedded instructions from changing system policy.

## 13. Mobile interaction and UI plan

### 13.1 Component refactor

Before the visual redesign:

- extract each screen from `App.tsx`;
- isolate data fetching and session state into feature hooks/controllers;
- isolate chart components;
- introduce shared loading, empty, offline, error, and status components; and
- retain current behaviour through TypeScript and focused component tests where
  practical.

### 13.2 Design direction

- Deep navy/charcoal surfaces rather than the current warm-paper dominant
  palette.
- Restrained cyan/blue technology accent.
- Semantic Bull green and Bear red with icons/labels so colour is not the only
  distinction.
- Neutral Judge styling.
- Tabular or monospaced numerals for prices, dates, percentages, and indicators.
- Clear density hierarchy: market snapshot, evidence quality, debate messages,
  then trace/diagnostics.
- Subtle motion for streaming and status; avoid casino/trading-execution visual
  language.
- WCAG-conscious contrast, keyboard focus, screen-reader labels, and reduced
  motion support.

### 13.3 Debate experience

- Desktop/Web: readable debate timeline or two-sided layout without forcing
  equal-height columns.
- Mobile: chronological message timeline with explicit round/exchange labels.
- Stream only the active message; completed messages become stable cards.
- Show queue, generation, awaiting-user, cancelled, failed, and replay states.
- Display citations and evidence freshness per completed message.
- Provide separate `Explain` and `Challenge debate` actions.
- Start with model-provided `terms` as clickable spans/chips across platforms.
- Add arbitrary Web text selection after the term path is stable; treat native
  long-press selection as a later platform-specific enhancement.

### 13.4 Search/watchlist experience

- Debounced server-side search.
- Company name, ticker, exchange, sector, and coverage badge.
- Watchlist star works for catalog-only results.
- Catalog-only detail explains exactly what is and is not configured.
- No disabled feature is presented as a provider/API error.

## 14. Demo Replay design

- Store one sanitized, versioned replay fixture under `data/demo/`.
- The fixture contains no user identity, secret, raw token, or private question.
- It contains the same event envelopes emitted by Live AI, excluding real-time
  provider metadata that should not be replayed as current.
- Replay uses controlled timing and an obvious `REPLAY` label.
- The classroom script wakes the Render API, verifies `/health`, demonstrates
  search/watchlist, runs Replay for reliability, then optionally starts one Live
  AI session and shows queue/Redis diagnostics.
- Replay is a resilience feature, not a substitute for live integration tests.

## 15. Observability and portfolio evidence

### 15.1 Structured fields

Log safe structured fields:

- trace_id
- session_id
- job_id
- job_type
- attempt
- state transition
- queue wait milliseconds
- stage and turn duration
- provider model name
- provider request count
- token usage
- cache status
- retry/failure code

Do not log prompts, full user questions, JWTs, Redis credentials, provider keys,
or raw authorization headers.

### 15.2 Measurable demonstrations

Prepare commands or tests showing:

- uncached versus cached stock/search latency;
- cache hit rate and avoided repository calls;
- duplicate submission collapsing into one job;
- queue backpressure with several jobs;
- Worker crash and redelivery;
- Redis outage fallback;
- SSE event order and reconnect;
- user cancellation ignoring late chunks; and
- model calls/token use for round one, explanation, and round two.

### 15.3 Honest portfolio language

Accurate examples after implementation:

- “Implemented a durable asynchronous AI debate pipeline with Supabase Queues,
  bounded consumers, retry, visibility timeout, backpressure, and idempotent
  recovery.”
- “Added Redis-backed caching, rate limiting, and distributed duplicate-request
  locks with database fallbacks and measurable cache-hit behaviour.”
- “Built stateful Bull/Bear/Judge orchestration with evidence-constrained
  rebuttals, SSE streaming, user interventions, and resumable persisted turns.”
- “Designed a provider registry that normalizes technical, macro, news, filing,
  and financial facts while allowing future factor adapters without modifying
  the Debate orchestrator.”

Do not claim production-scale concurrency, separately trained agents, real-time
market coverage, or live Debate support for the full symbol catalog.

## 16. Security and safety requirements

- Server-only Supabase and Redis secrets remain in deployment secrets.
- Queue messages contain IDs only and never carry user/provider credentials.
- Worker writes are scoped to the job/session being processed.
- RLS tests cover both Debate reads and user-created interventions.
- All user input and retrieved evidence are untrusted prompt content.
- Citation IDs are filtered against the immutable allowed evidence set.
- Guardrails run per completed user-facing message and Judge/Explainer output.
- Rate limits protect expensive provider paths but do not block public cached
  stock reads unnecessarily.
- Cancellation and retries do not duplicate token ledger or citations.
- Error responses use safe codes and never include provider payloads or secrets.

## 17. Implementation phases

Complete phases in order unless the plan records a justified dependency change.
Only one phase should be marked `In progress` at a time.

### Phase 0 — Documentation baseline

Status: Done

- [x] Establish a canonical planning index and verified current-status file.
- [x] Archive superseded week-numbered plans and original MVP notes.
- [x] Add this canonical implementation plan.
- [x] Align architecture, API, agent, database, setup, and root documentation
  with current-versus-target terminology.
- [x] Verify local Markdown links.

Completion evidence: focused documentation commits, clean link check, backend
tests, and mobile typecheck. Documentation commits: `fd7bc52`, `5eab700`,
`bf901be`, `85df94e`, and `40ec318`.

### Phase 1 — Characterization and modular boundaries

Status: Done

- [x] Record the staged Supabase business-table and Queue migration decision;
  Phase 1 intentionally makes no hosted DDL change.
- [x] Add characterization tests for current analysis, history, watchlist,
  evidence snapshots, and provider adapters.
- [x] Define immutable factor domain models and validation rules.
- [x] Define domain models for sessions, messages, jobs, and events.
- [x] Introduce the `FactorProvider` protocol without changing runtime output.
- [x] Introduce Debate repository/provider protocols.
- [x] Add `FactorRegistry` and wrap the current technical-indicator calculation.
- [x] Wrap the current macro, news, filing, and financial-fact sources.
- [x] Add the test-only mock factor extension proof.
- [x] Begin extracting mobile screens and shared design tokens without a visual
  rewrite.

Progress evidence: `9374398`, `58c70f8`, `6b415a5`, `598eb3d`, `f689328`,
`191f65c`, `ab206bf`, `2183974`, `4831b22`, `554118f`, `22bacd3`, `330f1f9`,
`29d1251`, and `731844d`. All current factor categories and Debate domain
boundaries are implemented. Shared mobile tokens/components and the Watchlist,
History, and About screens are extracted without changing behaviour. At the
Phase 1 checkpoint the factor snapshot and state machine were not connected;
the completed Phase 3 preview now supplies that integration.

Completion rule: current API/mobile behaviour remains compatible and tests prove
a new factor provider is additive. Verified with 123 backend tests, mobile
TypeScript, and Expo Web export on 2026-08-27.

Suggested focused commits:

1. domain factor contract and validation tests;
2. current-source factor adapters;
3. mock-provider extension test;
4. Debate domain/event models;
5. mobile screen extraction with no visual change.

### Phase 2 — Catalog search and coverage-aware watchlist

Status: In progress

- [x] Choose and document a bounded static symbol catalog source.
- [x] Add catalog/coverage migration and seed data.
- [x] Make Supabase repository stock lookup authoritative instead of inheriting
  the four-item `DemoStore` catalog.
- [x] Implement ranked, limited server-side search.
- [x] Allow catalog-only watchlist persistence.
- [x] Add coverage badges and catalog-only detail state.
- [x] Keep Debate restricted to `debate_ready` symbols.
- [x] Prove search causes zero market-data provider requests.
- [ ] Apply the three catalog migrations to hosted Supabase only after the
  preflight size check; then record relation size and verify public-read RLS.

Completion rule: an unsupported catalog ticker can be searched, identified, and
saved without consuming a market-data call or showing synthetic analysis.

Source decision evidence:
[`ADR-0002`](../architecture/decisions/0002-sec-static-stock-catalog.md) selects a
versioned SEC ticker/exchange snapshot, filtered to Nasdaq, NYSE, and CBOE and
bounded to at most 10,000 rows. It is a securities identity catalog rather than a
claim of live price, evidence, or Debate coverage.

Implementation evidence: `c8fa984`, `f049a59`, `89b0044`, `f99c2da`,
`e1b088c`, `40c8fae`, `0977967`, `6a19c4c`, `e155fb3`, `4846b39`, `ae6e104`,
`e48a7de`, `4f870e3`, and `791bcc0`. The repository contains the validated
7,695-row snapshot, coverage/search DDL, idempotent seed, authoritative
repository paths, API coverage gates, regression proofs, and mobile catalog
flow. These migrations are prepared but not yet applied to the hosted Supabase
project.

### Phase 3 — Debate persistence and deterministic state machine

Status: Done in code; hosted migrations pending deployment verification

- [x] Add Supabase migrations and RLS for sessions, jobs, messages, citations,
  and interventions.
- [x] Add repositories and state-transition validation.
- [x] Implement deterministic round-one and round-two turn plans.
- [x] Persist every complete message and citation.
- [x] Implement interim and final Judge states using the demo provider first.
- [x] Add legacy-analysis compatibility and feature flag.
- [x] Prove Bull/Bear inputs contain the prior opponent message.

Completion rule: deterministic tests complete the entire two-round workflow,
including awaiting-user, without streaming or a live provider.

Implementation evidence: `7830a65`, `334e853`, `fb0c474`, `b1686dc`,
`d96bd46`, `3c921b6`, `e0635e0`, and `6f6d0d7`. The repository now
contains five constrained Debate tables, owner-read RLS, service-only writes,
transaction RPCs for Session+Job and Message+citations, an in-memory adapter,
and a Supabase adapter. Both adapters enforce optimistic state transitions and
idempotency. The deterministic provider/orchestrator now completes six Round 1
turns plus Interim Judge, pauses for a persisted Challenge, then completes four
Round 2 turns plus Final Judge. Tests inspect every request's latest-opponent
target and safe failure state. The default-off V2 preview exposes owner-scoped
Session, Message, and Challenge routes, freezes the current factor snapshot,
and completes both rounds through the same repositories. It is explicitly
synchronous and deterministic; the legacy `/analysis` contract is unchanged.
The migrations are prepared but not applied to hosted Supabase, so production
keeps `DEBATE_WORKFLOW_V2=false`.

### Phase 4 — Provider turn generation and SSE

Status: In progress

- [x] Refactor provider adapters from one full JSON draft to one bounded turn at
  a time while retaining a compatibility adapter for the old flow.
- [x] Add asynchronous streaming support to the chosen first live provider.
- [x] Implement the versioned event envelope and heartbeat.
- [x] Add authenticated Web/React Native stream client abstraction.
- [x] Validate/correct citations at turn completion.
- [x] Implement reconnect from canonical completed messages.
- [x] Add cancellation generation IDs and late-event rejection.

Completion rule: one local Live AI round streams in order, persists validated
messages, reconnects safely, and never exposes partial output as a completed
claim.

Progress evidence: `03627b5`, `cfac90d`, and `82e2374` add a bounded
process-local broker, ordered orchestration events, labelled buffered preview
deltas, authenticated SSE, heartbeat, owner isolation, sequence/Last-Event-ID
resume, and expired-cursor recovery through canonical messages. This does not
satisfy the completion rule yet: the HTTP preview still selects synchronous
whole-draft generation.

Additional evidence: `5209db1`, `cfc5dfa`, and `149a7ed` define the async
per-Turn stream/completion contract, preserve whitespace, provide whole-draft
and zero-token deterministic adapters, validate completion/length/target/
citations, account for tokens, and ensure an interrupted stream never persists
an incomplete message.

`77c33c4` replaces the retired Groq model default with
`openai/gpt-oss-20b` and keeps the independent Debate provider selector at
`deterministic`. `a6529c3` adds a real `AsyncGroq` Turn stream with bounded
plain-text prompts, server-owned evidence aliases/metadata, cross-chunk
financial guardrails, completion validation, safe errors, and mock-only tests.
It deliberately avoids Structured Outputs because Groq does not support that
mode together with streaming. `b1ba884` exposes the latest event sequence on
cursor expiry. `7057628` adds the authenticated XHR Web/React Native client,
fragment-safe SSE parsing, temporary draft state, canonical completion
replacement, generation filtering, cursor recovery, and the initial five Node
tests.

`4caa46c`, `ca9cf45`, and `9f772cf` add deterministic generation invalidation,
one-active-Job persistence constraints, an atomic Supabase late-write guard,
idempotent owner-scoped cancellation API, running-executor polling, safe Job and
Session settlement, and mobile cancellation reduction. A controlled async test
releases provider output only after cancellation and proves that no late
message, completion event, or failure state is produced.

With the Phase 5 Queue flag enabled, HTTP creation now returns before the
Worker selects the async Turn provider. This still does not satisfy the full
Phase 4 completion rule: no real Groq quota was consumed for a recorded live
smoke test. The client is now mounted behind a default-off flag and was locally
verified with the deterministic async Worker; production live-provider
selection is not claimed.

### Phase 5 — Durable Queue and Worker

Status: Done in code; hosted verification pending

- [x] Enable/configure Supabase Queues through a migration.
- [x] Implement atomic session/job creation and enqueue.
- [x] Implement the bounded Worker consumer and standalone entry point.
- [x] Move round-one/round-two execution behind queued stage jobs.
- [x] Add retry, visibility timeout, safe failure classification, and terminal
  job handling.
- [x] Add startup recovery and idempotent completed-turn checks.
- [x] Display queue/job status in the client.
- [x] Run crash, redelivery, duplicate, and backpressure tests.

Completion rule: the API returns `202`, several jobs queue, only configured
concurrency runs, and a crash/retry cannot duplicate a turn.

Progress evidence: `c00dc13` adds the logged `pgmq` migration, identifier-only
Queue transport, service-role-only atomic enqueue/claim/archive/retry RPCs, and
matching in-memory/Supabase repository adapters. `1b3393e`, `97127b0`, and the
intervening admission commits add a bounded same-process consumer, standalone
entry point, idempotent `202` Round 1 creation, and safe configuration defaults.

`f18ac80` through `2c6bca9` add retryable provider classification, atomic
Job/Queue retry settlement, bounded `Retry-After`, visibility-timeout crash
recovery, completed-turn resume, terminal failure, and cancellation recovery.
`fb5549c` repeatedly proves that two Workers run only two of three submitted
sessions while the third remains queued. `f240ce7` through `2c26702` add atomic,
idempotent queued Round 2 admission. `d340d40` and `a5c7688` expose active Job,
retry, and failure state through the API/event/mobile contracts.

All Queue behaviour is locally verified with deterministic/in-memory or mocked
Supabase boundaries. The migration has not been applied to hosted Supabase,
production flags remain off. `7fddcc1` and `7be800d` add canonical Session
state, mount the V2 client, render Queue/Worker/retry/failure/draft states,
expose cancellation, and queue Round 2 from an exact selected passage. Desktop
and 390px browser checks completed both deterministic rounds without console
errors. Hosted migration/RLS/restart verification is the remaining Phase 5
gate.

### Phase 6 — Redis cache and coordination

Status: In progress

- [x] Add Redis/local coordination adapters and configuration validation.
- [x] Cache stock search and stock bundle reads.
- [x] Add standard-Debate snapshot cache where privacy rules allow it.
- [x] Add per-user rate limits and one-active-Debate rule.
- [x] Add distributed idempotency lock with database unique fallback.
- [x] Add cache status instrumentation.
- [ ] Prove correct Redis-outage degradation.
- [ ] Record before/after latency and call-count evidence.

Progress evidence: `7058acd` adds Redis/local TTL, lock, and counter adapters,
strict timeouts, configuration validation, health state, and failure-open local
fallback. The first response-cache slice adds hashed 30-minute stock-search
entries, versioned five-minute public stock bundles, cache-status headers and
counters, and one mobile bundle request in place of seven detail reads. The
current quote remains outside the cached bundle core. API and unit tests prove
repeat reads avoid repository calls without caching raw query text.

The second slice caches only the normalized factor snapshot for
`question=null`, keyed by a digest of the exact immutable public analysis
context and ordered factor-provider contract. Custom questions and top-level
metadata return `BYPASS`. Cross-user tests prove Session, Message, Job, and
generated text records remain separate.

The third slice hashes user IDs, atomically reserves an active slot, checks the
canonical repository for non-terminal Sessions, and increments a configurable
expiring admission counter before expensive work. The default is three new V2
admissions per hour. `409`, `429`, remaining-capacity headers, bounded
`Retry-After`, terminal-session recovery, and sequential idempotency replay are
covered.

The fourth slice wraps queued creation requests that carry an idempotency key
in a configurable, owner-scoped lock before factor work begins. The key hashes
the user and client key; concurrent duplicates receive a retryable `409`, and
success, failure, or TTL expiry safely releases or recovers ownership.
Deterministic Session/Job IDs, the PostgreSQL transaction advisory lock, and
the unique Job idempotency key remain the canonical fallback when Redis is
disabled or degraded.

Completion rule: cache and locks create measurable effects, while disabling
Redis does not corrupt or disable canonical workflows.

### Phase 7 — Explanation, interruption, and round two

Status: Planned

- [ ] Render model-provided terms as clickable cross-platform elements.
- [ ] Implement context-bounded Explanation Agent requests.
- [ ] Keep explanations outside the Debate state transition.
- [x] Implement challenge/intervention persistence.
- [ ] Cancel or branch from the last complete message using generation IDs.
- [x] Enqueue and stream round two around the user question.
- [ ] Add final Judge summary and history rendering.
- [ ] Add arbitrary Web selection only after term explanation is stable.

Completion rule: the user can explain a term without stopping Debate or can
challenge the debate and receive a grounded second round.

### Phase 8 — Financial-technology UI redesign

Status: Planned

- [ ] Finalize design tokens, typography, semantic colours, spacing, elevation,
  and motion rules.
- [ ] Redesign authentication and home/search/watchlist.
- [ ] Redesign stock detail and charts without losing provenance/accessibility.
- [ ] Redesign Debate timeline, active streaming turn, Judge, evidence, queue,
  explanation, and failure states.
- [ ] Redesign History/About and diagnostic presentation.
- [ ] Test responsive Web, keyboard navigation, reduced motion, and screen-reader
  labels.
- [ ] Test iOS/Android simulator and one physical device.

Completion rule: all core states use the same reusable design system and pass
Web export/typecheck plus recorded visual/device review.

### Phase 9 — Replay, observability, resilience, and release proof

Status: Planned

- [ ] Capture and sanitize one versioned real Debate fixture.
- [ ] Implement labelled Replay through the shared event protocol.
- [ ] Add safe structured logs and job/cache metrics.
- [ ] Add a bounded burst/load script that never calls paid/live providers.
- [ ] Verify Queue backpressure and Redis caching with recorded measurements.
- [ ] Run full backend, mobile, export, RLS, restart, CORS, and production smoke
  checks.
- [ ] Update the current status, architecture, API contract, setup guide, and a
  new milestone report with commit evidence.
- [ ] Prepare a short classroom demo script and honest resume bullets.

Completion rule: a fresh clone can run deterministic verification; the deployed
demo can search/save a catalog symbol, replay a full Debate reliably, and run a
bounded Live AI path when quota is available.

## 18. Cross-phase test matrix

| Capability | Required proof |
| --- | --- |
| Factor extension | Mock provider appears without orchestrator modification. |
| Stock search | Catalog query uses no market/provider client. |
| Coverage | Catalog-only stock saves but cannot start Debate. |
| Debate rebuttal | Every rebuttal input includes the immediately prior opponent message. |
| Evidence safety | Invented citation IDs are removed/rejected per turn. |
| State machine | Invalid state transitions fail deterministically. |
| SSE | Ordered events, heartbeat, terminal event, reconnect, and error parsing. |
| Cancellation | Late generation events are ignored and no cancelled message becomes complete. |
| Queue | Backpressure, retry, redelivery, terminal failure, restart survival. |
| Idempotency | Duplicate HTTP submissions and queue deliveries create one canonical result. |
| Redis | HIT/MISS, expiry, lock contention, rate limit, and outage fallback. |
| RLS | User A cannot read or mutate User B's sessions/messages/interventions. |
| Legacy history | Old current-format analysis remains readable or explicitly labelled; incompatible rows do not break lists. |
| Guardrails | Every role, including Explainer and Judge, retains the educational boundary. |
| Replay | Same client reducer handles replay and live events, with visible mode label. |

## 19. Definition of done for the seven requested improvements

1. **Future factors:** current sources enter through `FactorProvider`; mock
   extension proves new providers are additive.
2. **Message queue:** a real durable queue handles Debate stages with visible
   job state, bounded consumers, retry, redelivery, and idempotency.
3. **Redis:** real remote Redis is used for cache, rate limiting, and locks with
   measurable effects and safe fallback.
4. **UI:** reusable financial-technology design tokens/components cover all core
   responsive and accessibility states.
5. **Debate:** round one has six mutually aware Bull/Bear messages and interim
   Judge; user input leads to four second-round messages and final Judge; output
   streams and persists.
6. **Interaction:** term explanation and user challenge are distinct, and a
   challenge can redirect an active session safely.
7. **Search/watchlist:** a zero-cost local catalog identifies additional
   symbols and saves them with explicit coverage; only verified symbols start
   Debate.

The milestone is complete only when all seven have automated or recorded
acceptance evidence. Adding a dependency or UI label alone does not count.

## 20. Documentation and commit discipline during implementation

For every focused change:

1. inspect current status and the active phase;
2. implement one bounded behaviour;
3. add or update proportional tests;
4. run the smallest relevant checks, then the full phase gate;
5. update the matching checkbox and completion evidence only when proven;
6. make one descriptive commit; and
7. avoid mixing refactors, schema migrations, UI redesign, and provider changes
   in the same commit.

When a phase completes:

- mark it `Done` and the next phase `In progress`;
- update [`current-status.md`](current-status.md);
- update affected architecture/API/database/agent/setup documents;
- add a milestone report with verification and commit IDs; and
- keep historical reports append-only.

## 21. Current coding entry point

Phase 2 behaviour is implemented and passes local acceptance tests. Before
declaring the hosted phase done, use the SQL Editor procedure in
[`live-services.md`](../setup/live-services.md): verify the current hosted
database is below 400 MB, apply coverage, search, and seed migrations in filename
order, measure the `stocks` relation against the 15 MiB budget, and rerun
public-read plus two-user Watchlist RLS checks.

Do not enable hosted Redis or Queue flags until that deployment gate is
recorded. Default-off code and local fallback work may proceed. Phase 3 is
complete in code: `DEBATE_WORKFLOW_V2=false` is the safe default, the
synchronous deterministic Session/Message/Challenge preview is covered by API
tests, and legacy `/analysis` remains compatible. Production remains disabled
because the checked-in Debate migrations have not been applied or verified on
hosted Supabase.

The cancellation boundary, Phase 5 Queue/Worker, and default-off V2 mobile
experience are implemented and verified locally. Phase 6 now has its
Redis/local adapter, public stock-search/bundle cache, and privacy-bounded
standard-Debate factor snapshot cache, per-user admission limits, and the
one-active-Debate rule. The next code-only slice is the distributed
duplicate-request lock with database uniqueness as the final fallback.
Independently,
apply the catalog, Debate, and Queue migrations to hosted Supabase in filename
order and record size/RLS/restart evidence before enabling hosted flags. Do not
claim Redis, hosted Queue durability, or cross-process transient-event replay
before those checks are complete.

## 22. Primary implementation references

Revalidate free limits and SDK details when the relevant phase starts; provider
quotas and platform behaviour can change after this plan is written.

- Supabase Queues: <https://supabase.com/docs/guides/queues>
- Supabase pricing and free-plan quotas: <https://supabase.com/pricing>
- Render Free limitations: <https://render.com/docs/free>
- Upstash Redis pricing: <https://upstash.com/pricing/redis>
- Groq streaming: <https://console.groq.com/docs/text-chat>
- Gemini streaming API: <https://ai.google.dev/api/generate-content>
- Alpha Vantage documentation: <https://www.alphavantage.co/documentation/>
