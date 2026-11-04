import type { Stock } from "@/lib/contracts/research";

export const DEMO_AS_OF = "2026-10-30";

const entries = [
  [
    "AAPL",
    "Apple Inc.",
    "Technology",
    246.72,
    2.18,
    "3.68T",
    "32.4",
    "A connected ecosystem of devices, services, and personal computing.",
  ],
  [
    "MSFT",
    "Microsoft Corporation",
    "Technology",
    523.61,
    -3.24,
    "3.89T",
    "37.8",
    "Enterprise software, cloud infrastructure, and productivity tools.",
  ],
  [
    "NVDA",
    "NVIDIA Corporation",
    "Semiconductors",
    187.23,
    4.62,
    "4.56T",
    "48.2",
    "Accelerated computing platforms and AI infrastructure.",
  ],
  [
    "GOOGL",
    "Alphabet Inc.",
    "Communication",
    238.45,
    1.76,
    "2.87T",
    "24.1",
    "Search, digital advertising, cloud services, and computing research.",
  ],
  [
    "AMZN",
    "Amazon.com Inc.",
    "Consumer cyclical",
    232.18,
    -1.14,
    "2.48T",
    "35.7",
    "Global commerce, logistics, and cloud infrastructure.",
  ],
  [
    "TSLA",
    "Tesla Inc.",
    "Consumer cyclical",
    431.65,
    -8.36,
    "1.39T",
    "78.6",
    "Electric vehicles, energy storage, and manufacturing technology.",
  ],
  [
    "META",
    "Meta Platforms Inc.",
    "Communication",
    746.38,
    5.92,
    "1.88T",
    "28.9",
    "Social platforms, digital advertising, and immersive computing.",
  ],
  [
    "NFLX",
    "Netflix Inc.",
    "Communication",
    118.42,
    0.84,
    "508B",
    "42.3",
    "Subscription entertainment and a global content distribution platform.",
  ],
] as const;

export const stocks: Stock[] = entries.map(
  ([ticker, name, sector, price, change, marketCap, pe, description]) => ({
    ticker,
    name,
    sector,
    price,
    change,
    marketCap,
    pe,
    changePercent: Number(((change / (price - change)) * 100).toFixed(2)),
    coverage: ticker === "NFLX" ? "limited" : "ready",
    description: `${description} All figures in this workspace are fictional demo data.`,
  }),
);

export function findStock(ticker: string): Stock | undefined {
  return stocks.find((stock) => stock.ticker === ticker.toUpperCase());
}
