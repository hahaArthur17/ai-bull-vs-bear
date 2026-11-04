import { formatMarketDate } from "../dateFormat";
import type { SeriesPoint, seriesTrend } from "./chartMath";

export function describeTrend(
  label: string,
  trend: ReturnType<typeof seriesTrend>,
  prefix = "",
  suffix = "",
): string {
  if (!trend)
    return `${label} trend is unavailable because fewer than two labelled values are available.`;
  const direction =
    trend.direction === "up" ? "rose" : trend.direction === "down" ? "fell" : "was unchanged";
  const absoluteChange = `${prefix}${Math.abs(trend.absoluteChange).toFixed(2)}${suffix}`;
  const percentage =
    trend.percentChange === null
      ? "percentage change unavailable"
      : `${Math.abs(trend.percentChange).toFixed(1)}%`;
  return `${label} ${direction} by ${absoluteChange} (${percentage}) from ${formatMarketDate(trend.startDate)} to ${formatMarketDate(trend.endDate)}.`;
}

export function describeLatest(
  label: string,
  points: SeriesPoint[],
  prefix = "",
  suffix = "",
  formatValue?: (value: number) => string,
): string {
  const latest = [...points].reverse().find((point) => point.value !== null);
  return latest?.value === null || latest === undefined
    ? `${label} latest value is unavailable.`
    : `Latest · ${formatValue ? formatValue(latest.value) : `${prefix}${latest.value.toFixed(2)}${suffix}`} · ${formatMarketDate(latest.date)}`;
}

export function latestSeriesValue(points: SeriesPoint[]): number | null {
  return [...points].reverse().find((point) => point.value !== null)?.value ?? null;
}

export function compactTrend(label: string, trend: ReturnType<typeof seriesTrend>): string {
  const name = label ? `${label} ` : "";
  if (!trend || trend.percentChange === null) return `${name}change unavailable`;
  const sign = trend.direction === "up" ? "+" : trend.direction === "down" ? "−" : "";
  return `${name}${sign}${Math.abs(trend.percentChange).toFixed(1)}%`;
}
