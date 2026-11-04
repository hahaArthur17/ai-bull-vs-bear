import { describe, expect, it } from "vitest";
import { mapResearchDto } from "./research.mapper";

function bundle() {
  return {
    stock: {
      ticker: "AAPL",
      company_name: "Apple Inc.",
      sector: "Technology",
      coverage_status: "debate_ready",
    },
    prices: [
      { date: "2026-10-30", close: 246, volume: 12 },
      { date: "2026-10-29", close: 244, volume: 10 },
    ],
    quote: { close: 247, previous_close: 244 },
    evidence: [
      {
        id: "e1",
        title: "Actual backend title",
        source_type: "filing",
        excerpt: "Backend evidence",
        published_at: "2026-10-30T00:00:00Z",
        url: null,
      },
    ],
  };
}

describe("FastAPI research mapping", () => {
  it("maps snake-case fields without inventing company valuation data", () => {
    const result = mapResearchDto(bundle());
    expect(result.stock).toMatchObject({
      ticker: "AAPL",
      name: "Apple Inc.",
      price: 247,
      change: 3,
      coverage: "ready",
      marketCap: "Not provided",
      pe: "Not provided",
    });
    expect(result.prices.map((point) => point.date)).toEqual(["2026-10-29", "2026-10-30"]);
    expect(result.evidence[0]).toMatchObject({ type: "filing", date: "2026-10-30" });
    expect(result.evidence[0]).not.toHaveProperty("url");
  });

  it("uses supplied close history when the live quote is unavailable", () => {
    expect(mapResearchDto({ ...bundle(), quote: null }).stock).toMatchObject({
      price: 246,
      change: 2,
    });
  });

  it("refuses an incompatible or price-less response instead of returning demo data", () => {
    expect(() => mapResearchDto({ stocks: [] })).toThrow(/not compatible/);
    expect(() => mapResearchDto({ ...bundle(), quote: null, prices: [] })).toThrow(
      /enough verified price data/,
    );
  });
});
