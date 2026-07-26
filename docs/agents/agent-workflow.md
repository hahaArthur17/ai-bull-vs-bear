# Multi-Agent Workflow

## Step 1: Technical Agent

Input:
- OHLCV price data

Output:
- RSI
- MACD
- moving averages
- volatility
- volume spike
- technical signal summary

## Step 2: News RAG Agent

Input:
- ticker
- user question
- recent news chunks

Output:
- relevant news evidence
- news summary

## Step 3: Filing RAG Agent

Input:
- ticker
- company filing chunks

Output:
- relevant filing evidence
- risk factor summary

## Step 4: Evidence Aggregator

Input:
- technical signals
- news evidence
- filing evidence

Output:
- structured context for AI agents

## Step 5: Bull Agent

Output:
- positive claims
- evidence IDs
- confidence level

## Step 6: Bear Agent

Output:
- risk claims
- evidence IDs
- confidence level

## Step 7: Judge Agent

Output:
- neutral summary
- evidence strength
- uncertainty
- risk level

## Step 8: Guardrail Agent

Output:
- safe final response
- removed or rewritten unsafe advice