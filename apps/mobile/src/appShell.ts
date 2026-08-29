import { layout, spacing } from "./theme/tokens.ts";

export type ResponsiveAppShellLayout = {
  contentMaxWidth: number;
  navigationGap: number;
  navigationPadding: number;
};

/**
 * Keep the application frame readable on wide Web viewports while letting the
 * same bottom navigation remain comfortably tappable on compact screens.
 */
export function getResponsiveAppShellLayout(viewportWidth: number): ResponsiveAppShellLayout {
  if (viewportWidth >= layout.breakpoints.desktop) {
    return {
      contentMaxWidth: layout.contentMaxWidth,
      navigationGap: spacing.lg,
      navigationPadding: spacing.xl,
    };
  }
  if (viewportWidth >= layout.breakpoints.tablet) {
    return {
      contentMaxWidth: layout.contentMaxWidth,
      navigationGap: spacing.md,
      navigationPadding: spacing.lg,
    };
  }
  return {
    contentMaxWidth: layout.contentMaxWidth,
    navigationGap: spacing.xs,
    navigationPadding: spacing.sm,
  };
}
