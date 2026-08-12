# Week 4 Todo — Authentication, Persistence, and Live Evidence

Planning window: 2026-08-17 to 2026-08-23

This is the ordered operating checklist for the next project week. It carries
forward the unfinished Week 3 completion condition before starting new live
evidence work.

## Weekly outcome

An authenticated user can sign in, keep a watchlist and analysis history across
backend restarts, and run an analysis whose news/filing evidence is stored and
retrieved from Supabase with traceable source metadata.

## Ordered todo list

### 1. Authenticate API requests with Supabase JWT

Priority: P0 — carry-over from GitHub issue #3

- Add Supabase sign-in/session handling to the Expo client.
- Send the access token as `Authorization: Bearer <token>`.
- Validate the token in FastAPI and derive the user ID from the JWT.
- Remove the production dependency on `X-User-Id` and hard-coded `demo-user`.
- Keep an explicit demo-mode fallback for local credential-free development.

Acceptance criteria:

- A signed-in user can call protected endpoints.
- Missing, expired, and invalid tokens return 401 without leaking details.
- The backend never trusts a client-supplied user ID.

### 2. Persist watchlists and analysis history in Supabase

Priority: P0 — completes the persistence part of issue #3

- Introduce a repository interface for watchlists and analysis runs.
- Implement a Supabase-backed repository selected by configuration.
- Persist analysis summary, agent outputs, claim evidence, and token usage.
- Retain `DemoStore` only for deterministic demo mode and tests.

Acceptance criteria:

- Watchlist changes survive a backend restart.
- Analysis history survives a backend restart.
- User A cannot access User B's stored records.

### 3. Verify RLS with two test users

Priority: P0 — security gate

- Create two non-production test users.
- Exercise watchlist and analysis policies with both JWTs.
- Add automated integration checks where they can run without committing
  credentials.
- Record the manual verification result in `docs/setup/live-services.md`.

Acceptance criteria:

- Allowed operations succeed for the owner.
- Cross-user reads and writes are rejected.
- No service-role key is present in the mobile bundle.

### 4. Ingest live RSS news into Supabase

Priority: P1 — part of GitHub issue #6

- Select one approved RSS source for the supported demo tickers.
- Reuse the existing RSS parser and normalize source metadata.
- Deduplicate documents by source/external ID.
- Store ingestion timestamps and expose cached/live provenance to the API.

Acceptance criteria:

- At least one supported ticker returns live cached news evidence.
- Every item has title, source, URL, published time, and ingestion time.
- Feed outages fall back to the last successful cache.

### 5. Ingest SEC EDGAR filing evidence

Priority: P1 — completes the filing portion of issue #6

- Map supported tickers to SEC CIK identifiers.
- Fetch submissions/filing metadata with a compliant User-Agent.
- Store selected 10-K/10-Q sections and source URLs.
- Add rate limiting, retries, and deterministic fixtures for tests.

Acceptance criteria:

- At least one recent filing is retrievable for each supported ticker.
- Filing evidence links to the SEC source and identifies form/filing date.
- CI uses fixtures and does not call SEC endpoints.

### 6. Add embeddings and pgvector retrieval

Priority: P1 — completes live RAG retrieval

- Chunk stored news and filing text with overlap.
- Generate embeddings through one configured provider.
- Store vectors in `evidence_chunks` and add a similarity-search function.
- Combine vector similarity with source/type metadata filters.

Acceptance criteria:

- A user question retrieves relevant stored chunks from Supabase.
- Returned claims can cite only IDs present in the retrieved context.
- Retrieval tests cover empty results and provider failure.

### 7. Add live price caching and resilience tests

Priority: P2 — start only after P0 work is complete

- Select one production-safe price source and document its limits.
- Cache OHLCV data and preserve deterministic fallback data.
- Add timeout, retry, rate-limit, stale-cache, and provider-error behavior.
- Mock external providers in automated tests; do not spend API credits in CI.

Acceptance criteria:

- Stock detail identifies live versus fallback price data.
- Temporary provider failure does not break the main app flow.
- All backend tests pass without network access.

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
