import assert from "node:assert/strict";
import test from "node:test";
import { buildPriceChartGeometry, selectPriceChartPoints } from "./research/priceChart.ts";

const daily = Array.from({ length: 60 }, (_, index) => ({
  date: `2026-${String(8 + Math.floor(index / 28)).padStart(2, "0")}-${String((index % 28) + 1).padStart(2, "0")}`,
  open: index + 1,
  high: index + 1,
  low: index + 1,
  close: index + 1,
  volume: 100,
  is_stale: false,
  source: "daily_market_cache" as const,
}));

test("price chart calculates averages from history before clipping the displayed month", () => {
  const points = selectPriceChartPoints(daily, [], "1M", true, false);
  assert.equal(points.length, 22);
  assert.equal(points[0].close, 39);
  assert.equal(points[0].ma20, 29.5);
  assert.equal(points[0].ma50, null);
  assert.equal(points.at(-1)?.ma50, 35.5);
  assert.deepEqual(selectPriceChartPoints(daily, [], "1M", false, false), []);
});

test("price chart keeps flat and initially collapsed layouts finite", () => {
  const points = selectPriceChartPoints(daily.slice(0, 2), [], "1M", true, false).map((point) => ({
    ...point,
    close: 10,
  }));
  const geometry = buildPriceChartGeometry(points, 1, 154, {
    top: 14,
    right: 12,
    bottom: 26,
    left: 12,
  });
  assert.ok(geometry.coordinates.every(({ x, y }) => Number.isFinite(x) && Number.isFinite(y)));
  assert.ok(geometry.coordinates[1].x > geometry.coordinates[0].x);
  assert.doesNotMatch(geometry.linePath, /NaN|Infinity/);
});
