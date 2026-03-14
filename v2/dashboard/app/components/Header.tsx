"use client";

import { RefreshCw, Shield } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import type { DashboardSnapshot } from "@/app/types";

interface HeaderProps {
  snapshot: DashboardSnapshot | null;
  lastRefresh: Date | null;
  onRefresh: () => void;
}

export default function Header({
  snapshot,
  lastRefresh,
  onRefresh,
}: HeaderProps) {
  const vixValue = snapshot?.vix?.value;
  const conflictDay = snapshot?.conflict_day;

  const vixColor =
    vixValue && vixValue > 25
      ? "text-loss"
      : vixValue && vixValue > 18
        ? "text-warning"
        : "text-profit";

  return (
    <header className="sticky top-0 z-50 bg-bg/90 backdrop-blur border-b border-bg-elevated">
      <div className="max-w-7xl mx-auto px-3 py-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Shield className="w-5 h-5 text-purple" />
          <span className="font-bold text-sm">Ardi MCC</span>
          {conflictDay && (
            <span className="text-xs text-txt-muted ml-1">
              Day {conflictDay}
            </span>
          )}
        </div>

        <div className="flex items-center gap-3">
          {vixValue && (
            <span className={`text-xs font-medium ${vixColor}`}>
              VIX {vixValue.toFixed(1)}
            </span>
          )}
          {lastRefresh && (
            <span className="text-xs text-txt-muted">
              {formatDistanceToNow(lastRefresh, { addSuffix: true })}
            </span>
          )}
          <button
            onClick={onRefresh}
            className="p-1 hover:bg-bg-elevated rounded transition-colors"
            title="Refresh data"
          >
            <RefreshCw className="w-4 h-4 text-txt-secondary" />
          </button>
        </div>
      </div>
    </header>
  );
}
