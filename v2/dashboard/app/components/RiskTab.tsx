"use client";

import clsx from "clsx";
import { ShieldAlert, AlertTriangle, PieChart } from "lucide-react";

interface RiskTabProps {
  data: any;
}

export default function RiskTab({ data }: RiskTabProps) {
  const positions = data?.portfolio?.positions ?? {};
  const scenarios = data?.scenarios;
  const vix = data?.vix;

  // Calculate sector concentration
  const sectorMap: Record<string, number> = {};
  let total = 0;
  Object.values(positions).forEach((pos: any) => {
    const sector = pos?.sector?.toLowerCase() ?? "other";
    const bucket =
      sector.includes("defen") ? "Defence" :
      sector.includes("energy") || sector.includes("oil") ? "Energy" :
      sector.includes("safe") || sector.includes("gold") ? "Safe Haven" :
      sector.includes("nuclear") ? "Nuclear" :
      sector.includes("travel") ? "Travel" :
      "Other";
    sectorMap[bucket] = (sectorMap[bucket] || 0) + 1;
    total++;
  });

  const concentration = Object.entries(sectorMap)
    .map(([sector, count]) => ({
      sector,
      count,
      pct: total > 0 ? (count / total) * 100 : 0,
    }))
    .sort((a, b) => b.pct - a.pct);

  const concentrationColor = (pct: number) => {
    if (pct > 40) return "text-loss";
    if (pct > 25) return "text-warning";
    return "text-profit";
  };

  const barColor = (pct: number) => {
    if (pct > 40) return "bg-loss";
    if (pct > 25) return "bg-warning";
    return "bg-profit";
  };

  return (
    <div className="space-y-8">
      {/* Portfolio Concentration */}
      <section className="bg-bg-surface border border-txt-muted/10 rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <PieChart className="w-4 h-4 text-info" />
          <h2 className="text-sm font-semibold text-txt-secondary uppercase tracking-wider">
            Portfolio Concentration
          </h2>
        </div>
        {concentration.length > 0 ? (
          <div className="space-y-3">
            {concentration.map(({ sector, count, pct }) => (
              <div key={sector}>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-txt">{sector}</span>
                  <span className={clsx("font-medium", concentrationColor(pct))}>
                    {pct.toFixed(0)}% ({count})
                  </span>
                </div>
                <div className="h-2 bg-bg-elevated rounded-full overflow-hidden">
                  <div
                    className={clsx("h-full rounded-full transition-all", barColor(pct))}
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-txt-muted">No positions to analyze</p>
        )}
      </section>

      {/* VaR */}
      {(data?.var_95 != null || data?.risk?.var_95 != null) && (
        <section className="bg-bg-surface border border-txt-muted/10 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle className="w-4 h-4 text-warning" />
            <h2 className="text-sm font-semibold text-txt-secondary uppercase tracking-wider">
              Value at Risk (95%)
            </h2>
          </div>
          <p className="text-2xl font-bold text-loss">
            ${(data?.var_95 ?? data?.risk?.var_95)?.toFixed(2)}
          </p>
          <p className="text-xs text-txt-muted mt-1">
            Maximum expected daily loss at 95% confidence
          </p>
        </section>
      )}

      {/* Stress Scenarios */}
      {scenarios && Object.keys(scenarios).length > 0 && (
        <section className="bg-bg-surface border border-txt-muted/10 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <ShieldAlert className="w-4 h-4 text-loss" />
            <h2 className="text-sm font-semibold text-txt-secondary uppercase tracking-wider">
              Stress Scenarios
            </h2>
          </div>
          <div className="space-y-3">
            {Object.entries(scenarios).map(([name, scenario]: [string, any]) => (
              <div
                key={name}
                className="bg-bg-elevated rounded-lg p-3 space-y-1"
              >
                <p className="text-sm font-medium text-txt capitalize">
                  {name.replace(/_/g, " ")}
                </p>
                {scenario?.description && (
                  <p className="text-xs text-txt-secondary">
                    {scenario.description}
                  </p>
                )}
                {scenario?.portfolio_impact != null && (
                  <p
                    className={clsx(
                      "text-sm font-semibold",
                      scenario.portfolio_impact < 0 ? "text-loss" : "text-profit"
                    )}
                  >
                    Impact: {scenario.portfolio_impact > 0 ? "+" : ""}
                    {typeof scenario.portfolio_impact === "number"
                      ? scenario.portfolio_impact.toFixed(1)
                      : scenario.portfolio_impact}
                    %
                  </p>
                )}
                {scenario?.probability && (
                  <p className="text-[10px] text-txt-muted">
                    Probability: {scenario.probability}
                  </p>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Correlation Warnings */}
      {(data?.correlation_warnings?.length > 0 ||
        data?.risk?.correlation_warnings?.length > 0) && (
        <section className="bg-bg-surface border border-txt-muted/10 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <AlertTriangle className="w-4 h-4 text-warning" />
            <h2 className="text-sm font-semibold text-txt-secondary uppercase tracking-wider">
              Correlation Warnings
            </h2>
          </div>
          <div className="space-y-2">
            {(data?.correlation_warnings ?? data?.risk?.correlation_warnings ?? []).map(
              (warning: any, i: number) => (
                <div
                  key={i}
                  className="flex items-start gap-2 text-sm text-warning"
                >
                  <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                  <span>
                    {typeof warning === "string" ? warning : warning?.message ?? JSON.stringify(warning)}
                  </span>
                </div>
              )
            )}
          </div>
        </section>
      )}

      {/* VIX Context */}
      {vix && (
        <section className="bg-bg-surface border border-txt-muted/10 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-txt-secondary uppercase tracking-wider mb-3">
            Market Volatility Context
          </h2>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-txt-secondary">VIX</p>
              <p className="text-xl font-bold text-txt">{vix.value?.toFixed(1)}</p>
            </div>
            <div>
              <p className="text-txt-secondary">Regime</p>
              <p
                className={clsx(
                  "text-xl font-bold",
                  vix.regime === "CALM"
                    ? "text-profit"
                    : vix.regime === "NORMAL"
                    ? "text-info"
                    : vix.regime === "ELEVATED"
                    ? "text-warning"
                    : "text-loss"
                )}
              >
                {vix.regime}
              </p>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
