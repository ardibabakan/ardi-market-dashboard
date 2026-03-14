"use client";

import { useState, useEffect } from "react";
import { getTechnicalAnalysis } from "@/app/lib/supabase";
import type { DashboardSnapshot, TechnicalAnalysisRow } from "@/app/types";
import clsx from "clsx";

interface TechnicalTabProps {
  snapshot: DashboardSnapshot | null;
}

function fmt(val: number | null | undefined, decimals = 2): string {
  if (val == null || isNaN(val)) return "N/A";
  return val.toFixed(decimals);
}

function scoreBadge(score: string | null | undefined) {
  const s = (score ?? "").toUpperCase();
  const color =
    s === "STRONG"
      ? "bg-profit/20 text-profit"
      : s === "BULLISH"
        ? "bg-profit/10 text-profit"
        : s === "NEUTRAL"
          ? "bg-bg-elevated text-txt-muted"
          : s === "BEARISH"
            ? "bg-loss/10 text-loss"
            : s === "WEAK"
              ? "bg-loss/20 text-loss"
              : "bg-bg-elevated text-txt-muted";
  return (
    <span className={clsx("text-xs px-1.5 py-0.5 rounded font-medium", color)}>
      {s || "N/A"}
    </span>
  );
}

function rsiColor(rsi: number | null | undefined): string {
  if (rsi == null) return "text-txt-muted";
  if (rsi >= 70) return "text-loss";
  if (rsi <= 30) return "text-profit";
  return "text-txt";
}

function macdColor(val: number | null | undefined): string {
  if (val == null) return "text-txt-muted";
  return val >= 0 ? "text-profit" : "text-loss";
}

export default function TechnicalTab({ snapshot: _snapshot }: TechnicalTabProps) {
  const [technicals, setTechnicals] = useState<TechnicalAnalysisRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getTechnicalAnalysis()
      .then((data) => setTechnicals(data as unknown as TechnicalAnalysisRow[]))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="space-y-2">
        {[1, 2, 3].map((i) => (
          <div key={i} className="card animate-pulse-slow h-28 bg-bg-surface" />
        ))}
      </div>
    );
  }

  if (technicals.length === 0) {
    return (
      <div className="card text-center text-txt-secondary text-sm py-8">
        No technical analysis data yet. Run the daily analysis first.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {technicals.map((ta) => {
        const ticker = ta.ticker ?? "???";
        const rsi = ta.rsi;
        const rsiSig = ta.rsi_signal ?? "N/A";
        const macd = ta.macd;
        const macdSigLine = ta.macd_signal_line;
        const macdHist = ta.macd_histogram;
        const macdCross = ta.macd_crossover ?? "N/A";
        const ma50 = ta.ma50;
        const ma200 = ta.ma200;
        const maStatus = ta.ma_status ?? "N/A";
        const bbUpper = ta.bb_upper;
        const bbLower = ta.bb_lower;
        const bbPos = ta.bb_position;
        const volRatio = ta.volume_ratio;
        const overall = ta.overall_score;

        return (
          <div key={ta.id ?? ticker} className="card">
            {/* Header row */}
            <div className="flex justify-between items-center mb-3">
              <div className="flex items-center gap-2">
                <span className="font-bold text-sm">{ticker}</span>
                {scoreBadge(overall)}
              </div>
              <span className={clsx("text-sm font-medium", rsiColor(rsi))}>
                RSI {fmt(rsi, 1)}
                <span className="text-xs text-txt-muted ml-1">({rsiSig})</span>
              </span>
            </div>

            {/* Indicators grid */}
            <div className="grid grid-cols-3 sm:grid-cols-6 gap-3 text-xs">
              <div>
                <p className="text-txt-muted">MACD</p>
                <p className={clsx("font-medium", macdColor(macd))}>{fmt(macd, 3)}</p>
              </div>
              <div>
                <p className="text-txt-muted">Signal Line</p>
                <p className="font-medium">{fmt(macdSigLine, 3)}</p>
              </div>
              <div>
                <p className="text-txt-muted">Histogram</p>
                <p className={clsx("font-medium", macdColor(macdHist))}>{fmt(macdHist, 3)}</p>
              </div>
              <div>
                <p className="text-txt-muted">MACD Cross</p>
                <p
                  className={clsx(
                    "font-medium",
                    macdCross === "BULLISH" ? "text-profit" : macdCross === "BEARISH" ? "text-loss" : "text-txt-muted"
                  )}
                >
                  {macdCross}
                </p>
              </div>
              <div>
                <p className="text-txt-muted">MA50</p>
                <p className="font-medium">{ma50 != null ? `$${fmt(ma50)}` : "N/A"}</p>
              </div>
              <div>
                <p className="text-txt-muted">MA200</p>
                <p className="font-medium">{ma200 != null ? `$${fmt(ma200)}` : "N/A"}</p>
              </div>
            </div>

            {/* Second row */}
            <div className="grid grid-cols-3 sm:grid-cols-5 gap-3 text-xs mt-2 pt-2 border-t border-bg-elevated">
              <div>
                <p className="text-txt-muted">MA Status</p>
                <p
                  className={clsx(
                    "font-medium",
                    maStatus.includes("GOLDEN") ? "text-profit" : maStatus.includes("DEATH") ? "text-loss" : "text-txt-secondary"
                  )}
                >
                  {maStatus.replace(/_/g, " ")}
                </p>
              </div>
              <div>
                <p className="text-txt-muted">BB Upper</p>
                <p className="font-medium">{bbUpper != null ? `$${fmt(bbUpper)}` : "N/A"}</p>
              </div>
              <div>
                <p className="text-txt-muted">BB Lower</p>
                <p className="font-medium">{bbLower != null ? `$${fmt(bbLower)}` : "N/A"}</p>
              </div>
              <div>
                <p className="text-txt-muted">BB Position</p>
                <p className="font-medium">{bbPos != null ? fmt(bbPos, 3) : "N/A"}</p>
              </div>
              <div>
                <p className="text-txt-muted">Vol Ratio</p>
                <p
                  className={clsx(
                    "font-medium",
                    volRatio != null && volRatio >= 2.0 ? "text-warning" : "text-txt"
                  )}
                >
                  {volRatio != null ? `${fmt(volRatio)}x` : "N/A"}
                </p>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
