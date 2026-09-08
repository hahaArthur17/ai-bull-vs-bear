import assert from "node:assert/strict";
import test from "node:test";

import { isWideHistoryLayout } from "./historyLayout.ts";
import { layout } from "./theme/tokens.ts";

test("History cards stack below the tablet breakpoint", () => {
  assert.equal(isWideHistoryLayout(layout.breakpoints.phone), false);
  assert.equal(isWideHistoryLayout(layout.breakpoints.tablet - 1), false);
  assert.equal(isWideHistoryLayout(layout.breakpoints.tablet), true);
});
