"""
Correlation Agent — Layer 2 Analysis
Ardi Market Command Center v2

Calculates 30-day pairwise correlations between portfolio tickers.
Flags significant changes from 90-day average. Tracks ITA overlap
with LMT and RTX.
"""
import json, logging, sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import PLANNED_POSITIONS, CACHE_DIR, AGENT_OUTPUT_DIR
from lib.supabase_client import insert
from lib.safe_scalar import safe_scalar

import pandas as pd
import numpy as np

logger = logging.getLogger("ardi.layer2.correlation")

PORTFOLIO_TICKERS = list(PLANNED_POSITIONS.keys())
CHANGE_THRESHOLD = 0.3  # flag changes > 0.3 from 90-day avg


def _load_closes():
    """Load close prices for all portfolio tickers into a DataFrame."""
    frames = {}
    for ticker in PORTFOLIO_TICKERS:
        path = CACHE_DIR / f"{ticker}_hist.json"
        if not path.exists():
            logger.warning(f"No cached history for {ticker}")
            continue
        try:
            with open(path) as f:
                raw = json.load(f)
            df = pd.DataFrame(raw)
            # Normalize columns
            df.columns = [c.lower() for c in df.columns]
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])
                df = df.set_index("date")
            else:
                df.index = pd.to_datetime(df.index)
            df = df.sort_index()
            if "close" in df.columns:
                frames[ticker] = df["close"]
        except Exception as e:
            logger.warning(f"Failed to load {ticker}: {e}")
    if not frames:
        return None
    return pd.DataFrame(frames).dropna()


def run():
    """Main entry point."""
    logger.info("Correlation Agent starting...")

    prices = _load_closes()
    if prices is None or len(prices) < 30:
        return {"status": "error", "reason": "insufficient price data"}

    results = []
    records_written = 0
    tickers = list(prices.columns)

    # Compute return correlations
    returns = prices.pct_change().dropna()
    corr_30d = returns.tail(30).corr() if len(returns) >= 30 else returns.corr()
    corr_90d = returns.tail(90).corr() if len(returns) >= 90 else returns.corr()

    for i in range(len(tickers)):
        for j in range(i + 1, len(tickers)):
            ta, tb = tickers[i], tickers[j]
            c30 = safe_scalar(corr_30d.loc[ta, tb]) if ta in corr_30d.index and tb in corr_30d.columns else None
            c90 = safe_scalar(corr_90d.loc[ta, tb]) if ta in corr_90d.index and tb in corr_90d.columns else None

            if c30 is None:
                continue

            change = round(abs(c30 - c90), 4) if c90 is not None else 0.0
            alert = change >= CHANGE_THRESHOLD

            # Special flag for ITA overlap
            pair_set = {ta, tb}
            ita_note = ""
            if "ITA" in pair_set and ("LMT" in pair_set or "RTX" in pair_set):
                other = (pair_set - {"ITA"}).pop()
                if c30 and c30 > 0.85:
                    ita_note = f"HIGH OVERLAP: ITA/{other} corr {c30:.2f} — consider reducing ITA"
                    alert = True

            entry = {
                "ticker_a": ta,
                "ticker_b": tb,
                "correlation_30d": round(c30, 4),
                "correlation_90d": round(c90, 4) if c90 is not None else None,
                "change_from_normal": round(change, 4),
                "alert": alert,
            }
            if ita_note:
                entry["note"] = ita_note

            results.append(entry)
            insert("correlations", {
                "ticker_a": ta,
                "ticker_b": tb,
                "correlation_30d": entry["correlation_30d"],
                "correlation_90d": entry["correlation_90d"],
                "change_from_normal": entry["change_from_normal"],
                "alert": alert,
            })
            records_written += 1

    # Write local JSON
    output_path = AGENT_OUTPUT_DIR / "correlation_agent_output.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    alerts = [r for r in results if r.get("alert")]
    logger.info(f"Correlation Agent complete. {records_written} pairs, {len(alerts)} alerts.")
    return {"status": "ok", "records": records_written, "alerts": len(alerts), "data": results}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
