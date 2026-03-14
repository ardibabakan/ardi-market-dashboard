"""
Ceasefire Signal Agent — Layer 3 Signals
Ardi Market Command Center v2

Checks 6 ceasefire signals:
1. Oil drops 3%+ in one day
2. VIX below 20
3. VIX backwardation (VIX > VIX3M)
4. Iranian FM peace language (events, two-source)
5. Mediator announces talks (events, two-source)
6. Trump ceasefire statement (events, two-source)

If 2+ signals fire, sends ceasefire alert.
"""
import json, logging, sys
from pathlib import Path
from datetime import datetime, timezone, date, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import *
from lib.supabase_client import insert, select, get_client
from lib.ntfy_client import send_ceasefire_alert, send_alert
from lib.safe_scalar import safe_scalar

logger = logging.getLogger("ardi.layer3.ceasefire_signal")


def _load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load {path}: {e}")
        return {}


def _check_oil_drop():
    """Signal 1: Oil drops 3%+ in one day."""
    # Try yahoo agent output first
    yahoo = _load_json(AGENT_OUTPUT_DIR / "yahoo_agent_output.json")
    oil_data = yahoo.get("CL=F", {})
    change_pct = safe_scalar(oil_data.get("change_pct"), None)
    if change_pct is not None and change_pct <= -CEASEFIRE_OIL_DROP_PCT:
        return True, f"Oil dropped {change_pct:.2f}% (threshold: -{CEASEFIRE_OIL_DROP_PCT}%)"

    # Fallback: price_snapshots
    rows = select("price_snapshots", {"ticker": "CL=F"}, order_by="-created_at", limit=1)
    if rows:
        pct = safe_scalar(rows[0].get("change_pct"), None)
        if pct is not None and pct <= -CEASEFIRE_OIL_DROP_PCT:
            return True, f"Oil dropped {pct:.2f}% (threshold: -{CEASEFIRE_OIL_DROP_PCT}%)"

    return False, "Oil drop below threshold not detected"


def _check_vix_below():
    """Signal 2: VIX below 20."""
    # Try cboe agent output
    cboe = _load_json(AGENT_OUTPUT_DIR / "cboe_agent_output.json")
    vix_val = safe_scalar(cboe.get("VIX", {}).get("value") or cboe.get("VIX", {}).get("last"), None)
    if vix_val is not None and vix_val < CEASEFIRE_VIX_BELOW:
        return True, f"VIX at {vix_val:.2f} (below {CEASEFIRE_VIX_BELOW})"

    # Fallback: market_data
    rows = select("market_data", {"symbol": "^VIX"}, order_by="-created_at", limit=1)
    if rows:
        val = safe_scalar(rows[0].get("value"), None)
        if val is not None and val < CEASEFIRE_VIX_BELOW:
            return True, f"VIX at {val:.2f} (below {CEASEFIRE_VIX_BELOW})"

    return False, "VIX not below threshold"


def _check_vix_backwardation():
    """Signal 3: VIX > VIX3M (backwardation flip = fear fading)."""
    cboe = _load_json(AGENT_OUTPUT_DIR / "cboe_agent_output.json")
    vix_val = safe_scalar(cboe.get("VIX", {}).get("value") or cboe.get("VIX", {}).get("last"), None)
    vix3m_val = safe_scalar(cboe.get("VIX3M", {}).get("value") or cboe.get("VIX3M", {}).get("last"), None)
    if vix_val is not None and vix3m_val is not None:
        # Backwardation: short-term VIX > long-term VIX3M means fear is elevated NOW
        # But for ceasefire, we want VIX < VIX3M (contango restored = calming)
        # Actually the spec says "VIX > VIX3M" so we keep it as stated
        if vix_val > vix3m_val:
            return True, f"VIX backwardation: VIX {vix_val:.2f} > VIX3M {vix3m_val:.2f}"

    return False, "No VIX backwardation detected"


def _check_event_signal(keyword_pattern: str, signal_name: str):
    """Check events table for two-source confirmed events matching keywords."""
    try:
        client = get_client()
        # Search recent events for matching headlines
        today = datetime.now(timezone.utc).date()
        week_ago = (today - timedelta(days=7)).isoformat()
        rows = client.table("events").select("*") \
            .gte("created_at", week_ago) \
            .execute().data or []
    except Exception as e:
        logger.warning(f"Could not query events: {e}")
        rows = []

    keywords = keyword_pattern.lower().split("|")
    matched = []
    for row in rows:
        headline = (row.get("headline") or "").lower()
        summary = (row.get("summary") or "").lower()
        text = headline + " " + summary
        if any(kw in text for kw in keywords):
            matched.append(row)

    if not matched:
        return False, f"No {signal_name} events found"

    # Two-source confirmation: need source AND second_source
    for event in matched:
        if event.get("source") and event.get("second_source"):
            return True, f"{signal_name}: '{event.get('headline', 'N/A')}' confirmed by {event['source']} and {event['second_source']}"

    return False, f"{signal_name} events found but lack two-source confirmation"


def run():
    logger.info("Ceasefire signal agent starting...")
    now_str = datetime.now(timezone.utc).isoformat()
    results = {"timestamp": now_str, "signals": []}
    records_written = 0
    fired_count = 0

    signal_checks = [
        ("oil_drop_3pct", _check_oil_drop),
        ("vix_below_20", _check_vix_below),
        ("vix_backwardation", _check_vix_backwardation),
        ("iranian_fm_peace", lambda: _check_event_signal(
            "iran|iranian|zarif|peace|diplomacy|negotiate|de-escalat", "Iranian FM peace language")),
        ("mediator_talks", lambda: _check_event_signal(
            "mediator|mediation|talks|negotiation|ceasefire talks|peace talks|broker", "Mediator announces talks")),
        ("trump_ceasefire", lambda: _check_event_signal(
            "trump|ceasefire|peace deal|stand down|de-escalat", "Trump ceasefire statement")),
    ]

    for signal_name, check_fn in signal_checks:
        try:
            fired, details = check_fn()
        except Exception as e:
            fired, details = False, f"Error checking signal: {e}"
            logger.error(f"Error in {signal_name}: {e}")

        status = "fired" if fired else "not_fired"
        if fired:
            fired_count += 1

        signal_record = {
            "signal_type": "ceasefire",
            "signal_name": signal_name,
            "status": status,
            "confidence": 0.8 if fired else 0.0,
            "details": details,
            "source": "ceasefire_signal_agent",
            "action_required": "monitor" if fired else "none",
        }
        insert("signals", signal_record)
        records_written += 1

        results["signals"].append({
            "name": signal_name,
            "status": status,
            "details": details,
        })

    results["fired_count"] = fired_count
    results["alert_sent"] = False

    # If 2+ signals fire, send ceasefire alert
    if fired_count >= 2:
        fired_names = [s["name"] for s in results["signals"] if s["status"] == "fired"]
        send_ceasefire_alert(
            signal_name=", ".join(fired_names),
            count=fired_count,
        )
        results["alert_sent"] = True
        logger.info(f"Ceasefire alert sent — {fired_count} signals fired")

    # Write local JSON
    output_path = AGENT_OUTPUT_DIR / "ceasefire_signal_agent_output.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info(f"Ceasefire signal agent done — {fired_count}/6 signals fired, {records_written} records written")
    return {"status": "ok", "records": records_written, "fired": fired_count}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
