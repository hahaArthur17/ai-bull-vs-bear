import type { StockBundle } from "../types";
import { simpleMovingAverage } from "./chartMath.ts";

export type ChartRange = "1M" | "3M" | "6M" | "1Y";

export type InteractivePricePoint = {
  date: string;
  close: number;
  frequency: "daily" | "weekly";
  source: "daily_market_cache" | "demo_fallback" | "review_fixture" | "alpha_vantage_weekly";
  ma20: number | null;
  ma50: number | null;
  is_stale?: boolean;
  retrieved_at?: string;
};

export function priceRangeAvailable(
  range: ChartRange,
  hasDaily: boolean,
  hasWeekly: boolean,
): boolean {
  return range === "1M" || range === "3M" ? hasDaily : hasWeekly;
}

/** Compute averages before clipping the viewport so warm-up history is retained. */
export function selectPriceChartPoints(
  dailyPrices: StockBundle["prices"],
  weeklyPrices: StockBundle["weekly_history"],
  range: ChartRange,
  hasDailyPriceCurve: boolean,
  hasWeeklyPriceCurve: boolean,
): InteractivePricePoint[] {
  const isDailyRange = range === "1M" || range === "3M";
  const source = !priceRangeAvailable(range, hasDailyPriceCurve, hasWeeklyPriceCurve)
    ? []
    : isDailyRange
      ? dailyPrices.map((point) => ({ ...point, frequency: "daily" as const }))
      : weeklyPrices;
  const visibleLimit = range === "1M" ? 22 : range === "3M" ? 66 : range === "6M" ? 27 : 53;
  const ma20 = simpleMovingAverage(
    source.map((point) => point.close),
    20,
  );
  const ma50 = simpleMovingAverage(
    source.map((point) => point.close),
    50,
  );
  const firstVisibleIndex = Math.max(0, source.length - visibleLimit);
  return source.slice(firstVisibleIndex).map((point, visibleIndex) => {
    const sourceIndex = firstVisibleIndex + visibleIndex;
    return { ...point, ma20: ma20[sourceIndex], ma50: ma50[sourceIndex] };
  });
}

/** Shared coordinates keep close and moving-average paths on the same scale. */
export function buildPriceChartGeometry(
  points: InteractivePricePoint[],
  width: number,
  height: number,
  padding: { top: number; right: number; bottom: number; left: number },
) {
  if (points.length < 2) throw new Error("A price chart requires at least two points");
  const plottedValues = points.flatMap((point) =>
    [point.close, point.ma20, point.ma50].filter((value): value is number => value !== null),
  );
  const minClose = Math.min(...plottedValues);
  const maxClose = Math.max(...plottedValues);
  const closeRange = Math.max(0.01, maxClose - minClose);
  const plotWidth = Math.max(1, width - padding.left - padding.right);
  const plotHeight = height - padding.top - padding.bottom;
  const coordinates = points.map((point, index) => {
    const x = padding.left + (index / Math.max(1, points.length - 1)) * plotWidth;
    const y = padding.top + (1 - (point.close - minClose) / closeRange) * plotHeight;
    return { x, y };
  });
  const linePath = coordinates
    .map((point, index) => `${index === 0 ? "M" : "L"}${point.x.toFixed(2)},${point.y.toFixed(2)}`)
    .join(" ");
  const averagePath = (key: "ma20" | "ma50") => {
    let started = false;
    return points
      .map((point, index) => {
        const value = point[key];
        if (value === null) {
          started = false;
          return "";
        }
        const x = padding.left + (index / Math.max(1, points.length - 1)) * plotWidth;
        const y = padding.top + (1 - (value - minClose) / closeRange) * plotHeight;
        const command = started ? "L" : "M";
        started = true;
        return `${command}${x.toFixed(2)},${y.toFixed(2)}`;
      })
      .join(" ");
  };
  const ma20Path = averagePath("ma20");
  const ma50Path = averagePath("ma50");
  const first = coordinates[0];
  const last = coordinates[coordinates.length - 1];
  const areaPath = `${linePath} L${last.x.toFixed(2)},${(height - padding.bottom).toFixed(2)} L${first.x.toFixed(2)},${(height - padding.bottom).toFixed(2)} Z`;
  return {
    minClose,
    maxClose,
    plotHeight,
    coordinates,
    linePath,
    areaPath,
    ma20Path,
    ma50Path,
  };
}
