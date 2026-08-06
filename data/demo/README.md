# Demo data

The backend currently generates deterministic cached OHLCV data and serves
curated demo evidence for AAPL, GOOG, NVDA, and TSLA. This keeps the MVP
reproducible and avoids live-provider rate limits while the data-ingestion
adapters are being implemented.

The next provider integrations can replace backend/app/services/demo_store.py
without changing the public API contract.

