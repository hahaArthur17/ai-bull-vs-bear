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
  source: "alpha_vantage_cache" | "demo_fallback";
  is_stale: boolean;
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

export type EvidenceItem = {
  id: string;
  ticker: string;
  source_type: "news" | "filing" | "technical";
  title: string;
  url?: string | null;
  published_at?: string | null;
  excerpt: string;
  metadata: Record<string, unknown>;
};

export type StockBundle = {
  stock: Stock;
  prices: PricePoint[];
  indicators: TechnicalIndicators;
  evidence: EvidenceItem[];
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
