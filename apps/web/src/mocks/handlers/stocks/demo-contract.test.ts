import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { setupServer } from "msw/node";
import type { DebateRecord, Stock } from "@/lib/contracts/research";
import { clearDemoStorage } from "@/lib/storage";
import { createDebate } from "@/mocks/fixtures/debates";
import { makeResearch } from "@/mocks/fixtures/market";
import { resetDemoState, setDemoScenario } from "@/mocks/state/scenarios";
import { debateHandlers } from "../debates";
import { historyHandlers } from "../history";
import { watchlistHandlers } from "../watchlist";
import { stockHandlers } from "./index";

const server = setupServer(
  ...stockHandlers,
  ...watchlistHandlers,
  ...historyHandlers,
  ...debateHandlers,
);
const endpoint = (path: string) => `${window.location.origin}/api${path}`;

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  resetDemoState();
});
afterAll(() => server.close());

describe("public demo data contracts", () => {
  it("searches tickers and company names and exposes reproducible empty/error states", async () => {
    const response = await fetch(endpoint("/stocks?q=apple"));
    expect(((await response.json()) as Stock[]).map((stock) => stock.ticker)).toEqual(["AAPL"]);
    setDemoScenario("empty");
    expect(await (await fetch(endpoint("/stocks"))).json()).toEqual([]);
    setDemoScenario("error");
    expect((await fetch(endpoint("/stocks"))).status).toBe(503);
  });

  it("persists watchlist changes and restores the known baseline on reset", async () => {
    await fetch(endpoint("/watchlist"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker: "META" }),
    });
    expect(await (await fetch(endpoint("/watchlist"))).json()).toEqual({
      tickers: ["AAPL", "NVDA", "MSFT", "META"],
    });
    clearDemoStorage();
    expect(await (await fetch(endpoint("/watchlist"))).json()).toEqual({
      tickers: ["AAPL", "NVDA", "MSFT"],
    });
  });

  it("stores canonical synthetic history rather than arbitrary submitted text", async () => {
    const record = createDebate("AAPL");
    record.messages[0].content = "private@example.com";
    const response = await fetch(endpoint("/history"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(record),
    });
    expect(response.status).toBe(201);
    const saved = (await response.json()) as DebateRecord;
    expect(saved.id).toBe(record.id);
    expect(saved.messages[0].content).not.toContain("private@example.com");
    expect(localStorage.getItem("counterpoint.demo.v1.history")).not.toContain(
      "private@example.com",
    );
    await fetch(endpoint(`/history/${saved.id}`), { method: "DELETE" });
    expect(
      ((await (await fetch(endpoint("/history"))).json()) as DebateRecord[]).some(
        (item) => item.id === saved.id,
      ),
    ).toBe(false);
  });

  it("returns a useful not-found response for deleted or unknown replay IDs", async () => {
    expect((await fetch(endpoint("/demo/debates/missing-replay"))).status).toBe(404);
    const response = await fetch(endpoint("/demo/debates/demo-aapl"));
    expect(((await response.json()) as DebateRecord).ticker).toBe("AAPL");
  });

  it("supplies a deterministic full-year synthetic price series ending at the displayed quote", () => {
    const research = makeResearch("AAPL")!;
    expect(research.prices.at(-1)).toMatchObject({ date: "2026-10-30", close: 246.72 });
    const span = Date.parse(research.prices.at(-1)!.date) - Date.parse(research.prices[0].date);
    expect(span / 86_400_000).toBeGreaterThanOrEqual(365);
    expect(makeResearch("AAPL")!.prices).toEqual(research.prices);
  });
});
