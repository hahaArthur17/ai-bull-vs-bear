import { delay, http, HttpResponse } from "msw";
import { watchlistSchema } from "@/lib/contracts/schemas";
import { readDemoValue, writeDemoValue } from "@/lib/storage";
import { findStock } from "@/mocks/fixtures/market";

export function readWatchlist(): string[] {
  return readDemoValue("watchlist", watchlistSchema, ["AAPL", "NVDA", "MSFT"]);
}

export const watchlistHandlers = [
  http.get("/api/watchlist", async () => {
    await delay(160);
    return HttpResponse.json({ tickers: readWatchlist() });
  }),
  http.post("/api/watchlist", async ({ request }) => {
    const body: unknown = await request.json();
    const ticker =
      typeof body === "object" && body !== null && "ticker" in body ? String(body.ticker) : "";
    if (!findStock(ticker))
      return HttpResponse.json({ message: "Only demo securities can be saved." }, { status: 422 });
    await delay(220);
    const tickers = [...new Set([...readWatchlist(), ticker])];
    writeDemoValue("watchlist", tickers);
    return HttpResponse.json({ tickers }, { status: 201 });
  }),
  http.delete("/api/watchlist/:ticker", async ({ params }) => {
    await delay(180);
    const tickers = readWatchlist().filter((ticker) => ticker !== params.ticker);
    writeDemoValue("watchlist", tickers);
    return HttpResponse.json({ tickers });
  }),
];
