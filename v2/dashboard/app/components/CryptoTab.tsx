"use client";

import clsx from "clsx";
import { Bitcoin, TrendingUp, TrendingDown } from "lucide-react";

interface CryptoTabProps {
  data: any;
}

const COINS = ["ripple", "bitcoin", "stellar", "cardano", "hedera-hashgraph"];
const SYMBOL_MAP: Record<string, string> = {
  ripple: "XRP",
  bitcoin: "BTC",
  stellar: "XLM",
  cardano: "ADA",
  "hedera-hashgraph": "HBAR",
};

export default function CryptoTab({ data }: CryptoTabProps) {
  const crypto = data?.crypto;
  const fearGreed = data?.crypto_fear_greed ?? data?.fear_greed;

  const xrp = crypto?.ripple ?? crypto?.XRP;

  return (
    <div className="space-y-8">
      {/* Fear & Greed */}
      {fearGreed != null && (
        <section className="bg-bg-surface border border-txt-muted/10 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-txt-secondary uppercase tracking-wider mb-3">
            Crypto Fear &amp; Greed Index
          </h2>
          <div className="flex items-center gap-4">
            <span
              className={clsx(
                "text-4xl font-bold",
                typeof fearGreed === "number"
                  ? fearGreed <= 25
                    ? "text-loss"
                    : fearGreed <= 50
                    ? "text-warning"
                    : fearGreed <= 75
                    ? "text-txt"
                    : "text-profit"
                  : "text-txt-muted"
              )}
            >
              {typeof fearGreed === "object"
                ? fearGreed?.value ?? "—"
                : fearGreed}
            </span>
            <div className="flex-1 h-3 bg-bg-elevated rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all bg-gradient-to-r from-loss via-warning to-profit"
                style={{
                  width: `${Math.min(
                    typeof fearGreed === "number"
                      ? fearGreed
                      : fearGreed?.value ?? 50,
                    100
                  )}%`,
                }}
              />
            </div>
          </div>
        </section>
      )}

      {/* XRP Featured */}
      {xrp && (
        <section className="bg-bg-surface border border-info/20 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-info uppercase tracking-wider mb-3">
            Featured — XRP (Largest Holding)
          </h2>
          <div className="flex flex-wrap items-end gap-6">
            <div>
              <p className="text-3xl font-bold text-txt">
                ${xrp.price?.toFixed(4) ?? "—"}
              </p>
              {xrp.change_24h_pct != null && (
                <p
                  className={clsx(
                    "text-sm font-medium flex items-center gap-1 mt-1",
                    xrp.change_24h_pct >= 0 ? "text-profit" : "text-loss"
                  )}
                >
                  {xrp.change_24h_pct >= 0 ? (
                    <TrendingUp className="w-4 h-4" />
                  ) : (
                    <TrendingDown className="w-4 h-4" />
                  )}
                  {xrp.change_24h_pct >= 0 ? "+" : ""}
                  {xrp.change_24h_pct.toFixed(2)}% (24h)
                </p>
              )}
            </div>
            {xrp.baseline != null && (
              <div className="text-sm space-y-1">
                <p className="text-txt-secondary">
                  Baseline: ${xrp.baseline.toFixed(4)}
                </p>
                {xrp.price != null && (
                  <p
                    className={clsx(
                      "font-medium",
                      xrp.price >= xrp.baseline ? "text-profit" : "text-loss"
                    )}
                  >
                    {(
                      ((xrp.price - xrp.baseline) / xrp.baseline) *
                      100
                    ).toFixed(2)}
                    % from baseline
                  </p>
                )}
              </div>
            )}
          </div>
        </section>
      )}

      {/* All Coins Grid */}
      <section>
        <h2 className="text-sm font-semibold text-txt-secondary uppercase tracking-wider mb-4">
          All Coins
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {COINS.map((coinId) => {
            const coin =
              crypto?.[coinId] ??
              crypto?.[SYMBOL_MAP[coinId]?.toLowerCase()] ??
              crypto?.[SYMBOL_MAP[coinId]];
            if (!coin) {
              return (
                <div
                  key={coinId}
                  className="bg-bg-surface border border-txt-muted/10 rounded-xl p-4"
                >
                  <span className="text-lg font-bold text-txt-muted">
                    {SYMBOL_MAP[coinId] || coinId}
                  </span>
                  <p className="text-xs text-txt-muted mt-1">No data</p>
                </div>
              );
            }

            const symbol = coin.symbol ?? SYMBOL_MAP[coinId] ?? coinId;
            const change24 = coin.change_24h_pct;
            const baseline = coin.baseline;
            const price = coin.price;
            const baselineChange =
              price != null && baseline
                ? ((price - baseline) / baseline) * 100
                : null;

            return (
              <div
                key={coinId}
                className="bg-bg-surface border border-txt-muted/10 rounded-xl p-4 space-y-2"
              >
                <div className="flex items-center justify-between">
                  <span className="text-lg font-bold text-txt">{symbol}</span>
                  <Bitcoin className="w-4 h-4 text-txt-muted" />
                </div>
                <p className="text-xl font-semibold text-txt">
                  ${price?.toFixed(price < 1 ? 4 : 2) ?? "—"}
                </p>
                <div className="flex justify-between text-sm">
                  <span className="text-txt-secondary">24h</span>
                  {change24 != null ? (
                    <span
                      className={clsx(
                        "font-medium",
                        change24 >= 0 ? "text-profit" : "text-loss"
                      )}
                    >
                      {change24 >= 0 ? "+" : ""}
                      {change24.toFixed(2)}%
                    </span>
                  ) : (
                    <span className="text-txt-muted">—</span>
                  )}
                </div>
                {baseline != null && (
                  <>
                    <div className="flex justify-between text-sm">
                      <span className="text-txt-secondary">Baseline</span>
                      <span className="text-txt-muted">
                        ${baseline.toFixed(baseline < 1 ? 4 : 2)}
                      </span>
                    </div>
                    {baselineChange != null && (
                      <div className="flex justify-between text-sm">
                        <span className="text-txt-secondary">vs Baseline</span>
                        <span
                          className={clsx(
                            "font-medium",
                            baselineChange >= 0 ? "text-profit" : "text-loss"
                          )}
                        >
                          {baselineChange >= 0 ? "+" : ""}
                          {baselineChange.toFixed(2)}%
                        </span>
                      </div>
                    )}
                  </>
                )}
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
