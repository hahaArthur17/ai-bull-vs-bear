import assert from "node:assert/strict";
import test from "node:test";

import { chartScale, simpleMovingAverage, technicalPath } from "./research/chartMath.ts";

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
