# Database Schema Plan

Last reviewed: 2026-08-27

The authoritative implemented DDL is `backend/supabase/schema.sql` plus its
migrations. This document summarizes the current schema and the planned
portfolio additions; planned tables are not implemented until their migration
phase completes.

The timing and ownership of those migrations are fixed by
[`ADR-0001`](../architecture/decisions/0001-staged-supabase-schema-and-queue.md).
In particular, Phase 1 changes domain contracts but does not alter the hosted
database. Debate business tables arrive in Phase 3, while the `pgmq` Queue is a
separate Phase 5 migration.

Phase 1 now has validated database-independent models and repository protocols
for the planned Debate relations. They are the input to Phase 3 DDL design, not
evidence that the tables already exist.

## Implemented tables

### stocks

Stores supported stock tickers.

Fields:
- id
- ticker
- company_name
- exchange
- sector

### stock_prices

Stores daily stock price data.

Fields:
- id
- stock_id
- date
- open
- high
- low
- close
- volume

### technical_indicators

Stores calculated indicator values.

Fields:
- id
- stock_id
- date
- rsi
- macd
- macd_signal
- moving_average_20
- moving_average_50
- volatility
- volume_spike

### evidence_documents

Stores news articles and filing documents.

Fields:
- id
- stock_id
- source_type
- title
- url
- published_at
- raw_text

### financial_facts

Stores typed SEC XBRL facts for exact filtering, comparisons, and arithmetic.
Vector retrieval can locate a relevant statement, but numerical answers use
these values and their explicit period/unit context.

Fields:
- id
- stock_id
- taxonomy
- concept
- label
- description
- unit
- value
- period_start
- period_end
- fiscal_year
- fiscal_period
- form
- filed_at
- accession_number
- frame
- source_url
- metadata

### evidence_chunks

Stores chunks for RAG retrieval.

Fields:
- id
- document_id
- chunk_text
- embedding
- metadata

The legacy `embedding` column remains the deterministic `local-hash-v1`
compatibility path. New model-generated vectors are stored separately.

### embedding_profiles

Defines one versioned vector-space contract.

Fields:
- id
- slug
- provider
- model
- dimensions
- distance_metric
- normalization
- modality
- query_instruction
- document_instruction
- preprocessing_version
- status
- metadata

### chunk_embeddings

Stores zero or more model-specific embeddings for each canonical evidence
chunk. The `(chunk_id, profile_id)` key prevents one provider from overwriting
another. A validation trigger rejects vectors whose dimensions do not match
their profile.

Fields:
- chunk_id
- profile_id
- embedding
- input_hash
- created_at

Production profiles receive their own partial HNSW expression index because
pgvector indexes can cover only one dimension count at a time.

### analysis_runs

Stores each user-triggered AI analysis.

Fields:
- id
- user_id
- stock_id
- created_at
- final_summary
- guardrail_status

### agent_outputs

Stores each agent output.

Fields:
- id
- analysis_run_id
- agent_name
- output_json
- created_at

### token_usage

Stores estimated token usage.

Fields:
- id
- analysis_run_id
- model_name
- prompt_tokens
- completion_tokens
- total_tokens

### Other implemented relations

The current DDL also includes:

- `watchlists` for user-owned saved stocks;
- `stock_price_history` for labelled weekly history;
- `macro_series` and `macro_observations` for cached dated market context;
- `claim_evidence` for analysis-claim citations; and
- RLS/grants and vector-search functions used by the API and ingestion jobs.

## Planned portfolio additions

Detailed fields, state names, and acceptance criteria are canonical in the
[`portfolio implementation plan`](../planning/portfolio-implementation-plan.md).

### Stock catalog coverage

Extend `stocks` with bounded catalog and capability metadata:

- sec_cik (nullable and non-unique across share classes)
- country
- aliases/search_text
- is_active
- coverage_status: `catalog_only`, `price_cached`, `evidence_ready`, or
  `debate_ready`
- coverage_updated_at

Coverage describes configured capabilities. Response-level source/freshness
still determines whether cached data is safe to display or use.

[`ADR-0002`](../architecture/decisions/0002-sec-static-stock-catalog.md)
selects a checked-in snapshot derived from the SEC ticker/exchange association
file. The first import includes Nasdaq, NYSE, and CBOE rows only, rejects more
than 10,000 normalized rows, leaves unverified country and sector values null,
and assigns every non-demo row `catalog_only`. Catalog generation is a manual
maintenance operation; application search never calls the SEC or a market-data
provider.

### `debate_sessions`

Canonical state and immutable context for one multi-turn Debate:

- owner, stock, mode, status, opening side, initial question;
- active branch and generation IDs;
- factor/price/evidence snapshot;
- interim/final Judge outputs and guardrail status;
- safe error code and timestamps.

### `debate_jobs`

Persistent application job ledger paired with the Supabase Queue:

- session/owner/job type/status;
- unique idempotency key and queue message ID;
- attempts, availability, start/finish times;
- safe failure code, provider call count, and token usage.

The Queue payload contains only job/session IDs and safe trace metadata. It does
not contain credentials, raw authorization headers, or protected prompt text.

### `debate_messages`

Ordered, branch-aware completed or cancelled messages:

- session, branch, generation, sequence, round, and exchange;
- Bull/Bear/Judge/User/Explainer role and message kind;
- content and bounded confidence metadata;
- completion/cancellation state and timestamps;
- unique `(session_id, branch_id, sequence_number)` for idempotent redelivery.

### `debate_message_evidence`

Many-to-many citations between complete messages and the immutable allowed
evidence set, with citation order and optional support-span metadata.

### `debate_interventions`

User-owned selected text, question, target message, and mode (`explain` or
`challenge`). Inputs are length-bounded and protected by session ownership RLS.

### Factor storage decision

Define `FactorObservation` as a versioned domain contract first. Store its
immutable list in the Debate session snapshot for this milestone rather than
adding a table for every possible future provider. Add normalized factor tables
only when cross-session queries or ingestion volume justify them.

### Queue extension

Enable Supabase Queues/`pgmq` through a focused migration. Create enqueue/claim
RPCs with the minimum required privileges. User-facing RLS and the server-only
Worker role remain separate.

Do not manually reproduce `pgmq` transport columns in `public`. The planned
`public.debate_jobs` relation is an application job ledger; the extension-owned
active/archive queue tables handle delivery and visibility.

## Migration rules

- Add new relations; do not destructively rewrite legacy analysis history.
- Keep `/analysis` compatible behind the V2 feature flag until the new path is
  verified.
- Add every table, grant, RLS policy, and index in reviewable migrations.
- Test two-user isolation and service-worker access before deployment.
- Make queue redelivery and HTTP duplicate submissions safe through database
  uniqueness, not Redis alone.
