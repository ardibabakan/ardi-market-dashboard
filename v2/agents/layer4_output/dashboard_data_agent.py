"""
Dashboard Data Agent — Layer 4 Output
Ardi Market Command Center v2

Prepares a clean JSON snapshot for the Next.js dashboard.
Writes to dashboard_state table in Supabase.
"""
import json
import logging
import sys
from pathlib import Path
from datetime import datetime, timezone, date

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import *
from lib.supabase_client import select, get_client

logger = logging.getLogger("ardi.layer4.dashboard_data")


def _load_output(name):
    try:
        p = AGENT_OUTPUT_DIR / f"{name}_output.json"
        if p.exists():
            with open(p) as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _conflict_day():
    start = date.fromisoformat(CONFLICT_START_DATE)
    return (date.today() - start).days


def run():
    logger.info("Dashboard Data Agent starting...")
    records_written = 0

    # Build dashboard snapshot
    snapshot = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "conflict_day": _conflict_day(),
        "portfolio": {
            "budget": PORTFOLIO_BUDGET,
            "status": "paper_trading",
            "positions": {},
        },
        "signals": {
            "ceasefire_count": 0,
            "danger_count": 0,
        },
        "action": "HOLD — No trades needed today.",
        "market": {},
        "crypto": {},
        "vix": {},
    }

    # Positions
    try:
        positions = select("positions") or []
        for p in positions:
            if isinstance(p, dict):
                snapshot["portfolio"]["positions"][p.get("ticker", "")] = {
                    "company": p.get("company"),
                    "sector": p.get("sector"),
                    "status": p.get("status"),
                    "entry_price": p.get("entry_price"),
                }
    except Exception as e:
        logger.warning(f"Could not read positions: {e}")

    # VIX data
    cboe = _load_output("cboe_agent")
    if cboe:
        snapshot["vix"] = {
            "value": cboe.get("vix"),
            "vix3m": cboe.get("vix3m"),
            "regime": cboe.get("regime"),
            "term_structure": cboe.get("term_structure"),
        }

    # Signals
    ceasefire = _load_output("ceasefire_signal_agent")
    danger = _load_output("danger_signal_agent")
    if ceasefire:
        snapshot["signals"]["ceasefire_count"] = ceasefire.get("total_fired", 0)
    if danger:
        snapshot["signals"]["danger_count"] = danger.get("total_fired", 0)
        if danger.get("total_fired", 0) > 0:
            snapshot["action"] = "DANGER SIGNAL — Do not trade."

    # Oil
    oil = _load_output("oil_premium_agent")
    if oil:
        snapshot["market"]["oil_price"] = oil.get("current_price")
        snapshot["market"]["war_premium"] = oil.get("war_premium")

    # Crypto
    crypto = _load_output("coingecko_agent")
    if crypto and crypto.get("coins"):
        snapshot["crypto"] = crypto["coins"]

    # Scenarios
    geo = _load_output("geopolitical_scenario_agent")
    if geo and geo.get("scenarios"):
        snapshot["scenarios"] = geo["scenarios"]

    # Write to Supabase dashboard_state table
    try:
        client = get_client()
        client.table("dashboard_state").upsert({
            "id": "current",
            "data": snapshot,
        }, on_conflict="id").execute()
        records_written += 1
        logger.info("Dashboard state written to Supabase")
    except Exception as e:
        logger.warning(f"Dashboard state write failed (table may not exist yet): {e}")

    # Local JSON
    output_path = AGENT_OUTPUT_DIR / "dashboard_data_agent_output.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(snapshot, f, indent=2, default=str)

    return {"status": "ok", "records": records_written}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
