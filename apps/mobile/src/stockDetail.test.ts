import assert from "node:assert/strict";
import test from "node:test";

import { loadStockDetail } from "./stockDetail.ts";
import type { Stock, StockBundle } from "./types";

const nvda: Stock = {
  ticker: "NVDA",
  company_name: "NVIDIA Corporation",
  exchange: "NASDAQ",
  sector: "Technology",
  sec_cik: 1045810,
  country: "US",
  aliases: [],
  is_active: true,
  coverage_status: "debate_ready",
  coverage_updated_at: "2026-08-29T00:00:00Z",
};

const nvdaBundle: StockBundle = {
  stock: nvda,
  prices: [],
  weekly_history: [],
  quote: null,
  indicators: {
    ticker: "NVDA",
    as_of: "2026-08-29",
    rsi: 50,
    macd: 0,
    macd_signal: 0,
    moving_average_20: 1,
    moving_average_50: 1,
    volatility: 0,
    volume_spike: false,
    signal_summary: "Neutral",
  },
  evidence: [],
  macro_context: [],
};

test("Loading a saved Debate ticker replaces the stock snapshot with its matching bundle", async () => {
  const result = await loadStockDetail({
    getStock: async (ticker) => ({ ...nvda, ticker }),
    getStockBundle: async () => nvdaBundle,
  }, "NVDA");

  assert.equal(result.stock.ticker, "NVDA");
  assert.equal(result.bundle?.stock.ticker, "NVDA");
});

test("Catalog-only stocks do not request a missing market-data bundle", async () => {
  let bundleRequested = false;
  const result = await loadStockDetail({
    getStock: async () => ({ ...nvda, coverage_status: "catalog_only" }),
    getStockBundle: async () => {
      bundleRequested = true;
      return nvdaBundle;
    },
  }, "NVDA");

  assert.equal(result.bundle, null);
  assert.equal(bundleRequested, false);
});
