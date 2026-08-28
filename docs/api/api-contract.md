# API Contract

Last reviewed: 2026-08-28

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
does not call the SEC, a market-data provider, or a model provider.

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

### Default-off Debate V2 preview

`DEBATE_WORKFLOW_V2=false` is the default. In that state all `/debates` routes
return `404` and are omitted from OpenAPI. Existing `/analysis` and claim
examination behavior is unchanged.

When the flag is deliberately enabled, these authenticated Phase 3 routes are
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
  "opening_side": "bull"
}
```

Only `debate_ready` stocks are accepted. `POST /debates` synchronously runs six
alternating Bull/Bear messages and an Interim Judge, persists complete messages
and citations, then returns `201 Created` with `session`, `messages`, `job_id`,
and `execution_mode=synchronous_preview`. The Session is then
`awaiting_user`.

Challenge request:

```json
{
  "selected_message_id": "uuid",
  "selected_text": "exact text selected from that message",
  "question": "Does this rebuttal underweight the filing risk?"
}
```

The target must belong to the owner's active branch and the selected text must
occur in that message. A valid Challenge persists the user question, runs four
more alternating turns and the Final Judge, and returns the completed Session.
Session/detail/history reads are owner-scoped.

`GET /debates/{session_id}/events` returns authenticated `text/event-stream`.
Frames use the versioned `DebateEvent` JSON envelope, the per-session sequence
as the SSE `id`, `Last-Event-ID` or `after_sequence` as a resume cursor, and
bounded heartbeats while a non-terminal Session is idle. The current-process
buffer is capped at 256 events for each of at most 128 Sessions. An expired
cursor returns `409`; the client must reload canonical Session/Messages and
then attach to newer events. The response includes
`X-Debate-Latest-Sequence`, which is the safe resume cursor after that reload.

The HTTP preview's compatibility adapter publishes `turn.delta` chunks only
after it has received one complete provider draft, and labels them
`source=buffered_compatibility`. This proves ordering, framing, owner isolation, and
resume behavior but is not live model token streaming. Complete messages and
citations remain canonical in the repository; transient event publication
failure does not block them.

A separate code-only async orchestration path now accepts real ordered Provider
deltas. It rejects missing/late completion, non-contiguous chunks, truncated
finish reasons, text mismatch, output overflow, wrong rebuttal targets, and
out-of-snapshot evidence before persistence. It is not yet selected by an HTTP
creation mode, so this section does not present it as an available live API.

The code-only path now has one real Groq async Turn adapter and an authenticated
Web/React Native stream client. Both are default-off and mock-tested; no live
provider request was made. A generation-scoped cancel route is now implemented:

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

The preview still does not select live generation or mount the client in the
current screen, and does not implement Queue publication, explanation,
cross-process replay, or Redis. In Supabase persistence mode it additionally
requires the server-only secret and checked-in Debate migrations; production
remains disabled until those are applied and verified.

## Planned portfolio API

The canonical request/response and SSE event shapes live in the
[`portfolio implementation plan`](../planning/portfolio-implementation-plan.md).

### Queue and streaming additions

The later Queue phase will change `POST /debates` from the explicit synchronous
preview contract to `202 Accepted` with session/job IDs and a stream path. It
will enqueue work rather than block until every model turn completes.

The existing events endpoint will later receive true live provider deltas and
Queue/Worker events rather than buffered deterministic preview chunks.

### Human interaction

```text
POST /debates/{session_id}/explanations
```

Explanation will not change Debate state. The implemented Challenge endpoint
will later gain Queue-backed Round 2 from the last complete message. The cancel
route is already generation-scoped; the queued start contract is what will make
mid-generation cancellation reachable from the active screen.

### Compatibility

Current `/analysis` and `/claims/{claim_id}/examine` routes remain during the
feature-flagged migration. Legacy single analyses are not rewritten as
multi-turn sessions.
