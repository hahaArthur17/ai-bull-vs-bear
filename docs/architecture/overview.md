# Architecture overview

Last reviewed: 2026-08-27

This document distinguishes the implemented baseline from the accepted target.
The detailed phase order and acceptance criteria live in the canonical
[`portfolio-implementation-plan.md`](../planning/portfolio-implementation-plan.md).

## Implemented baseline

The project is organized as a small monorepo:

    apps/mobile  ->  FastAPI  ->  DemoStore or Supabase
                         |
                         +-> indicators
                         +-> evidence retrieval
                         +-> Bull / Bear / Judge / Guardrail workflow

## Implemented runtime modes

### Demo mode

Demo mode is the default. The API creates deterministic cached OHLCV data and
serves curated evidence for AAPL, GOOG, NVDA, and TSLA. It keeps the mobile
flow reproducible and does not require credentials.

### Persistence mode

Supabase `schema.sql` defines the tables, pgvector storage, grants, and row-level
security policies needed for persistent watchlists, analyses, agent outputs,
evidence, price/macro caches, structured financial facts, and token usage. The
deployed production API uses Supabase; `DemoStore` remains the credential-free
local/test fallback.

### Model-provider mode

The analysis service uses the deterministic provider by default and can select
Groq or Gemini through ANALYSIS_PROVIDER. The provider adapters return a
validated Bull/Bear/Judge JSON draft, filter evidence IDs to the retrieved
corpus, record token usage, and pass all user-facing text through the guardrail
policy before it reaches the user.

## Implemented single-response data flow

1. The mobile client requests supported stocks and the user's watchlist.
2. Stock detail requests cached OHLCV, calculated indicators, and evidence.
3. An analysis run retrieves and ranks evidence for the user's question.
4. Technical, news, and filing context is aggregated into Bull and Bear claims.
5. The Judge produces a neutral summary with uncertainty and risk level.
6. Guardrails check language and the API returns claims, citations, trace, and
   token usage.
7. Cross-examination requests use the claim ID to return focused explanations
   and the relevant evidence.

## Accepted portfolio target

The next milestone remains a modular monolith but adds clear domain and process
boundaries:

```text
Expo client -> FastAPI API -> Supabase canonical data
                    |             `-> durable Debate Queue
                    |-> Redis cache, rate limits, idempotency locks
                    `-> bounded Worker -> Factor Registry
                                       -> Bull/Bear/Judge/Explainer
                                       -> streamed Debate events
```

The free deployment initially runs the API and bounded Queue consumer in the
same FastAPI service. The Worker also receives a standalone entry point so the
consumer can move to separate compute later without changing the Debate domain
or provider contracts.

Target responsibilities:

- `FactorProvider` adapters normalize the existing technical, macro, news,
  filing, and financial-fact inputs. No new live factor source is part of this
  milestone.
- Supabase remains the source of truth for sessions, jobs, complete messages,
  citations, interventions, history, and immutable snapshots.
- Supabase Queues provides durable admission, retry, visibility timeout, and
  backpressure for Debate stages.
- Redis accelerates hot reads, rate limits expensive work, and coordinates
  duplicate-request locks. It is not the canonical Queue or history store.
- Authenticated SSE-formatted events stream the active turn. Complete validated
  messages are persisted so a reconnect can recover without storing every token.
- Catalog search is independent of market-data providers. A stock can be
  watchlist-only while full Debate remains restricted to `debate_ready` symbols.

## Target Debate flow

1. Create an authenticated session and immutable factor/evidence snapshot.
2. Enqueue a round-one stage and return `202 Accepted`.
3. The Worker produces six mutually aware Bull/Bear messages and an interim
   Judge summary while the client receives streamed events.
4. Persist each completed message and pause at `awaiting_user`.
5. An explanation request leaves the session state unchanged; a challenge
   creates an intervention and a new branch from the last complete message.
6. Enqueue round two, produce four grounded messages and a final Judge summary,
   then mark the session complete.
7. Retry/redelivery resumes from the next missing planned turn, and Redis plus
   database uniqueness prevents duplicate submissions and outputs.
