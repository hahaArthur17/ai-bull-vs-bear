import { formatMarketDate, formatQuoteTime } from "./dateFormat.ts";
import type { StockBundle } from "./types";

export type QuoteProvenance = {
  curveSource: string;
  freshness: string;
  hasCompleteTechnicalHistory: boolean;
  hasDailyPriceCurve: boolean;
  hasPriceCurve: boolean;
  hasVerifiedMarketData: boolean;
  hasWeeklyPriceCurve: boolean;
  label: string;
  preferredChartRange: "1M" | "6M";
  source: string;
  timestamp: string;
  value: number | null;
  warning: string | null;
};

function hasValidWeeklyCurve(bundle: StockBundle, isReviewFixture: boolean): boolean {
  if (bundle.weekly_history.length < 2) return false;
  const source = bundle.weekly_history[0]?.source;
  const expectedSource = isReviewFixture ? "review_fixture" : "alpha_vantage_weekly";
  if (source !== expectedSource) return false;
  return bundle.weekly_history.every((point, index, points) => (
    point.source === source
    && Number.isFinite(point.close)
    && point.close > 0
    && !Number.isNaN(Date.parse(`${point.date}T00:00:00Z`))
    && (index === 0 || points[index - 1].date < point.date)
  ));
}

function hasValidDailyHistory(bundle: StockBundle, isReviewFixture: boolean): boolean {
  const history = bundle.indicators.history;
  const allowedSources = isReviewFixture ? ["review_fixture"] : ["daily_market_cache"];
  const hasExpectedProvenance = isReviewFixture
    ? history?.provenance === "review_fixture"
    : history !== undefined && ["live_fresh", "live_stale"].includes(history.provenance);
  return Boolean(
    history
    && hasExpectedProvenance
    && history.is_valid
    && history.is_ordered
    && history.has_unique_dates
    && history.has_valid_closes
    && history.has_valid_ohlcv
    && history.has_only_completed_closes
    && bundle.prices.length >= 1
    && bundle.prices.every((point, index, points) => (
      allowedSources.includes(point.source)
      && Number.isFinite(point.close)
      && point.close > 0
      && !Number.isNaN(Date.parse(`${point.date}T00:00:00Z`))
      && (index === 0 || points[index - 1].date < point.date)
    )),
  );
}

function hasValidDailyCurve(bundle: StockBundle, isReviewFixture: boolean): boolean {
  return Boolean(
    bundle.indicators.availability?.price_line
    && bundle.prices.length >= 2
    && hasValidDailyHistory(bundle, isReviewFixture),
  );
}

/**
 * Keep the value shown at the top of research separate from the evidence
 * curve, and make every source, timestamp, freshness state, and warning
 * explicit in one display model.
 */
export function getQuoteProvenance(bundle: StockBundle): QuoteProvenance {
  const latestDailyPrice = bundle.prices[bundle.prices.length - 1] ?? null;
  const history = bundle.indicators.history;
  const isReviewFixture = bundle.data_mode === "review_fixture"
    || history?.provenance === "review_fixture";
  const hasValidDailyData = hasValidDailyHistory(bundle, isReviewFixture);
  const hasVerifiedMarketData = !isReviewFixture && hasValidDailyData;
  const hasDailyPriceCurve = hasValidDailyCurve(bundle, isReviewFixture);
  const hasWeeklyPriceCurve = hasValidWeeklyCurve(bundle, isReviewFixture);
  const hasPriceCurve = hasDailyPriceCurve || hasWeeklyPriceCurve;
  const hasCompleteTechnicalHistory = Boolean(history?.complete_view && hasValidDailyData);
  const curveSource = hasDailyPriceCurve
    ? isReviewFixture ? "Simulated review fixture" : "Verified daily history"
    : hasWeeklyPriceCurve
      ? bundle.weekly_history[0]?.source === "review_fixture"
        ? "Simulated review fixture"
        : "Verified weekly Alpha Vantage history"
      : "Unavailable at the current history threshold";
  const fixtureWarning = isReviewFixture
    ? "Simulated review data for interface evaluation only; it is not live market data."
    : null;
  const preferredChartRange = hasDailyPriceCurve ? "1M" : "6M";

  if (bundle.quote && !isReviewFixture) {
    return {
      label: "Market quote snapshot",
      preferredChartRange,
      value: bundle.quote.close,
      source: "Finnhub quote",
      timestamp: `Quote time · ${formatQuoteTime(bundle.quote.as_of)}`,
      freshness: "Quote snapshot · cached server-side for up to one minute",
      curveSource,
      hasVerifiedMarketData,
      hasDailyPriceCurve,
      hasPriceCurve,
      hasWeeklyPriceCurve,
      hasCompleteTechnicalHistory,
      warning: fixtureWarning ?? (latestDailyPrice?.is_stale
        ? "The latest daily price history is stale. The curve and technical signals may need a refresh."
        : history && !history.complete_view ? history.explanation : null),
    };
  }

  if (isReviewFixture && latestDailyPrice?.source === "review_fixture") {
    return {
      label: latestDailyPrice.is_stale ? "Simulated stale review close" : "Simulated review close",
      preferredChartRange,
      value: latestDailyPrice.close,
      source: "Review fixture (simulated)",
      timestamp: `Fixture date · ${formatMarketDate(latestDailyPrice.date)}`,
      freshness: latestDailyPrice.is_stale ? "Simulated stale review data" : "Simulated review data",
      curveSource,
      hasVerifiedMarketData: false,
      hasDailyPriceCurve,
      hasPriceCurve,
      hasWeeklyPriceCurve,
      hasCompleteTechnicalHistory,
      warning: fixtureWarning,
    };
  }

  if (hasVerifiedMarketData && latestDailyPrice) {
    return {
      label: "Latest daily close",
      preferredChartRange,
      value: latestDailyPrice.close,
      source: "Daily market cache",
      timestamp: `Market close · ${formatMarketDate(latestDailyPrice.date)}`,
      freshness: latestDailyPrice.is_stale ? "Stale daily market data" : "Verified daily market data",
      curveSource,
      hasVerifiedMarketData,
      hasDailyPriceCurve,
      hasPriceCurve,
      hasWeeklyPriceCurve,
      hasCompleteTechnicalHistory,
      warning: latestDailyPrice.is_stale
        ? "This daily close is stale. Refresh market data before treating the signals as current."
        : history && !history.complete_view ? history.explanation : null,
    };
  }

  if (isReviewFixture) {
    return {
      label: "Simulated price unavailable",
      preferredChartRange,
      value: null,
      source: "Review fixture (simulated)",
      timestamp: "Fixture state · no price history",
      freshness: "Simulated unavailable state",
      hasVerifiedMarketData: false,
      curveSource,
      hasDailyPriceCurve,
      hasPriceCurve,
      hasWeeklyPriceCurve,
      hasCompleteTechnicalHistory: false,
      warning: "This fixture intentionally omits price history to review the unavailable state; it is not a market-data failure.",
    };
  }

  return {
    label: "Verified price unavailable",
    preferredChartRange,
    value: null,
    source: latestDailyPrice?.source === "demo_fallback"
      ? "Demo fallback (not displayed as a market price)"
      : "No verified market-data source",
    timestamp: "Market timestamp unavailable",
    freshness: "Market-data verification pending",
    hasVerifiedMarketData: false,
    curveSource,
    hasDailyPriceCurve,
    hasPriceCurve,
    hasWeeklyPriceCurve,
    hasCompleteTechnicalHistory: false,
    warning: "A verified daily price will appear after the market-data cache refresh completes.",
  };
}
