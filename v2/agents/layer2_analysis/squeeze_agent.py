"""
Agent 15: Squeeze Agent
Reads yahoo_agent_output.json. For portfolio + Phase B tickers,
tries to get short interest from yfinance.
If days to cover > 5: SQUEEZE POTENTIAL. Skips gracefully if data unavailable.
Writes to events Supabase table.
"""
import json, logging, sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import *
from lib.supabase_client import insert
from lib.safe_scalar import safe_scalar

logger = logging.getLogger("ardi.squeeze")

YAHOO_OUTPUT = AGENT_OUTPUT_DIR / "yahoo_agent_output.json"
LOCAL_OUTPUT = AGENT_OUTPUT_DIR / "squeeze_output.json"


def _load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load {path}: {e}")
        return {}


def _get_short_interest(ticker):
    """Try to get short interest data from yfinance. Returns dict or None."""
    try:
        import yfinance as yf
        import time
        time.sleep(0.5)  # rate limiting
        stock = yf.Ticker(ticker)
        info = stock.info or {}

        short_pct = safe_scalar(info.get("shortPercentOfFloat"), None)
        short_ratio = safe_scalar(info.get("shortRatio"), None)  # days to cover
        shares_short = safe_scalar(info.get("sharesShort"), None)
        avg_volume = safe_scalar(info.get("averageVolume"), None)

        if short_ratio is None and shares_short and avg_volume and avg_volume > 0:
            short_ratio = round(shares_short / avg_volume, 2)

        return {
            "short_pct_float": short_pct,
            "days_to_cover": short_ratio,
            "shares_short": shares_short,
            "avg_volume": avg_volume,
        }
    except Exception as e:
        logger.debug(f"Could not get short interest for {ticker}: {e}")
        return None


def run():
    logger.info("Squeeze Agent starting")
    now = datetime.now(timezone.utc).isoformat()

    yahoo_data = _load_json(YAHOO_OUTPUT)

    # Tickers to check: portfolio + Phase B
    try:
        tickers = list(PLANNED_POSITIONS.keys()) + list(PHASE_B_POSITIONS.keys())
        tickers = sorted(set(tickers))
    except Exception:
        tickers = []

    squeeze_candidates = []
    checked = []

    for ticker in tickers:
        logger.info(f"Checking short interest for {ticker}")
        si = _get_short_interest(ticker)

        if si is None:
            checked.append({"ticker": ticker, "status": "data_unavailable"})
            continue

        days_to_cover = si.get("days_to_cover")
        short_pct = si.get("short_pct_float")

        entry = {
            "ticker": ticker,
            "days_to_cover": days_to_cover,
            "short_pct_float": short_pct,
            "shares_short": si.get("shares_short"),
            "squeeze_potential": False,
        }

        if days_to_cover is not None and days_to_cover > 5:
            entry["squeeze_potential"] = True
            entry["alert"] = f"SQUEEZE POTENTIAL: {ticker} has {days_to_cover:.1f} days to cover"
            squeeze_candidates.append(entry)
            logger.warning(f"SQUEEZE POTENTIAL: {ticker} days_to_cover={days_to_cover:.1f}")
        elif short_pct is not None and short_pct > 20:
            entry["squeeze_potential"] = True
            entry["alert"] = f"HIGH SHORT INTEREST: {ticker} at {short_pct:.1f}% of float"
            squeeze_candidates.append(entry)
            logger.warning(f"HIGH SHORT INTEREST: {ticker} short_pct={short_pct:.1f}%")

        checked.append(entry)

    result = {
        "agent": "squeeze",
        "timestamp": now,
        "tickers_checked": len(tickers),
        "squeeze_candidates": len(squeeze_candidates),
        "candidates": squeeze_candidates,
        "all_checked": checked,
    }

    # Write local output
    try:
        LOCAL_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        with open(LOCAL_OUTPUT, "w") as f:
            json.dump(result, f, indent=2)
        logger.info(f"Wrote {LOCAL_OUTPUT}")
    except Exception as e:
        logger.error(f"Failed to write local output: {e}")

    # Write squeeze candidates to Supabase events table (valid columns only)
    for candidate in squeeze_candidates:
        try:
            row = {
                "event_type": "squeeze_alert",
                "headline": candidate.get("alert", f"Squeeze potential: {candidate['ticker']}"),
                "summary": json.dumps(candidate),
                "affected_tickers": candidate["ticker"],
                "severity": "high",
            }
            insert("events", row)
        except Exception as e:
            logger.error(f"Supabase write failed for {candidate['ticker']}: {e}")

    logger.info(f"Squeeze Agent complete: {len(squeeze_candidates)} candidates")
    result["status"] = "ok"
    result["records"] = result.get("records", 0)
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
