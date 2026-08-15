# AI Bull vs Bear

AI Bull vs Bear is an educational Agentic RAG mobile application that helps
users examine possible reasons behind stock-price movements using technical
indicators, cached financial evidence, and a Bull vs Bear debate.

The app explains evidence and uncertainty. It does not provide stock
predictions, buy/sell/hold recommendations, or personalised financial advice.

Project planning and the current completion record are maintained in
[`docs/planning/weekly-roadmap.md`](docs/planning/weekly-roadmap.md). Review that
file before starting the next week's work.

## What is implemented

- Expo / React Native mobile flow for Watchlist, Stock Detail, Evidence Board,
  Debate Arena, Cross Examination, History, and About.
- FastAPI API contract for stocks, prices, indicators, watchlist, analysis,
  trace, token usage, and claim examination.
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
- Optional Alpha Vantage daily OHLCV ingestion into Supabase with stale-cache
  provenance and deterministic price fallback.
- Database-local evidence vectors and ticker-filtered pgvector retrieval with a
  deterministic cached fallback.
- Financial-advice rewrites and a required educational disclaimer.

## Run the backend

    cd backend
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    uvicorn app.main:app --reload --port 8000

Open http://localhost:8000/docs for the interactive API docs.

## Run the mobile app

In another terminal:

    cd apps/mobile
    npm install
    npm run start

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
- data/demo: demo-data notes and future seed artifacts.
- docs: planning, API, database, agent, and safety specifications.

## Disclaimer

This project is for educational purposes only and does not constitute financial
advice.
