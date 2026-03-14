"use client";

import clsx from "clsx";
import { Globe, Tag } from "lucide-react";

interface EventsTabProps {
  events: any[];
}

const severityColor: Record<string, string> = {
  critical: "bg-loss/20 text-loss",
  major: "bg-warning/30 text-warning",
  moderate: "bg-warning/15 text-warning",
  minor: "bg-txt-muted/20 text-txt-muted",
};

function formatTime(ts: string | undefined): string {
  if (!ts) return "";
  try {
    return new Date(ts).toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return ts;
  }
}

export default function EventsTab({ events }: EventsTabProps) {
  if (!events?.length) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-txt-secondary">
        <Globe className="w-12 h-12 mb-4 text-txt-muted" />
        <p className="text-lg">No events recorded yet</p>
        <p className="text-sm text-txt-muted mt-1">
          World events affecting the portfolio will appear here
        </p>
      </div>
    );
  }

  const sorted = [...events].sort((a, b) => {
    const ta = a?.timestamp ?? a?.created_at ?? "";
    const tb = b?.timestamp ?? b?.created_at ?? "";
    return new Date(tb).getTime() - new Date(ta).getTime();
  });

  return (
    <div className="space-y-4">
      <h2 className="text-sm font-semibold text-txt-secondary uppercase tracking-wider">
        World Events
      </h2>
      <div className="space-y-3">
        {sorted.map((event: any, i: number) => {
          const severity = (
            event?.severity ?? event?.level ?? "minor"
          ).toLowerCase();
          const tickers = event?.affected_tickers ?? event?.tickers ?? [];

          return (
            <div
              key={event?.id ?? i}
              className="bg-bg-surface border border-txt-muted/10 rounded-xl p-4 space-y-2"
            >
              <div className="flex items-start justify-between gap-3">
                <p className="text-sm font-medium text-txt flex-1">
                  {event?.headline ?? event?.title ?? "Untitled event"}
                </p>
                <span
                  className={clsx(
                    "text-[10px] px-2 py-0.5 rounded-full font-semibold uppercase flex-shrink-0",
                    severityColor[severity] || "bg-bg-elevated text-txt-muted"
                  )}
                >
                  {severity}
                </span>
              </div>
              <div className="flex flex-wrap items-center gap-2 text-xs text-txt-muted">
                {event?.source && <span>{event.source}</span>}
                {(event?.timestamp || event?.created_at) && (
                  <span>
                    {formatTime(event.timestamp ?? event.created_at)}
                  </span>
                )}
              </div>
              {tickers.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {(Array.isArray(tickers) ? tickers : [tickers]).map(
                    (t: string, j: number) => (
                      <span
                        key={j}
                        className="text-[10px] px-2 py-0.5 rounded bg-bg-elevated text-txt-secondary flex items-center gap-1"
                      >
                        <Tag className="w-2.5 h-2.5" />
                        {t}
                      </span>
                    )
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
