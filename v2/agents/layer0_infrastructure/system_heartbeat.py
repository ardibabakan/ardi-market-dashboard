"""
Layer 0 — System Heartbeat Agent
Verifies Supabase reachable, API keys set, disk space OK.
Writes results to system_health table.
"""
import logging
import os
import shutil
from datetime import datetime, timezone

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import (
    SUPABASE_URL, SUPABASE_KEY, FINNHUB_KEY, PERPLEXITY_KEY,
    EXA_KEY, ALPHA_VANTAGE_KEY, EIA_KEY, NTFY_TOPIC, V2_DIR
)
from lib.supabase_client import insert, get_client
from lib.ntfy_client import send_system_health

logger = logging.getLogger("ardi.heartbeat")


def check_supabase():
    """Verify Supabase is reachable."""
    try:
        client = get_client()
        # Simple query to confirm connectivity
        client.table("system_health").select("id").limit(1).execute()
        return True, "Supabase reachable"
    except Exception as e:
        return False, f"Supabase unreachable: {e}"


def check_api_keys():
    """Verify required API keys are set."""
    keys = {
        "SUPABASE_URL": SUPABASE_URL,
        "SUPABASE_KEY": SUPABASE_KEY,
        "FINNHUB_KEY": FINNHUB_KEY,
        "NTFY_TOPIC": NTFY_TOPIC,
    }
    optional_keys = {
        "PERPLEXITY_KEY": PERPLEXITY_KEY,
        "EXA_KEY": EXA_KEY,
        "ALPHA_VANTAGE_KEY": ALPHA_VANTAGE_KEY,
        "EIA_KEY": EIA_KEY,
    }

    missing_required = [k for k, v in keys.items() if not v]
    missing_optional = [k for k, v in optional_keys.items() if not v]

    if missing_required:
        return False, f"Missing required keys: {', '.join(missing_required)}"

    msg = "All required keys set"
    if missing_optional:
        msg += f" (optional missing: {', '.join(missing_optional)})"
    return True, msg


def check_disk_space():
    """Verify at least 1 GB free disk space."""
    usage = shutil.disk_usage(str(V2_DIR))
    free_gb = usage.free / (1024 ** 3)
    if free_gb < 1.0:
        return False, f"Low disk space: {free_gb:.1f} GB free"
    return True, f"Disk OK: {free_gb:.1f} GB free"


def run():
    """Run all heartbeat checks and write to system_health table."""
    checks = {}
    all_ok = True

    for name, func in [
        ("supabase", check_supabase),
        ("api_keys", check_api_keys),
        ("disk_space", check_disk_space),
    ]:
        try:
            ok, msg = func()
            checks[name] = {"ok": ok, "message": msg}
            if not ok:
                all_ok = False
        except Exception as e:
            checks[name] = {"ok": False, "message": str(e)}
            all_ok = False

    status = "healthy" if all_ok else "degraded"
    now = datetime.now(timezone.utc).isoformat()

    record = {
        "agent_name": "system_heartbeat",
        "status": "ok" if all_ok else "warning",
        "message": str(checks)[:500],
    }

    insert("system_health", record)

    if not all_ok:
        failed = [f"{k}: {v['message']}" for k, v in checks.items() if not v["ok"]]
        send_system_health(f"Heartbeat DEGRADED: {'; '.join(failed)}", ok=False)
        logger.warning(f"Heartbeat: {status} — {checks}")
    else:
        logger.info(f"Heartbeat: {status}")

    return {"status": "ok" if all_ok else "degraded", "records": 1}
