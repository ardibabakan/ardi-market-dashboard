"""
Options Flow Agent — Layer 2 Analysis
Ardi Market Command Center v2

Reads options chain data from yfinance for portfolio tickers.
Calculates put/call ratio and flags unusual activity.
Gracefully skips tickers with no options data.
"""
import json, logging, sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import PLANNED_POSITIONS, AGENT_OUTPUT_DIR
from lib.supabase_client import insert
from lib.safe_scalar import safe_scalar

import time

logger = logging.getLogger("ardi.layer2.options_flow")

PORTFOLIO_TICKERS = list(PLANNED_POSITIONS.keys())


def _get_options_data(ticker_symbol):
    """Fetch options chain from yfinance. Returns None on failure."""
    try:
        import yfinance as yf
        tk = yf.Ticker(ticker_symbol)
        expirations = tk.options
        if not expirations:
            logger.info(f"No options expirations for {ticker_symbol}")
            return None

        # Use nearest expiration
        nearest_exp = expirations[0]
        chain = tk.option_chain(nearest_exp)
        return {
            "expiration": nearest_exp,
            "calls": chain.calls,
            "puts": chain.puts,
        }
    except Exception as e:
        logger.warning(f"Options fetch failed for {ticker_symbol}: {e}")
        return None


def _analyze_options(ticker, chain_data):
    """Analyze options chain for sentiment signals."""
    calls_df = chain_data["calls"]
    puts_df = chain_data["puts"]

    total_call_vol = safe_scalar(calls_df["volume"].sum()) if "volume" in calls_df.columns else 0
    total_put_vol = safe_scalar(puts_df["volume"].sum()) if "volume" in puts_df.columns else 0
    total_call_oi = safe_scalar(calls_df["openInterest"].sum()) if "openInterest" in calls_df.columns else 0
    total_put_oi = safe_scalar(puts_df["openInterest"].sum()) if "openInterest" in puts_df.columns else 0

    # Put/Call ratio
    pc_ratio_vol = round(total_put_vol / total_call_vol, 3) if total_call_vol > 0 else None
    pc_ratio_oi = round(total_put_oi / total_call_oi, 3) if total_call_oi > 0 else None

    # Sentiment interpretation
    sentiment = "NEUTRAL"
    if pc_ratio_vol is not None:
        if pc_ratio_vol > 1.5:
            sentiment = "VERY_BEARISH"
        elif pc_ratio_vol > 1.0:
            sentiment = "BEARISH"
        elif pc_ratio_vol < 0.5:
            sentiment = "VERY_BULLISH"
        elif pc_ratio_vol < 0.7:
            sentiment = "BULLISH"

    # Flag unusual volume (any single strike with vol > 5x OI)
    unusual_calls = []
    unusual_puts = []

    if "volume" in calls_df.columns and "openInterest" in calls_df.columns:
        for _, row in calls_df.iterrows():
            vol = safe_scalar(row.get("volume", 0))
            oi = safe_scalar(row.get("openInterest", 1))
            if oi > 0 and vol > 5 * oi and vol > 100:
                unusual_calls.append({
                    "strike": safe_scalar(row.get("strike")),
                    "volume": int(vol),
                    "open_interest": int(oi),
                    "ratio": round(vol / oi, 1),
                })

    if "volume" in puts_df.columns and "openInterest" in puts_df.columns:
        for _, row in puts_df.iterrows():
            vol = safe_scalar(row.get("volume", 0))
            oi = safe_scalar(row.get("openInterest", 1))
            if oi > 0 and vol > 5 * oi and vol > 100:
                unusual_puts.append({
                    "strike": safe_scalar(row.get("strike")),
                    "volume": int(vol),
                    "open_interest": int(oi),
                    "ratio": round(vol / oi, 1),
                })

    has_unusual = len(unusual_calls) > 0 or len(unusual_puts) > 0

    return {
        "ticker": ticker,
        "expiration": chain_data["expiration"],
        "total_call_volume": int(total_call_vol),
        "total_put_volume": int(total_put_vol),
        "total_call_oi": int(total_call_oi),
        "total_put_oi": int(total_put_oi),
        "pc_ratio_volume": pc_ratio_vol,
        "pc_ratio_oi": pc_ratio_oi,
        "sentiment": sentiment,
        "unusual_activity": has_unusual,
        "unusual_calls": unusual_calls[:5],
        "unusual_puts": unusual_puts[:5],
    }


def run():
    """Main entry point."""
    logger.info("Options Flow Agent starting...")

    results = {}
    records_written = 0

    for ticker in PORTFOLIO_TICKERS:
        time.sleep(0.5)  # rate limit
        chain = _get_options_data(ticker)
        if chain is None:
            logger.info(f"Skipping {ticker} — no options data")
            continue

        try:
            analysis = _analyze_options(ticker, chain)
            results[ticker] = analysis

            severity = "info"
            if analysis["unusual_activity"]:
                severity = "warning"
            if analysis["sentiment"] in ("VERY_BEARISH", "VERY_BULLISH"):
                severity = "warning"

            insert("events", {
                "event_type": "options_flow",
                "ticker": ticker,
                "summary": json.dumps(analysis),
                "severity": severity,
            })
            records_written += 1
        except Exception as e:
            logger.warning(f"Options analysis failed for {ticker}: {e}")

    # Write local JSON
    output_path = AGENT_OUTPUT_DIR / "options_flow_agent_output.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info(f"Options Flow Agent complete. {records_written} tickers analyzed.")
    return {"status": "ok", "records": records_written, "data": results}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
