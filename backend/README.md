# Backend

The backend is a FastAPI service. It runs in deterministic demo mode by default,
so the project can be explored without API keys or a Supabase project.

The public baseline produces one synchronous Bull/Bear/Judge response. A
default-off `DEBATE_WORKFLOW_V2` path exercises the complete two-round
Session/Message workflow and exposes bounded lifecycle events through resumable
SSE. With `DEBATE_QUEUE_ENABLED=false`, it remains a synchronous deterministic
preview whose deltas come from an already completed Turn. With the Queue flag
enabled, Round 1 and Round 2 return `202 Accepted`, publish atomically to a
durable Supabase Queue, and run through bounded background Workers. Redis
adapters and public stock-search/bundle caching are implemented with a local
failure fallback. Per-user Debate admission limits and duplicate-request locks
are wired into the default-off V2 path; Redis never replaces canonical Debate
persistence. Follow the canonical
[`portfolio implementation plan`](../docs/planning/portfolio-implementation-plan.md)
rather than adding these concerns directly to the current analysis service.

The Phase 4/5 domain also includes an async per-Turn stream protocol, a
whole-draft compatibility adapter, a zero-token deterministic async provider,
an async orchestrator path, and a real Groq `AsyncGroq` Turn adapter. That path
publishes deltas as they arrive but persists only after a normal completion
frame passes text, output-bound, rebuttal-target, evidence-ID, and financial
language validation. `DEBATE_STREAMING_PROVIDER=deterministic` is the safe
default; `groq` is an explicit, quota-consuming selection. Queue Workers select
this async path. One quota-controlled local Groq Round 1 passed the live stream,
canonical persistence, citation, token-accounting, and reconnect gates; the
provider is still not selected by production configuration. The default-off API
also exposes generation-scoped cancellation:
queued work stops immediately, running work stops at its next generation check,
and the repository rejects any late completion after cancellation.

## Run locally

    cd backend
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    uvicorn app.main:app --reload --port 8000

Open http://localhost:8000/docs for the interactive API documentation.

## Test

    cd backend
    pytest

## Configuration

Copy the repository-level .env.example to .env when you are ready to add
Supabase or model-provider credentials. The deterministic demo provider remains
the default until a real provider is selected explicitly.

`REDIS_ENABLED=false` is also the safe default. When enabled with a valid
`redis://` or `rediss://` URL, stock search and the public stock bundle use the
remote cache with bounded timeouts and a process-local fallback. Responses
expose `X-Cache-Status`; Redis failure must not prevent canonical repository
reads. `GET /health/cache` exposes only safe mode, reachability, and degraded
operation counts; add `?probe=true` for a bounded connectivity check. The
current slice does not use Redis as Debate persistence or Queue transport.
Reproduce the local stock-search latency and repository-call evidence with:

    PYTHONPATH=backend backend/.venv/bin/python \
      scripts/benchmark_stock_search_cache.py

The recorded method and non-SLA limits are in the
[`Week 15 report`](../docs/planning/reports/project-week-15.md).

The default V2 request (`question=null`) may also reuse its public normalized
`FactorSnapshot` for six hours when Redis caching is enabled. Any custom
question or top-level context metadata forces `BYPASS`. Only the derived factor
snapshot is reused; every user still receives new canonical Session, Message,
Job, and history records, and model-generated Debate messages are not cached.

V2 admission also enforces one non-terminal Debate per user and a configurable
default of three new admissions per hour. `DEBATE_RATE_LIMIT_PER_WINDOW`,
`DEBATE_RATE_LIMIT_WINDOW_SECONDS`, and `DEBATE_ACTIVE_TTL_SECONDS` control the
bounded policy. Successful new admissions expose remaining capacity; an active
Session returns `409`, and an exhausted window returns `429` with
`Retry-After`. Sequential queued idempotency replays do not consume another
slot. Queued creation with an idempotency key also acquires an owner-scoped,
hashed duplicate-request lock before factor work;
`DEBATE_IDEMPOTENCY_LOCK_TTL_SECONDS` controls its two-minute default. A
competing request returns `409` with a short `Retry-After`, while deterministic
IDs and the database transaction/unique constraints remain the final fallback.

The first Explanation Agent slice is a read-only backend service boundary. It
requires an exact selection from a complete message on the owned active branch,
passes only that message's linked evidence to an injected provider, applies the
financial-language guardrail, and leaves Session/Job/transcript state
unchanged. Its authenticated HTTP route is available only with Debate V2
enabled and has a separate per-user fixed-window admission limit (12 requests
per hour by default) using only a hashed cache key; the mobile explanation panel
is not mounted yet.

`DEBATE_WORKFLOW_V2=false` is the safe default. Enabling it exposes the V2
routes but does not by itself enable Queue admission. Set
`DEBATE_QUEUE_ENABLED=true` only after the checked-in catalog, Debate, and Queue
migrations have been applied to Supabase and the service-role/RLS checks pass.
This makes create/challenge return `202` and starts
`DEBATE_WORKER_CONCURRENCY` lifespan consumers (1 by default, maximum 2) using
`DEBATE_WORKER_VISIBILITY_TIMEOUT_SECONDS` and
`DEBATE_WORKER_POLL_SECONDS`. The hosted deterministic Queue lifecycle checks
passed on 2026-08-29. Production still keeps both flags false pending an
explicit live-provider rollout. Reproduce the checks with:

    PYTHONPATH=backend backend/.venv/bin/python \
      scripts/verify_supabase_debate_queue.py

The script prints the exact active/archive Queue message IDs that must be
removed after the disposable run; never blanket-purge the Queue.

The same Worker can be run separately from the `backend` directory:

    python -m app.debate_worker_main

Do not run the standalone command at the same time as lifespan consumers unless
the additional bounded concurrency is intentional.

`DEBATE_STREAMING_PROVIDER` is separate from both `DEBATE_WORKFLOW_V2` and
`ANALYSIS_PROVIDER`. Keep it at `deterministic` for tests and the deployed
preview. A deliberate local `groq` selection additionally requires
`GROQ_API_KEY`; `DEBATE_GROQ_MODEL` defaults to `openai/gpt-oss-20b`.

Run the bounded live Round 1 only with explicit quota confirmation. It makes at
most six Groq requests, uses a 220-token completion cap per Turn, persists only
to the in-memory repository, and prints no generated content or credentials:

    DEBATE_STREAMING_PROVIDER=groq PYTHONPATH=backend \
      backend/.venv/bin/python scripts/verify_groq_debate_streaming.py \
      --confirm-live-quota

Supported model providers:

- ANALYSIS_PROVIDER=groq with GROQ_API_KEY and optional GROQ_MODEL.
- ANALYSIS_PROVIDER=gemini with GEMINI_API_KEY and optional GEMINI_MODEL.

Both providers must return the structured Bull/Bear/Judge JSON shape. The
backend validates the shape, removes evidence IDs that were not supplied by
retrieval, records provider token usage, and applies the financial safety
guardrail before returning the result. No model key is needed in demo mode.

## Evidence import

The RSS importer can turn a feed into the same evidence shape used by the API:

    PYTHONPATH=backend python scripts/ingest_rss.py \
      --ticker AAPL \
      --url https://example.com/feed.xml

The command prints JSON so it can be reviewed before being loaded into a
database or checked into a demo-data fixture.

The live ingestion command upserts the configured RSS feed plus recent 10-K
and 10-Q filings into Supabase, replaces their text chunks, and lets the
database trigger generate local evidence vectors:

    PYTHONPATH=backend python scripts/ingest_live_evidence.py

This command requires `SUPABASE_URL`, the server-only
`SUPABASE_SECRET_KEY`, and a declared `SEC_USER_AGENT` containing the project
name and a monitored contact email. It downloads selected narrative sections
from each filing, currently Risk Factors and Management's Discussion and
Analysis. SEC requests are throttled below 10 requests per second and retry
temporary rate-limit and server failures. If one filing remains unavailable,
the ingestion retains its citation-ready metadata with
`content_status=metadata_only` instead of aborting the whole batch.

## Daily price cache

The price ingestion command fetches the latest 100 daily OHLCV points for AAPL
from Alpha Vantage (or Finnhub when Alpha Vantage is not configured) and
upserts them into Supabase:

    PYTHONPATH=backend python scripts/ingest_live_prices.py

It requires `SUPABASE_URL`, the server-only `SUPABASE_SECRET_KEY`, and either
`ALPHA_VANTAGE_API_KEY` or a `FINNHUB_API_KEY` with daily-candle permission.
The default batch covers only AAPL and makes one provider call. Run it no more
than once per trading day and never from an API request handler. A failed ticker
retains its previous Supabase rows. The read API hides the synthetic price in
the client when its cache is empty or unavailable, rather than passing it off
as a market close.

`PRICE_TICKERS` and `PRICE_MAX_CALLS_PER_RUN` can expand this deliberately, but
the settings validation does not allow a value above three. Each returned price
is a completed daily close, not an intraday quote.

`PRICE_STALE_AFTER_DAYS` defaults to 5. The price API labels Supabase rows as
`daily_market_cache` and demo rows as `demo_fallback`, with an `is_stale` flag
that the mobile stock detail screen displays.

When `FINNHUB_API_KEY` is present, the stock detail request also retrieves a
current Finnhub quote through the API. The server retains it in memory for 60
seconds, so active AAPL viewers generate at most one quote-provider request per
minute per backend instance. The quote is labelled separately from the daily
price curve.
