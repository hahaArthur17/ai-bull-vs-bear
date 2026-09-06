import type { StockBundle } from "../types";

export type SeriesPoint = { date: string; value: number | null };

export type SeriesTrend = {
  absoluteChange: number;
  direction: "down" | "flat" | "up";
  endDate: string;
  endValue: number;
  percentChange: number | null;
  startDate: string;
  startValue: number;
};

export type MacroChart = {
  code: string;
  label: string;
  source: string;
  unit: string;
  points: SeriesPoint[];
  latest: SeriesPoint;
};

export function simpleMovingAverage(values: number[], period: number): Array<number | null> {
  return values.map((_, index) => {
    if (index < period - 1) return null;
    const window = values.slice(index - period + 1, index + 1);
    return window.reduce((sum, value) => sum + value, 0) / period;
  });
}

export function calculateRsi(values: number[], period = 14): Array<number | null> {
  const result: Array<number | null> = values.map(() => null);
  if (values.length <= period) return result;
  let gains = 0;
  let losses = 0;
  for (let index = 1; index <= period; index += 1) {
    const change = values[index] - values[index - 1];
    gains += Math.max(0, change);
    losses += Math.max(0, -change);
  }
  let averageGain = gains / period;
  let averageLoss = losses / period;
  result[period] = averageGain === 0 && averageLoss === 0
    ? 50
    : averageLoss === 0 ? 100 : 100 - 100 / (1 + averageGain / averageLoss);
  for (let index = period + 1; index < values.length; index += 1) {
    const change = values[index] - values[index - 1];
    averageGain = (averageGain * (period - 1) + Math.max(0, change)) / period;
    averageLoss = (averageLoss * (period - 1) + Math.max(0, -change)) / period;
    result[index] = averageGain === 0 && averageLoss === 0
      ? 50
      : averageLoss === 0 ? 100 : 100 - 100 / (1 + averageGain / averageLoss);
  }
  return result;
}

export function calculateMacd(values: number[]): {
  macd: Array<number | null>;
  signal: Array<number | null>;
} {
  const ema12 = exponentialMovingAverage(values, 12);
  const ema26 = exponentialMovingAverage(values, 26);
  const rawMacd = values.map((_, index) => ema12[index] - ema26[index]);
  const rawSignal = exponentialMovingAverage(rawMacd, 9);
  return {
    macd: rawMacd.map((value, index) => index < 25 ? null : value),
    signal: rawSignal.map((value, index) => index < 33 ? null : value),
  };
}

export function exponentialMovingAverage(values: number[], period: number): number[] {
  const multiplier = 2 / (period + 1);
  return values.reduce<number[]>((result, value, index) => {
    result.push(index === 0 ? value : value * multiplier + result[index - 1] * (1 - multiplier));
    return result;
  }, []);
}

export function calculateVolatility(values: number[], period = 20): Array<number | null> {
  return values.map((_, index) => {
    if (index < period) return null;
    const window = values.slice(index - period, index + 1);
    const returns = window.slice(1).map((value, returnIndex) => Math.log(value / window[returnIndex]));
    const average = returns.reduce((sum, value) => sum + value, 0) / returns.length;
    const variance = returns.reduce((sum, value) => sum + (value - average) ** 2, 0) / returns.length;
    return Math.sqrt(variance) * Math.sqrt(252) * 100;
  });
}

export function macroChart(
  context: StockBundle["macro_context"],
  code: string,
  label: string,
): MacroChart | null {
  const item = context.find((value) => value.series.code === code);
  if (!item) return null;
  const points = [...item.observations]
    .sort((left, right) => left.observation_date.localeCompare(right.observation_date))
    .slice(-30)
    .map((observation) => ({ date: observation.observation_date, value: observation.value }));
  const latest = points[points.length - 1];
  if (!latest || latest.value === null) return null;
  return { code, label, source: item.series.source, unit: item.series.unit, points, latest };
}

export function formatMacroValue(value: number, unit: string): string {
  if (unit === "percent") return `${value.toFixed(2)}%`;
  if (unit === "USD/barrel") return `$${value.toFixed(2)}`;
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(value);
}

export function chartScale(
  series: SeriesPoint[][],
  references: number[] = [],
  fixedDomain?: [number, number],
) {
  const values = series.flatMap((points) => points.flatMap((point) => point.value === null ? [] : [point.value]));
  const min = fixedDomain?.[0] ?? Math.min(...values, ...references);
  const max = fixedDomain?.[1] ?? Math.max(...values, ...references);
  const padding = Math.max((max - min) * 0.12, 0.01);
  return { min: fixedDomain ? min : min - padding, max: fixedDomain ? max : max + padding };
}

export function seriesTrend(points: SeriesPoint[]): SeriesTrend | null {
  const values = points.filter((point): point is { date: string; value: number } => point.value !== null);
  if (values.length < 2) return null;
  const start = values[0];
  const end = values[values.length - 1];
  const absoluteChange = end.value - start.value;
  const percentChange = start.value === 0 ? null : (absoluteChange / Math.abs(start.value)) * 100;
  return {
    startDate: start.date,
    endDate: end.date,
    startValue: start.value,
    endValue: end.value,
    absoluteChange,
    percentChange,
    direction: absoluteChange > 0 ? "up" : absoluteChange < 0 ? "down" : "flat",
  };
}

export function technicalPath(
  points: SeriesPoint[],
  min: number,
  max: number,
  width: number,
  height: number,
  padding: number,
): string {
  const plotWidth = width - padding * 2;
  const plotHeight = height - padding * 2;
  const range = Math.max(max - min, 0.0001);
  let started = false;
  return points.map((point, index) => {
    if (point.value === null) {
      started = false;
      return "";
    }
    const x = padding + (index / Math.max(points.length - 1, 1)) * plotWidth;
    const y = padding + (1 - (point.value - min) / range) * plotHeight;
    const command = started ? "L" : "M";
    started = true;
    return `${command}${x.toFixed(2)},${y.toFixed(2)}`;
  }).join(" ");
}
