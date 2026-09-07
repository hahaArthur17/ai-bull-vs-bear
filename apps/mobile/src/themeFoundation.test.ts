import assert from "node:assert/strict";
import test from "node:test";

import { colors, elevation, layout, motion, motionForPreference, palette, radii, spacing, typography } from "./theme/tokens.ts";

test("prototype-derived theme foundation uses deep semantic surfaces and role colours", () => {
  assert.equal(colors.surface.canvas, "#09101d");
  assert.equal(colors.surface.raised, "#122039");
  assert.equal(colors.surface.elevated, "#1a2b47");
  assert.equal(palette.paper, colors.surface.canvas);
  assert.equal(palette.card, colors.surface.raised);
  assert.equal(palette.bull, colors.market.bull);
  assert.equal(palette.bear, colors.market.bear);
  assert.equal(colors.action.primary, "#ffc66f");
  assert.equal(colors.action.secondary, "#6cd8c8");
  assert.equal(colors.market.bear, "#f59ba8");
  assert.notEqual(colors.surface.canvas, "#f5f1e8", "warm-paper canvas must not reappear in the shared shell");
});

test("foundation exposes one typography, spacing, radius, focus, and elevation contract", () => {
  assert.equal(typography.fontFamily.native, "System");
  assert.match(typography.fontFamily.web, /Inter/);
  assert.ok(spacing.xxxl > spacing.xxl);
  assert.equal(radii.pill, 999);
  assert.ok(elevation.floating.elevation > elevation.raised.elevation);
  assert.ok(layout.readingMaxWidth < layout.contentMaxWidth);
  assert.match(elevation.raised.boxShadow, /12px/);
  assert.match(elevation.floating.boxShadow, /24px/);
});

test("reduced-motion callers receive zero-duration timing without changing standard motion", () => {
  assert.deepEqual(motionForPreference(false), motion.standard);
  assert.deepEqual(motionForPreference(true), motion.reduced);
  assert.equal(motionForPreference(true).fast, 0);
  assert.equal(motionForPreference(true).normal, 0);
  assert.equal(motionForPreference(true).slow, 0);
});
