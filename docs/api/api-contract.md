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
