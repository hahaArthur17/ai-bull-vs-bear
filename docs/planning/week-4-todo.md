# Week 4 Todo — Authentication, Persistence, and Live Evidence

Planning window: 2026-08-17 to 2026-08-23

This is the ordered operating checklist for the next project week. It carries
forward the unfinished Week 3 completion condition before starting new live
evidence work.

## Weekly outcome

An authenticated user can sign in, keep a watchlist and analysis history across
backend restarts, and run an analysis whose news/filing evidence is stored and
retrieved from Supabase with traceable source metadata.

## Progress update — 2026-08-15

Implementation completed:

- Supabase JWT verification, mobile session forwarding, persistent watchlists,
  and persistent analysis history.
- RLS migrations for user data and public read-only market/evidence data.
- Stable NVIDIA RSS ingestion and SEC submissions metadata for all supported
  tickers, with Supabase upserts and ingestion timestamps.
- Evidence chunk storage, database-local embeddings, and ticker-filtered
  pgvector retrieval.
- SEC 10-K/10-Q Risk Factors and Management's Discussion and Analysis parsing,
  fair-access request spacing, retry handling, and metadata-only fallback.
- Alpha Vantage daily price parsing, four-ticker Supabase batch upserts,
  stale-cache provenance, and deterministic price fallback.

Verification evidence:

- Backend: 41 tests pass with mocked external providers.
- Mobile: `npm run typecheck` passes.
- Supabase read-only check: four stocks, six evidence documents, six chunks,
  and six populated vectors.

Remaining gates:

- Two-user live Auth/RLS and backend-restart persistence verification.
- A server-side Supabase secret and compliant SEC User-Agent are required to
  refresh the existing metadata-only filing rows with selected sections.
- The live price code is complete, but the empty Supabase price cache needs a
  server secret and Alpha Vantage key for its first population.

## Ordered todo list

### 1. Authenticate API requests with Supabase JWT

Priority: P0 — carry-over from GitHub issue #3

Implementation status: complete; live test-user verification remains.

- [x] Add Supabase sign-in/session handling to the Expo client.
- [x] Send the access token as `Authorization: Bearer <token>`.
- [x] Validate the token in FastAPI and derive the user ID from the JWT.
- [x] Remove the production dependency on `X-User-Id` and hard-coded `demo-user`.
- [x] Keep an explicit demo-mode fallback for local credential-free development.

Acceptance criteria:

- [ ] A signed-in live test user can call protected endpoints.
- [x] Missing, expired, and invalid tokens return 401 without leaking details.
- [x] The backend never trusts a client-supplied user ID in Supabase mode.

### 2. Persist watchlists and analysis history in Supabase

Priority: P0 — completes the persistence part of issue #3

Implementation status: complete; live restart/isolation verification remains.

- [x] Introduce a shared store contract for watchlists and analysis runs.
- [x] Implement a Supabase-backed repository selected by configuration.
- [x] Persist analysis summary, agent outputs, claim evidence, and token usage.
- [x] Retain `DemoStore` only for deterministic demo mode and tests.

Acceptance criteria:

- [ ] Watchlist changes survive a live backend restart.
- [ ] Analysis history survives a live backend restart.
- [ ] User A cannot access User B's stored records in a two-user live test.

### 3. Verify RLS with two test users

Priority: P0 — security gate

- [ ] Create two non-production test users.
- [ ] Exercise watchlist and analysis policies with both JWTs.
- [ ] Add automated integration checks where they can run without committing
  credentials.
- [ ] Record the manual verification result in `docs/setup/live-services.md`.

Acceptance criteria:

- [ ] Allowed operations succeed for the owner.
- [ ] Cross-user reads and writes are rejected.
- [x] No service-role key is present in the mobile bundle.

### 4. Ingest live RSS news into Supabase

Priority: P1 — part of GitHub issue #6

- [x] Select one stable RSS source for a supported demo ticker.
- [x] Reuse the existing RSS parser and normalize source metadata.
- [x] Deduplicate documents by source/external ID.
- [x] Store ingestion timestamps and expose cached/live provenance to the API.

Acceptance criteria:

- [x] At least one supported ticker returns live cached news evidence.
- [x] Every item has title, source, URL, published time, and ingestion time.
- [x] Feed outages retain the last successful Supabase cache.

### 5. Ingest SEC EDGAR filing evidence

Priority: P1 — completes the filing portion of issue #6

Implementation status: complete; live selected-section refresh remains.

- [x] Map supported tickers to SEC CIK identifiers.
- [x] Fetch submissions/filing metadata with a compliant User-Agent.
- [x] Store selected 10-K/10-Q sections and source URLs.
- [x] Add rate limiting, retries, and deterministic fixtures for tests.

Acceptance criteria:

- [x] At least one recent filing metadata record is retrievable for each ticker.
- [x] Filing evidence links to the SEC source and identifies form/filing date.
- [x] CI uses fixtures and does not call SEC endpoints.
- [ ] Refresh live rows so `content_status=selected_sections` is present.

### 6. Add embeddings and pgvector retrieval

Priority: P1 — completes live RAG retrieval

- [x] Chunk stored news and filing text with overlap.
- [x] Generate deterministic database-local embeddings.
- [x] Store vectors in `evidence_chunks` and add a similarity-search function.
- [x] Separate canonical chunks from versioned model/dimension profiles.
- [x] Add source-aware news/filing chunk context and section paths.
- [x] Add typed SEC XBRL storage so table arithmetic does not depend on vectors.
- [x] Combine vector similarity with source/type metadata filters.

Acceptance criteria:

- [x] A user question retrieves relevant stored chunks from Supabase.
- [x] Returned claims can cite only IDs present in the retrieved context.
- [x] Retrieval tests cover empty Supabase results and RPC failure fallback.

### 7. Add live price caching and resilience tests

Priority: P2 — start only after P0 work is complete

Implementation status: complete; live AAPL cache populated on 2026-08-20.

- [x] Select one production-safe price source and document its limits.
- [x] Cache OHLCV data and preserve deterministic fallback data.
- [x] Add timeout, retry, quota, stale-cache, and provider-error behavior.
- [x] Mock external providers in automated tests; do not spend API credits in CI.

Acceptance criteria:

- [x] Stock detail identifies live versus fallback price data.
- [x] Temporary provider failure does not break the main app flow.
- [x] All backend tests pass without network access.
- [x] Populate Supabase `stock_prices` from a real Alpha Vantage response.

Live verification — 2026-08-20:

- The AAPL daily-price ingestion completed with one provider request and wrote
  100 OHLCV rows to Supabase.
- The production API returned a latest completed close of `$316.83` on
  `2026-08-19`, marked `daily_market_cache` and not stale.
- The weekday GitHub Actions refresh workflow is active with encrypted
  `ALPHA_VANTAGE_API_KEY`, `SUPABASE_URL`, and `SUPABASE_SECRET_KEY` secrets.

### 8. Make Debate evidence current, traceable, and appropriate to the price date

Priority: P0 — required before presenting a Debate as an explanation of the
latest market close

Audit result — 2026-08-20:

- The price series is current (100 real AAPL daily rows through 2026-08-19),
  but the AAPL retrieval response contains no live news item.
- The newest retrieved filing is the AAPL 10-Q filed 2026-07-31; it is useful
  long-horizon company context, not an explanation by itself for a current
  daily move.
- The current Supabase-backed evidence board still prepends two deterministic
  demo items dated January 2026. The similarity search used by Debate returned
  older filing chunks and no current news item.
- Therefore the current Debate can combine verified technical indicators with
  stale or demo narrative evidence. It must not claim to explain the latest
  price move until the following acceptance criteria are met.

Required work:

- [ ] Add an AAPL-specific, licensable news source and scheduled ingestion;
  the current live evidence job refreshes an NVIDIA RSS feed only.
- [ ] Record and expose `published_at`, `ingested_at`, source, and an explicit
  freshness status for every news, filing, and financial-fact item.
- [ ] Define source-specific freshness windows: daily price must match the
  latest completed market session; news must be recent enough for a daily-move
  explanation; filings remain long-horizon context and must display their age.
- [ ] Exclude deterministic demo news/filing evidence from production Debate
  retrieval whenever Supabase is available. If no qualifying live evidence
  exists, return an explicit “insufficient current evidence” result rather
  than a causal narrative.
- [ ] Persist an immutable analysis snapshot containing the close date/price,
  exact evidence IDs, publication dates, retrieval time, and freshness result.
- [ ] Make the Debate question explicit: “What available evidence may relate
  to the AAPL close on <date>?” It must distinguish correlation from cause and
  report when no contemporaneous catalyst was found.
- [ ] Retain the educational safety boundary. Replace requests for personalised
  buy/sell/hold or percentage allocations with a non-personal scenario and
  risk-tolerance framework, including uncertainty and sources to investigate.

Acceptance criteria:

- [ ] A current Debate cannot silently use demo evidence or evidence outside
  its declared freshness window.
- [ ] Every displayed claim shows the market-close date and its linked,
  dated evidence.
- [ ] An empty current-news result is visible to the user and lowers evidence
  strength instead of producing a confident explanation.

### 9. Build interactive multi-horizon price and indicator charts for AAPL

Priority: P1 — begins after task 8 enforces data freshness

Product requirements:

- [ ] Replace the static 30-session SVG with an interactive chart: range
  selector, drag/pan, tap/hover crosshair, date/price tooltip, and accessible
  textual equivalent.
- [ ] Support `1M`, `3M`, `6M`, and `1Y` views. Keep recent views on verified
  daily candles. Bootstrap the one-year view from a separately labelled weekly
  series, then preserve the daily series for detailed recent periods.
- [ ] Store frequency/granularity with every point; do not present a weekly
  close as a daily close.
- [ ] Overlay MA20 and MA50 on the price chart with a legend and clear colour
  distinction.
- [ ] Add separate, synchronised technical panels: RSI with 30/70 reference
  lines; MACD and signal lines with histogram; volume bars; and volatility as
  a continuous series. A latest-number summary may remain, but cannot be the
  only representation.
- [ ] Calculate indicators exclusively from verified market data and display
  their as-of date plus any insufficient-lookback state.

Data-source constraint:

- Alpha Vantage free daily `compact` output returns only 100 recent daily
  points. Its full daily history requires a premium key. Its weekly endpoint
  provides a 20+ year weekly series, so a one-year weekly bootstrap can retain
  the current one-call-per-day AAPL budget. See the official documentation:
  <https://www.alphavantage.co/documentation/>.

Acceptance criteria:

- [ ] The user can inspect an individual point and see its exact date, close,
  data frequency, and source freshness.
- [ ] One-year navigation works without increasing routine daily API use above
  one AAPL request per trading day.
- [ ] Chart interactions work with mouse, touch, keyboard focus, and a screen
  reader summary.

## Recommended execution order

1. Complete tasks 1–3 before starting live-data work.
2. Build tasks 4 and 5 independently, then connect both through task 6.
3. Treat task 7 as stretch work if the P0/P1 completion rules are satisfied.

## Not part of this week

- Production deployment and app-store builds.
- Social-media sentiment.
- Trading execution, price targets, or buy/sell/hold recommendations.
- Replacing the educational disclaimer or safety guardrails.

## End-of-week review

- Update `docs/planning/weekly-roadmap.md` with evidence and blockers.
- Update this checklist with completed acceptance criteria.
- Run backend tests and mobile typecheck.
- Sync GitHub Project statuses only after the acceptance criteria are met.
