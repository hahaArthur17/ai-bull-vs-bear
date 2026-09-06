import { layout, spacing } from "./theme/tokens.ts";

export type ResponsiveAppShellLayout = {
  contentMaxWidth: number;
  contentGutter: number;
  navigationGap: number;
  navigationMaxWidth: number;
  navigationPadding: number;
};

/**
 * Keep the application frame readable on wide Web viewports while letting the
 * same bottom navigation remain comfortably tappable on compact screens.
 */
export function getResponsiveAppShellLayout(viewportWidth: number): ResponsiveAppShellLayout {
  const isDesktop = viewportWidth >= layout.breakpoints.desktop;
  const isTablet = viewportWidth >= layout.breakpoints.tablet;
  const contentGutter = isDesktop ? spacing.xxxl : isTablet ? spacing.xxl : viewportWidth >= layout.breakpoints.phone ? spacing.xl : spacing.lg;
  const frameWidth = Math.max(0, viewportWidth - contentGutter * 2);

  if (viewportWidth >= layout.breakpoints.desktop) {
    return {
      contentMaxWidth: Math.min(layout.contentMaxWidth, frameWidth),
      contentGutter,
      navigationGap: spacing.lg,
      navigationMaxWidth: Math.min(layout.navigationMaxWidth, frameWidth),
      navigationPadding: spacing.xl,
    };
  }
  if (viewportWidth >= layout.breakpoints.tablet) {
    return {
      contentMaxWidth: Math.min(layout.contentMaxWidth, frameWidth),
      contentGutter,
      navigationGap: spacing.md,
      navigationMaxWidth: Math.min(layout.navigationMaxWidth, frameWidth),
      navigationPadding: spacing.lg,
    };
  }
  return {
    contentMaxWidth: Math.min(layout.contentMaxWidth, frameWidth),
    contentGutter,
    navigationGap: spacing.xs,
    navigationMaxWidth: Math.min(layout.navigationMaxWidth, frameWidth),
    navigationPadding: spacing.sm,
  };
}
