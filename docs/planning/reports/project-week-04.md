# Project Week 4 Report — Live Evidence and Persistence

Reporting dates: 2026-08-13 to 2026-08-15  
Status: In progress; implementation complete, live credential gates remain

## Outcome

The project now has Supabase authentication/session forwarding, persistent
watchlists and analysis history, public read-only evidence, live RSS and SEC
ingestion, deterministic vector retrieval with graceful fallback, and an Alpha
Vantage daily-price cache with provenance.

## Completed work

- Supabase JWT validation and removal of trusted client-supplied user IDs in
  Supabase mode.
- Mobile sign-in/session restoration and bearer-token forwarding.
- Supabase persistence for watchlists, analysis runs, agent output, citations,
  and token usage.
- RLS policies for user-owned data and read-only public evidence.
- NVIDIA RSS ingestion and stable evidence upserts.
- SEC submissions ingestion for AAPL, GOOG, NVDA, and TSLA.
- SEC filing HTML extraction for Risk Factors and MD&A, with fair-access request
  spacing, retry/backoff, and metadata-only fallback.
- Chunk storage, deterministic 1,536-dimensional word-hash vectors, ticker
  filters, similarity RPC, and fallback retrieval.
- Alpha Vantage daily OHLCV parsing, cached Supabase upserts, staleness
  detection, deterministic fallback, and mobile provenance display.

Key commits include `4af130d`, `04d66c1`, `3ead176`, `e00c33d`, `a34ab9b`,
`170a4a0`, `461c64b`, and `82880ff`.

## Verification

- Backend: 37 tests passed at the end of this work segment.
- Mobile: TypeScript typecheck passed.
- Live Supabase: four stocks, six evidence documents, six chunks, and six
  populated vectors.
- Current evidence rows were created before selected-section extraction and
  therefore still need a credentialed refresh.
- `stock_prices` remained empty pending a server secret and Alpha Vantage key.

## Remaining gates

- Configure a server-side Supabase secret in the ignored local `.env`.
- Configure a real monitored contact in `SEC_USER_AGENT` and refresh evidence.
- Configure Alpha Vantage and populate the first price cache.
- Run two-user RLS and persistence verification using non-production users.

No web-account password belongs in the environment. Only project-scoped API
keys, short-lived tokens, and disposable test-user credentials may be stored in
the ignored `.env`.
