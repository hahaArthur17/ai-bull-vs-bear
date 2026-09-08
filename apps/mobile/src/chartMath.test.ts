import assert from "node:assert/strict";
import test from "node:test";

import {
  chartBarScaleMaximum,
  calculateMacd,
  calculateRsi,
  calculateVolatility,
  chartScale,
  nearestChartPointIndex,
  seriesTrend,
  simpleMovingAverage,
  technicalPath,
} from "./research/chartMath.ts";

test("bar charts keep a finite scale for all-zero observations", () => {
  assert.equal(chartBarScaleMaximum([0, 0, 0]), 1);
  assert.equal(chartBarScaleMaximum([0, 12, 4]), 12);
});

test("chart calculations retain gaps and use complete trailing windows", () => {
  assert.deepEqual(simpleMovingAverage([1, 2, 3, 4], 3), [null, null, 2, 3]);
  assert.equal(
    technicalPath(
      [{ date: "2026-01-01", value: 1 }, { date: "2026-01-02", value: null }, { date: "2026-01-03", value: 3 }],
      0,
      4,
      100,
      100,
      10,
    ),
    "M10.00,70.00  M90.00,30.00",
  );
});

test("chart scale pads data domains but preserves fixed reference domains", () => {
  assert.deepEqual(chartScale([[{ date: "2026-01-01", value: 10 }, { date: "2026-01-02", value: 20 }]]), { min: 8.8, max: 21.2 });
  assert.deepEqual(chartScale([[{ date: "2026-01-01", value: 10 }]], [30, 70], [0, 100]), { min: 0, max: 100 });
});

test("chart gestures choose the closest horizontal price point and clamp chart gutters", () => {
  const options = { chartWidth: 300, pointCount: 7, paddingLeft: 12, paddingRight: 12 };
  assert.equal(nearestChartPointIndex(12, options.chartWidth, options.pointCount, options.paddingLeft, options.paddingRight), 0);
  assert.equal(nearestChartPointIndex(155, options.chartWidth, options.pointCount, options.paddingLeft, options.paddingRight), 3);
  assert.equal(nearestChartPointIndex(288, options.chartWidth, options.pointCount, options.paddingLeft, options.paddingRight), 6);
  assert.equal(nearestChartPointIndex(-20, options.chartWidth, options.pointCount, options.paddingLeft, options.paddingRight), 0);
  assert.equal(nearestChartPointIndex(350, options.chartWidth, options.pointCount, options.paddingLeft, options.paddingRight), 6);
  assert.equal(nearestChartPointIndex(120, 0, 1), 0);
});

test("chart trend retains the selected date range and does not invent a percentage from zero", () => {
  assert.deepEqual(seriesTrend([
    { date: "2026-08-01", value: 100 },
    { date: "2026-08-02", value: 112 },
  ]), {
    startDate: "2026-08-01",
    endDate: "2026-08-02",
    startValue: 100,
    endValue: 112,
    absoluteChange: 12,
    percentChange: 12,
    direction: "up",
  });
  assert.equal(seriesTrend([{ date: "2026-08-01", value: 0 }, { date: "2026-08-02", value: 3 }])?.percentChange, null);
  assert.equal(seriesTrend([{ date: "2026-08-01", value: null }]), null);
});

test("canonical indicator golden vector matches the backend", () => {
  const closes = Array.from(
    { length: 55 },
    (_, index) => 100 + index * 0.7 + ((index % 5) - 2) * 0.9,
  );
  const rsi = calculateRsi(closes);
  const volatility = calculateVolatility(closes);
  const { macd, signal } = calculateMacd(closes);

  assert.equal(rsi.at(-1)?.toFixed(4), "72.9231");
  assert.equal(macd.at(-1)?.toFixed(4), "4.9502");
  assert.equal(signal.at(-1)?.toFixed(4), "4.7633");
  assert.equal(volatility.at(-1)?.toFixed(4), "22.0120");
  assert.equal(simpleMovingAverage(closes, 20).at(-1)?.toFixed(4), "131.1500");
  assert.equal(simpleMovingAverage(closes, 50).at(-1)?.toFixed(4), "120.6500");
});

test("indicator warm-up boundaries remain unavailable per series", () => {
  assert.equal(calculateRsi(Array(14).fill(100)).at(-1), null);
  assert.equal(calculateRsi(Array(15).fill(100)).at(-1), 50);
  assert.equal(calculateVolatility(Array(20).fill(100)).at(-1), null);
  assert.equal(calculateVolatility(Array(21).fill(100)).at(-1), 0);
  assert.equal(calculateMacd(Array(25).fill(100)).macd.at(-1), null);
  assert.equal(calculateMacd(Array(26).fill(100)).macd.at(-1), 0);
  assert.equal(calculateMacd(Array(33).fill(100)).signal.at(-1), null);
  assert.equal(calculateMacd(Array(34).fill(100)).signal.at(-1), 0);
});
