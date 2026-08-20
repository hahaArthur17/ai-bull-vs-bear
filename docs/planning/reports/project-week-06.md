# Project Week 6 Report — Current-price integrity, charts, and macro cache

Reporting date: 2026-08-21  
Status: In progress

## Goal

Make an AAPL Debate reproducible against a completed market close, distinguish
dated context from proven causation, and replace numeric-only Signals with
inspectable continuous charts. Begin a zero-cost market-background data layer
without letting it become an unsupported causal narrative.

## Completed work

- Removed the Supabase-path fallback to deterministic evidence (`698913f`) and
  classified source freshness (`a41f9e6`, `5eec7e7`). News has a seven-day
  window and filing context has a 120-day window; stale or undated external
  items are excluded before Debate generation (`b256d1`).
- Added an AAPL Apple Newsroom RSS source and weekday, AAPL-only evidence
  refresh (`b7b2bfa`, `7ce603e`, `3d0a9bd`). The job also refreshes SEC context.
- Made the current-close question explicit, restored technical context when
  vector retrieval omits it, cited only included technical evidence, and
  persisted an analysis snapshot (`542dd27`, `1ae9521`, `0cfaff5`, `f45f2fe`).
- Displayed the immutable snapshot in mobile Debate and added claim-level
  market-close dates plus dated/freshness-tagged evidence citations
  (`90db560`, `e90ecc3`). The snapshot now freezes each evidence item's type,
  publication date, and freshness metadata (`1f2ac21`).
- Added a no-current-news safety cap: in that state the Judge is `weak`, both
  claims are `weak`/`low`, and a filing is named as long-horizon context rather
  than a proven daily-price catalyst (`3a76172`).
- Stored a labelled AAPL weekly history and scheduled a Saturday refresh
  (`d8a8665`, `31de197`, `96cb0b6`), then added a mobile 1M/3M/6M/1Y chart with
  drag/crosshair, accessible Earlier/Later controls, selected point metadata,
  and data provenance (`a735c1b`, `e42d0b2`).
- Replaced numeric-only Signals with continuous MA20/MA50, RSI (30/70 guide
  lines), MACD plus histogram, volume, and annualised-volatility charts
  (`2c20ec4`); added price-chart MA overlays (`2268ac3`) and indicator as-of
  dates (`d4c4bde`).
- Added FRED and EIA clients, bounded Supabase market-context storage, a
  seven-series cache, typed read endpoints, and one weekday GitHub Actions
  refresh (`713a402` through `c815250`). Live initialization wrote 2,719
  observations across S&P 500, VIX, effective Fed funds, 2Y/10Y/30Y Treasury
  yields, and WTI oil.
- Added a grouped cache-only context API, AAPL-only mobile loading, four
  continuous market-background charts, and the immutable Debate macro snapshot
  (`8c43ad7`, `fe3dacc`, `a28f1af`, `1e15a7d`, `21c2d84`).

## Live data and deployment state

- The two new Supabase migrations for macro observations and AAPL weekly price
  history are applied. Initial macro, Apple Newsroom/SEC, and weekly-history
  backfills ran successfully.
- A read-only audit found that `macro_series` did not have its intended public
  RLS policy: the service role saw seven cached rows while the anonymous
  frontend saw none. Applied the narrow read-only policy repair and added
  `20260821_fix_macro_series_read_policy.sql` (`9581206`). Anonymous reads now
  return all seven series and their latest observation dates.
- GitHub Actions holds the needed secrets for FRED, EIA, SEC identity, Alpha
  Vantage, and Supabase. Values are encrypted and are not recorded in this
  repository or report.
- The scheduled routine stays bounded: one AAPL Alpha Vantage daily request on
  market weekdays, one weekly-history request on Saturday, and a single cache
  pass for macro/evidence data. The app reads Supabase caches and does not call
  providers when a user opens a screen.

## Verification

- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests -q`:
  76 passed. The only output is an existing Starlette/httpx deprecation warning.
- `npm run typecheck` and `npm run build:web` in `apps/mobile`: pass.
- A live production-store audit confirmed that included Debate source types are
  filing, news, and technical; every claim citation is included; demo evidence
  is absent; and the recorded close source is a non-stale daily market cache.

## Decisions and boundaries

- A current close, exact evidence set, and freshness result are one analytical
  unit. A later refresh must not rewrite the stored analysis record.
- News is necessary for a plausible same-day company catalyst. A filing can
  explain longer-horizon business context, but does not replace current news.
- FRED/EIA market series are background inputs only. Any future Debate wording
  must say that they may provide context, not that they caused AAPL's move.
- CME FedWatch represents market-implied probabilities derived from Fed funds
  futures, not the Federal Reserve's own forecast. The public website can be
  cited manually; the official API is paid. Do not scrape it or use an
  undocumented endpoint.

## Remaining work

1. Choose a licensed, automated Fed-funds-probability source only if that data
   becomes necessary; otherwise keep a manual CME FedWatch reference.
2. Complete physical iOS/Android and browser visual checks for the new charts.
3. Consider a bounded news source for broader market narratives (Fed meetings,
   geopolitical shocks, and oil/liquidity effects) without treating headlines
   as evidence of causation.

## Handoff links

- [`../week-4-todo.md`](../week-4-todo.md)
- [`../weekly-roadmap.md`](../weekly-roadmap.md)
- [`../../architecture/vectorization-strategy.md`](../../architecture/vectorization-strategy.md)
