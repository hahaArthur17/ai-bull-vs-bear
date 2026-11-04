import { watchlistSchema } from "@/lib/contracts/schemas";
import { request, requireDemo } from "@/lib/http";

type WatchlistResponse = { tickers: string[] };

export async function getWatchlist(signal?: AbortSignal): Promise<string[]> {
  requireDemo("Saved watchlists; live authentication");
  const response = await request<WatchlistResponse>("/watchlist", { signal });
  return watchlistSchema.parse(response.tickers);
}

export async function addWatchlist(ticker: string): Promise<string[]> {
  requireDemo("Saving a watchlist; live authentication");
  const response = await request<WatchlistResponse>("/watchlist", {
    method: "POST",
    body: JSON.stringify({ ticker }),
  });
  return watchlistSchema.parse(response.tickers);
}

export async function removeWatchlist(ticker: string): Promise<string[]> {
  requireDemo("Updating a watchlist; live authentication");
  const response = await request<WatchlistResponse>(`/watchlist/${encodeURIComponent(ticker)}`, {
    method: "DELETE",
  });
  return watchlistSchema.parse(response.tickers);
}
