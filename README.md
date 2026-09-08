# AI Bull vs Bear

AI Bull vs Bear is an educational Agentic RAG mobile application that helps
users examine possible reasons behind stock-price movements using technical
indicators, cached financial evidence, and a Bull vs Bear debate.

The app explains evidence and uncertainty. It does not provide stock
predictions, buy/sell/hold recommendations, or personalised financial advice.

Start project planning and context recovery from
[`docs/planning/README.md`](docs/planning/README.md). The verified implementation
baseline is maintained in
[`docs/planning/current-status.md`](docs/planning/current-status.md).

## What is implemented

- Expo / React Native mobile flow for coverage-aware security search, Watchlist,
  Stock Detail, Evidence Board, Debate Arena, Cross Examination, History, and
  About.
- FastAPI API contract for ranked catalog search, coverage, prices, indicators,
  watchlist, analysis, trace, token usage, and claim examination.
- A versioned 7,695-row SEC ticker/exchange identity catalog. Search makes no
  runtime SEC or market-data request; catalog-only identities can be saved but
  cannot show synthetic prices or start Debate.
- Database-independent multi-turn Debate contracts plus local/Supabase
  repositories for sessions, complete messages/citations, interventions, and
  the application job ledger. A deterministic runtime completes both rounds and
  the user-Challenge pause. A default-off V2 preview exposes the Session,
  Message, Challenge, Queue, and resumable SSE event API while production
  remains unchanged. With Queue admission disabled, preview deltas are buffered
  deterministic chunks, not live model tokens. A default-off async per-Turn
  contract and Groq adapter validate true provider streams before persistence.
  The V2 mobile screen mounts the resumable SSE client, Queue state, Round 2,
  generation-scoped cancellation, and a read-only point-question modal before
  an explicit Round 2 confirmation. Explanation defaults to deterministic and
  has a separately configured, bounded Groq option. Cancellation rotates the
  active generation and prevents late provider completion from becoming a
  canonical message.
- Deterministic demo data for AAPL, GOOG, NVDA, and TSLA, so no credentials are
  required for the first run.
- RSI, MACD, 20/50-day moving averages, volatility, and volume-spike signals.
- Local lexical-RAG retrieval with overlapping chunks and query-based evidence
  ranking as the credential-free fallback.
- Bull Agent, Bear Agent, Judge Agent, Guardrail Agent, evidence IDs, a trace,
  and a token ledger in the demo provider.
- Groq and Gemini model-provider adapters with structured JSON validation,
  evidence-ID filtering, token accounting, and the same safety guardrails.
- Supabase email authentication, mobile session persistence, bearer-token API
  protection, and Supabase-backed watchlists and analysis history.
- Live RSS and SEC EDGAR ingestion with stable IDs, Supabase document/chunk
  storage, selected 10-K/10-Q section extraction, and retry/rate-limit handling.
- Optional daily OHLCV ingestion (Alpha Vantage or Finnhub) into Supabase with stale-cache
  provenance and deterministic price fallback.
- Optional Redis-backed public stock-search and stock-bundle response caching
  with strict timeouts, local outage fallback, hashed search keys, and visible
  cache status. Redis remains disabled by default.
- A six-hour shared factor-snapshot cache is available only for the standard
  V2 Debate request with no user question or user metadata. Custom questions,
  Sessions, Messages, Jobs, and history are never shared through this cache.
- New V2 generation is bounded to one non-terminal Debate per user and three
  admissions per configurable one-hour window. Redis provides the atomic fast
  path when enabled; the process-local fallback and canonical Session check
  remain active when it is disabled or unavailable.
- Queued V2 creation with a client idempotency key uses a hashed, owner-scoped
  Redis lock before factor work. Deterministic IDs, a PostgreSQL transaction
  lock, and the Job idempotency unique key remain the canonical fallback.
- Database-local evidence vectors and ticker-filtered pgvector retrieval with a
  deterministic cached fallback.
- Immutable completed-close/evidence snapshots with source freshness, dated
  citations, and confidence reduction when current company evidence is missing.
- Interactive 1M/3M daily and 6M/1Y weekly price views with moving averages,
  RSI, MACD, volume, volatility, and dated macro-market context.
- Financial-advice rewrites and a required educational disclaimer.

## Current roadmap

The deployed mobile Debate is currently a single synchronous Bull/Bear/Judge
response. A default-off V2 API and screen prove deterministic multi-turn state,
durable background Queue work, and live-stream selection without changing that
production baseline. Phase 7 is complete: the default-off V2 experience now
includes bounded Explanation, Challenge, Round 2, Final Judge, History, and an
opt-in local Groq Explanation verification. The active
[`portfolio implementation plan`](docs/planning/portfolio-implementation-plan.md)
defines Phase 8 as a reusable financial-technology UI system and Phase 9 as
Demo Replay, observability, resilience, and release proof. General message
branching and arbitrary Web text selection are deferred enhancements; V2
intentionally remains linear after the durable Round 1 pause. The
quota-controlled local live Groq Round 1 now passes its
streaming/persistence/reconnect gate. Redis cache and coordination work is
complete in code and local verification; its measurements remain explicitly
separate from hosted performance claims. Factor-provider and catalog/watchlist
foundations are implemented, and the hosted Catalog plus Debate persistence/RLS
gates passed on 2026-08-29. The hosted Queue migration and deterministic
admission/Worker/retry/restart gate also passed; production V2 flags remain
default-off until a deliberate production deployment smoke test with a rollback
plan.

Planned features are documented separately from implemented behaviour so the
repository does not overstate its current capabilities.

## Run the backend

    cd backend
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    uvicorn app.main:app --reload --port 8000

For deterministic visual acceptance, use the explicit local-only fixture profile:

    ENVIRONMENT=development APP_DATA_MODE=review_fixture uvicorn app.main:app --reload --port 8000

It overrides `.env` provider/persistence settings, makes no outbound requests,
and labels all simulated prices, evidence, macro data, and Debate context.

Open http://localhost:8000/docs for the interactive API docs.

## Run the mobile app

In another terminal:

    cd apps/mobile
    npm install
    npm run start

When the backend uses `APP_DATA_MODE=review_fixture`, explicitly disable the
client's configured Supabase authentication as well:

    EXPO_PUBLIC_AUTH_MODE=demo EXPO_PUBLIC_API_URL=http://localhost:8000 npm run web

The client reads the backend's local-only mode from `/health`, enables the
deterministic V2 flow, and keeps a simulated-data banner above every screen.

The mobile app defaults to http://localhost:8000. For a physical device, set
EXPO_PUBLIC_API_URL to the computer's LAN address, for example
http://192.168.1.20:8000.

Mobile API requests time out after 15 seconds by default. Override this with
`EXPO_PUBLIC_API_TIMEOUT_MS` when a slower development environment needs it.

## Test

    cd backend
    pytest

## Optional credentials

The demo mode works without any keys. When you are ready to add persistence or
live model providers:

Follow the secure checklist in
[`docs/setup/live-services.md`](docs/setup/live-services.md). Never place secrets
in tracked files.

- Create a Supabase project at https://supabase.com/dashboard, run
  backend/supabase/schema.sql in SQL Editor, then place the project URL and anon
  key in a local .env file.
- Create a Groq API key at https://console.groq.com/keys and put it in
  GROQ_API_KEY.
- Create a Gemini API key at https://aistudio.google.com/apikey and put it in
  GEMINI_API_KEY.

To use a real model after adding one of those keys, set exactly one provider in
the local .env file:

    ANALYSIS_PROVIDER=groq
    GROQ_API_KEY=your-local-key

or:

    ANALYSIS_PROVIDER=gemini
    GEMINI_API_KEY=your-local-key

The model name can be changed with GROQ_MODEL or GEMINI_MODEL. The backend
returns HTTP 503 with a safe configuration message if a selected provider is
missing its key; it never includes the key in a response.

Never commit .env or paste secret keys into GitHub issues, README files, or
chat messages.

## Project layout

- backend/app: FastAPI routes, schemas, demo store, indicators, RAG, analysis,
  and guardrails.
- backend/tests: API and service tests.
- backend/supabase: database schema and setup notes.
- apps/mobile: Expo application.
- data/catalog: versioned, source-attributed stock-identity snapshots.
- data/demo: deterministic demo-data notes and seed artifacts.
- docs: planning, API, database, agent, and safety specifications.

## Disclaimer

This project is for educational purposes only and does not constitute financial
advice.
