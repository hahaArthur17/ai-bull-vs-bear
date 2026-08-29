const semanticColors = {
  surface: {
    canvas: "#f5f1e8",
    raised: "#fffdf8",
    inverse: "#1d5c56",
    subtle: "#ebe4d3",
    signalUnavailable: "#f3eadb",
    positive: "#e9f0e5",
    warning: "#fff5e4",
    information: "#eef0f6",
    danger: "#fae2db",
    inverseOverlay: "rgba(255,255,255,0.12)",
  },
  content: {
    primary: "#1e2826",
    secondary: "#5e6d66",
    inverse: "#fffdf8",
    inverseMuted: "#c8d9d3",
    inverseSubtle: "#d7f0dc",
    danger: "#8d332b",
  },
  border: {
    subtle: "#d8d5ca",
    information: "#d4d7e4",
    warning: "#ead4ad",
    inverse: "rgba(255,255,255,0.32)",
    inverseStrong: "rgba(255,255,255,0.34)",
    inverseSubtle: "rgba(255,255,255,0.24)",
  },
  action: {
    primary: "#a33d2b",
    secondary: "#1d5c56",
  },
  market: {
    bull: "#3e8b6d",
    bear: "#b95455",
  },
  chart: {
    movingAverageShort: "#f5c86e",
    movingAverageLong: "#d59be3",
  },
} as const;

export const designTokens = {
  colors: semanticColors,
  typography: {
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
  },
  radii: {
    sm: 8,
    md: 12,
    lg: 16,
    xl: 20,
  },
  elevation: {
    flat: { elevation: 0, shadowOpacity: 0 },
    raised: {
      elevation: 2,
      shadowColor: "#1e2826",
      shadowOffset: { width: 0, height: 1 },
      shadowOpacity: 0.08,
      shadowRadius: 4,
    },
  },
  layout: {
    contentMaxWidth: 1160,
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

// Compatibility aliases keep the existing render output stable while screens
// migrate to semantic token names in their dedicated redesign slices.
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
