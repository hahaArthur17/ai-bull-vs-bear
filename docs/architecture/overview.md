# Architecture overview

The project is organized as a small monorepo:

    apps/mobile  ->  FastAPI  ->  DemoStore or Supabase
                         |
                         +-> indicators
                         +-> evidence retrieval
                         +-> Bull / Bear / Judge / Guardrail workflow

## Runtime modes

### Demo mode

Demo mode is the default. The API creates deterministic cached OHLCV data and
serves curated evidence for AAPL, GOOG, NVDA, and TSLA. It keeps the mobile
flow reproducible and does not require credentials.

### Persistence mode

Supabase schema.sql defines the tables, pgvector column, and row-level security
policies needed for persistent watchlists, analyses, agent outputs, evidence
chunks, and token usage. The current API keeps DemoStore as the safe fallback
until a Supabase project and authentication flow are configured.

### Model-provider mode

The analysis service uses the deterministic provider by default and can select
Groq or Gemini through ANALYSIS_PROVIDER. The provider adapters return a
validated Bull/Bear/Judge JSON draft, filter evidence IDs to the retrieved
corpus, record token usage, and pass all user-facing text through the guardrail
policy before it reaches the user.

## Data flow

1. The mobile client requests supported stocks and the user's watchlist.
2. Stock detail requests cached OHLCV, calculated indicators, and evidence.
3. An analysis run retrieves and ranks evidence for the user's question.
4. Technical, news, and filing context is aggregated into Bull and Bear claims.
5. The Judge produces a neutral summary with uncertainty and risk level.
6. Guardrails check language and the API returns claims, citations, trace, and
   token usage.
7. Cross-examination requests use the claim ID to return focused explanations
   and the relevant evidence.
