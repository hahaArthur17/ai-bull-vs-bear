/**
 * Shared visual language for native and Web. These are semantic roles rather
 * than screen-specific paint values, so the fixture, error, chart, and Debate
 * states retain their meaning as surfaces evolve.
 *
 * The palette is derived from repository-root `prototype.html`: deep navy
 * canvas, layered blue surfaces, teal constructive signals, pink risk, and a
 * restrained gold for evidence and neutral attention.
 */
const semanticColors = {
  surface: {
    canvas: "#09101d",
    raised: "#122039",
    elevated: "#1a2b47",
    floating: "#142540",
    subtle: "#0e1a2d",
    selected: "#17364d",
    signalUnavailable: "#17243a",
    positive: "#123137",
    warning: "#382d19",
    information: "#172b46",
    danger: "#3a1f2d",
    inverse: "#6cd8c8",
    inverseOverlay: "rgba(245,248,252,0.12)",
  },
  content: {
    primary: "#f5f8fc",
    secondary: "#a8bacb",
    inverse: "#09101d",
    inverseMuted: "#164b54",
    inverseSubtle: "#1f5660",
    onSignal: "#241a08",
    danger: "#ffbac3",
    warning: "#ffd891",
  },
  border: {
    subtle: "#2c4361",
    information: "#3b5d84",
    warning: "#7b6030",
    danger: "#82435a",
    inverse: "rgba(9,16,29,0.30)",
    inverseStrong: "rgba(9,16,29,0.42)",
    inverseSubtle: "rgba(9,16,29,0.22)",
  },
  action: {
    primary: "#ffc66f",
    secondary: "#6cd8c8",
    focus: "#ffc66f",
  },
  market: {
    bull: "#6cd8c8",
    bear: "#f59ba8",
  },
  agent: {
    bull: "#6cd8c8",
    bear: "#f59ba8",
    judge: "#d3b4ff",
    user: "#78d9ee",
  },
  chart: {
    price: "#6cd8c8",
    priceArea: "#6cd8c8",
    movingAverageShort: "#ffc66f",
    movingAverageLong: "#d3b4ff",
    grid: "#2c4361",
    reference: "#b8a36f",
    oscillator: "#a993f2",
    volume: "#7aaed0",
    positive: "#6cd8c8",
    negative: "#f59ba8",
  },
} as const;

export const designTokens = {
  colors: semanticColors,
  typography: {
    fontFamily: {
      native: "System",
      web: "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif",
    },
    display: { fontSize: 38, lineHeight: 42, fontWeight: "800" },
    pageTitle: { fontSize: 30, lineHeight: 36, fontWeight: "800" },
    sectionTitle: { fontSize: 17, lineHeight: 22, fontWeight: "800" },
    body: { fontSize: 16, lineHeight: 24, fontWeight: "400" },
    bodySmall: { fontSize: 13, lineHeight: 20, fontWeight: "400" },
    label: { fontSize: 11, lineHeight: 16, fontWeight: "800", letterSpacing: 1.1 },
  },
  spacing: {
    xxs: 2,
    xs: 4,
    sm: 8,
    md: 12,
    lg: 16,
    xl: 22,
    xxl: 26,
    xxxl: 32,
  },
  radii: {
    sm: 8,
    md: 12,
    lg: 16,
    xl: 20,
    pill: 999,
  },
  elevation: {
    flat: { elevation: 0, boxShadow: "none" },
    raised: {
      elevation: 2,
      boxShadow: "0px 4px 12px rgba(0,0,0,0.18)",
    },
    floating: {
      elevation: 8,
      boxShadow: "0px 10px 24px rgba(0,0,0,0.30)",
    },
  },
  layout: {
    contentMaxWidth: 1160,
    navigationMaxWidth: 680,
    floatingNavigationInset: 12,
    breakpoints: { compact: 320, phone: 390, tablet: 768, desktop: 1280 },
  },
  interaction: {
    minTargetSize: 44,
    focusRingWidth: 3,
    focusRingOffset: 2,
  },
  motion: {
    standard: { fast: 120, normal: 200, slow: 320 },
    reduced: { fast: 0, normal: 0, slow: 0 },
  },
} as const;

export const colors = designTokens.colors;
export const typography = designTokens.typography;
export const spacing = designTokens.spacing;
export const radii = designTokens.radii;
export const elevation = designTokens.elevation;
export const layout = designTokens.layout;
export const interaction = designTokens.interaction;
export const motion = designTokens.motion;

/** Select timing values without making native/Web call sites know token shape. */
export function motionForPreference(reduceMotion: boolean) {
  return reduceMotion ? motion.reduced : motion.standard;
}

// Compatibility aliases allow feature packages to migrate independently while
// ensuring every existing route switches to the deep semantic foundation now.
export const palette = {
  ink: colors.content.primary,
  muted: colors.content.secondary,
  paper: colors.surface.canvas,
  card: colors.surface.raised,
  line: colors.border.subtle,
  signal: colors.action.primary,
  bull: colors.market.bull,
  bear: colors.market.bear,
  accent: colors.action.secondary,
} as const;
