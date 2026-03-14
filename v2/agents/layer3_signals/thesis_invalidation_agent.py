"""
Thesis Invalidation Agent — Layer 3 Signals
Ardi Market Command Center v2

Checks if the core investment thesis is being invalidated:
- Day 30+ with 0 ceasefire signals
- Day 60+ with no resolution
- Oil below $75 without ceasefire
- S&P 500 above pre-Feb 28 level (conflict priced out)
"""
import json, logging, sys
from pathlib import Path
from datetime import datetime, timezone, date, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import *
from lib.supabase_client import insert, select, get_client
from lib.ntfy_client import send_alert
from lib.safe_scalar import safe_scalar

logger = logging.getLogger("ardi.layer3.thesis_invalidation")


def _load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load {path}: {e}")
        return {}


def _conflict_day():
    """Calculate how many days since conflict started."""
    start = date.fromisoformat(CONFLICT_START_DATE)
    today = date.today()
    return (today - start).days


def _count_ceasefire_signals_fired():
    """Count how many ceasefire signals have ever fired."""
    try:
        client = get_client()
        rows = client.table("signals").select("*") \
            .eq("signal_type", "ceasefire") \
            .eq("status", "fired") \
            .execute().data or []
        return len(rows)
    except Exception as e:
        logger.warning(f"Could not count ceasefire signals: {e}")
        return -1  # unknown


def _get_oil_price():
    """Get current oil price."""
    yahoo = _load_json(AGENT_OUTPUT_DIR / "yahoo_agent_output.json")
    oil = yahoo.get("CL=F", {})
    price = safe_scalar(oil.get("price") or oil.get("regularMarketPrice"), None)
    if price and price > 0:
        return price

    rows = select("price_snapshots", {"ticker": "CL=F"}, order_by="-created_at", limit=1)
    if rows:
        return safe_scalar(rows[0].get("price"), None)
    return None


def _get_sp500_price():
    """Get current S&P 500 level."""
    yahoo = _load_json(AGENT_OUTPUT_DIR / "yahoo_agent_output.json")
    sp = yahoo.get("^GSPC", {})
    price = safe_scalar(sp.get("price") or sp.get("regularMarketPrice"), None)
    if price and price > 0:
        return price

    rows = select("price_snapshots", {"ticker": "^GSPC"}, order_by="-created_at", limit=1)
    if rows:
        return safe_scalar(rows[0].get("price"), None)
    return None


def _get_pre_conflict_sp500():
    """Get S&P 500 level from before conflict start date."""
    try:
        client = get_client()
        rows = client.table("market_data").select("*") \
            .eq("symbol", "^GSPC") \
            .lte("created_at", CONFLICT_START_DATE) \
            .order("created_at", desc=True) \
            .limit(1).execute().data or []
        if rows:
            return safe_scalar(rows[0].get("value"), None)
    except Exception as e:
        logger.warning(f"Could not get pre-conflict S&P: {e}")
    return None


def run():
    logger.info("Thesis invalidation agent starting...")
    now_str = datetime.now(timezone.utc).isoformat()
    conflict_days = _conflict_day()
    results = {
        "timestamp": now_str,
        "conflict_day": conflict_days,
        "invalidation_triggers": [],
    }
    records_written = 0
    fired_count = 0

    triggers = []

    # Trigger 1: Day 30+ with 0 ceasefire signals
    ceasefire_count = _count_ceasefire_signals_fired()
    if conflict_days >= 30 and ceasefire_count == 0:
        triggers.append({
            "name": "no_ceasefire_day30",
            "fired": True,
            "details": f"Day {conflict_days} of conflict with 0 ceasefire signals fired. Thesis may be stale.",
        })
        fired_count += 1
    else:
        triggers.append({
            "name": "no_ceasefire_day30",
            "fired": False,
            "details": f"Day {conflict_days}, ceasefire signals fired: {ceasefire_count}",
        })

    # Trigger 2: Day 60+ no resolution
    if conflict_days >= 60:
        triggers.append({
            "name": "no_resolution_day60",
            "fired": True,
            "details": f"Day {conflict_days} — conflict exceeds 60-day window. Extended timeline invalidates quick-resolution thesis.",
        })
        fired_count += 1
    else:
        triggers.append({
            "name": "no_resolution_day60",
            "fired": False,
            "details": f"Day {conflict_days} — within 60-day window",
        })

    # Trigger 3: Oil below $75 without ceasefire
    oil_price = _get_oil_price()
    if oil_price is not None and oil_price < 75.0 and ceasefire_count == 0:
        triggers.append({
            "name": "oil_below_75_no_ceasefire",
            "fired": True,
            "details": f"Oil at ${oil_price:.2f} (below $75) with no ceasefire signals. Market may be pricing out conflict premium.",
        })
        fired_count += 1
    else:
        triggers.append({
            "name": "oil_below_75_no_ceasefire",
            "fired": False,
            "details": f"Oil: ${oil_price:.2f}" if oil_price else "Oil price unavailable",
        })

    # Trigger 4: S&P 500 above pre-Feb 28 level
    sp_current = _get_sp500_price()
    sp_pre = _get_pre_conflict_sp500()
    if sp_current and sp_pre and sp_current > sp_pre:
        triggers.append({
            "name": "sp500_above_pre_conflict",
            "fired": True,
            "details": f"S&P 500 at {sp_current:.0f} above pre-conflict level of {sp_pre:.0f}. Conflict may be fully priced in.",
        })
        fired_count += 1
    else:
        detail = f"S&P current: {sp_current:.0f}" if sp_current else "S&P price unavailable"
        if sp_pre:
            detail += f", pre-conflict: {sp_pre:.0f}"
        triggers.append({
            "name": "sp500_above_pre_conflict",
            "fired": False,
            "details": detail,
        })

    results["invalidation_triggers"] = triggers
    results["fired_count"] = fired_count

    # Write each trigger to signals table
    for trigger in triggers:
        signal_record = {
            "signal_type": "thesis_invalidation",
            "signal_name": trigger["name"],
            "status": "fired" if trigger["fired"] else "not_fired",
            "confidence": 0.7 if trigger["fired"] else 0.0,
            "details": trigger["details"],
            "source": "thesis_invalidation_agent",
            "action_required": "review_thesis" if trigger["fired"] else "none",
        }
        insert("signals", signal_record)
        records_written += 1

    # Alert if any invalidation triggers fire
    if fired_count > 0:
        fired_names = [t["name"] for t in triggers if t["fired"]]
        send_alert(
            title=f"THESIS CHECK: {fired_count} invalidation trigger(s)",
            message="\n".join(f"- {t['details']}" for t in triggers if t["fired"]),
            priority="high",
            tags=["warning"],
        )

    # Write local JSON
    output_path = AGENT_OUTPUT_DIR / "thesis_invalidation_agent_output.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info(f"Thesis invalidation agent done — {fired_count} triggers fired, {records_written} records written")
    return {"status": "ok", "records": records_written, "fired": fired_count}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
