import type { PricePoint, Stock, StockResearch } from "@/lib/contracts/research";
import { DEMO_AS_OF, findStock } from "./stocks";

function tradingDates(count: number): string[] {
  const dates: string[] = [];
  const cursor = new Date(`${DEMO_AS_OF}T12:00:00Z`);
  while (dates.length < count) {
    if (cursor.getUTCDay() !== 0 && cursor.getUTCDay() !== 6)
      dates.unshift(cursor.toISOString().slice(0, 10));
    cursor.setUTCDate(cursor.getUTCDate() - 1);
  }
  return dates;
}

export function makePrices(stock: Stock): PricePoint[] {
  const dates = tradingDates(262);
  const seed = [...stock.ticker].reduce((sum, char) => sum + char.charCodeAt(0), 0);
  return dates.map((date, index) => {
    const progress = index / (dates.length - 1);
    const wave = Math.sin(index * 0.31) - Math.sin((dates.length - 1) * 0.31) * progress;
    return {
      date,
      close: Number((stock.price * (0.81 + 0.19 * progress + wave * 0.018)).toFixed(2)),
      volume: 12_000_000 + ((index * 927_113 + seed * 13_379) % 44_000_000),
    };
  });
}

export function makeResearch(ticker: string): StockResearch | undefined {
  const stock = findStock(ticker);
  if (!stock) return undefined;
  return {
    stock,
    prices: makePrices(stock),
    metrics: [
      { label: "Market cap", value: `$${stock.marketCap}`, detail: "Simulated valuation" },
      { label: "P/E ratio", value: `${stock.pe}×`, detail: "Illustrative trailing multiple" },
      { label: "Revenue growth", value: "+8.2%", detail: "Fictional year-over-year scenario" },
      { label: "Operating margin", value: "29.4%", detail: "Fictional operating scenario" },
    ],
    bullCase: `The constructive case for ${stock.ticker} combines recurring demand, operating discipline, and investment capacity. In this fictional scenario, durable cash generation could support the next growth cycle.`,
    bearCase: `The cautious case for ${stock.ticker} focuses on expectations already priced in, competitive pressure, and execution risk. Even solid business performance may not justify an elevated multiple.`,
    evidence: makeEvidence(stock.ticker),
  };
}

function makeEvidence(ticker: string): StockResearch["evidence"] {
  return [
    {
      id: `${ticker}-filing`,
      type: "filing",
      title: "Operating resilience and recurring demand",
      excerpt:
        "Fictional filing-style excerpt: recurring business activity supports cash generation, while the pace of future growth remains uncertain. This is not a quote from a real filing.",
      date: DEMO_AS_OF,
    },
    {
      id: `${ticker}-news`,
      type: "news",
      title: "A market narrative with two interpretations",
      excerpt:
        "Fictional news-style summary: investment in new capacity creates potential upside and near-term cost pressure. This is a scripted demonstration, not reporting.",
      date: "2026-10-29",
    },
    {
      id: `${ticker}-technical`,
      type: "technical",
      title: "Trend strength meets valuation sensitivity",
      excerpt:
        "Synthetic price series: the latest close is above the illustrative medium-term trend. A trend is an observation, not a prediction or recommendation.",
      date: DEMO_AS_OF,
    },
  ];
}
