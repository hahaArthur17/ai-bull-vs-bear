import type { DebateRecord } from "@/lib/contracts/research";
import { findStock } from "../market";

export function createDebate(ticker: string): DebateRecord {
  const stock = findStock(ticker);
  if (!stock) throw new Error("This stock is not part of the demo dataset.");
  return {
    id: `demo_${crypto.randomUUID()}`,
    ticker: stock.ticker,
    title: `${stock.name}: resilience or expectations?`,
    createdAt: new Date().toISOString(),
    messages: [
      {
        id: "bull-opening",
        role: "bull",
        content: `${stock.ticker} has a constructive story in this fictional scenario. Recurring demand and cash generation could give the business room to invest through a changing market. The key question is how much of that resilience is already reflected in the price.`,
        evidenceId: `${stock.ticker}-filing`,
      },
      {
        id: "bear-opening",
        role: "bear",
        content:
          "Business quality alone does not settle the valuation question. This simulated case assumes expectations remain elevated, while competition and new investment could pressure margins. The downside case deserves the same scrutiny as the growth narrative.",
        evidenceId: `${stock.ticker}-news`,
      },
      {
        id: "bull-response",
        role: "bull",
        content:
          "That valuation concern is reasonable. A stronger constructive case would need evidence that investment converts into recurring revenue rather than just higher spending. The synthetic trend provides context, but it cannot establish the business outcome.",
        evidenceId: `${stock.ticker}-technical`,
      },
      {
        id: "bear-response",
        role: "bear",
        content:
          "Agreed on the distinction. I would watch the gap between revenue growth and operating costs, and test whether the market is assuming an unusually smooth execution path. Missing evidence should remain visible rather than be filled with certainty.",
        evidenceId: `${stock.ticker}-filing`,
      },
      {
        id: "judge-summary",
        role: "judge",
        content:
          "Both arguments depend on assumptions that require further evidence. The constructive view emphasizes resilience and investment capacity; the cautious view emphasizes valuation and execution. This scripted replay demonstrates competing interpretations, not live AI output or an investment recommendation.",
      },
    ],
    summary:
      "Resilience supports the constructive scenario; valuation and execution constrain it. Compare the assumptions, inspect the evidence, and keep uncertainty explicit. Scripted demo — not live market analysis.",
  };
}

export function seedHistory(): DebateRecord[] {
  return ["AAPL", "NVDA"].map((ticker, index) => ({
    ...createDebate(ticker),
    id: `sample-${ticker.toLowerCase()}`,
    createdAt: `2026-10-${30 - index}T09:30:00Z`,
  }));
}
