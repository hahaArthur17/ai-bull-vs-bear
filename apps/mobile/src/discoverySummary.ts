import type { Stock } from "./types";

export type DiscoverySummary = {
  readyToReview: number;
};

export type CoveragePresentation = {
  label: string;
  tone: "ready" | "partial" | "catalog";
};

/**
 * Translate backend coverage into an honest, compact catalog label. Partial
 * research states must remain discoverable so reviewers can exercise their
 * insufficient/unavailable-data screens instead of mistaking them for an
 * identity-only catalog record.
 */
export function getCoveragePresentation(status: Stock["coverage_status"]): CoveragePresentation {
  switch (status) {
    case "debate_ready":
      return { label: "Research ready", tone: "ready" };
    case "evidence_ready":
      return { label: "Evidence ready", tone: "ready" };
    case "price_cached":
      return { label: "Limited coverage", tone: "partial" };
    case "catalog_only":
      return { label: "Watchlist only", tone: "catalog" };
  }
}

/**
 * Summarise the stocks that have been loaded into the workspace, rather than
 * the transient result set currently rendered by catalog search.
 */
export function getDiscoverySummary(loadedStocks: readonly Stock[]): DiscoverySummary {
  return {
    readyToReview: loadedStocks.filter((stock) => stock.coverage_status === "debate_ready").length,
  };
}
