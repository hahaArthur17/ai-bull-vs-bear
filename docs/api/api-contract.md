# API Contract

Last reviewed: 2026-08-27

Endpoints in the first section are implemented. The portfolio target is
explicitly marked planned and must not be presented as available before its
phase acceptance tests pass.

## Implemented API

### Auth

Supabase mode requires `Authorization: Bearer <access-token>` for user-owned
watchlist and analysis endpoints. Demo mode retains the local credential-free
fallback.

### Stocks

GET /stocks
Returns the four supported stocks. Accepts an optional `q` parameter, although
the current mobile client filters its already-loaded list locally.

GET /stocks/{ticker}
Returns stock profile.

### Watchlist

GET /watchlist
Returns user's watchlist.

POST /watchlist
Adds a stock to watchlist.

DELETE /watchlist/{ticker}
Removes a stock from watchlist.

### Stock Detail

GET /stocks/{ticker}/prices
Returns cached daily OHLCV data. Every price point includes `source` with
`daily_market_cache` or `demo_fallback`, plus `is_stale`. A daily market cache
is populated from the configured provider (Alpha Vantage when available,
otherwise Finnhub); it is not an intraday quote.

GET /stocks/{ticker}/quote
Returns a current Finnhub quote when `FINNHUB_API_KEY` is configured, or `null`
when it is not available. The backend caches this response for 60 seconds. It
is displayed as a quote, never as a completed daily close.

GET /stocks/{ticker}/indicators
Returns technical indicators.

GET /stocks/{ticker}/evidence
Returns technical, news, and filing evidence. Supports an optional q query
parameter for Supabase vector retrieval with deterministic lexical fallback.

### AI Analysis

POST /analysis/{ticker}
Starts a Bull vs Bear analysis.

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

## Planned portfolio API

The canonical request/response and SSE event shapes live in the
[`portfolio implementation plan`](../planning/portfolio-implementation-plan.md).

### Catalog and coverage

```text
GET /stocks?q=<query>&limit=<limit>
GET /stocks/{ticker}/coverage
```

Search will use the local/Supabase catalog and consume no market-data provider
request. Results include `coverage_status`; catalog-only stocks can be saved to
the watchlist but cannot start Debate.

### Debate sessions

```text
POST /debates
GET  /debates
GET  /debates/{session_id}
GET  /debates/{session_id}/messages
GET  /debates/{session_id}/events
POST /debates/{session_id}/cancel
```

`POST /debates` will return `202 Accepted` with session/job IDs and a stream
path. It will enqueue work rather than block until every model turn completes.

The events endpoint emits authenticated SSE-formatted, versioned events such
as `job.queued`, `turn.started`, `turn.delta`, `turn.completed`,
`session.awaiting_user`, and terminal session events.

### Human interaction

```text
POST /debates/{session_id}/explanations
POST /debates/{session_id}/interventions
```

Explanation does not change Debate state. An intervention records a free-form
challenge, cancels the active generation on a best-effort basis, and queues
round two from the last complete message.

### Compatibility

Current `/analysis` and `/claims/{claim_id}/examine` routes remain during the
feature-flagged migration. Legacy single analyses are not rewritten as
multi-turn sessions.
