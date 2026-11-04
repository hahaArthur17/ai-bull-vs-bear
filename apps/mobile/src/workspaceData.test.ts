import assert from "node:assert/strict";
import test from "node:test";
import type { Stock } from "./types";
import { loadWorkspaceHome } from "./workspaceData.ts";

const stock = (ticker: string): Stock => ({
  ticker,
  company_name: ticker,
  exchange: "NASDAQ",
  sector: "Technology",
  coverage_status: "debate_ready",
  sec_cik: null,
  country: null,
  aliases: [],
  is_active: true,
  coverage_updated_at: "2026-10-17T00:00:00Z",
});

function source() {
  return {
    getHealth: async () => ({
      data_mode: "review_fixture",
      debate_workflow_v2: true,
    }),
    listStocks: async () => [stock("AAPL")],
    getWatchlist: async () => ({
      user_id: "user-a",
      tickers: ["MSFT", "DELISTED"],
    }),
    listAnalyses: async () => [],
    listDebates: async () => [],
    getStock: async (ticker: string) => {
      if (ticker === "DELISTED") throw new Error("Stock not found");
      return stock(ticker);
    },
  };
}

test("workspace retains saved identities and tolerates missing optional routes", async () => {
  const api = source();
  api.listDebates = async () => {
    throw new Error("Older deployment");
  };
  const home = await loadWorkspaceHome(api, false);
  assert.deepEqual(
    home.stocks.map(({ ticker }) => ticker),
    ["AAPL", "MSFT"],
  );
  assert.deepEqual(home.watchlist, ["MSFT", "DELISTED"]);
  assert.equal(home.reviewFixtureMode, true);
  assert.deepEqual(home.debates, []);
});

test("a failed workspace request is observed while the optional health request is pending", async () => {
  const api = source();
  let finishHealth!: (health: Awaited<ReturnType<typeof api.getHealth>>) => void;
  api.getHealth = () =>
    new Promise((resolve) => {
      finishHealth = resolve;
    });
  api.listStocks = async () => {
    throw new Error("Catalog unavailable");
  };
  await assert.rejects(loadWorkspaceHome(api, false), /Catalog unavailable/);
  finishHealth({ data_mode: "standard", debate_workflow_v2: false });
});
