import type { Stock, StockBundle } from "./types";

export type StockDetailLoader = {
  getStock: (ticker: string) => Promise<Stock>;
  getStockBundle: (ticker: string) => Promise<StockBundle>;
};

export type LoadedStockDetail = {
  stock: Stock;
  bundle: StockBundle | null;
};

export async function loadStockDetail(
  loader: StockDetailLoader,
  ticker: string,
): Promise<LoadedStockDetail> {
  const stock = await loader.getStock(ticker);
  if (stock.coverage_status === "catalog_only") {
    return { stock, bundle: null };
  }
  const bundle = await loader.getStockBundle(ticker);
  return { stock: bundle.stock, bundle };
}
