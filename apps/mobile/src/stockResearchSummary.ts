import { formatMarketDate, formatQuoteTime } from "./dateFormat.ts";
import type { StockBundle } from "./types";

export type QuoteProvenance = {
  freshness: string;
  hasVerifiedMarketData: boolean;
  label: string;
  source: string;
  timestamp: string;
  value: number | null;
  warning: string | null;
};

/**
 * Keep the value shown at the top of research separate from the evidence
 * curve, and make every source, timestamp, freshness state, and warning
 * explicit in one display model.
 */
export function getQuoteProvenance(bundle: StockBundle): QuoteProvenance {
  const latestDailyPrice = bundle.prices[bundle.prices.length - 1] ?? null;
  const hasVerifiedMarketData = latestDailyPrice?.source === "daily_market_cache";

  if (bundle.quote) {
    return {
      label: "Latest market quote",
      value: bundle.quote.close,
      source: "Finnhub quote",
      timestamp: `Quote time · ${formatQuoteTime(bundle.quote.as_of)}`,
      freshness: "Cached server-side for up to one minute",
      hasVerifiedMarketData,
      warning: latestDailyPrice?.is_stale
        ? "The latest daily price history is stale. The curve and technical signals may need a refresh."
        : null,
    };
  }

  if (hasVerifiedMarketData && latestDailyPrice) {
    return {
      label: "Latest daily close",
      value: latestDailyPrice.close,
      source: "Daily market cache",
      timestamp: `Market close · ${formatMarketDate(latestDailyPrice.date)}`,
      freshness: latestDailyPrice.is_stale ? "Stale daily market data" : "Verified daily market data",
      hasVerifiedMarketData,
      warning: latestDailyPrice.is_stale
        ? "This daily close is stale. Refresh market data before treating the signals as current."
        : null,
    };
  }

  return {
    label: "Verified price unavailable",
    value: null,
    source: latestDailyPrice?.source === "demo_fallback"
      ? "Demo fallback (not displayed as a market price)"
      : "No verified market-data source",
    timestamp: "Market timestamp unavailable",
    freshness: "Market-data verification pending",
    hasVerifiedMarketData: false,
    warning: "A verified daily price will appear after the market-data cache refresh completes.",
  };
}
