"""
Profit Target Agent — Layer 3 Signals
Ardi Market Command Center v2

Reads positions. Checks if current price >= entry_price * (1 + PROFIT_TARGET_PCT).
If hit, sends opportunity alert.
"""
import json, logging, sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import *
from lib.supabase_client import insert, select
from lib.ntfy_client import send_opportunity_alert, send_alert
from lib.safe_scalar import safe_scalar

logger = logging.getLogger("ardi.layer3.profit_target")


def _load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load {path}: {e}")
        return {}


def _get_current_price(ticker):
    """Get current price from yahoo agent output or price_snapshots."""
    yahoo = _load_json(AGENT_OUTPUT_DIR / "yahoo_agent_output.json")
    ticker_data = yahoo.get(ticker, {})
    price = safe_scalar(
        ticker_data.get("price") or ticker_data.get("regularMarketPrice"), None
    )
    if price and price > 0:
        return price

    rows = select("price_snapshots", {"ticker": ticker}, order_by="-created_at", limit=1)
    if rows:
        p = safe_scalar(rows[0].get("price"), None)
        if p and p > 0:
            return p

    return None


def run():
    logger.info("Profit target agent starting...")
    now_str = datetime.now(timezone.utc).isoformat()
    results = {"timestamp": now_str, "checks": []}
    records_written = 0
    alerts_sent = 0

    # Get open and planned positions
    positions = []
    for status in ("open", "planned"):
        rows = select("positions", {"status": status})
        if rows:
            positions.extend(rows)

    for pos in positions:
        ticker = pos.get("ticker")
        if not ticker:
            continue

        entry_price = safe_scalar(pos.get("entry_price"), None)
        profit_target_override = safe_scalar(pos.get("profit_target"), None)

        if not entry_price or entry_price <= 0:
            results["checks"].append({
                "ticker": ticker,
                "status": "skipped",
                "reason": "no entry price set",
            })
            continue

        current_price = _get_current_price(ticker)
        if current_price is None:
            results["checks"].append({
                "ticker": ticker,
                "status": "skipped",
                "reason": "could not fetch current price",
            })
            continue

        if profit_target_override and profit_target_override > 0:
            target_level = profit_target_override
        else:
            target_level = entry_price * (1 + PROFIT_TARGET_PCT)

        hit = current_price >= target_level
        pct_from_entry = ((current_price - entry_price) / entry_price) * 100

        check_result = {
            "ticker": ticker,
            "entry_price": entry_price,
            "current_price": current_price,
            "target_level": round(target_level, 2),
            "pct_from_entry": round(pct_from_entry, 2),
            "target_hit": hit,
        }
        results["checks"].append(check_result)

        signal_record = {
            "signal_type": "profit_target",
            "signal_name": f"profit_target_{ticker}",
            "status": "fired" if hit else "not_fired",
            "confidence": 1.0 if hit else 0.0,
            "details": f"{ticker}: ${current_price:.2f} vs target ${target_level:.2f} ({pct_from_entry:+.2f}% from entry)",
            "source": "profit_target_agent",
            "action_required": "consider_selling" if hit else "none",
        }
        insert("signals", signal_record)
        records_written += 1

        if hit:
            send_opportunity_alert(
                ticker=ticker,
                reason=f"PROFIT TARGET HIT: {ticker} at ${current_price:.2f} (+{pct_from_entry:.1f}% from ${entry_price:.2f}). Target was ${target_level:.2f}. Consider taking profits.",
            )
            alerts_sent += 1
            logger.info(f"Profit target hit: {ticker} at ${current_price:.2f} (target: ${target_level:.2f})")

    results["alerts_sent"] = alerts_sent

    # Write local JSON
    output_path = AGENT_OUTPUT_DIR / "profit_target_agent_output.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info(f"Profit target agent done — {alerts_sent} alerts sent, {records_written} records written")
    return {"status": "ok", "records": records_written, "alerts": alerts_sent}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
