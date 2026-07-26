users
watchlists
stocks
stock_prices
technical_indicators
evidence_documents
evidence_chunks
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

## evidence_chunks

Stores chunks for RAG retrieval.

Fields:
- id
- document_id
- chunk_text
- embedding
- metadata

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