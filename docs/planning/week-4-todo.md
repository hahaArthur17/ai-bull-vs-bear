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

Implementation status: complete; first live cache population remains.

- [x] Select one production-safe price source and document its limits.
- [x] Cache OHLCV data and preserve deterministic fallback data.
- [x] Add timeout, retry, quota, stale-cache, and provider-error behavior.
- [x] Mock external providers in automated tests; do not spend API credits in CI.

Acceptance criteria:

- [x] Stock detail identifies live versus fallback price data.
- [x] Temporary provider failure does not break the main app flow.
- [x] All backend tests pass without network access.
- [ ] Populate Supabase `stock_prices` from a real Alpha Vantage response.

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
