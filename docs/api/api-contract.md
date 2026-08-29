# API Contract

Last reviewed: 2026-08-29

Endpoints in the first section are implemented. The portfolio target is
explicitly marked planned and must not be presented as available before its
phase acceptance tests pass.

## Implemented API

### Auth

Supabase mode requires `Authorization: Bearer <access-token>` for user-owned
watchlist, analysis, and enabled Debate endpoints. Demo mode retains the local
credential-free fallback.

### Stocks

GET /stocks
Without a query, returns the active `debate_ready` stocks. Optional parameters:

- `q`: ticker, issuer name, or alias query, at most 40 characters;
- `limit`: 1–25 results, default 20.

Search is ranked by exact ticker, ticker prefix, exact alias, company prefix,
alias prefix, then substring. It reads the local/Supabase identity catalog and
does not call the SEC, a market-data provider, or a model provider. When Redis
response caching is enabled, `X-Cache-Status` is `MISS`, `HIT`, or `DEGRADED`;
the disabled default returns `BYPASS`.

GET /stocks/{ticker}
Returns a stock/security identity with nullable classification and explicit
coverage fields: `sec_cik`, `country`, `aliases`, `is_active`,
`coverage_status`, and `coverage_updated_at`.

GET /stocks/{ticker}/coverage
Returns `coverage_status`, `has_price_data`, `has_evidence`, and `can_debate`.
The initial status values are `catalog_only`, `price_cached`, `evidence_ready`,
and `debate_ready`.

### Watchlist

GET /watchlist
Returns user's watchlist.

POST /watchlist
Adds any known active catalog identity to Watchlist, including a
`catalog_only` identity.

DELETE /watchlist/{ticker}
Removes a stock from watchlist.

### Stock Detail

GET /stocks/{ticker}/prices
Returns cached daily OHLCV data. Every price point includes `source` with
`daily_market_cache` or `demo_fallback`, plus `is_stale`. A daily market cache
is populated from the configured provider (Alpha Vantage when available,
otherwise Finnhub); it is not an intraday quote. Returns an empty list for a
catalog-only identity.

GET /stocks/{ticker}/quote
Returns a current Finnhub quote when `FINNHUB_API_KEY` is configured, or `null`
when it is not available. The backend caches this response for 60 seconds. It
is displayed as a quote, never as a completed daily close. A catalog-only
identity returns `null` without calling the quote provider.

GET /stocks/{ticker}/indicators
Returns technical indicators when price coverage exists. A catalog-only
identity returns `409 Conflict`.

GET /stocks/{ticker}/evidence
Returns technical, news, and filing evidence. Supports an optional q query
parameter for Supabase vector retrieval with deterministic lexical fallback. A
catalog-only identity returns an empty list.

GET /stocks/{ticker}/bundle
Returns the stock identity, daily and weekly history, technical indicators,
evidence, applicable macro context, and the latest optional quote in one mobile
request. The public core is cached for five minutes when Redis is enabled; the
current quote is resolved after the cache read and is not stored in the bundle
cache. A catalog-only identity returns `409 Conflict`. `X-Cache-Status` uses the
same values as stock search.

### AI Analysis

POST /analysis/{ticker}
Starts a Bull vs Bear analysis only when the identity is `debate_ready`.
Unsupported coverage returns `409 Conflict` before any provider work.

GET /analysis/{analysis_id}
Returns analysis result.

GET /analysis
Returns analysis runs scoped to the authenticated user. Supabase mode persists
them across backend restarts.

GET /analysis/{analysis_id}/trace
Returns agent trace.

GET /analysis/{analysis_id}/tokens
Returns token usage.

### Cross Examination

POST /claims/{claim_id}/examine
Request body:

- question_type: explain_term | evidence_support | signal_strength | risk_meaning

Returns focused explanation.

### Default-off Debate V2

`DEBATE_WORKFLOW_V2=false` is the default. In that state all `/debates` routes
return `404` and are omitted from OpenAPI. Existing `/analysis` and claim
examination behavior is unchanged.

When the flag is deliberately enabled, these authenticated routes are
implemented:

```text
POST /debates
GET  /debates?limit=
GET  /debates/{session_id}
GET  /debates/{session_id}/messages
GET  /debates/{session_id}/events
POST /debates/{session_id}/interventions
```

Create request:

```json
{
  "ticker": "AAPL",
  "question": "Which dated factors support each side?",
  "opening_side": "bull",
  "idempotency_key": "classroom_demo_001"
}
```

For the standard request with `question=null`, the server may reuse the public
normalized `FactorSnapshot` for the exact immutable input snapshot. The cache
key digests that context together with the ordered factor-provider versions,
and the response exposes `X-Cache-Status`. A custom question or top-level
context metadata always returns `BYPASS`; user identity, Session,
Message, Job, history, and generated Debate text are not shared or cached by
this boundary.

A genuinely new V2 request is admitted only when the user has no canonical
non-terminal Debate and remains within the configured generation window
(default: three admissions per hour). Success exposes `X-RateLimit-Limit` and
`X-RateLimit-Remaining`. Another active Debate returns `409`; an exhausted
window returns `429` with a bounded `Retry-After`. A repository-confirmed
sequential retry of the same queued idempotency key returns the existing
Session/Job without consuming another admission. The distributed concurrency
lock for simultaneous duplicate requests remains a separate Phase 6 slice.

Only `debate_ready` stocks are accepted. The transport is controlled by the
separate `DEBATE_QUEUE_ENABLED` flag:

- `false` (default): `POST /debates` synchronously runs six alternating
  Bull/Bear messages and an Interim Judge, then returns `201 Created` with
  `execution_mode=synchronous_preview`;
- `true`: Session, Job, and Queue message creation is atomic and idempotent, the
  route returns `202 Accepted` immediately with `execution_mode=queued`, and a
  bounded background Worker performs Round 1.

Both responses contain `session`, `messages`, `job`, and `job_id`. A supplied
idempotency key must be 8–80 URL-safe alphanumeric/underscore/hyphen characters.
Repeating the same key and same request returns the same queued Session/Job;
conflicting reuse returns `409`.

Challenge request:

```json
{
  "selected_message_id": "uuid",
  "selected_text": "exact text selected from that message",
  "question": "Does this rebuttal underweight the filing risk?",
  "idempotency_key": "round_two_demo_001"
}
```

The target must belong to the owner's active branch and the selected text must
occur in that message. With Queue disabled, a valid Challenge persists the user
question, runs four alternating turns plus the Final Judge synchronously, and
returns `201`. With Queue enabled, intervention, user question, Session/Job
transition, and Queue publication are atomic; the route returns `202` and the
Worker performs Round 2. Session/detail/history reads are owner-scoped.

`GET /debates/{session_id}/events` returns authenticated `text/event-stream`.
Frames use the versioned `DebateEvent` JSON envelope, the per-session sequence
as the SSE `id`, `Last-Event-ID` or `after_sequence` as a resume cursor, and
bounded heartbeats while a non-terminal Session is idle. The current-process
buffer is capped at 256 events for each of at most 128 Sessions. An expired
cursor returns `409`; the client must reload canonical Session/Messages and
then attach to newer events. The response includes
`X-Debate-Latest-Sequence`, which is the safe resume cursor after that reload.

With Queue disabled, the compatibility adapter publishes `turn.delta` chunks
only after it has received one complete provider draft and labels them
`source=buffered_compatibility`. With Queue enabled, the Worker selects the
async Turn provider and publishes deltas as they arrive. Complete messages and
citations remain canonical in the repository; transient event publication
failure does not block them.

The async path rejects missing/late completion, non-contiguous chunks,
truncated finish reasons, text mismatch, output overflow, wrong rebuttal
targets, and out-of-snapshot evidence before persistence. It has deterministic
and Groq implementations; Groq is explicit opt-in and mock-tested, and no live
provider request has been recorded. A generation-scoped cancel route is also
implemented:

```text
POST /debates/{session_id}/cancel
```

Request:

```json
{"generation_id": "expected-active-generation-uuid"}
```

The owner-scoped route returns `202` with canonical `DebateSessionDetail`. It
rotates the active generation before acknowledging cancellation, is idempotent
after acceptance, returns `409` for a stale generation or non-cancellable
completed/failed Session, and returns `404` across the ownership boundary.
Queued work
settles immediately. Running work may first return `cancel_requested`; the
executor polls the canonical generation before deltas and persistence, cancels
the Job, and moves the Session to `cancelled`. Provider transport cancellation
is best effort, but late output cannot pass the repository's atomic
status/generation check or become a new canonical message.

`GET /debates/{session_id}` includes the current active Job, if one exists.
Events include `job.queued`, `job.started`, `job.retry_scheduled`, and
`job.failed`; retry payloads expose a safe attempt count/delay, never a provider
response body. The durable Worker retries bounded temporary failures, resumes
after visibility timeout from the next missing complete turn, and records a
safe terminal failure when attempts are exhausted.

The authenticated Web/React Native stream client and reducer are mounted behind
`EXPO_PUBLIC_DEBATE_V2_ENABLED=false`. The screen renders Queue/Worker states,
temporary drafts, durable messages, cancellation, exact selected-passage
Challenge input, and queued Round 2. Explanation and cross-process
transient-event replay are not implemented. Redis-backed admission limits and
owner-scoped idempotency coordination are implemented with safe local/database
fallbacks. Public stock search/bundle caching is implemented but remains
disabled by default. In Supabase persistence mode V2 additionally requires the
server-only secret and deployed catalog/Debate/Queue migrations. Those hosted
schema and deterministic Queue lifecycle gates passed on 2026-08-29;
production remains disabled pending deliberate rollout and a live-provider
smoke test.

## Planned portfolio API

The canonical request/response and SSE event shapes live in the
[`portfolio implementation plan`](../planning/portfolio-implementation-plan.md).

### Queue and streaming additions

Queued Round 1 and Round 2 creation, Worker events, live async deltas, retry,
redelivery, terminal handling, and the feature-flagged visible V2 screen are
implemented. Controlled hosted Supabase admission, retry, restart, exhaustion,
authorization, and cleanup verification passed on 2026-08-29.

### Human interaction

```text
POST /debates/{session_id}/explanations
```

Explanation will not change Debate state. The Challenge endpoint and mounted V2
screen already queue Round 2 from an exact passage in a complete message. The
cancel route is generation-scoped and is reachable while a queued/running Job
is active; redirecting an active Debate into a new branch remains Phase 7.

### Compatibility

Current `/analysis` and `/claims/{claim_id}/examine` routes remain during the
feature-flagged migration. Legacy single analyses are not rewritten as
multi-turn sessions.
