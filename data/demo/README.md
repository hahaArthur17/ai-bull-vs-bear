# Demo data

Last reviewed: 2026-10-17.

`backend/app/services/demo_store.py` provides deterministic OHLCV and curated
evidence for AAPL, GOOG, NVDA and TSLA, alongside the versioned identity catalog.
It keeps default local tests usable without credentials. Live ingestion and
Supabase adapters are implemented separately; they do not replace demo inputs
silently or make deterministic evidence current market data.

For UI review, explicitly select `APP_DATA_MODE=review_fixture`. The separate
`review_fixture_store.py` supplies fresh/stale/insufficient/unavailable/catalog-only
states and seven dated simulated macro series. The profile forces demo
Auth/persistence, deterministic models, Queue off and Redis off even when a
local `.env` contains live credentials. Every fixture surface retains the
`SIMULATED DATA` label. Its synchronous V2 flow does not prove queued
streaming/Stop/Continue behavior.

See the [root quick start](../../README.md), [backend guide](../../backend/README.md)
and [live services setup](../../docs/setup/live-services.md) for the mode boundary.
