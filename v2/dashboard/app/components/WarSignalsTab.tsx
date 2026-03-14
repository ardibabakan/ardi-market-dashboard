"use client";

import { AlertTriangle, Shield, Minus } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import type { DashboardSnapshot, SignalRow } from "@/app/types";
import clsx from "clsx";

interface WarSignalsTabProps {
  snapshot: DashboardSnapshot | null;
  signals: SignalRow[];
}

export default function WarSignalsTab({
  snapshot,
  signals,
}: WarSignalsTabProps) {
  const signalsData = snapshot?.signals;

  return (
    <div className="space-y-3">
      {/* Signal counts */}
      {signalsData && (
        <div className="grid grid-cols-2 gap-2">
          <div className="card text-center">
            <p className="text-xs text-txt-muted mb-1">Ceasefire Signals</p>
            <p className="text-2xl font-bold text-profit">
              {signalsData.ceasefire_count}
            </p>
          </div>
          <div className="card text-center">
            <p className="text-xs text-txt-muted mb-1">Danger Signals</p>
            <p className="text-2xl font-bold text-loss">
              {signalsData.danger_count}
            </p>
          </div>
        </div>
      )}

      {/* Signal list */}
      <div className="space-y-2">
        {signals.length === 0 ? (
          <div className="card text-center text-txt-secondary text-sm py-6">
            No signals recorded yet
          </div>
        ) : (
          signals.map((signal) => {
            const SentIcon =
              signal.sentiment === "escalation"
                ? AlertTriangle
                : signal.sentiment === "ceasefire"
                  ? Shield
                  : Minus;
            const sentColor =
              signal.sentiment === "escalation" || signal.sentiment === "bearish"
                ? "text-loss"
                : signal.sentiment === "ceasefire" ||
                    signal.sentiment === "bullish"
                  ? "text-profit"
                  : "text-txt-muted";

            return (
              <div key={signal.id} className="card">
                <div className="flex items-start gap-2">
                  <SentIcon
                    className={clsx("w-4 h-4 mt-0.5 flex-shrink-0", sentColor)}
                  />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium leading-snug">
                      {signal.headline}
                    </p>
                    {signal.summary && (
                      <p className="text-xs text-txt-secondary mt-1">
                        {signal.summary}
                      </p>
                    )}
                    <div className="flex items-center gap-2 mt-1.5">
                      <span className="text-xs text-txt-muted">
                        {signal.source}
                      </span>
                      <span className="text-xs text-txt-muted">
                        {formatDistanceToNow(new Date(signal.created_at), {
                          addSuffix: true,
                        })}
                      </span>
                      {signal.confidence > 0 && (
                        <span className="text-xs text-txt-muted">
                          {Math.round(signal.confidence * 100)}% conf
                        </span>
                      )}
                    </div>
                    {signal.tickers?.length > 0 && (
                      <div className="flex gap-1 mt-1.5 flex-wrap">
                        {signal.tickers.map((t) => (
                          <span
                            key={t}
                            className="text-xs px-1.5 py-0.5 bg-bg-elevated rounded text-txt-secondary"
                          >
                            {t}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
