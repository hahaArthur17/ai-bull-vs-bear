import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";

import { focusablePressableStyle } from "./focusablePressable.ts";
import { colors, interaction } from "./theme/tokens.ts";

test("shared focus treatment is visible only for enabled focused controls", () => {
  assert.deepEqual(focusablePressableStyle(false), null);
  assert.deepEqual(focusablePressableStyle(true, true), null);
  assert.deepEqual(focusablePressableStyle(true), {
    borderColor: colors.action.focus,
    borderWidth: interaction.focusRingWidth,
  });
});

test("all production Pressable call sites use the shared focus contract", () => {
  const productionSources = [
    "App.tsx",
    "src/AuthScreen.tsx",
    "src/components/debate/LegacyClaimCard.tsx",
    "src/components/debate/LiveDebateMessage.tsx",
    "src/screens/AboutScreen.tsx",
    "src/screens/EvidenceScreen.tsx",
    "src/screens/ExaminationScreen.tsx",
    "src/screens/HistoryScreen.tsx",
    "src/screens/LegacyDebateScreen.tsx",
    "src/screens/LiveDebateScreen.tsx",
    "src/screens/StockDetailScreen.tsx",
    "src/screens/WatchlistScreen.tsx",
  ];

  for (const sourcePath of productionSources) {
    const source = readFileSync(join(process.cwd(), sourcePath), "utf8");
    assert.match(source, /\bFocusablePressable\b/, `${sourcePath} must use shared focus treatment`);
    assert.doesNotMatch(source, /\bPressable\b/, `${sourcePath} must not bypass shared focus treatment`);
  }
});
