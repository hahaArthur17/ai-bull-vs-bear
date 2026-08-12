import type {
  AnalysisResponse,
  ExaminationResponse,
  Stock,
  StockBundle,
  WatchlistResponse,
} from "./types";
import { supabase } from "./supabase";

const API_URL = process.env.EXPO_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const session = supabase ? (await supabase.auth.getSession()).data.session : null;
  const response = await fetch(API_URL + path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(session ? { Authorization: `Bearer ${session.access_token}` } : {}),
      ...(options.headers || {}),
    },
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "The API request failed.");
  }
  return response.json() as Promise<T>;
}

export const api = {
  listStocks: (query = ""): Promise<Stock[]> =>
    request<Stock[]>(query ? "/stocks?q=" + encodeURIComponent(query) : "/stocks"),

  getWatchlist: (): Promise<WatchlistResponse> => request<WatchlistResponse>("/watchlist"),

  listAnalyses: (): Promise<AnalysisResponse[]> => request<AnalysisResponse[]>("/analysis"),

  addToWatchlist: (ticker: string): Promise<WatchlistResponse> =>
    request<WatchlistResponse>("/watchlist", {
      method: "POST",
      body: JSON.stringify({ ticker }),
    }),

  removeFromWatchlist: (ticker: string): Promise<WatchlistResponse> =>
    request<WatchlistResponse>("/watchlist/" + ticker, { method: "DELETE" }),

  getStockBundle: async (ticker: string): Promise<StockBundle> => {
    const [stock, prices, indicators, evidence] = await Promise.all([
      request<Stock>("/stocks/" + ticker),
      request<StockBundle["prices"]>("/stocks/" + ticker + "/prices"),
      request<StockBundle["indicators"]>("/stocks/" + ticker + "/indicators"),
      request<StockBundle["evidence"]>("/stocks/" + ticker + "/evidence"),
    ]);
    return { stock, prices, indicators, evidence };
  },

  runAnalysis: (ticker: string, question?: string): Promise<AnalysisResponse> =>
    request<AnalysisResponse>("/analysis/" + ticker, {
      method: "POST",
      body: JSON.stringify({ question }),
    }),

  examineClaim: (
    claimId: string,
    questionType: ExaminationResponse["question_type"],
  ): Promise<ExaminationResponse> =>
    request<ExaminationResponse>("/claims/" + claimId + "/examine", {
      method: "POST",
      body: JSON.stringify({ question_type: questionType }),
    }),
};
