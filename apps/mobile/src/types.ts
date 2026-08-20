export type Stock = {
  ticker: string;
  company_name: string;
  exchange: string;
  sector: string;
};

export type PricePoint = {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  source: "daily_market_cache" | "demo_fallback";
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
  source: "alpha_vantage_weekly";
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
      source: "daily_market_cache" | "demo_fallback";
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
