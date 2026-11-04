import config from "@/app/config/env";
import type { Stock, StockResearch } from "@/lib/contracts/research";
import { HttpError, request } from "@/lib/http";
import { mapResearchDto } from "./research.mapper";

export async function searchStocks(query: string, signal?: AbortSignal): Promise<Stock[]> {
  if (config.dataMode !== "demo")
    throw new HttpError(
      "The live catalog does not provide the quote fields required by this Web view yet. Explore the complete Demo while that adapter is being connected.",
      501,
    );
  return request<Stock[]>(`/stocks?q=${encodeURIComponent(query)}&limit=20`, { signal });
}

export async function getResearch(ticker: string, signal?: AbortSignal): Promise<StockResearch> {
  const payload = await request<unknown>(
    `/stocks/${encodeURIComponent(ticker.toUpperCase())}/bundle`,
    { signal },
  );
  return config.dataMode === "demo" ? (payload as StockResearch) : mapResearchDto(payload);
}
