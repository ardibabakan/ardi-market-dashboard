import { createClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

export const supabase = createClient(url, key);

export async function getDashboardState() {
  const { data, error } = await supabase
    .from("dashboard_state")
    .select("data, updated_at")
    .eq("id", "current")
    .single();
  if (error) throw error;
  return data;
}

export async function getSignals(limit = 20) {
  const { data, error } = await supabase
    .from("signals")
    .select("*")
    .order("created_at", { ascending: false })
    .limit(limit);
  if (error) throw error;
  return data ?? [];
}

export async function getEvents(limit = 30) {
  const { data, error } = await supabase
    .from("events")
    .select("*")
    .order("created_at", { ascending: false })
    .limit(limit);
  if (error) throw error;
  return data ?? [];
}

export async function getFallenAngels() {
  const { data, error } = await supabase
    .from("fallen_angels")
    .select("*")
    .order("created_at", { ascending: false })
    .limit(50);
  if (error) throw error;
  return data ?? [];
}

export async function getLatestPrices(tickers: string[]) {
  const { data, error } = await supabase
    .from("price_snapshots")
    .select("*")
    .in("ticker", tickers)
    .order("created_at", { ascending: false });
  if (error) throw error;
  const latest: Record<string, PriceSnapshotRecord> = {};
  for (const row of data || []) {
    if (!latest[row.ticker]) latest[row.ticker] = row;
  }
  return Object.values(latest);
}

export async function getTechnicalAnalysis() {
  const { data, error } = await supabase
    .from("technical_analysis")
    .select("*")
    .order("created_at", { ascending: false })
    .limit(20);
  if (error) throw error;
  const latest: Record<string, TechnicalAnalysisRecord> = {};
  for (const row of data || []) {
    if (!latest[row.ticker]) latest[row.ticker] = row;
  }
  return Object.values(latest);
}

export async function getAgentRuns(limit = 50) {
  const { data, error } = await supabase
    .from("agent_runs")
    .select("*")
    .order("created_at", { ascending: false })
    .limit(limit);
  if (error) throw error;
  return data ?? [];
}

// Internal types for deduplication records
interface PriceSnapshotRecord {
  ticker: string;
  [key: string]: unknown;
}

interface TechnicalAnalysisRecord {
  ticker: string;
  [key: string]: unknown;
}
