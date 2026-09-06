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

function indicatorsWithHistory(
  provenance: "live_fresh" | "live_stale" | "review_fixture" | "unavailable",
  recordCount = 50,
): StockBundle["indicators"] {
  const usable = provenance !== "unavailable";
  return {
    ...bundle().indicators,
    availability: {
      price_line: usable && recordCount >= 2,
      price_change: usable && recordCount >= 2,
      moving_average_20: usable && recordCount >= 20,
      moving_average_50: usable && recordCount >= 50,
      rsi: usable && recordCount >= 15,
      macd: usable && recordCount >= 26,
      macd_signal: usable && recordCount >= 34,
      volume: usable && recordCount >= 1,
      volatility: usable && recordCount >= 21,
    },
    history: {
      provenance,
      record_count: recordCount,
      completed_close_count: recordCount,
      required_for_complete: 50,
      is_ordered: true,
      has_unique_dates: true,
      has_valid_closes: true,
      has_valid_ohlcv: true,
      has_only_completed_closes: true,
      is_valid: recordCount > 0,
      complete_view: usable && recordCount >= 50,
      explanation: `${recordCount} verified closes are available.`,
    },
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
  assert.match(summary.freshness, /^Quote snapshot/);
  assert.equal(summary.hasVerifiedMarketData, false);
  assert.equal(summary.hasDailyPriceCurve, false);
  assert.match(summary.warning ?? "", /daily price history is stale/);
});

test("missing history and availability fail closed even when a daily-cache point exists", () => {
  const summary = getQuoteProvenance(bundle());

  assert.equal(summary.hasVerifiedMarketData, false);
  assert.equal(summary.hasDailyPriceCurve, false);
  assert.equal(summary.hasPriceCurve, false);
  assert.equal(summary.preferredChartRange, "6M");
});

test("a stale daily close is never presented as current", () => {
  const summary = getQuoteProvenance(bundle({
    indicators: indicatorsWithHistory("live_stale"),
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
  assert.equal(summary.hasVerifiedMarketData, true);
  assert.equal(summary.hasPriceCurve, false);
  assert.equal(summary.preferredChartRange, "6M");
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

test("weekly history never makes demo fallback eligible for a daily curve", () => {
  const summary = getQuoteProvenance(bundle({
    prices: ["2026-08-27", "2026-08-28"].map((date, index) => ({
      date,
      open: 500 + index,
      high: 505 + index,
      low: 499 + index,
      close: 503 + index,
      volume: 100 + index,
      source: "demo_fallback" as const,
      is_stale: false,
    })),
    weekly_history: ["2026-08-21", "2026-08-28"].map((date, index) => ({
      date,
      open: 490 + index,
      high: 505 + index,
      low: 480 + index,
      close: 500 + index,
      volume: 1_000 + index,
      frequency: "weekly" as const,
      source: "alpha_vantage_weekly" as const,
      retrieved_at: "2026-08-29T00:00:00Z",
    })),
    indicators: indicatorsWithHistory("live_fresh", 2),
  }));

  assert.equal(summary.hasDailyPriceCurve, false);
  assert.equal(summary.hasWeeklyPriceCurve, true);
  assert.equal(summary.hasPriceCurve, true);
  assert.equal(summary.preferredChartRange, "6M");
  assert.match(summary.source, /Demo fallback/);
});

test("a cache source alone cannot claim verified or complete history", () => {
  const summary = getQuoteProvenance(bundle({
    indicators: {
      ...bundle().indicators,
      availability: {
        price_line: false,
        price_change: false,
        moving_average_20: false,
        moving_average_50: false,
        rsi: false,
        macd: false,
        macd_signal: false,
        volume: false,
        volatility: false,
      },
      history: {
        provenance: "live_fresh",
        record_count: 1,
        completed_close_count: 1,
        required_for_complete: 50,
        is_ordered: true,
        has_unique_dates: true,
        has_valid_closes: true,
        has_valid_ohlcv: true,
        has_only_completed_closes: true,
        is_valid: true,
        complete_view: false,
        explanation: "1 verified close is available; 50 are required for the complete technical view.",
      },
    },
  }));

  assert.equal(summary.hasVerifiedMarketData, true);
  assert.equal(summary.hasPriceCurve, false);
  assert.equal(summary.hasCompleteTechnicalHistory, false);
});

test("review fixture allows a curve but never claims verified market data", () => {
  const reviewPrices = ["2026-08-27", "2026-08-28"].map((date, index) => ({
    date,
    open: 500 + index,
    high: 505 + index,
    low: 499 + index,
    close: 503 + index,
    volume: 100 + index,
    source: "review_fixture" as const,
    is_stale: false,
  }));
  const summary = getQuoteProvenance(bundle({
    prices: reviewPrices,
    indicators: indicatorsWithHistory("review_fixture", 2),
  }));

  assert.equal(summary.label, "Simulated review close");
  assert.equal(summary.source, "Review fixture (simulated)");
  assert.equal(summary.freshness, "Simulated review data");
  assert.equal(summary.hasVerifiedMarketData, false);
  assert.equal(summary.hasDailyPriceCurve, true);
  assert.equal(summary.hasPriceCurve, true);
  assert.equal(summary.preferredChartRange, "1M");
  assert.match(summary.curveSource, /Simulated/);
  assert.match(summary.warning ?? "", /not live market data/);
});

test("review fixture never exposes a bundled quote as live market data", () => {
  const reviewPrices = ["2026-08-27", "2026-08-28"].map((date, index) => ({
    date,
    open: 500 + index,
    high: 505 + index,
    low: 499 + index,
    close: 503 + index,
    volume: 100 + index,
    source: "review_fixture" as const,
    is_stale: false,
  }));
  const summary = getQuoteProvenance(bundle({
    prices: reviewPrices,
    indicators: indicatorsWithHistory("review_fixture", 2),
    quote: {
      ticker: "MSFT",
      close: 999,
      open: 998,
      high: 1_000,
      low: 997,
      previous_close: 996,
      as_of: "2026-08-30T01:30:00Z",
      source: "finnhub_quote",
    },
  }));

  assert.equal(summary.label, "Simulated review close");
  assert.equal(summary.value, 504);
  assert.equal(summary.source, "Review fixture (simulated)");
  assert.equal(summary.hasVerifiedMarketData, false);
  assert.match(summary.warning ?? "", /not live market data/);
});

test("valid weekly history remains inspectable without daily verification", () => {
  const summary = getQuoteProvenance(bundle({
    prices: [{
      date: "2026-08-28",
      open: 500,
      high: 505,
      low: 499,
      close: 503,
      volume: 100,
      source: "demo_fallback",
      is_stale: true,
    }],
    weekly_history: ["2026-08-21", "2026-08-28"].map((date, index) => ({
      date,
      open: 490 + index,
      high: 505 + index,
      low: 480 + index,
      close: 500 + index,
      volume: 1_000 + index,
      frequency: "weekly" as const,
      source: "alpha_vantage_weekly" as const,
      retrieved_at: "2026-08-29T00:00:00Z",
    })),
  }));

  assert.equal(summary.hasVerifiedMarketData, false);
  assert.equal(summary.hasDailyPriceCurve, false);
  assert.equal(summary.hasWeeklyPriceCurve, true);
  assert.equal(summary.hasPriceCurve, true);
  assert.match(summary.curveSource, /weekly Alpha Vantage/);
  assert.equal(summary.preferredChartRange, "6M");
});

test("review-fixture weekly history is labelled simulated instead of Alpha Vantage", () => {
  const summary = getQuoteProvenance(bundle({
    data_mode: "review_fixture",
    prices: [],
    weekly_history: ["2025-02-14", "2025-02-21"].map((date, index) => ({
      date,
      open: 100 + index,
      high: 102 + index,
      low: 99 + index,
      close: 101 + index,
      volume: 1000,
      frequency: "weekly" as const,
      source: "review_fixture" as const,
      retrieved_at: "2025-03-01T00:00:00Z",
    })),
    indicators: indicatorsWithHistory("unavailable", 0),
  }));

  assert.equal(summary.hasPriceCurve, true);
  assert.equal(summary.curveSource, "Simulated review fixture");
  assert.equal(summary.preferredChartRange, "6M");
  assert.equal(summary.hasVerifiedMarketData, false);
});

test("mixed weekly provenance fails closed instead of inheriting the first source label", () => {
  const summary = getQuoteProvenance(bundle({
    data_mode: "review_fixture",
    prices: [],
    weekly_history: [
      {
        date: "2025-02-14",
        open: 100,
        high: 102,
        low: 99,
        close: 101,
        volume: 1000,
        frequency: "weekly",
        source: "review_fixture",
        retrieved_at: "2025-03-01T00:00:00Z",
      },
      {
        date: "2025-02-21",
        open: 101,
        high: 103,
        low: 100,
        close: 102,
        volume: 1100,
        frequency: "weekly",
        source: "alpha_vantage_weekly",
        retrieved_at: "2025-03-01T00:00:00Z",
      },
    ],
    indicators: indicatorsWithHistory("unavailable", 0),
  }));

  assert.equal(summary.hasWeeklyPriceCurve, false);
  assert.equal(summary.hasPriceCurve, false);
  assert.equal(summary.curveSource, "Unavailable at the current history threshold");
});

test("history provenance must match the bundle mode before daily data can be shown", () => {
  const liveMetadataWithFixtureRows = getQuoteProvenance(bundle({
    prices: ["2026-08-27", "2026-08-28"].map((date, index) => ({
      date,
      open: 500 + index,
      high: 505 + index,
      low: 499 + index,
      close: 503 + index,
      volume: 100 + index,
      source: "review_fixture" as const,
      is_stale: false,
    })),
    indicators: indicatorsWithHistory("live_fresh", 50),
  }));
  const fixtureModeWithLiveMetadata = getQuoteProvenance(bundle({
    data_mode: "review_fixture",
    prices: ["2026-08-27", "2026-08-28"].map((date, index) => ({
      date,
      open: 500 + index,
      high: 505 + index,
      low: 499 + index,
      close: 503 + index,
      volume: 100 + index,
      source: "review_fixture" as const,
      is_stale: false,
    })),
    indicators: indicatorsWithHistory("live_fresh", 50),
  }));

  assert.equal(liveMetadataWithFixtureRows.hasDailyPriceCurve, false);
  assert.equal(liveMetadataWithFixtureRows.hasCompleteTechnicalHistory, false);
  assert.equal(fixtureModeWithLiveMetadata.hasDailyPriceCurve, false);
  assert.equal(fixtureModeWithLiveMetadata.hasCompleteTechnicalHistory, false);
});

test("review-fixture unavailable state stays visibly simulated", () => {
  const summary = getQuoteProvenance(bundle({
    data_mode: "review_fixture",
    prices: [],
    weekly_history: [],
    indicators: indicatorsWithHistory("unavailable", 0),
  }));

  assert.equal(summary.label, "Simulated price unavailable");
  assert.equal(summary.source, "Review fixture (simulated)");
  assert.equal(summary.freshness, "Simulated unavailable state");
  assert.match(summary.warning ?? "", /intentionally omits/);
});
