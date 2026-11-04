import { beforeEach, describe, expect, it, vi } from "vitest";
import { z } from "zod";
import { clearDemoStorage, readDemoValue, writeDemoValue } from "./versioned-storage";

const tickers = z.array(z.string());

describe("versioned demo storage", () => {
  beforeEach(() => {
    clearDemoStorage();
    localStorage.clear();
  });

  it("stores only an explicit versioned envelope and resets its own namespace", () => {
    localStorage.setItem("another-app", "keep");
    writeDemoValue("watchlist", ["AAPL"]);
    expect(JSON.parse(localStorage.getItem("counterpoint.demo.v1.watchlist")!)).toEqual({
      version: 1,
      data: ["AAPL"],
    });
    expect(readDemoValue("watchlist", tickers, [])).toEqual(["AAPL"]);
    clearDemoStorage();
    expect(readDemoValue("watchlist", tickers, ["NVDA"])).toEqual(["NVDA"]);
    expect(localStorage.getItem("another-app")).toBe("keep");
  });

  it.each(["not json", '{"version":2,"data":["AAPL"]}', '{"version":1,"data":42}'])(
    "recovers from invalid stored data: %s",
    (raw) => {
      localStorage.setItem("counterpoint.demo.v1.watchlist", raw);
      expect(readDemoValue("watchlist", tickers, ["MSFT"])).toEqual(["MSFT"]);
    },
  );

  it("preserves the current session when browser storage is unavailable", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("Storage blocked");
    });
    writeDemoValue("watchlist", ["AAPL", "NVDA"]);
    expect(readDemoValue("watchlist", tickers, [])).toEqual(["AAPL", "NVDA"]);
  });
});
