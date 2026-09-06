# Phase 8 market-history and indicator contract

**Status:** Implemented locally in WP1

**Recorded:** 2026-09-07

**Parent:** [`phase-8-design-remediation.md`](phase-8-design-remediation.md)

## Daily-history integrity

Technical presentation consumes rows exactly as received. It does not silently
sort or deduplicate them. A structurally valid history has positive finite
closes, valid ISO dates, strictly increasing unique dates, and no date after the
UTC completed-candle cutoff. Ingestion additionally rejects non-finite or
non-positive OHLC values, inconsistent high/low ranges, and negative volume.
The configured daily providers return date-only completed candles; provider
ingestion and API presentation use the same close-history validator.

Trusted presentation provenance is one of `live_fresh`, `live_stale`, or the
separately labelled `review_fixture`. A review fixture may satisfy mathematical
series thresholds, but it never sets `hasVerifiedMarketData` and every value,
curve source, and warning identifies it as simulated. `demo_fallback`, missing,
and mixed source rows map to `unavailable`. Staleness does not erase otherwise
verified history: the chart may render with a warning, while freshness remains
explicit.

A complete technical view requires 50 valid, trusted closes. Each series still
uses its own mathematical minimum:

| Series | Minimum closes | Rule |
| --- | ---: | --- |
| Price line and selected-range price change | 2 | Use the first and last visible close; do not invent a percentage when the start is zero. |
| Volume | 1 | Display observed daily volume only. |
| RSI 14 | 15 | First value after 14 price changes. |
| MA20 | 20 | Complete trailing arithmetic-mean window. |
| Volatility 20 | 21 | Twenty close-to-close log returns. |
| MACD | 26 | EMA(12) minus EMA(26), with each EMA seeded from the first close. |
| MACD signal | 34 | EMA(9) over the full MACD sequence; values remain hidden through index 32. |
| MA50 / complete view | 50 | Complete trailing arithmetic-mean window. |

The API retains the existing numeric indicator fields for legacy consumers and
adds `availability` and `history`. A numeric compatibility value must never be
displayed when its availability flag is false. `history.complete_view` is the
only complete-view claim; a matching source string by itself is insufficient.

Long-horizon weekly history is independent of daily technical sufficiency. Two
or more positive, finite, strictly chronological `alpha_vantage_weekly` closes
allow the 6M/1Y curve shell to open even if the daily line is unavailable. This
does not set daily `hasVerifiedMarketData`, and the chart source remains
explicitly weekly.

## Canonical calculations

- RSI uses Wilder smoothing. The first average gain and loss divide all 14
  changes, including zero changes. A flat window is 50; gain with no loss is
  100.
- MA20 and MA50 use complete trailing windows and no partial-window average.
- MACD uses EMA multipliers `2 / (period + 1)` and first-close seeding. The
  signal uses the same rule over the full MACD sequence.
- Volatility uses the population standard deviation of the latest 20 natural
  log returns, annualised by `sqrt(252)` and expressed as a percentage.
- The API rounds scalar indicator outputs to four decimal places. Charts retain
  full calculation precision and format only at presentation.
- A volume spike requires at least 20 volumes and means the newest volume is
  greater than 1.35 times the mean of that same trailing 20-volume window.

The mirrored backend and TypeScript golden vector is part of the automated
test suite. Boundary tests cover 14/15, 19/20, 20/21, 25/26, 33/34, and 49/50
record transitions.

## Refresh success contract

Daily refresh reads the newest cached date before writing, validates provider
history before persistence, then reads the newest cached date again. A failed
ticker, invalid history, zero-row write, empty ticker selection, failed
post-write check, or newest fetched date that does not advance beyond the cached
date makes the CLI exit nonzero. The GitHub workflow runs that CLI directly, so
a green job means the expected cache advanced. Skipped tickers caused solely by
the explicit provider-call budget remain reported separately.

A non-advancing result does not necessarily mean a software defect: a market
holiday or a provider serving a stale candle can produce the same condition.
The workflow intentionally reports it as a failed freshness gate so an operator
can distinguish and acknowledge the cause instead of accepting an ambiguous
green run.

Supabase requires no schema change for WP1. Reads request the newest 100 rows in
descending order and reverse them in memory so the API receives the latest
window in chronological order. This prevents an ever-growing table from
returning its oldest 100 rows and appearing permanently stale.
