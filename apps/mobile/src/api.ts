import type {
  AnalysisResponse,
  ExaminationResponse,
  Stock,
  StockBundle,
  WatchlistResponse,
} from "./types";
import { supabase } from "./supabase";

const API_URL = process.env.EXPO_PUBLIC_API_URL || "http://localhost:8000";
const configuredTimeout = Number(process.env.EXPO_PUBLIC_API_TIMEOUT_MS || "15000");
const REQUEST_TIMEOUT_MS = Number.isFinite(configuredTimeout) && configuredTimeout > 0
  ? configuredTimeout
  : 15000;

async function responseError(response: Response): Promise<Error> {
  let detail = "";
  try {
    const payload = await response.json() as { detail?: unknown };
    if (typeof payload.detail === "string") detail = payload.detail;
  } catch {
    // Non-JSON provider and proxy errors use the safe status-specific message below.
  }
  if (response.status === 401) {
    return new Error("Your session is missing or expired. Sign in again and retry.");
  }
  if (response.status === 503) {
    return new Error(detail || "A live service is temporarily unavailable. Retry shortly.");
  }
  return new Error(detail || `The API request failed (${response.status}).`);
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const session = supabase ? (await supabase.auth.getSession()).data.session : null;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(API_URL + path, {
      ...options,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...(session ? { Authorization: `Bearer ${session.access_token}` } : {}),
        ...(options.headers || {}),
      },
    });
    if (!response.ok) throw await responseError(response);
    return response.json() as Promise<T>;
  } catch (error) {
    if (controller.signal.aborted) {
      throw new Error("The request timed out. Check the connection and retry.");
    }
    if (error instanceof TypeError) {
      throw new Error("The API is unreachable. Check the network and backend, then retry.");
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
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
