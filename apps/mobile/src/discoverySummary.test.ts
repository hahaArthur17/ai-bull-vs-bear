import assert from "node:assert/strict";
import test from "node:test";

import { getCoveragePresentation, getDiscoverySummary } from "./discoverySummary.ts";
import type { Stock } from "./types.ts";

function stock(ticker: string, coverageStatus: Stock["coverage_status"]): Stock {
  return {
    ticker,
    company_name: `${ticker} Incorporated`,
    exchange: "NASDAQ",
    sector: null,
    sec_cik: null,
    country: "US",
    aliases: [],
    is_active: true,
    coverage_status: coverageStatus,
    coverage_updated_at: "2026-08-30T00:00:00Z",
  };
}

const loadedStocks = [stock("AAPL", "debate_ready"), stock("MSFT", "catalog_only")];

test("discovery summary stays based on loaded stocks during a catalog search", () => {
  const temporarySearchResults = [stock("TSLA", "catalog_only")];

  assert.equal(getDiscoverySummary(loadedStocks).readyToReview, 1);
  assert.equal(temporarySearchResults.filter((item) => item.coverage_status === "debate_ready").length, 0);
});

test("clearing catalog search does not change the loaded-stock discovery summary", () => {
  const clearedSearchResults = [stock("AAPL", "debate_ready")];

  assert.equal(getDiscoverySummary(loadedStocks).readyToReview, 1);
  assert.equal(clearedSearchResults.length, 1);
});

test("rapid catalog query switches cannot replace the discovery summary", () => {
  const firstQueryResults = [stock("NVDA", "debate_ready")];
  const laterQueryResults = [stock("AMZN", "catalog_only")];

  assert.deepEqual(getDiscoverySummary(loadedStocks), { readyToReview: 1 });
  assert.notDeepEqual(firstQueryResults, laterQueryResults);
  assert.deepEqual(getDiscoverySummary(loadedStocks), { readyToReview: 1 });
});

test("coverage labels preserve partial research states in catalog results", () => {
  assert.deepEqual(getCoveragePresentation("debate_ready"), { label: "Research ready", tone: "ready" });
  assert.deepEqual(getCoveragePresentation("evidence_ready"), { label: "Evidence ready", tone: "ready" });
  assert.deepEqual(getCoveragePresentation("price_cached"), { label: "Limited coverage", tone: "partial" });
  assert.deepEqual(getCoveragePresentation("catalog_only"), { label: "Watchlist only", tone: "catalog" });
});
