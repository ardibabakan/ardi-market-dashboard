"""
Alert Dispatcher — Layer 0 Infrastructure
Ardi Market Command Center v2

Central alert management with:
- Deduplication (don't send same alert twice in 2 hours)
- Priority queue (urgent > high > default > low > min)
- Alert logging to system_health table
"""
import json, logging, sys, hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import *
from lib.supabase_client import insert, select, get_client
from lib.ntfy_client import send_alert

logger = logging.getLogger("ardi.layer0.alert_dispatcher")

# In-memory dedup cache (persists within a single process run)
# For cross-run dedup, we also check the alerts log file
DEDUP_WINDOW_HOURS = 2
ALERT_LOG_PATH = AGENT_OUTPUT_DIR / "alert_log.json"

PRIORITY_ORDER = {"urgent": 5, "high": 4, "default": 3, "low": 2, "min": 1}


def _load_alert_log():
    """Load the alert log from disk."""
    try:
        if ALERT_LOG_PATH.exists():
            with open(ALERT_LOG_PATH) as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load alert log: {e}")
    return {"alerts": []}


def _save_alert_log(log_data):
    """Save alert log to disk."""
    try:
        ALERT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(ALERT_LOG_PATH, "w") as f:
            json.dump(log_data, f, indent=2, default=str)
    except Exception as e:
        logger.error(f"Could not save alert log: {e}")


def _alert_fingerprint(title: str, message: str) -> str:
    """Create a dedup fingerprint for an alert."""
    content = f"{title}|{message}".lower().strip()
    return hashlib.md5(content.encode()).hexdigest()


def _is_duplicate(fingerprint: str, log_data: dict) -> bool:
    """Check if this alert was already sent within the dedup window."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=DEDUP_WINDOW_HOURS)).isoformat()
    for entry in log_data.get("alerts", []):
        if entry.get("fingerprint") == fingerprint:
            sent_at = entry.get("sent_at", "")
            if sent_at >= cutoff:
                return True
    return False


def dispatch_alert(title: str, message: str, priority: str = "default",
                   tags: list = None, source: str = "unknown",
                   force: bool = False) -> bool:
    """
    Central alert dispatch with deduplication and logging.

    Args:
        title: Alert title
        message: Alert body
        priority: urgent/high/default/low/min
        tags: ntfy emoji tags
        source: which agent sent this
        force: bypass dedup check

    Returns:
        True if alert was sent, False if deduplicated or failed
    """
    fingerprint = _alert_fingerprint(title, message)
    log_data = _load_alert_log()

    # Dedup check (unless forced)
    if not force and _is_duplicate(fingerprint, log_data):
        logger.info(f"Alert deduplicated (sent within {DEDUP_WINDOW_HOURS}h): {title}")
        return False

    # Send the alert
    sent = send_alert(title=title, message=message, priority=priority, tags=tags)

    # Log regardless of success
    log_entry = {
        "fingerprint": fingerprint,
        "title": title,
        "message": message[:200],
        "priority": priority,
        "source": source,
        "sent": sent,
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }
    log_data["alerts"].append(log_entry)

    # Prune old entries (keep last 7 days)
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    log_data["alerts"] = [
        a for a in log_data["alerts"] if a.get("sent_at", "") >= week_ago
    ]

    _save_alert_log(log_data)

    # Log to system_health table
    insert("system_health", {
        "agent_name": "alert_dispatcher",
        "status": "alert_sent" if sent else "alert_failed",
        "message": f"[{priority}] {title} (source: {source}, dedup: {fingerprint[:8]})",
    })

    return sent


def dispatch_queue(alerts: list) -> dict:
    """
    Process a queue of alerts, sorted by priority (urgent first).

    Args:
        alerts: list of dicts with keys: title, message, priority, tags, source

    Returns:
        Summary dict with sent/deduped/failed counts
    """
    # Sort by priority (highest first)
    sorted_alerts = sorted(
        alerts,
        key=lambda a: PRIORITY_ORDER.get(a.get("priority", "default"), 3),
        reverse=True,
    )

    sent = 0
    deduped = 0
    failed = 0

    for alert in sorted_alerts:
        result = dispatch_alert(
            title=alert.get("title", "Alert"),
            message=alert.get("message", ""),
            priority=alert.get("priority", "default"),
            tags=alert.get("tags"),
            source=alert.get("source", "queue"),
            force=alert.get("force", False),
        )
        if result:
            sent += 1
        elif result is False:
            # Could be deduped or failed — check log
            fp = _alert_fingerprint(alert.get("title", ""), alert.get("message", ""))
            log_data = _load_alert_log()
            if _is_duplicate(fp, log_data):
                deduped += 1
            else:
                failed += 1

    return {"sent": sent, "deduped": deduped, "failed": failed}


def run():
    """
    Standalone run: process any pending alerts from signal agents.
    Reads signal agent outputs and dispatches alerts for fired signals.
    """
    logger.info("Alert dispatcher starting...")
    now_str = datetime.now(timezone.utc).isoformat()
    results = {"timestamp": now_str, "dispatched": []}
    records_written = 0
    alerts_queue = []

    # Scan signal agent outputs for fired signals
    signal_files = [
        "ceasefire_signal_agent_output.json",
        "danger_signal_agent_output.json",
        "stop_loss_agent_output.json",
        "profit_target_agent_output.json",
        "thesis_invalidation_agent_output.json",
        "black_swan_agent_output.json",
        "opportunity_agent_output.json",
        "event_detection_agent_output.json",
        "regime_change_agent_output.json",
    ]

    for filename in signal_files:
        path = AGENT_OUTPUT_DIR / filename
        if not path.exists():
            continue
        try:
            with open(path) as f:
                data = json.load(f)
        except Exception:
            continue

        agent_name = filename.replace("_output.json", "")

        # Check for fired signals
        fired_count = data.get("fired_count", 0) or data.get("alerts_sent", 0)
        if fired_count > 0 and not data.get("alert_sent"):
            # Build summary alert
            signals = data.get("signals", data.get("checks", []))
            fired_details = [
                s.get("details", s.get("name", ""))
                for s in signals
                if s.get("status") == "fired" or s.get("fired") is True
            ]

            if fired_details:
                priority_map = {
                    "danger_signal_agent": "urgent",
                    "black_swan_agent": "urgent",
                    "stop_loss_agent": "high",
                    "ceasefire_signal_agent": "high",
                    "thesis_invalidation_agent": "high",
                    "regime_change_agent": "high",
                    "event_detection_agent": "default",
                    "profit_target_agent": "default",
                    "opportunity_agent": "default",
                }

                alerts_queue.append({
                    "title": f"{agent_name}: {fired_count} signal(s) fired",
                    "message": "\n".join(f"- {d[:100]}" for d in fired_details[:5]),
                    "priority": priority_map.get(agent_name, "default"),
                    "tags": ["warning"],
                    "source": agent_name,
                })

    # Dispatch the queue
    if alerts_queue:
        summary = dispatch_queue(alerts_queue)
        results["queue_summary"] = summary
        records_written = summary.get("sent", 0)
    else:
        results["queue_summary"] = {"sent": 0, "deduped": 0, "failed": 0}

    # Log dispatcher health
    insert("system_health", {
        "agent_name": "alert_dispatcher",
        "status": "ok",
        "message": f"Processed {len(alerts_queue)} queued alerts. Sent: {results['queue_summary']['sent']}, Deduped: {results['queue_summary']['deduped']}",
    })

    # Write local JSON
    output_path = AGENT_OUTPUT_DIR / "alert_dispatcher_output.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info(f"Alert dispatcher done — {results['queue_summary']}")
    return {"status": "ok", "records": records_written}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
