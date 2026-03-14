"""
Black Swan Agent — Layer 3 Signals
Ardi Market Command Center v2

Detects unprecedented / extreme market conditions:
- Any stock moves 10%+ in a day
- VIX jumps 10+ points in a day
- Credit spreads AND VIX AND oil all spiking simultaneously
- Any event with severity="critical"

If detected, sends urgent phone alert.
"""
import json, logging, sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import *
from lib.supabase_client import insert, select, get_client
from lib.ntfy_client import send_danger_alert, send_alert
from lib.safe_scalar import safe_scalar

logger = logging.getLogger("ardi.layer3.black_swan")


def _load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load {path}: {e}")
        return {}


def _check_stock_moves():
    """Check if any stock in our universe moved 10%+ in a day."""
    yahoo = _load_json(AGENT_OUTPUT_DIR / "yahoo_agent_output.json")
    extreme_movers = []

    for ticker in ALL_TICKERS:
        data = yahoo.get(ticker, {})
        change_pct = safe_scalar(data.get("change_pct") or data.get("regularMarketChangePercent"), None)
        if change_pct is not None and abs(change_pct) >= 10.0:
            extreme_movers.append(f"{ticker}: {change_pct:+.2f}%")

    if extreme_movers:
        return True, f"Extreme moves: {'; '.join(extreme_movers)}"
    return False, "No 10%+ stock moves detected"


def _check_vix_jump():
    """Check if VIX jumped 10+ points in one day."""
    cboe = _load_json(AGENT_OUTPUT_DIR / "cboe_agent_output.json")
    vix_data = cboe.get("VIX", {})
    vix_val = safe_scalar(vix_data.get("value") or vix_data.get("last"), None)
    vix_change = safe_scalar(vix_data.get("change") or vix_data.get("net_change"), None)

    if vix_change is not None and vix_change >= 10:
        return True, f"VIX jumped +{vix_change:.2f} points to {vix_val:.2f}"

    # Fallback: check previous close from yahoo
    yahoo = _load_json(AGENT_OUTPUT_DIR / "yahoo_agent_output.json")
    vix_yahoo = yahoo.get("^VIX", {})
    price = safe_scalar(vix_yahoo.get("price") or vix_yahoo.get("regularMarketPrice"), None)
    prev = safe_scalar(vix_yahoo.get("prev_close") or vix_yahoo.get("regularMarketPreviousClose"), None)
    if price and prev:
        jump = price - prev
        if jump >= 10:
            return True, f"VIX jumped +{jump:.2f} points (from {prev:.2f} to {price:.2f})"

    return False, "No VIX 10-point jump detected"


def _check_triple_spike():
    """Check if credit spreads AND VIX AND oil are all spiking simultaneously."""
    spikes = []

    # VIX spike (above 30 and rising)
    cboe = _load_json(AGENT_OUTPUT_DIR / "cboe_agent_output.json")
    vix_val = safe_scalar(cboe.get("VIX", {}).get("value") or cboe.get("VIX", {}).get("last"), None)
    if vix_val and vix_val > 30:
        spikes.append(f"VIX at {vix_val:.2f}")

    # Oil spike (above baseline + 20%)
    yahoo = _load_json(AGENT_OUTPUT_DIR / "yahoo_agent_output.json")
    oil = yahoo.get("CL=F", {})
    oil_price = safe_scalar(oil.get("price") or oil.get("regularMarketPrice"), None)
    oil_threshold = OIL_BASELINE * 1.20
    if oil_price and oil_price > oil_threshold:
        spikes.append(f"Oil at ${oil_price:.2f} (>{oil_threshold:.0f})")

    # Credit spread widening
    fred = _load_json(AGENT_OUTPUT_DIR / "fred_agent_output.json")
    hy = fred.get("BAMLH0A0HYM2", {})
    spread = safe_scalar(hy.get("value"), None)
    if spread and spread > 5.0:
        spikes.append(f"HY spread at {spread:.2f}%")

    if len(spikes) >= 3:
        return True, f"Triple spike: {'; '.join(spikes)}"
    return False, f"Only {len(spikes)}/3 spike conditions met"


def _check_critical_events():
    """Check for any event with severity='critical'."""
    try:
        client = get_client()
        today = datetime.now(timezone.utc).date()
        day_ago = (today - timedelta(days=1)).isoformat()
        rows = client.table("events").select("*") \
            .eq("severity", "critical") \
            .gte("created_at", day_ago) \
            .execute().data or []
        if rows:
            headlines = [r.get("headline", "N/A") for r in rows[:3]]
            return True, f"Critical events: {'; '.join(headlines)}"
    except Exception as e:
        logger.warning(f"Could not check critical events: {e}")

    return False, "No critical-severity events in last 24h"


def run():
    logger.info("Black swan agent starting...")
    now_str = datetime.now(timezone.utc).isoformat()
    results = {"timestamp": now_str, "checks": []}
    records_written = 0
    fired_count = 0

    checks = [
        ("stock_move_10pct", _check_stock_moves),
        ("vix_jump_10pts", _check_vix_jump),
        ("triple_spike", _check_triple_spike),
        ("critical_event", _check_critical_events),
    ]

    for check_name, check_fn in checks:
        try:
            fired, details = check_fn()
        except Exception as e:
            fired, details = False, f"Error: {e}"
            logger.error(f"Error in {check_name}: {e}")

        if fired:
            fired_count += 1

        results["checks"].append({
            "name": check_name,
            "fired": fired,
            "details": details,
        })

        signal_record = {
            "signal_type": "black_swan",
            "signal_name": check_name,
            "status": "fired" if fired else "not_fired",
            "confidence": 0.95 if fired else 0.0,
            "details": details,
            "source": "black_swan_agent",
            "action_required": "immediate_review" if fired else "none",
        }
        insert("signals", signal_record)
        records_written += 1

        # Urgent alert for any black swan detection
        if fired:
            send_alert(
                title=f"BLACK SWAN: {check_name}",
                message=f"{details}\n\nHALT ALL TRADING. Review positions immediately.\nFidelity: 800-343-3548",
                priority="urgent",
                tags=["rotating_light", "skull"],
            )
            logger.warning(f"BLACK SWAN ALERT: {check_name} — {details}")

    results["fired_count"] = fired_count

    # Write local JSON
    output_path = AGENT_OUTPUT_DIR / "black_swan_agent_output.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info(f"Black swan agent done — {fired_count} detections, {records_written} records written")
    return {"status": "ok", "records": records_written, "fired": fired_count}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
