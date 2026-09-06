import assert from "node:assert/strict";
import test from "node:test";

import { getResponsiveAppShellLayout } from "./appShell.ts";
import { layout } from "./theme/tokens.ts";

test("app shell keeps a readable content width and compacts navigation below tablet", () => {
  const compact = getResponsiveAppShellLayout(320);
  const phone = getResponsiveAppShellLayout(390);
  const tablet = getResponsiveAppShellLayout(768);
  const desktop = getResponsiveAppShellLayout(1280);

  assert.ok(compact.contentMaxWidth < layout.contentMaxWidth);
  assert.equal(desktop.contentMaxWidth, layout.contentMaxWidth);
  assert.ok(phone.contentGutter > compact.contentGutter);
  assert.equal(phone.navigationGap, compact.navigationGap);
  assert.ok(tablet.navigationGap > compact.navigationGap);
  assert.ok(desktop.navigationGap > tablet.navigationGap);
  assert.ok(desktop.navigationPadding > compact.navigationPadding);
  assert.ok(desktop.navigationMaxWidth <= layout.navigationMaxWidth);
});
