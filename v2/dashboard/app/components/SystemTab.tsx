"use client";

import clsx from "clsx";
import { Cpu, CheckCircle, XCircle, Clock, AlertTriangle } from "lucide-react";

interface SystemTabProps {
  agentRuns: any[];
}

const LAYERS: Record<string, string[]> = {
  "Layer 1": ["market_data", "news_scanner", "crypto_prices"],
  "Layer 2": ["technical_analysis", "signal_detector", "fallen_angels"],
  "Layer 3": ["scenario_engine", "risk_calculator"],
  "Layer 4": ["dashboard_compiler", "alert_dispatcher"],
};

function timeSince(ts: string | undefined): string {
  if (!ts) return "";
  const diff = Date.now() - new Date(ts).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export default function SystemTab({ agentRuns }: SystemTabProps) {
  if (!agentRuns?.length) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-txt-secondary">
        <Cpu className="w-12 h-12 mb-4 text-txt-muted" />
        <p className="text-lg">No agent runs recorded yet</p>
        <p className="text-sm text-txt-muted mt-1">
          Agent execution history will appear here after the first pipeline run
        </p>
      </div>
    );
  }

  // Index latest run per agent
  const latestByAgent: Record<string, any> = {};
  agentRuns.forEach((run: any) => {
    const name = run?.agent_name ?? run?.name;
    if (!name) return;
    const existing = latestByAgent[name];
    if (
      !existing ||
      new Date(run?.timestamp ?? run?.created_at ?? 0) >
        new Date(existing?.timestamp ?? existing?.created_at ?? 0)
    ) {
      latestByAgent[name] = run;
    }
  });

  return (
    <div className="space-y-8">
      {/* Agent Health by Layer */}
      {Object.entries(LAYERS).map(([layer, agents]) => (
        <section key={layer}>
          <h2 className="text-sm font-semibold text-txt-secondary uppercase tracking-wider mb-3">
            {layer}
          </h2>
          <div className="bg-bg-surface border border-txt-muted/10 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-txt-muted/10">
                  <th className="text-left text-txt-muted font-medium px-4 py-2">
                    Agent
                  </th>
                  <th className="text-center text-txt-muted font-medium px-4 py-2">
                    Status
                  </th>
                  <th className="text-right text-txt-muted font-medium px-4 py-2 hidden sm:table-cell">
                    Last Run
                  </th>
                  <th className="text-right text-txt-muted font-medium px-4 py-2 hidden md:table-cell">
                    Records
                  </th>
                </tr>
              </thead>
              <tbody>
                {agents.map((agentName) => {
                  const run = latestByAgent[agentName];
                  const isOk =
                    run?.status === "success" ||
                    run?.status === "ok" ||
                    run?.success === true;
                  const ts = run?.timestamp ?? run?.created_at;

                  return (
                    <tr
                      key={agentName}
                      className="border-b border-txt-muted/5 last:border-0"
                    >
                      <td className="px-4 py-3 text-txt font-medium capitalize">
                        {agentName.replace(/_/g, " ")}
                      </td>
                      <td className="px-4 py-3 text-center">
                        {run ? (
                          isOk ? (
                            <CheckCircle className="w-4 h-4 text-profit inline" />
                          ) : (
                            <XCircle className="w-4 h-4 text-loss inline" />
                          )
                        ) : (
                          <span className="text-txt-muted">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right text-txt-secondary hidden sm:table-cell">
                        {ts ? timeSince(ts) : "—"}
                      </td>
                      <td className="px-4 py-3 text-right text-txt-secondary hidden md:table-cell">
                        {run?.records_written ?? run?.records ?? "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      ))}

      {/* Data Freshness */}
      <section className="bg-bg-surface border border-txt-muted/10 rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <Clock className="w-4 h-4 text-info" />
          <h2 className="text-sm font-semibold text-txt-secondary uppercase tracking-wider">
            Data Freshness
          </h2>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {Object.entries(latestByAgent).map(([name, run]: [string, any]) => {
            const ts = run?.timestamp ?? run?.created_at;
            const ageMs = ts ? Date.now() - new Date(ts).getTime() : Infinity;
            const stale = ageMs > 6 * 60 * 60 * 1000;
            return (
              <div
                key={name}
                className="flex items-center justify-between bg-bg-elevated rounded-lg px-3 py-2"
              >
                <span className="text-xs text-txt capitalize">
                  {name.replace(/_/g, " ")}
                </span>
                <span
                  className={clsx(
                    "text-xs font-medium",
                    stale ? "text-warning" : "text-profit"
                  )}
                >
                  {ts ? timeSince(ts) : "N/A"}
                </span>
              </div>
            );
          })}
        </div>
      </section>

      {/* Alert History */}
      <section className="bg-bg-surface border border-txt-muted/10 rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <AlertTriangle className="w-4 h-4 text-warning" />
          <h2 className="text-sm font-semibold text-txt-secondary uppercase tracking-wider">
            Alert History
          </h2>
        </div>
        {agentRuns.filter((r: any) => r?.alerts?.length > 0).length > 0 ? (
          <div className="space-y-2">
            {agentRuns
              .filter((r: any) => r?.alerts?.length > 0)
              .flatMap((r: any) =>
                r.alerts.map((alert: any, i: number) => (
                  <div
                    key={`${r?.agent_name}-${i}`}
                    className="flex items-start gap-2 text-sm"
                  >
                    <AlertTriangle className="w-4 h-4 text-warning flex-shrink-0 mt-0.5" />
                    <span className="text-txt-secondary">
                      {typeof alert === "string" ? alert : alert?.message ?? JSON.stringify(alert)}
                    </span>
                  </div>
                ))
              )}
          </div>
        ) : (
          <p className="text-sm text-txt-muted">No alerts recorded</p>
        )}
      </section>
    </div>
  );
}
