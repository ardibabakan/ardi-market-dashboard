"use client";

import type { DashboardSnapshot, RealtimeResponse } from "@/app/types";
import clsx from "clsx";

interface MyStocksTabProps {
  snapshot: DashboardSnapshot | null;
  realtimePrices: RealtimeResponse | null;
}

export default function MyStocksTab({
  snapshot,
  realtimePrices,
}: MyStocksTabProps) {
  const portfolio = snapshot?.portfolio;
  const positions = portfolio?.positions;

  if (!positions) {
    return (
      <div className="card text-center text-txt-secondary text-sm py-8">
        No portfolio data available
      </div>
    );
  }

  const tickers = Object.keys(positions);

  return (
    <div className="space-y-3">
      {/* Budget summary */}
      <div className="card">
        <div className="flex justify-between items-center">
          <div>
            <p className="text-xs text-txt-muted uppercase tracking-wide">
              Budget
            </p>
            <p className="text-xl font-bold">
              ${portfolio.budget.toLocaleString()}
            </p>
          </div>
          <span className="text-xs px-2 py-1 bg-info/20 text-info rounded-full">
            {portfolio.status.replace("_", " ")}
          </span>
        </div>
      </div>

      {/* Positions */}
      <div className="space-y-2">
        {tickers.map((ticker) => {
          const pos = positions[ticker];
          const rt = realtimePrices?.prices?.[ticker];
          const price = rt?.price ?? pos.current_price;
          const changePct = rt?.changePct;

          return (
            <div key={ticker} className="card">
              <div className="flex justify-between items-start">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-sm">{ticker}</span>
                    <span
                      className={clsx(
                        "text-xs px-1.5 py-0.5 rounded",
                        pos.status === "active"
                          ? "bg-profit/20 text-profit"
                          : pos.status === "planned"
                            ? "bg-info/20 text-info"
                            : "bg-bg-elevated text-txt-muted"
                      )}
                    >
                      {pos.status}
                    </span>
                  </div>
                  <p className="text-xs text-txt-secondary mt-0.5">
                    {pos.company}
                  </p>
                  <p className="text-xs text-txt-muted">{pos.sector}</p>
                </div>
                <div className="text-right">
                  {price ? (
                    <>
                      <p className="font-semibold text-sm">
                        ${price.toFixed(2)}
                      </p>
                      {changePct !== undefined && changePct !== null && (
                        <p
                          className={clsx(
                            "text-xs",
                            changePct >= 0 ? "text-profit" : "text-loss"
                          )}
                        >
                          {changePct >= 0 ? "+" : ""}
                          {changePct.toFixed(2)}%
                        </p>
                      )}
                    </>
                  ) : (
                    <p className="text-xs text-txt-muted">--</p>
                  )}
                </div>
              </div>
              {pos.thesis && (
                <p className="text-xs text-txt-muted mt-2 border-t border-bg-elevated pt-2">
                  {pos.thesis}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
