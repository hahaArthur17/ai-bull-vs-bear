# API Contract

## Auth

Authentication will be handled through Supabase Auth.

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
Returns cached OHLCV data.

GET /stocks/{ticker}/indicators
Returns technical indicators.

GET /stocks/{ticker}/evidence
Returns technical, news, and filing evidence. Supports an optional q query
parameter for local lexical-RAG retrieval.

## AI Analysis

POST /analysis/{ticker}
Starts a Bull vs Bear analysis.

GET /analysis/{analysis_id}
Returns analysis result.

GET /analysis
Returns analysis runs created during the current runtime.

GET /analysis/{analysis_id}/trace
Returns agent trace.

GET /analysis/{analysis_id}/tokens
Returns token usage.

## Cross Examination

POST /claims/{claim_id}/examine
Request body:
- question_type: explain_term | evidence_support | signal_strength | risk_meaning

Returns focused explanation.
