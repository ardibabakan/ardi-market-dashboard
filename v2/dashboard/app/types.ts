// ── Dashboard Snapshot (top-level shape from dashboard_data_agent.py) ──

export interface PositionData {
  company: string;
  sector: string;
  status: "planned" | "active" | "exited" | "watching";
  entry_price: number | null;
  current_price?: number | null;
  shares?: number | null;
  target_price?: number | null;
  stop_loss?: number | null;
  thesis?: string;
  notes?: string;
}

export interface PortfolioData {
  budget: number;
  status: "paper_trading" | "live_trading" | "paused";
  positions: Record<string, PositionData>;
}

export interface SignalsData {
  ceasefire_count: number;
  danger_count: number;
  escalation_count?: number;
  latest_headline?: string;
}

export interface VixData {
  value: number;
  vix3m: number;
  regime: "LOW" | "NORMAL" | "ELEVATED" | "HIGH" | "EXTREME";
  term_structure: "contango" | "backwardation" | "flat";
  spread?: number;
}

export interface MarketData {
  oil_price: number;
  war_premium: number;
  gold_price?: number;
  dxy?: number;
  ten_year_yield?: number;
}

export interface CryptoAsset {
  coin_id: string;
  symbol: string;
  price: number;
  change_24h?: number;
  market_cap?: number;
  volume_24h?: number;
}

export interface CryptoData {
  [coinId: string]: CryptoAsset;
}

export interface ScenarioItem {
  name: string;
  probability: number;
  description: string;
  impact: string;
  trades?: string[];
}

export interface ScenarioData {
  scenarios: ScenarioItem[];
}

export interface DashboardSnapshot {
  updated_at: string;
  conflict_day: number;
  portfolio: PortfolioData;
  signals: SignalsData;
  action: string;
  market: MarketData;
  crypto: CryptoData;
  vix: VixData;
  scenarios: ScenarioData;
}

// ── Supabase table row types ──

export interface SignalRow {
  id: string;
  created_at: string;
  source: string;
  headline: string;
  sentiment: "bullish" | "bearish" | "neutral" | "ceasefire" | "escalation";
  confidence: number;
  tickers: string[];
  summary?: string;
  url?: string;
}

export interface EventRow {
  id: string;
  created_at: string;
  event_type: string;
  title: string;
  description: string;
  impact: "high" | "medium" | "low";
  region?: string;
  source?: string;
}

export interface FallenAngelRow {
  id: string;
  created_at: string;
  ticker: string;
  company: string;
  sector: string;
  drop_pct: number;
  current_price: number;
  high_52w: number;
  reason?: string;
  score?: number;
}

export interface PriceSnapshotRow {
  id: string;
  created_at: string;
  ticker: string;
  price: number;
  change: number;
  change_pct: number;
  volume?: number;
}

export interface TechnicalAnalysisRow {
  id: string;
  created_at: string;
  ticker: string;
  rsi: number | null;
  rsi_signal: string | null;
  macd: number | null;
  macd_signal_line: number | null;
  macd_histogram: number | null;
  macd_crossover: string | null;
  ma50: number | null;
  ma200: number | null;
  ma_status: string | null;
  bb_upper: number | null;
  bb_lower: number | null;
  bb_position: number | null;
  volume_ratio: number | null;
  overall_score: string | null;
}

export interface AgentRunRow {
  id: string;
  created_at: string;
  agent_name: string;
  status: "success" | "error" | "running" | "skipped";
  duration_ms?: number;
  message?: string;
  error?: string;
}

// ── Finnhub realtime price types ──

export interface RealtimePrice {
  price: number;
  change: number;
  changePct: number;
  high: number;
  low: number;
  prevClose: number;
}

export interface RealtimeResponse {
  prices: Record<string, RealtimePrice>;
  timestamp: string;
}

// ── Dashboard state wrapper from Supabase ──

export interface DashboardStateRow {
  data: DashboardSnapshot;
  updated_at: string;
}

// ── Tab type ──

export type TabId =
  | "stocks"
  | "signals"
  | "opportunities"
  | "technical"
  | "crypto"
  | "events"
  | "risk"
  | "system";
