export type Stock = {
  ticker: string;
  company_name: string;
  exchange: string;
  sector: string | null;
  sec_cik: number | null;
  country: string | null;
  aliases: string[];
  is_active: boolean;
  coverage_status: "catalog_only" | "price_cached" | "evidence_ready" | "debate_ready";
  coverage_updated_at: string | null;
};

export type PricePoint = {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  source: "daily_market_cache" | "demo_fallback" | "review_fixture";
  is_stale: boolean;
};

export type PriceHistoryPoint = {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  frequency: "weekly";
  source: "alpha_vantage_weekly" | "review_fixture";
  retrieved_at: string;
};

export type TechnicalIndicators = {
  ticker: string;
  as_of: string;
  rsi: number;
  macd: number;
  macd_signal: number;
  moving_average_20: number;
  moving_average_50: number;
  volatility: number;
  volume_spike: boolean;
  signal_summary: string;
  availability?: {
    price_line: boolean;
    price_change: boolean;
    moving_average_20: boolean;
    moving_average_50: boolean;
    rsi: boolean;
    macd: boolean;
    macd_signal: boolean;
    volume: boolean;
    volatility: boolean;
  };
  history?: {
    provenance: "live_fresh" | "live_stale" | "review_fixture" | "unavailable";
    record_count: number;
    completed_close_count: number;
    required_for_complete: number;
    is_ordered: boolean;
    has_unique_dates: boolean;
    has_valid_closes: boolean;
    has_valid_ohlcv: boolean;
    has_only_completed_closes: boolean;
    is_valid: boolean;
    complete_view: boolean;
    explanation: string;
  };
};

export type MarketQuote = {
  ticker: string;
  close: number;
  open: number;
  high: number;
  low: number;
  previous_close: number;
  as_of: string;
  source: "finnhub_quote";
};

export type MacroSeries = {
  code: string;
  name: string;
  source: "fred" | "eia" | "treasury" | "fomc" | "cme";
  unit: string;
  frequency: string;
  metadata: Record<string, unknown>;
};

export type MacroObservation = {
  series_code: string;
  observation_date: string;
  value: number;
  metadata: Record<string, unknown>;
  retrieved_at: string;
};

export type MacroSeriesContext = {
  series: MacroSeries;
  observations: MacroObservation[];
};

export type EvidenceItem = {
  id: string;
  ticker: string;
  source_type: "news" | "filing" | "technical";
  title: string;
  url?: string | null;
  published_at?: string | null;
  excerpt: string;
  metadata: Record<string, unknown>;
  freshness: {
    status: "current" | "stale" | "unknown";
    age_days?: number | null;
    max_age_days?: number | null;
    evaluated_at?: string | null;
  };
};

export type StockBundle = {
  stock: Stock;
  data_mode?: "standard" | "review_fixture";
  prices: PricePoint[];
  weekly_history: PriceHistoryPoint[];
  quote: MarketQuote | null;
  indicators: TechnicalIndicators;
  evidence: EvidenceItem[];
  macro_context: MacroSeriesContext[];
};

export type Claim = {
  id: string;
  agent: "bull" | "bear";
  text: string;
  evidence_ids: string[];
  signal_strength: "weak" | "medium" | "strong";
  confidence: "low" | "medium" | "high";
  risk_meaning: string;
  terms: string[];
};

export type AnalysisResponse = {
  analysis_id: string;
  ticker: string;
  created_at: string;
  question?: string | null;
  indicators: TechnicalIndicators;
  snapshot: {
    retrieved_at: string;
    price: {
      as_of: string;
      close: number;
      source: "daily_market_cache" | "demo_fallback" | "review_fixture";
      is_stale: boolean;
    };
    retrieved_evidence_count: number;
    included_evidence_ids: string[];
    evidence: Array<{
      id: string;
      source_type: "news" | "filing" | "technical";
      published_at?: string | null;
      freshness: EvidenceItem["freshness"];
    }>;
    macro_context: Array<{
      code: string;
      name: string;
      source: MacroSeries["source"];
      unit: string;
      observation_date: string;
      value: number;
      retrieved_at: string;
    }>;
    excluded_external_evidence_count: number;
    missing_current_evidence: Array<"news" | "filing">;
  };
  judge: {
    summary: string;
    evidence_strength: "weak" | "medium" | "strong";
    uncertainty: string;
    risk_level: "low" | "medium" | "high";
  };
  bull: Claim;
  bear: Claim;
  evidence: EvidenceItem[];
  disclaimer: string;
  guardrail_status: "passed" | "rewritten";
  trace: Array<{ step: string; status: string; detail: string }>;
  token_usage: {
    model_name: string;
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
};

export type ExaminationResponse = {
  claim_id: string;
  question_type: "explain_term" | "evidence_support" | "signal_strength" | "risk_meaning";
  answer: string;
  evidence: EvidenceItem[];
  disclaimer: string;
};

export type WatchlistResponse = {
  user_id: string;
  tickers: string[];
};

export type DebateSessionStatus =
  | "created"
  | "queued_round_1"
  | "running_round_1"
  | "awaiting_user"
  | "interrupted_awaiting_user"
  | "queued_round_2"
  | "running_round_2"
  | "completed"
  | "cancel_requested"
  | "cancelled"
  | "failed";

export type DebateMessage = {
  id: string;
  session_id: string;
  branch_id: string;
  generation_id: string;
  sequence_number: number;
  round_number: number;
  exchange_number: number;
  role: "bull" | "bear" | "judge" | "user" | "explainer" | "system";
  message_kind: "argument" | "rebuttal" | "summary" | "question" | "explanation";
  content: string;
  confidence?: "low" | "medium" | "high" | null;
  signal_strength?: "weak" | "medium" | "strong" | null;
  terms: string[];
  metadata: Record<string, unknown>;
  is_complete: boolean;
  cancelled_at?: string | null;
  created_at: string;
};

export type DebateMessageEvidence = {
  message_id: string;
  evidence_id: string;
  citation_order: number;
  support_span?: string | null;
  metadata: Record<string, unknown>;
};

export type DebateEvidencePresentation = {
  evidence_id: string;
  evidence_type: "news" | "filing" | "technical" | null;
  title: string | null;
  fact: string | null;
  source: string | null;
  date: string | null;
  freshness: EvidenceItem["freshness"];
  support_span: string | null;
  source_destination: string | null;
  missing_metadata: Array<
    | "evidence_type"
    | "title"
    | "fact"
    | "source"
    | "date"
    | "support_span"
    | "source_destination"
  >;
};

export type DebateMessagePresentation = {
  argument: string;
  facts_used: DebateEvidencePresentation[];
  interpretation: string | null;
  uncertainty: string | null;
};

export type DebateMessageRecord = {
  message: DebateMessage;
  citations: DebateMessageEvidence[];
  presentation?: DebateMessagePresentation | null;
};

export type DebateSessionSummary = {
  id: string;
  ticker: string;
  status: DebateSessionStatus;
  active_branch_id: string;
  active_generation_id: string;
  opening_side: "bull" | "bear";
  initial_question?: string | null;
  interim_judge_message_id?: string | null;
  final_judge_message_id?: string | null;
  safe_error_code?: string | null;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
};

export type DebateSessionDetail = {
  session: DebateSessionSummary;
  messages: DebateMessageRecord[];
  job?: DebateJobSummary | null;
  execution_mode: "synchronous_preview" | "queued";
};

export type DebateJobSummary = {
  id: string;
  session_id: string;
  job_type: "round_1" | "round_2" | "explanation" | "replay";
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  queue_message_id?: number | null;
  attempt_count: number;
  max_attempts: number;
  safe_error_code?: string | null;
};

export type DebateMutationResponse = DebateSessionDetail & {
  job_id: string;
};

export type ExplanationRequest = {
  messageId: string;
  selectedText: string;
  question: string;
};

export type ExplanationResult = {
  session_id: string;
  source_message_id: string;
  selected_text: string;
  question: string;
  content: string;
  evidence_ids: string[];
  terms: string[];
  provider_name: string;
  provider_version: string;
  guardrail_status: "passed" | "rewritten";
};

export type DebateEventType =
  | "session.created"
  | "job.queued"
  | "job.started"
  | "job.retry_scheduled"
  | "job.failed"
  | "turn.started"
  | "turn.delta"
  | "turn.citation"
  | "turn.completed"
  | "judge.started"
  | "judge.delta"
  | "judge.completed"
  | "session.awaiting_user"
  | "session.interrupted_awaiting_user"
  | "explanation.started"
  | "explanation.delta"
  | "explanation.completed"
  | "session.cancel_requested"
  | "session.cancelled"
  | "session.completed"
  | "session.failed"
  | "heartbeat";

export type DebateEvent = {
  version: 1;
  event_id: string;
  session_id: string;
  sequence: number;
  type: DebateEventType;
  timestamp: string;
  payload: Record<string, unknown>;
};
