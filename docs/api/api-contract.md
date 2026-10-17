# API Contract

Last reviewed: 2026-10-17 against `backend/app/main.py` and `debate_schemas.py`.

The endpoints below are implemented, with V2/interruptions controlled by
explicit flags. This contract describes source behavior, not production
rollout or physical-device acceptance. See [current status](../planning/current-status.md).

## Implemented API

### Auth

Supabase mode requires `Authorization: Bearer <access-token>` for user-owned
watchlist, analysis, and enabled Debate endpoints. Demo mode retains the local
credential-free fallback.

### Health

`GET /health` returns `status`, `environment`, legacy `provider`, `data_mode`,
`debate_workflow_v2`, and optional `build_sha`.
`GET /health/cache` returns safe cache mode/degradation metadata; `probe=true`
performs a bounded connectivity check. Neither endpoint exposes credentials.

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
`daily_market_cache`, `demo_fallback`, or the explicit local-only
`review_fixture`, plus `is_stale`. A daily market cache
is populated from the configured provider (Alpha Vantage when available,
otherwise Finnhub); it is not an intraday quote. Returns an empty list for a
catalog-only identity.

GET /stocks/{ticker}/price-history?frequency=weekly
Returns labelled weekly history. Only `weekly` is accepted; catalog-only
identities return an empty list. Weekly points are distinct from daily prices.

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
request. It includes `data_mode` (`standard` or `review_fixture`) so simulated
responses remain visibly distinguishable. Weekly rows use
`alpha_vantage_weekly` for the real provider and `review_fixture` for the
explicit local review profile. The public core is cached for five minutes when Redis is enabled; the
current quote is resolved after the cache read and is not stored in the bundle
cache. A catalog-only identity returns `409 Conflict`. `X-Cache-Status` uses the
same values as stock search.

### Macro context

- `GET /macro/series`: available dated series definitions.
- `GET /macro/series/{series_code}?limit=400`: observations; limit 1–1000.
- `GET /macro/context?limit=60`: definitions plus observations; limit 2–400.

The bundle includes macro context for AAPL. Missing/stale/simulated observations
must retain their metadata and are not an assertion of causal price prediction.

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
POST /debates/{session_id}/explanations
POST /debates/{session_id}/interventions
POST /debates/{session_id}/cancel
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
Session/Job without consuming another admission. An owner-scoped hashed
idempotency lock also coordinates simultaneous queued creation; a competing request returns `409` with a short `Retry-After`.
Database transactions/unique constraints remain the final fallback.

Explanation has an independent per-user fixed-window admission limit (12 per
hour by default). Accepted requests expose `X-RateLimit-Limit` and
`X-RateLimit-Remaining`; an exhausted window returns `429` with a bounded
`Retry-After`. Its cache key contains only a hash of the normalized user ID and
window number, never the selected passage or question. Redis remains an
optimization: an outage falls back safely to the bounded local adapter.

Only `debate_ready` stocks are accepted. The transport is controlled by the
separate `DEBATE_QUEUE_ENABLED` flag:

- `false` (default): `POST /debates` synchronously runs six alternating
  Bull/Bear messages and an Interim Judge, then returns `201 Created` with
  `execution_mode=synchronous_preview`;
- `true`: Session, Job, and Queue message creation is atomic and idempotent, the
  route returns `202 Accepted` immediately with `execution_mode=queued`, and a
  bounded background Worker performs Round 1.

Both mutation responses contain `session`, `messages`, `job`, `job_id`, and
`execution_mode`. Detail returns the same canonical Session/message records and
current Job, without a required `job_id`. Each message record wraps `message`,
`citations`, and a server-authored `presentation` of frozen facts/evidence,
interpretation, uncertainty and missing metadata. The presentation is not an
independent source of model-generated facts. A supplied
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

The target must be a complete message on the owner's active branch, the exact
selected text must occur in it, and the Session must be at `awaiting_user`. With Queue disabled, a valid Challenge persists the user
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
and Groq implementations. Groq remains explicit opt-in; a quota-controlled
local Round 1 passed ordered streaming, validation, persistence, token
accounting, and reconnect on 2026-08-29. A generation-scoped cancel route is
also implemented:

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
Challenge input, queued Round 2, and read-only Explanation. Its independently
flagged interruption controls add visible-prefix Stop/interjection/Continue/End.
Cross-process transient-event replay is not implemented.
Redis-backed admission limits and owner-scoped idempotency coordination are
implemented with safe local/database fallbacks. Public stock search/bundle
caching is implemented but remains disabled by default. In Supabase persistence
mode V2 additionally requires the server-only secret and deployed catalog/Debate migrations, plus Queue and
interruption migrations/security fixes when those features are enabled. Catalog,
V2 persistence and deterministic Queue gates passed on 2026-08-29;
interruption/security fixes have separate September hosted evidence, and
production remains disabled pending deliberate rollout and a live-provider
smoke test.

## Read-only Explanation

`POST /debates/{session_id}/explanations` accepts:

```json
{
  "message_id": "uuid",
  "selected_text": "exact passage from the source message",
  "question": "What does this term mean here?"
}
```

The source must be owned and on the active branch. Complete messages and
non-empty incomplete messages marked `metadata.interrupted=true` are eligible;
the selected passage must occur exactly in the retained text. Explanation
receives only that source's linked evidence, never treating the frozen partial
text as completed evidence. It returns `200` with bounded content, evidence IDs,
provider name/version and guardrail status. It does not change Session, Job,
generation or transcript.

Missing owned sources return `404`, invalid selections return `409`, and safe
provider failures return `503`. `EXPLANATION_PROVIDER=deterministic` is the
default; `groq` is a separate explicit live selection. The default 12/hour
admission window is independent of Debate admission. Explanation usage is not
included in the Debate provider-attempt ledger.

## Default-off interruptions and provider audit

These owner-scoped routes additionally require
`DEBATE_INTERRUPTIONS_ENABLED=true`; otherwise they return `404` and are hidden
from OpenAPI. Continue also requires Queue enabled.

| Route suffix under `/debates/{session_id}` | Request body | Success |
| --- | --- | --- |
| `POST /interrupt` | `generation_id`, `message_id`, `visible_prefix` (0–6000 characters, exact retained prefix) | `200` detail at `interrupted_awaiting_user` |
| `POST /interrupt-before-output` | `generation_id` | `200` detail with an empty interruption marker |
| `POST /interjections` | Waiting `generation_id`, `content` (1–500 characters), required `idempotency_key` | `201` detail; saves the point without calling a model |
| `POST /continue` | Waiting `generation_id`, saved `interjection_id`, required `idempotency_key` | `202` detail with a new generation and queued Job |
| `POST /end-interruption` | `interrupted_message_id` | `202` detail; cancellation may still be settling |
| `GET /provider-attempts` | No body | `200` owner-scoped attempts and usage aggregates |

Stop validates the visible prefix against durable checkpoint/canonical content,
rotates generation, removes later transcript material and retains an incomplete
record. It supports stopping a completed provider message whose client display
is still catching up. Identical retries are idempotent; stale generations,
invented prefixes, conflicting idempotency reuse and invalid states return
`409`. Wrong ownership returns `404`.

Continue requires a saved interjection and atomically enqueues the remaining
stage using the original frozen snapshot. It cannot create another round on a
completed Session. End targets the interruption marker, including a competing
Continue descended from that marker; it rejects a newer interruption point.
Provider cancellation is best effort, and already dispatched work may consume
tokens even when no complete message is retained.

The audit response contains `attempts`, `admitted_count`, `dispatch_attempts`,
`reported_tokens`, and `unknown_usage_attempts`. Each attempt records provider,
model, role, generation/message IDs, admission/dispatch/finish times, outcome,
usage status and nullable token counts. Unknown usage is not zero usage.
V2 mobile diagnostics do not yet consume this endpoint.

## Compatibility and deferred work

Current `/analysis` and `/claims/{claim_id}/examine` remain available with V2
off. Legacy analyses are not rewritten into multi-turn Sessions. General
branching, Replay and shared cross-process transient-event transport remain
future work; validated domain event names alone do not mean a route emits every
possible event. Runtime models/OpenAPI are authoritative for complete schemas.
