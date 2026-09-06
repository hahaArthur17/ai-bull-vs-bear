import type {
  AnalysisResponse,
  DebateMessageRecord,
  DebateMutationResponse,
  DebateSessionDetail,
  DebateSessionSummary,
  ExaminationResponse,
  ExplanationRequest,
  ExplanationResult,
  Stock,
  StockBundle,
  WatchlistResponse,
} from "./types";
import { DebateStreamClient } from "./debateStream";
import type { DebateStreamSnapshot } from "./debateStream";
import { serializeExplanationRequest } from "./explanationRequest";
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
  getHealth: (): Promise<{ data_mode?: string; debate_workflow_v2?: boolean }> =>
    request<{ data_mode?: string; debate_workflow_v2?: boolean }>("/health"),

  listStocks: (query = "", limit = 20): Promise<Stock[]> => {
    const params = new URLSearchParams();
    if (query) params.set("q", query);
    params.set("limit", String(limit));
    return request<Stock[]>("/stocks?" + params.toString());
  },

  getStock: (ticker: string): Promise<Stock> =>
    request<Stock>("/stocks/" + encodeURIComponent(ticker)),

  getWatchlist: (): Promise<WatchlistResponse> => request<WatchlistResponse>("/watchlist"),

  listAnalyses: (): Promise<AnalysisResponse[]> => request<AnalysisResponse[]>("/analysis"),

  getDebate: (sessionId: string): Promise<DebateSessionDetail> =>
    request<DebateSessionDetail>("/debates/" + encodeURIComponent(sessionId)),

  getDebateMessages: (sessionId: string): Promise<DebateMessageRecord[]> =>
    request<DebateMessageRecord[]>(
      "/debates/" + encodeURIComponent(sessionId) + "/messages",
    ),

  listDebates: (limit = 50): Promise<DebateSessionSummary[]> =>
    request<DebateSessionSummary[]>("/debates?limit=" + encodeURIComponent(String(limit))),

  explainDebate: (
    sessionId: string,
    explanation: ExplanationRequest,
  ): Promise<ExplanationResult> =>
    request<ExplanationResult>(
      "/debates/" + encodeURIComponent(sessionId) + "/explanations",
      {
        method: "POST",
        body: JSON.stringify(serializeExplanationRequest(explanation)),
      },
    ),

  createDebate: (
    ticker: string,
    options: {
      question?: string;
      openingSide?: "bull" | "bear";
      idempotencyKey?: string;
    } = {},
  ): Promise<DebateMutationResponse> =>
    request<DebateMutationResponse>("/debates", {
      method: "POST",
      body: JSON.stringify({
        ticker,
        question: options.question,
        opening_side: options.openingSide || "bull",
        idempotency_key: options.idempotencyKey,
      }),
    }),

  challengeDebate: (
    sessionId: string,
    challenge: {
      selectedMessageId: string;
      selectedText: string;
      question: string;
      idempotencyKey?: string;
    },
  ): Promise<DebateMutationResponse> =>
    request<DebateMutationResponse>(
      "/debates/" + encodeURIComponent(sessionId) + "/interventions",
      {
        method: "POST",
        body: JSON.stringify({
          selected_message_id: challenge.selectedMessageId,
          selected_text: challenge.selectedText,
          question: challenge.question,
          idempotency_key: challenge.idempotencyKey,
        }),
      },
    ),

  cancelDebate: (sessionId: string, generationId: string): Promise<DebateSessionDetail> =>
    request<DebateSessionDetail>(
      "/debates/" + encodeURIComponent(sessionId) + "/cancel",
      {
        method: "POST",
        body: JSON.stringify({ generation_id: generationId }),
      },
    ),

  addToWatchlist: (ticker: string): Promise<WatchlistResponse> =>
    request<WatchlistResponse>("/watchlist", {
      method: "POST",
      body: JSON.stringify({ ticker }),
    }),

  removeFromWatchlist: (ticker: string): Promise<WatchlistResponse> =>
    request<WatchlistResponse>("/watchlist/" + ticker, { method: "DELETE" }),

  getStockBundle: (ticker: string): Promise<StockBundle> =>
    request<StockBundle>("/stocks/" + encodeURIComponent(ticker) + "/bundle"),

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

export function createDebateStreamClient(
  sessionId: string,
  onSnapshot: (snapshot: DebateStreamSnapshot) => void,
): DebateStreamClient {
  const encodedSessionId = encodeURIComponent(sessionId);
  return new DebateStreamClient({
    eventUrl: `${API_URL}/debates/${encodedSessionId}/events`,
    getAccessToken: async () => {
      const session = supabase ? (await supabase.auth.getSession()).data.session : null;
      return session?.access_token || null;
    },
    loadCanonical: () => api.getDebate(sessionId),
    onSnapshot,
  });
}
