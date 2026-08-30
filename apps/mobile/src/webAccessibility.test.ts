import assert from "node:assert/strict";
import test from "node:test";

import { getResponsiveAppShellLayout } from "./appShell.ts";
import { colors, interaction, layout, palette } from "./theme/tokens.ts";

function luminance(hex: string): number {
  const channels = hex.match(/[a-f\d]{2}/gi)?.map((channel) => Number.parseInt(channel, 16) / 255);
  if (!channels || channels.length !== 3) throw new Error(`Expected a six-digit hex colour, received ${hex}`);
  const [red, green, blue] = channels.map((channel) => (
    channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4
  ));
  return red * 0.2126 + green * 0.7152 + blue * 0.0722;
}

function contrastRatio(foreground: string, background: string): number {
  const [lighter, darker] = [luminance(foreground), luminance(background)].sort((left, right) => right - left);
  return (lighter + 0.05) / (darker + 0.05);
}

test("responsive web shell keeps every required viewport inside its frame", () => {
  for (const viewport of [320, 390, 768, 1280]) {
    const shell = getResponsiveAppShellLayout(viewport);
    const navigationWidth = (
      shell.navigationPadding * 2
      + interaction.minTargetSize * 4
      + shell.navigationGap * 3
    );
    assert.ok(navigationWidth <= viewport, `${viewport}px should keep all four navigation targets reachable`);
  }
  assert.ok(layout.contentMaxWidth < layout.breakpoints.desktop, "desktop content must not span a 1280px viewport");
  assert.ok(interaction.focusRingWidth >= 2, "keyboard focus needs a visible ring");
});

test("watchlist labels use AA text contrast on their rendered surfaces", () => {
  assert.ok(contrastRatio(palette.accent, colors.surface.positive) >= 4.5);
  assert.ok(contrastRatio(palette.accent, colors.surface.canvas) >= 4.5);
  assert.ok(contrastRatio(palette.muted, colors.surface.raised) >= 4.5);
});

test("small positive-state labels and interactive controls keep their accessibility tokens", () => {
  assert.ok(contrastRatio(palette.accent, colors.surface.positive) >= 4.5);
  assert.equal(interaction.minTargetSize, 44);
});
