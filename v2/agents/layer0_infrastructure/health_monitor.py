"""
Layer 0 — Health Monitor Agent
After each run, checks if critical agents succeeded by reading
the agent_runs table. Alerts if any critical agent failed.
"""
import logging
from datetime import datetime, timezone, timedelta

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from lib.supabase_client import get_client
from lib.ntfy_client import send_system_health

logger = logging.getLogger("ardi.health_monitor")

CRITICAL_AGENTS = [
    "yahoo_agent",
    "cboe_agent",
    "danger_signal_agent",
]


def run():
    """Check if critical agents succeeded in the most recent run."""
    try:
        client = get_client()
    except Exception as e:
        logger.error(f"Cannot connect to Supabase: {e}")
        return {"status": "failed", "records": 0, "error": str(e)}

    # Look at agent runs from the last 6 hours
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat()
    failed_critical = []

    for agent_name in CRITICAL_AGENTS:
        try:
            result = (
                client.table("agent_runs")
                .select("agent_name, status, error_message, completed_at")
                .eq("agent_name", agent_name)
                .gte("completed_at", cutoff)
                .order("completed_at", desc=True)
                .limit(1)
                .execute()
            )
            rows = result.data
            if not rows:
                failed_critical.append(f"{agent_name}: no run found in last 6h")
            elif rows[0]["status"] == "failed":
                err = rows[0].get("error_message", "unknown error")
                failed_critical.append(f"{agent_name}: FAILED — {err}")
        except Exception as e:
            failed_critical.append(f"{agent_name}: query error — {e}")

    if failed_critical:
        msg = "Critical agent failures:\n" + "\n".join(failed_critical)
        logger.warning(msg)
        send_system_health(msg, ok=False)
        return {"status": "ok", "records": len(failed_critical),
                "error": f"{len(failed_critical)} critical agents failed"}
    else:
        logger.info("All critical agents healthy")
        return {"status": "ok", "records": 0}
