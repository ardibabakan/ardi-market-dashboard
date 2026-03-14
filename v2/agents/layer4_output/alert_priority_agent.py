"""
Alert Priority Agent — Layer 4 Output
Ardi Market Command Center v2

Sends a single summary notification at end of each run.
Ranks alerts by priority: danger > stop_loss > ceasefire > thesis > opportunity.
"""
import json
import logging
import sys
from pathlib import Path
from datetime import datetime, timezone, date

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import *
from lib.supabase_client import select
from lib.ntfy_client import send_alert

logger = logging.getLogger("ardi.layer4.alert_priority")


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
    logger.info("Alert Priority Agent starting...")
    records_written = 0

    alerts = []

    # Check danger signals
    danger = _load_output("danger_signal_agent")
    if danger.get("total_fired", 0) > 0:
        fired = [s for s in danger.get("signals", []) if isinstance(s, dict) and s.get("status") == "fired"]
        for s in fired:
            alerts.append({"priority": 1, "type": "DANGER", "message": s.get("signal_name", "Unknown danger signal")})

    # Check ceasefire signals
    ceasefire = _load_output("ceasefire_signal_agent")
    if ceasefire.get("total_fired", 0) >= 2:
        alerts.append({"priority": 3, "type": "CEASEFIRE", "message": f"Phase B triggered — {ceasefire['total_fired']} signals fired"})

    # Check opportunities
    opp = _load_output("opportunity_agent")
    if opp.get("opportunities"):
        for o in opp["opportunities"][:3]:
            if isinstance(o, dict):
                alerts.append({"priority": 5, "type": "OPPORTUNITY", "message": f"{o.get('ticker', '?')}: {o.get('reason', 'check report')}"})

    # Sort by priority (lower = more urgent)
    alerts.sort(key=lambda x: x["priority"])

    # Build summary
    day = _conflict_day()
    benchmark = _load_output("benchmark_agent")
    spy_pct = benchmark.get("spy_change_pct", "?")
    port_pct = benchmark.get("portfolio_change_pct", "?")

    if alerts:
        top = alerts[:3]
        alert_text = "\n".join(f"- [{a['type']}] {a['message']}" for a in top)
        summary = f"Day {day} | SPY: {spy_pct}% | Alerts:\n{alert_text}"
    else:
        summary = f"Day {day} | SPY: {spy_pct}% | Port: {port_pct}% | No alerts. HOLD."

    # Send summary notification
    priority = "urgent" if any(a["priority"] == 1 for a in alerts) else "default"
    send_alert(
        title=f"Daily Summary — Day {day}",
        message=summary,
        priority=priority,
        tags=["chart_with_upwards_trend"] if not alerts else ["warning"],
    )
    records_written += 1

    # Local JSON
    output_path = AGENT_OUTPUT_DIR / "alert_priority_agent_output.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump({"alerts": alerts, "summary": summary}, f, indent=2, default=str)

    logger.info(f"Alert Priority Agent complete. {len(alerts)} alerts, summary sent.")
    return {"status": "ok", "records": records_written}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
