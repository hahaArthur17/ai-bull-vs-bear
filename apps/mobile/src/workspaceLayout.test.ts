import assert from "node:assert/strict";
import test from "node:test";

import { getResearchWorkspaceLayout } from "./research/workspaceLayout.ts";

test("research workspace keeps compact and phone layouts in one readable column", () => {
  assert.deepEqual(getResearchWorkspaceLayout(320), {
    overviewColumns: 1,
    chartColumns: 1,
    showReadinessSidebar: false,
  });
  assert.deepEqual(getResearchWorkspaceLayout(390), {
    overviewColumns: 1,
    chartColumns: 1,
    showReadinessSidebar: false,
  });
});

test("research workspace uses chart grids before it creates a desktop sidebar", () => {
  assert.deepEqual(getResearchWorkspaceLayout(768), {
    overviewColumns: 1,
    chartColumns: 2,
    showReadinessSidebar: false,
  });
});

test("research workspace uses a primary research column and readiness sidebar on desktop", () => {
  assert.deepEqual(getResearchWorkspaceLayout(1280), {
    overviewColumns: 2,
    chartColumns: 2,
    showReadinessSidebar: true,
  });
});
