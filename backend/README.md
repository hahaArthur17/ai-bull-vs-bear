# Backend

The backend is a FastAPI service. It runs in deterministic demo mode by default,
so the project can be explored without API keys or a Supabase project.

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

Supported model providers:

- ANALYSIS_PROVIDER=groq with GROQ_API_KEY and optional GROQ_MODEL.
- ANALYSIS_PROVIDER=gemini with GEMINI_API_KEY and optional GEMINI_MODEL.

Both providers must return the structured Bull/Bear/Judge JSON shape. The
backend validates the shape, removes evidence IDs that were not supplied by
retrieval, records provider token usage, and applies the financial safety
guardrail before returning the result. No model key is needed in demo mode.

## Evidence import

The standard-library RSS importer can turn a feed into the same evidence shape
used by the API:

    PYTHONPATH=backend python scripts/ingest_rss.py \
      --ticker AAPL \
      --url https://example.com/feed.xml

The command prints JSON so it can be reviewed before being loaded into a
database or checked into a demo-data fixture.
