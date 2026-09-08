import { layout } from "./theme/tokens.ts";

/** History cards stack their content until there is room for a readable CTA. */
export function isWideHistoryLayout(viewportWidth: number): boolean {
  return viewportWidth >= layout.breakpoints.tablet;
}
