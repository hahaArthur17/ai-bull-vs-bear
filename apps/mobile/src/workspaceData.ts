import type {
  AnalysisHistoryPage,
  AnalysisResponse,
  DebateSessionSummary,
  Stock,
  WatchlistResponse,
} from "./types";

type RuntimeHealth = { data_mode?: string; debate_workflow_v2?: boolean };
type WorkspaceDataSource = {
  getHealth: () => Promise<RuntimeHealth>;
  listStocks: () => Promise<Stock[]>;
  getWatchlist: () => Promise<WatchlistResponse>;
  listAnalyses: () => Promise<AnalysisResponse[]>;
  getAnalysisPage?: () => Promise<AnalysisHistoryPage>;
  listDebates: () => Promise<DebateSessionSummary[]>;
  getStock: (ticker: string) => Promise<Stock>;
};

export function mergeStocks(...groups: Stock[][]): Stock[] {
  const byTicker = new Map(groups.flat().map((stock) => [stock.ticker, stock]));
  return [...byTicker.values()].sort((left, right) => left.ticker.localeCompare(right.ticker));
}

/** Attach rejection handlers to every parallel request before awaiting health. */
export async function loadWorkspaceHome(source: WorkspaceDataSource, enableDebateV2: boolean) {
  const [health, stocks, watchlist, analysisPage] = await Promise.all([
    source.getHealth().catch((): RuntimeHealth => ({})),
    source.listStocks(),
    source.getWatchlist(),
    source.getAnalysisPage
      ? source.getAnalysisPage()
      : source.listAnalyses().then((items) => ({ items, next_offset: null })),
  ]);
  const reviewFixtureMode = health.data_mode === "review_fixture";
  const debateV2Enabled =
    enableDebateV2 || (reviewFixtureMode && health.debate_workflow_v2 === true);
  const [debates, watchedStocks] = await Promise.all([
    debateV2Enabled ? source.listDebates().catch(() => []) : Promise.resolve([]),
    Promise.all(watchlist.tickers.map((ticker) => source.getStock(ticker).catch(() => null))),
  ]);
  return {
    stocks: mergeStocks(
      stocks,
      watchedStocks.filter((item): item is Stock => item !== null),
    ),
    watchlist: watchlist.tickers,
    analyses: analysisPage.items,
    analysisNextOffset: analysisPage.next_offset,
    debates,
    reviewFixtureMode,
  };
}
