import { layout } from "../theme/tokens.ts";

export type ResearchWorkspaceLayout = {
  overviewColumns: 1 | 2;
  chartColumns: 1 | 2;
  showReadinessSidebar: boolean;
};

/**
 * Keep the research surface's breakpoint decisions deterministic and separate
 * from React Native layout. The content frame supplies the available viewport
 * width, so no chart or column needs a phone-sized fixed width.
 */
export function getResearchWorkspaceLayout(viewportWidth: number): ResearchWorkspaceLayout {
  if (viewportWidth >= layout.breakpoints.desktop) {
    return { overviewColumns: 2, chartColumns: 2, showReadinessSidebar: true };
  }
  if (viewportWidth >= layout.breakpoints.tablet) {
    return { overviewColumns: 1, chartColumns: 2, showReadinessSidebar: false };
  }
  return { overviewColumns: 1, chartColumns: 1, showReadinessSidebar: false };
}
