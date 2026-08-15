users
watchlists
stocks
stock_prices
technical_indicators
financial_facts
evidence_documents
evidence_chunks
embedding_profiles
chunk_embeddings
analysis_runs
agent_outputs
claim_evidence
token_usage

# Database Schema Plan

## stocks

Stores supported stock tickers.

Fields:
- id
- ticker
- company_name
- exchange
- sector

## stock_prices

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

## technical_indicators

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

## evidence_documents

Stores news articles and filing documents.

Fields:
- id
- stock_id
- source_type
- title
- url
- published_at
- raw_text

## financial_facts

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

## evidence_chunks

Stores chunks for RAG retrieval.

Fields:
- id
- document_id
- chunk_text
- embedding
- metadata

The legacy `embedding` column remains the deterministic `local-hash-v1`
compatibility path. New model-generated vectors are stored separately.

## embedding_profiles

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

## chunk_embeddings

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

## analysis_runs

Stores each user-triggered AI analysis.

Fields:
- id
- user_id
- stock_id
- created_at
- final_summary
- guardrail_status

## agent_outputs

Stores each agent output.

Fields:
- id
- analysis_run_id
- agent_name
- output_json
- created_at

## token_usage

Stores estimated token usage.

Fields:
- id
- analysis_run_id
- model_name
- prompt_tokens
- completion_tokens
- total_tokens
