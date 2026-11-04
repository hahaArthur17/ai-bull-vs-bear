import { z } from "zod";
import type { StockResearch } from "@/lib/contracts/research";

const bundleSchema = z.object({
  stock: z.object({
    ticker: z.string(),
    company_name: z.string(),
    sector: z.string().nullable(),
    coverage_status: z.string(),
  }),
  prices: z.array(z.object({ date: z.string(), close: z.number(), volume: z.number() })),
  quote: z.object({ close: z.number(), previous_close: z.number() }).nullable().optional(),
  evidence: z.array(
    z.object({
      id: z.string(),
      title: z.string(),
      source_type: z.enum(["filing", "news", "technical"]),
      excerpt: z.string(),
      published_at: z.string().nullable().optional(),
      url: z.string().nullable().optional(),
    }),
  ),
});

export function mapResearchDto(input: unknown): StockResearch {
  const parsed = bundleSchema.safeParse(input);
  if (!parsed.success)
    throw new Error("The live research response is not compatible with this Web client yet.");
  const { stock, quote, evidence } = parsed.data;
  const prices = [...parsed.data.prices].sort((left, right) => left.date.localeCompare(right.date));
  const price = quote?.close ?? prices.at(-1)?.close;
  const previous = quote?.previous_close ?? prices.at(-2)?.close;
  if (price === undefined || previous === undefined || previous <= 0)
    throw new Error("The backend did not provide enough verified price data for this view.");
  const change = Number((price - previous).toFixed(2));
  return {
    stock: {
      ticker: stock.ticker,
      name: stock.company_name,
      sector: stock.sector ?? "Not provided",
      price,
      change,
      changePercent: Number(((change / previous) * 100).toFixed(2)),
      coverage: stock.coverage_status === "debate_ready" ? "ready" : "limited",
      marketCap: "Not provided",
      pe: "Not provided",
      description:
        "Connected backend data. Company profile and valuation fields are not supplied by the current API.",
    },
    prices,
    metrics: [],
    bullCase: "A live generated constructive case is not connected to this Web view yet.",
    bearCase: "A live generated cautious case is not connected to this Web view yet.",
    evidence: evidence.map((item) => ({
      id: item.id,
      title: item.title,
      type: item.source_type,
      excerpt: item.excerpt,
      date: item.published_at?.slice(0, 10) ?? "Undated",
      ...(item.url ? { url: item.url } : {}),
    })),
  };
}
