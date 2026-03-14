"""
Danger Signal Agent — Layer 3 Signals
Ardi Market Command Center v2

Checks 7 danger signals:
1. Oil spikes 10%+ in one day
2. VIX above 40
3. S&P 500 drops 5%+ in one week
4. Credit spread widens 100+ bps
5. Iran nuclear announcement (events, two-source)
6. China Taiwan military (events, two-source)
7. US military asset attacked (events, two-source)

If ANY 1 fires, sends danger alert immediately.
"""
import json, logging, sys
from pathlib import Path
from datetime import datetime, timezone, date, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import *
from lib.supabase_client import insert, select, get_client
from lib.ntfy_client import send_danger_alert, send_alert
from lib.safe_scalar import safe_scalar

logger = logging.getLogger("ardi.layer3.danger_signal")


def _load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load {path}: {e}")
        return {}


def _check_oil_spike():
    """Signal 1: Oil spikes 10%+ in one day."""
    yahoo = _load_json(AGENT_OUTPUT_DIR / "yahoo_agent_output.json")
    oil_data = yahoo.get("CL=F", {})
    change_pct = safe_scalar(oil_data.get("change_pct"), None)
    if change_pct is not None and change_pct >= DANGER_OIL_SPIKE_PCT:
        return True, f"Oil spiked +{change_pct:.2f}% (threshold: +{DANGER_OIL_SPIKE_PCT}%)"

    rows = select("price_snapshots", {"ticker": "CL=F"}, order_by="-created_at", limit=1)
    if rows:
        pct = safe_scalar(rows[0].get("change_pct"), None)
        if pct is not None and pct >= DANGER_OIL_SPIKE_PCT:
            return True, f"Oil spiked +{pct:.2f}% (threshold: +{DANGER_OIL_SPIKE_PCT}%)"

    return False, "No oil spike detected"


def _check_vix_above():
    """Signal 2: VIX above 40."""
    cboe = _load_json(AGENT_OUTPUT_DIR / "cboe_agent_output.json")
    vix_val = safe_scalar(cboe.get("VIX", {}).get("value") or cboe.get("VIX", {}).get("last"), None)
    if vix_val is not None and vix_val > DANGER_VIX_ABOVE:
        return True, f"VIX at {vix_val:.2f} (above {DANGER_VIX_ABOVE})"

    rows = select("market_data", {"symbol": "^VIX"}, order_by="-created_at", limit=1)
    if rows:
        val = safe_scalar(rows[0].get("value"), None)
        if val is not None and val > DANGER_VIX_ABOVE:
            return True, f"VIX at {val:.2f} (above {DANGER_VIX_ABOVE})"

    return False, "VIX not above danger threshold"


def _check_sp500_weekly_drop():
    """Signal 3: S&P 500 drops 5%+ in one week."""
    yahoo = _load_json(AGENT_OUTPUT_DIR / "yahoo_agent_output.json")
    sp_data = yahoo.get("^GSPC", {})

    # Try to get weekly change from the output
    price = safe_scalar(sp_data.get("price") or sp_data.get("regularMarketPrice"), None)

    # Check market_data for weekly comparison
    try:
        client = get_client()
        week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        rows = client.table("market_data").select("*") \
            .eq("symbol", "^GSPC") \
            .lte("created_at", week_ago) \
            .order("created_at", desc=True) \
            .limit(1).execute().data or []
        if rows and price:
            old_val = safe_scalar(rows[0].get("value"), None)
            if old_val and old_val > 0:
                weekly_change = ((price - old_val) / old_val) * 100
                if weekly_change <= -DANGER_SP500_WEEKLY_DROP_PCT:
                    return True, f"S&P 500 dropped {weekly_change:.2f}% this week (threshold: -{DANGER_SP500_WEEKLY_DROP_PCT}%)"
    except Exception as e:
        logger.warning(f"Could not check S&P weekly: {e}")

    # Fallback: check price_snapshots
    rows = select("price_snapshots", {"ticker": "^GSPC"}, order_by="-created_at", limit=1)
    if rows:
        pct = safe_scalar(rows[0].get("change_pct"), None)
        # Daily change * ~5 is a rough weekly proxy, but not ideal
        # Better to just flag if daily drop is extreme
        if pct is not None and pct <= -(DANGER_SP500_WEEKLY_DROP_PCT / 2):
            return True, f"S&P 500 daily drop {pct:.2f}% suggests severe weekly decline"

    return False, "No S&P 500 weekly drop detected"


def _check_credit_spread():
    """Signal 4: Credit spread widens 100+ bps."""
    fred = _load_json(AGENT_OUTPUT_DIR / "fred_agent_output.json")
    hy_data = fred.get("BAMLH0A0HYM2", {})
    spread_val = safe_scalar(hy_data.get("value"), None)
    prev_val = safe_scalar(hy_data.get("previous_value") or hy_data.get("prev_value"), None)

    if spread_val is not None and prev_val is not None and prev_val > 0:
        widen_bps = (spread_val - prev_val) * 100  # already in pct, convert to bps
        if widen_bps >= DANGER_CREDIT_SPREAD_WIDEN_BPS:
            return True, f"Credit spread widened {widen_bps:.0f} bps (threshold: {DANGER_CREDIT_SPREAD_WIDEN_BPS} bps)"

    # Also check absolute level — spreads above 6% are dangerous
    if spread_val is not None and spread_val > 6.0:
        return True, f"Credit spread at {spread_val:.2f}% — extreme stress level"

    return False, "Credit spread within normal range"


def _check_event_signal(keyword_pattern: str, signal_name: str):
    """Check events table for two-source confirmed events."""
    try:
        client = get_client()
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

    for event in matched:
        if event.get("source") and event.get("second_source"):
            return True, f"{signal_name}: '{event.get('headline', 'N/A')}' confirmed by {event['source']} and {event['second_source']}"

    return False, f"{signal_name} events found but lack two-source confirmation"


def run():
    logger.info("Danger signal agent starting...")
    now_str = datetime.now(timezone.utc).isoformat()
    results = {"timestamp": now_str, "signals": []}
    records_written = 0
    fired_count = 0

    signal_checks = [
        ("oil_spike_10pct", _check_oil_spike),
        ("vix_above_40", _check_vix_above),
        ("sp500_weekly_drop_5pct", _check_sp500_weekly_drop),
        ("credit_spread_widen_100bps", _check_credit_spread),
        ("iran_nuclear", lambda: _check_event_signal(
            "iran|nuclear|enrichment|uranium|centrifuge|weapons grade|breakout", "Iran nuclear announcement")),
        ("china_taiwan_military", lambda: _check_event_signal(
            "china|taiwan|strait|military|blockade|invasion|pla|warship", "China Taiwan military")),
        ("us_military_attacked", lambda: _check_event_signal(
            "us military|american forces|base attacked|ship attacked|troops killed|drone strike on us|ambush",
            "US military asset attacked")),
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
            "signal_type": "danger",
            "signal_name": signal_name,
            "status": status,
            "confidence": 0.9 if fired else 0.0,
            "details": details,
            "source": "danger_signal_agent",
            "action_required": "halt_trading" if fired else "none",
        }
        insert("signals", signal_record)
        records_written += 1

        results["signals"].append({
            "name": signal_name,
            "status": status,
            "details": details,
        })

        # If ANY danger signal fires, send alert immediately
        if fired:
            send_danger_alert(signal_name=signal_name, details=details)
            logger.warning(f"DANGER ALERT sent for {signal_name}")

    results["fired_count"] = fired_count
    results["alerts_sent"] = fired_count

    # Write local JSON
    output_path = AGENT_OUTPUT_DIR / "danger_signal_agent_output.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info(f"Danger signal agent done — {fired_count}/7 signals fired, {records_written} records written")
    return {"status": "ok", "records": records_written, "fired": fired_count}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
