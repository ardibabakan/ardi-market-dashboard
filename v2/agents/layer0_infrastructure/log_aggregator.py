"""
Layer 0 — Log Aggregator Agent
Reads orchestrator_log.txt, counts errors in the last 24 hours.
If errors > 10, sends an alert.
"""
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import DAILY_DIR
from lib.ntfy_client import send_system_health

logger = logging.getLogger("ardi.log_aggregator")

LOG_FILE = DAILY_DIR / "orchestrator_log.txt"
ERROR_THRESHOLD = 10


def run():
    """Count errors in orchestrator log from the last 24 hours."""
    if not LOG_FILE.exists():
        logger.info("No orchestrator log file found — nothing to aggregate")
        return {"status": "skipped", "records": 0}

    cutoff = datetime.now() - timedelta(hours=24)
    error_count = 0
    total_lines = 0
    recent_errors = []

    # Pattern matches log lines like: 2026-03-14 03:00:12,345 [name] ERROR: ...
    timestamp_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")

    try:
        with open(LOG_FILE, "r") as f:
            for line in f:
                total_lines += 1
                match = timestamp_pattern.match(line)
                if match:
                    try:
                        line_time = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
                        if line_time < cutoff:
                            continue
                    except ValueError:
                        continue

                if "ERROR" in line or "CRASHED" in line:
                    error_count += 1
                    if len(recent_errors) < 5:
                        recent_errors.append(line.strip()[:200])
    except Exception as e:
        logger.error(f"Failed to read log file: {e}")
        return {"status": "failed", "records": 0, "error": str(e)}

    logger.info(f"Log aggregator: {error_count} errors in last 24h ({total_lines} total lines)")

    if error_count > ERROR_THRESHOLD:
        summary = f"High error rate: {error_count} errors in last 24h"
        if recent_errors:
            summary += "\nRecent:\n" + "\n".join(recent_errors)
        send_system_health(summary, ok=False)
        logger.warning(summary)

    return {"status": "ok", "records": error_count}
