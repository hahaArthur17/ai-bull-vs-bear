import assert from "node:assert/strict";
import test from "node:test";

import { getQuoteProvenance } from "./stockResearchSummary.ts";
import type { Stock, StockBundle } from "./types.ts";

const stock: Stock = {
  ticker: "MSFT",
  company_name: "Microsoft Corporation",
  exchange: "NASDAQ",
  sector: "Technology",
  sec_cik: 789019,
  country: "US",
  aliases: [],
  is_active: true,
  coverage_status: "debate_ready",
  coverage_updated_at: "2026-08-30T00:00:00Z",
};

function bundle(overrides: Partial<StockBundle> = {}): StockBundle {
  return {
    stock,
    prices: [{
      date: "2026-08-28",
      open: 500,
      high: 505,
      low: 499,
      close: 503,
      volume: 100,
      source: "daily_market_cache",
      is_stale: false,
    }],
    weekly_history: [],
    quote: null,
    indicators: {
      ticker: "MSFT",
      as_of: "2026-08-28",
      rsi: 50,
      macd: 0,
      macd_signal: 0,
      moving_average_20: 500,
      moving_average_50: 490,
      volatility: 10,
      volume_spike: false,
      signal_summary: "Neutral",
    },
    evidence: [],
    macro_context: [],
    ...overrides,
  };
}

test("quote provenance retains the intraday source, timestamp, and daily-history warning", () => {
  const summary = getQuoteProvenance(bundle({
    quote: {
      ticker: "MSFT",
      close: 504,
      open: 500,
      high: 505,
      low: 499,
      previous_close: 503,
      as_of: "2026-08-30T01:30:00Z",
      source: "finnhub_quote",
    },
    prices: [{
      date: "2026-08-28",
      open: 500,
      high: 505,
      low: 499,
      close: 503,
      volume: 100,
      source: "daily_market_cache",
      is_stale: true,
    }],
  }));

  assert.equal(summary.value, 504);
  assert.equal(summary.source, "Finnhub quote");
  assert.match(summary.timestamp, /^Quote time/);
  assert.match(summary.warning ?? "", /daily price history is stale/);
});

test("a stale daily close is never presented as current", () => {
  const summary = getQuoteProvenance(bundle({
    prices: [{
      date: "2026-08-28",
      open: 500,
      high: 505,
      low: 499,
      close: 503,
      volume: 100,
      source: "daily_market_cache",
      is_stale: true,
    }],
  }));

  assert.equal(summary.label, "Latest daily close");
  assert.equal(summary.freshness, "Stale daily market data");
  assert.match(summary.warning ?? "", /stale/);
});

test("demo fallback remains unavailable rather than being shown as a market quote", () => {
  const summary = getQuoteProvenance(bundle({
    prices: [{
      date: "2026-08-28",
      open: 500,
      high: 505,
      low: 499,
      close: 503,
      volume: 100,
      source: "demo_fallback",
      is_stale: false,
    }],
  }));

  assert.equal(summary.value, null);
  assert.equal(summary.hasVerifiedMarketData, false);
  assert.match(summary.source, /not displayed as a market price/);
});
