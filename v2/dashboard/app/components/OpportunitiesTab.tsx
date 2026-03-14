"use client";

import { TrendingDown } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import type { FallenAngelRow } from "@/app/types";
import clsx from "clsx";

interface OpportunitiesTabProps {
  fallenAngels: FallenAngelRow[];
}

export default function OpportunitiesTab({
  fallenAngels,
}: OpportunitiesTabProps) {
  if (fallenAngels.length === 0) {
    return (
      <div className="card text-center text-txt-secondary text-sm py-8">
        No fallen angel opportunities found yet
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <p className="text-xs text-txt-muted px-1">
        Stocks that have dropped significantly from their 52-week highs
      </p>
      {fallenAngels.map((angel) => (
        <div key={angel.id} className="card">
          <div className="flex justify-between items-start">
            <div>
              <div className="flex items-center gap-2">
                <TrendingDown className="w-4 h-4 text-loss" />
                <span className="font-bold text-sm">{angel.ticker}</span>
                {angel.score !== undefined && angel.score !== null && (
                  <span
                    className={clsx(
                      "text-xs px-1.5 py-0.5 rounded",
                      angel.score >= 7
                        ? "bg-profit/20 text-profit"
                        : angel.score >= 4
                          ? "bg-warning/20 text-warning"
                          : "bg-bg-elevated text-txt-muted"
                    )}
                  >
                    Score: {angel.score}
                  </span>
                )}
              </div>
              <p className="text-xs text-txt-secondary mt-0.5">
                {angel.company}
              </p>
              <p className="text-xs text-txt-muted">{angel.sector}</p>
            </div>
            <div className="text-right">
              <p className="font-semibold text-sm">
                ${angel.current_price.toFixed(2)}
              </p>
              <p className="text-xs text-loss">
                {angel.drop_pct.toFixed(1)}% from high
              </p>
              <p className="text-xs text-txt-muted">
                52w: ${angel.high_52w.toFixed(2)}
              </p>
            </div>
          </div>
          {angel.reason && (
            <p className="text-xs text-txt-muted mt-2 border-t border-bg-elevated pt-2">
              {angel.reason}
            </p>
          )}
          <p className="text-xs text-txt-muted mt-1">
            {formatDistanceToNow(new Date(angel.created_at), {
              addSuffix: true,
            })}
          </p>
        </div>
      ))}
    </div>
  );
}
