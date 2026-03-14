"use client";

import { useState, useEffect } from "react";
import { getTechnicalAnalysis } from "@/app/lib/supabase";
import type { DashboardSnapshot, TechnicalAnalysisRow } from "@/app/types";
import clsx from "clsx";

interface TechnicalTabProps {
  snapshot: DashboardSnapshot | null;
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
          <div
            key={i}
            className="card animate-pulse-slow h-24 bg-bg-surface"
          />
        ))}
      </div>
    );
  }

  if (technicals.length === 0) {
    return (
      <div className="card text-center text-txt-secondary text-sm py-8">
        No technical analysis data available
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {technicals.map((ta) => (
        <div key={ta.id} className="card">
          <div className="flex justify-between items-start mb-2">
            <div className="flex items-center gap-2">
              <span className="font-bold text-sm">{ta.ticker}</span>
              <span
                className={clsx(
                  "text-xs px-1.5 py-0.5 rounded",
                  ta.trend === "bullish"
                    ? "bg-profit/20 text-profit"
                    : ta.trend === "bearish"
                      ? "bg-loss/20 text-loss"
                      : "bg-bg-elevated text-txt-muted"
                )}
              >
                {ta.trend}
              </span>
            </div>
            <span className="text-xs text-txt-secondary">
              RSI {ta.rsi.toFixed(1)}
            </span>
          </div>

          <div className="grid grid-cols-3 gap-2 text-xs">
            <div>
              <p className="text-txt-muted">SMA 20</p>
              <p className="font-medium">${ta.sma_20.toFixed(2)}</p>
            </div>
            <div>
              <p className="text-txt-muted">SMA 50</p>
              <p className="font-medium">${ta.sma_50.toFixed(2)}</p>
            </div>
            <div>
              <p className="text-txt-muted">SMA 200</p>
              <p className="font-medium">${ta.sma_200.toFixed(2)}</p>
            </div>
            <div>
              <p className="text-txt-muted">MACD</p>
              <p
                className={clsx(
                  "font-medium",
                  ta.macd >= 0 ? "text-profit" : "text-loss"
                )}
              >
                {ta.macd.toFixed(2)}
              </p>
            </div>
            <div>
              <p className="text-txt-muted">ATR</p>
              <p className="font-medium">{ta.atr.toFixed(2)}</p>
            </div>
            <div>
              <p className="text-txt-muted">Signal</p>
              <p className="font-medium">{ta.macd_signal.toFixed(2)}</p>
            </div>
          </div>

          {(ta.support || ta.resistance) && (
            <div className="flex gap-4 mt-2 pt-2 border-t border-bg-elevated text-xs">
              {ta.support && (
                <span className="text-profit">
                  Support: ${ta.support.toFixed(2)}
                </span>
              )}
              {ta.resistance && (
                <span className="text-loss">
                  Resistance: ${ta.resistance.toFixed(2)}
                </span>
              )}
            </div>
          )}

          <p className="text-xs text-txt-secondary mt-2">
            {ta.recommendation}
          </p>
        </div>
      ))}
    </div>
  );
}
