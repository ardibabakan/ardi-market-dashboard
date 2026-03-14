"""
Relative Strength Agent — Layer 2 Analysis
Ardi Market Command Center v2

Ranks tickers from ALL_TICKERS by 1-week and 1-month relative
strength vs SPY. Writes top 20 and bottom 20 to Supabase events.
"""
import json, logging, sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import ALL_TICKERS, CACHE_DIR, AGENT_OUTPUT_DIR
from lib.supabase_client import insert
from lib.safe_scalar import safe_scalar
from lib.rate_limiter import rate_limited_download

import pandas as pd
import numpy as np

logger = logging.getLogger("ardi.layer2.relative_strength")

MAX_TICKERS = 30  # limit to avoid API throttling


def _load_cached_close(ticker):
    """Load cached close prices for a ticker."""
    path = CACHE_DIR / f"{ticker}_hist.json"
    if not path.exists():
        return None
    try:
        with open(path) as f:
            raw = json.load(f)
        df = pd.DataFrame(raw)
        df.columns = [c.lower() for c in df.columns]
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")
        else:
            df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        return df["close"] if "close" in df.columns else None
    except Exception:
        return None


def _calc_return(series, days):
    """Calculate return over last N trading days."""
    if series is None or len(series) < days + 1:
        return None
    current = safe_scalar(series.iloc[-1])
    past = safe_scalar(series.iloc[-(days + 1)])
    if past == 0:
        return None
    return (current - past) / past


def run():
    """Main entry point."""
    logger.info("Relative Strength Agent starting...")

    # Get SPY benchmark returns
    spy_data = rate_limited_download("SPY", period="3mo")
    if spy_data is None or spy_data.empty:
        return {"status": "error", "reason": "could not download SPY data"}

    spy_data.columns = [c[0].lower() if isinstance(c, tuple) else c.lower() for c in spy_data.columns]
    spy_close = spy_data["close"]
    spy_1w = _calc_return(spy_close, 5)
    spy_1m = _calc_return(spy_close, 21)

    if spy_1w is None or spy_1m is None:
        return {"status": "error", "reason": "insufficient SPY data"}

    tickers_to_scan = ALL_TICKERS[:MAX_TICKERS]
    rankings = []

    for ticker in tickers_to_scan:
        close = _load_cached_close(ticker)
        if close is None:
            continue

        ret_1w = _calc_return(close, 5)
        ret_1m = _calc_return(close, 21)

        if ret_1w is None or ret_1m is None:
            continue

        rs_1w = ret_1w - spy_1w
        rs_1m = ret_1m - spy_1m
        # Combined score: weight 1-month more heavily
        rs_combined = rs_1w * 0.4 + rs_1m * 0.6

        rankings.append({
            "ticker": ticker,
            "return_1w": round(ret_1w * 100, 2),
            "return_1m": round(ret_1m * 100, 2),
            "rs_vs_spy_1w": round(rs_1w * 100, 2),
            "rs_vs_spy_1m": round(rs_1m * 100, 2),
            "rs_combined": round(rs_combined * 100, 2),
        })

    # Sort by combined RS score
    rankings.sort(key=lambda x: x["rs_combined"], reverse=True)

    top_20 = rankings[:20]
    bottom_20 = rankings[-20:] if len(rankings) >= 20 else rankings

    # Write to Supabase events
    insert("events", {
        "event_type": "relative_strength_leaders",
        "ticker": None,
        "summary": json.dumps(top_20),
        "severity": "info",
    })

    insert("events", {
        "event_type": "relative_strength_laggards",
        "ticker": None,
        "summary": json.dumps(bottom_20),
        "severity": "info",
    })

    result_data = {
        "spy_return_1w": round(spy_1w * 100, 2),
        "spy_return_1m": round(spy_1m * 100, 2),
        "tickers_analyzed": len(rankings),
        "top_20": top_20,
        "bottom_20": bottom_20,
    }

    # Write local JSON
    output_path = AGENT_OUTPUT_DIR / "relative_strength_agent_output.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(result_data, f, indent=2, default=str)

    logger.info(f"Relative Strength Agent complete. {len(rankings)} tickers ranked.")
    return {"status": "ok", "tickers_ranked": len(rankings), "data": result_data}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
