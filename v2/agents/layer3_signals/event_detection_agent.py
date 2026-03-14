"""
Event Detection Agent — Layer 3 Signals
Ardi Market Command Center v2

Reads all recent events from the events table.
Flags severity "major" or "critical".
Checks if new theses or scenarios are detected.
"""
import json, logging, sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import *
from lib.supabase_client import insert, select, get_client
from lib.ntfy_client import send_alert
from lib.safe_scalar import safe_scalar

logger = logging.getLogger("ardi.layer3.event_detection")


def _load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load {path}: {e}")
        return {}


# Thesis keywords — events that suggest new investment theses
THESIS_KEYWORDS = {
    "sanctions": "New sanctions could create energy/defence opportunities",
    "embargo": "Embargo may shift trade flows — shipping/energy impact",
    "rate cut": "Rate cut signals pivot — growth stocks, REITs benefit",
    "rate hike": "Rate hike — defensive positioning, avoid high-duration",
    "tariff": "Tariff announcement — reshoring/domestic manufacturing thesis",
    "ai regulation": "AI regulation — potential headwind for tech sector",
    "nuclear deal": "Nuclear deal progress — ceasefire thesis support",
    "opec": "OPEC decision — direct oil price impact",
    "fed pivot": "Fed pivot signal — broad market regime change",
}


def run():
    logger.info("Event detection agent starting...")
    now_str = datetime.now(timezone.utc).isoformat()
    results = {"timestamp": now_str, "flagged_events": [], "new_theses": []}
    records_written = 0

    # Fetch recent events (last 48 hours)
    try:
        client = get_client()
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
        rows = client.table("events").select("*") \
            .gte("created_at", cutoff) \
            .order("created_at", desc=True) \
            .execute().data or []
    except Exception as e:
        logger.error(f"Could not fetch events: {e}")
        rows = []

    flagged = []
    new_theses = []

    for event in rows:
        severity = (event.get("severity") or "").lower()
        headline = event.get("headline") or ""
        summary = event.get("summary") or ""
        event_text = (headline + " " + summary).lower()

        # Flag major or critical events
        if severity in ("major", "critical"):
            flagged.append({
                "headline": headline,
                "severity": severity,
                "event_type": event.get("event_type"),
                "source": event.get("source"),
                "second_source": event.get("second_source"),
                "affected_tickers": event.get("affected_tickers"),
                "impact_assessment": event.get("impact_assessment"),
                "created_at": event.get("created_at"),
            })

            # Write signal for each flagged event
            signal_record = {
                "signal_type": "event_detection",
                "signal_name": f"event_{severity}_{event.get('event_type', 'unknown')}",
                "status": "fired",
                "confidence": 0.9 if severity == "critical" else 0.7,
                "details": f"[{severity.upper()}] {headline}",
                "source": "event_detection_agent",
                "second_source": event.get("source"),
                "action_required": "immediate_review" if severity == "critical" else "review",
            }
            insert("signals", signal_record)
            records_written += 1

        # Check for new thesis keywords
        for keyword, thesis_desc in THESIS_KEYWORDS.items():
            if keyword in event_text:
                thesis_entry = {
                    "keyword": keyword,
                    "thesis": thesis_desc,
                    "trigger_event": headline,
                    "created_at": event.get("created_at"),
                }
                # Avoid duplicates
                if not any(t["keyword"] == keyword for t in new_theses):
                    new_theses.append(thesis_entry)

    results["flagged_events"] = flagged
    results["new_theses"] = new_theses
    results["total_events_scanned"] = len(rows)

    # Alert for critical events
    critical = [e for e in flagged if e["severity"] == "critical"]
    if critical:
        send_alert(
            title=f"CRITICAL EVENTS: {len(critical)} detected",
            message="\n".join(f"- {e['headline']}" for e in critical[:5]),
            priority="urgent",
            tags=["rotating_light"],
        )

    # Alert for major events (lower priority)
    major = [e for e in flagged if e["severity"] == "major"]
    if major:
        send_alert(
            title=f"Major Events: {len(major)} flagged",
            message="\n".join(f"- {e['headline']}" for e in major[:5]),
            priority="high",
            tags=["warning"],
        )

    # Alert for new theses
    if new_theses:
        send_alert(
            title=f"New Thesis Detected: {len(new_theses)}",
            message="\n".join(f"- {t['thesis']} (trigger: {t['trigger_event'][:60]})" for t in new_theses[:3]),
            priority="default",
            tags=["bulb"],
        )

    # Write local JSON
    output_path = AGENT_OUTPUT_DIR / "event_detection_agent_output.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info(f"Event detection agent done — {len(flagged)} flagged, {len(new_theses)} new theses, {records_written} records")
    return {"status": "ok", "records": records_written, "flagged": len(flagged), "new_theses": len(new_theses)}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
