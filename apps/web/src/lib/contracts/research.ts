export type Stock = {
  ticker: string;
  name: string;
  sector: string;
  price: number;
  change: number;
  changePercent: number;
  coverage: "ready" | "limited";
  marketCap: string;
  pe: string;
  description: string;
};

export type PricePoint = { date: string; close: number; volume: number };

export type Evidence = {
  id: string;
  title: string;
  type: "filing" | "news" | "technical";
  excerpt: string;
  date: string;
  url?: string;
};

export type StockResearch = {
  stock: Stock;
  prices: PricePoint[];
  metrics: { label: string; value: string; detail: string }[];
  bullCase: string;
  bearCase: string;
  evidence: Evidence[];
};

export type DebateMessage = {
  id: string;
  role: "bull" | "bear" | "judge";
  content: string;
  evidenceId?: string;
};

export type DebateRecord = {
  id: string;
  ticker: string;
  title: string;
  createdAt: string;
  messages: DebateMessage[];
  summary: string;
};
