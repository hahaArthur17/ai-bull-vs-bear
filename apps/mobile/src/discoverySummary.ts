import type { Stock } from "./types";

export type DiscoverySummary = {
  readyToReview: number;
};

/**
 * Summarise the stocks that have been loaded into the workspace, rather than
 * the transient result set currently rendered by catalog search.
 */
export function getDiscoverySummary(loadedStocks: readonly Stock[]): DiscoverySummary {
  return {
    readyToReview: loadedStocks.filter((stock) => stock.coverage_status === "debate_ready").length,
  };
}
