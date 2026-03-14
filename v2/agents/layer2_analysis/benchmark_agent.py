"""
Agent 19: Benchmark Agent
Reads yahoo_agent_output.json for SPY data.
Reads cached price history for SPY and portfolio tickers.
Calculates SPY return since conflict start.
During paper trading, estimates portfolio return based on planned positions.
Writes to daily_reports Supabase table.
"""
import json, logging, sys
from pathlib import Path
from datetime import datetime, timezone, date

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import *
from lib.supabase_client import insert, select, upsert, get_client
from lib.safe_scalar import safe_scalar

logger = logging.getLogger("ardi.benchmark")

YAHOO_OUTPUT = AGENT_OUTPUT_DIR / "yahoo_agent_output.json"
LOCAL_OUTPUT = AGENT_OUTPUT_DIR / "benchmark_output.json"


def _load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load {path}: {e}")
        return {}


def _load_cache(ticker):
    """Load cached price history JSON for a ticker."""
    cache_path = CACHE_DIR / f"{ticker}_hist.json"
    if not cache_path.exists():
        return None
    try:
        with open(cache_path) as f:
            raw = json.load(f)
        if not raw:
            return None
        return raw  # list of dicts with date, close, etc.
    except Exception as e:
        logger.warning(f"Could not load cache for {ticker}: {e}")
        return None


def _get_return_from_cache(ticker, start_date_str):
    """Get return from cached data since start_date. Returns (start_price, end_price) or (None, None)."""
    data = _load_cache(ticker)
    if not data:
        return None, None
    try:
        start_date = date.fromisoformat(start_date_str)
        # Filter records on or after start_date
        filtered = [r for r in data if r.get("date", "") >= start_date_str]
        if not filtered:
            return None, None
        start_price = safe_scalar(filtered[0].get("close"), None)
        end_price = safe_scalar(filtered[-1].get("close"), None)
        return start_price, end_price
    except Exception as e:
        logger.warning(f"Could not compute return for {ticker}: {e}")
        return None, None


def _conflict_day():
    try:
        start = date.fromisoformat(CONFLICT_START_DATE)
        today = date.fromisoformat("2026-03-14")
        return (today - start).days
    except Exception:
        return 0


def run():
    logger.info("Benchmark Agent starting")
    now = datetime.now(timezone.utc).isoformat()
    day = _conflict_day()

    yahoo_data = _load_json(YAHOO_OUTPUT)

    # --- SPY return since conflict start ---
    spy_start_price = None
    spy_current_price = None
    spy_change_pct = None

    spy_start_price, spy_current_price = _get_return_from_cache("SPY", CONFLICT_START_DATE)

    # Fallback to yahoo output for current price
    if spy_current_price is None:
        spy_entry = yahoo_data.get("SPY", {})
        spy_current_price = safe_scalar(
            spy_entry.get("price") or spy_entry.get("current_price") or spy_entry.get("close"), None
        )

    if spy_start_price and spy_current_price and spy_start_price > 0:
        spy_change_pct = round(((spy_current_price - spy_start_price) / spy_start_price) * 100, 2)

    # --- Portfolio return estimate (paper trading) ---
    portfolio_tickers = list(PLANNED_POSITIONS.keys())
    num_positions = len(portfolio_tickers)
    budget_per = PORTFOLIO_BUDGET / num_positions if num_positions > 0 else 0

    ticker_returns = []
    for ticker in portfolio_tickers:
        try:
            start_p, end_p = _get_return_from_cache(ticker, CONFLICT_START_DATE)
            if start_p and end_p and start_p > 0:
                ret = ((end_p - start_p) / start_p) * 100
                ticker_returns.append({
                    "ticker": ticker,
                    "start_price": round(start_p, 2),
                    "current_price": round(end_p, 2),
                    "return_pct": round(ret, 2),
                })
        except Exception as e:
            logger.warning(f"Could not get history for {ticker}: {e}")

    # Equal-weight portfolio return
    portfolio_change_pct = None
    if ticker_returns:
        avg_return = sum(t["return_pct"] for t in ticker_returns) / len(ticker_returns)
        portfolio_change_pct = round(avg_return, 2)

    # Alpha
    outperformance_pct = None
    if portfolio_change_pct is not None and spy_change_pct is not None:
        outperformance_pct = round(portfolio_change_pct - spy_change_pct, 2)

    # Summary line
    summary = ""
    if portfolio_change_pct is not None and spy_change_pct is not None:
        sign = "+" if outperformance_pct >= 0 else ""
        p_sign = "+" if portfolio_change_pct >= 0 else ""
        s_sign = "+" if spy_change_pct >= 0 else ""
        summary = f"Portfolio: {p_sign}{portfolio_change_pct}%. SPY: {s_sign}{spy_change_pct}%. Alpha: {sign}{outperformance_pct}%"
    elif spy_change_pct is not None:
        s_sign = "+" if spy_change_pct >= 0 else ""
        summary = f"SPY: {s_sign}{spy_change_pct}%. Portfolio: insufficient data."

    result = {
        "agent": "benchmark",
        "timestamp": now,
        "conflict_day": day,
        "conflict_start": CONFLICT_START_DATE,
        "paper_trading": True,
        "spy": {
            "start_price": spy_start_price,
            "current_price": spy_current_price,
            "change_pct": spy_change_pct,
        },
        "portfolio": {
            "change_pct": portfolio_change_pct,
            "ticker_returns": ticker_returns,
        },
        "outperformance_pct": outperformance_pct,
        "summary": summary,
    }

    # Write local output
    try:
        LOCAL_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        with open(LOCAL_OUTPUT, "w") as f:
            json.dump(result, f, indent=2)
        logger.info(f"Wrote {LOCAL_OUTPUT}")
    except Exception as e:
        logger.error(f"Failed to write local output: {e}")

    # Write to Supabase daily_reports table (valid columns only)
    try:
        row = {
            "report_date": now[:10],
            "spy_change_pct": spy_change_pct,
            "portfolio_change_pct": portfolio_change_pct,
            "outperformance_pct": outperformance_pct,
            "conflict_day": day,
            "action_today": summary,
        }
        # Use upsert-like approach: try insert, on duplicate update
        try:
            client = get_client()
            client.table("daily_reports").upsert(row, on_conflict="report_date").execute()
        except Exception:
            insert("daily_reports", row)
        logger.info("Wrote benchmark to Supabase daily_reports")
    except Exception as e:
        logger.error(f"Supabase write failed: {e}")

    logger.info(f"Benchmark Agent complete: {summary}")
    result["status"] = "ok"
    result["records"] = result.get("records", 0)
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
