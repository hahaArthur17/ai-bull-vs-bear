# API Contract

## Auth

Supabase mode requires `Authorization: Bearer <access-token>` for user-owned
watchlist and analysis endpoints. Demo mode retains the local credential-free
fallback.

## Stocks

GET /stocks
Returns supported stocks.

GET /stocks/{ticker}
Returns stock profile.

## Watchlist

GET /watchlist
Returns user's watchlist.

POST /watchlist
Adds a stock to watchlist.

DELETE /watchlist/{ticker}
Removes a stock from watchlist.

## Stock Detail

GET /stocks/{ticker}/prices
Returns cached daily OHLCV data. Every price point includes `source` with
`alpha_vantage_cache` or `demo_fallback`, plus `is_stale`.

GET /stocks/{ticker}/indicators
Returns technical indicators.

GET /stocks/{ticker}/evidence
Returns technical, news, and filing evidence. Supports an optional q query
parameter for Supabase vector retrieval with deterministic lexical fallback.

## AI Analysis

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

## Cross Examination

POST /claims/{claim_id}/examine
Request body:
- question_type: explain_term | evidence_support | signal_strength | risk_meaning

Returns focused explanation.
