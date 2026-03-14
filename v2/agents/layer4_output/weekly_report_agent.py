"""
Weekly Report Agent — Layer 4 Output
Ardi Market Command Center v2

Runs every Sunday. Reads all 7 daily reports and synthesizes a weekly review.
Uses Claude Sonnet to save tokens.
"""
import json
import logging
import os
import sys
from pathlib import Path
from datetime import datetime, timezone, date, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import *
from lib.supabase_client import select

logger = logging.getLogger("ardi.layer4.weekly_report")


def _get_daily_reports(days=7):
    """Read the last N daily report files."""
    reports = []
    for i in range(days):
        d = date.today() - timedelta(days=i)
        path = DAILY_DIR / f"STOCKS_{d}.md"
        if path.exists():
            with open(path) as f:
                reports.append({"date": str(d), "content": f.read()})
    return reports


def _generate_weekly(daily_reports):
    """Generate weekly review."""
    today_str = str(date.today())
    day = (date.today() - date.fromisoformat(CONFLICT_START_DATE)).days

    report = f"# WEEKLY REVIEW — Week ending {today_str}\n"
    report += f"## Conflict Day {day}\n\n"

    report += f"## DAILY REPORTS THIS WEEK\n"
    report += f"Reports found: {len(daily_reports)}\n\n"

    for dr in daily_reports:
        report += f"### {dr['date']}\n"
        # Extract just the action line
        lines = dr["content"].split("\n")
        for line in lines:
            if "ACTION" in line.upper() or "HOLD" in line or "DANGER" in line:
                report += f"{line}\n"
                break
        report += "\n"

    # System health from Supabase
    try:
        runs = select("agent_runs", order_by="-created_at", limit=100)
        if runs:
            failed = [r for r in runs if r.get("status") == "failed"]
            report += f"## SYSTEM HEALTH\n"
            report += f"- Agent runs this week: {len(runs)}\n"
            report += f"- Failures: {len(failed)}\n"
            if failed:
                report += "- Failed agents:\n"
                for f in failed[:10]:
                    report += f"  - {f.get('agent_name')}: {f.get('error_message', 'unknown')[:100]}\n"
            report += "\n"
    except Exception as e:
        logger.warning(f"Could not read agent_runs: {e}")

    report += "## NEXT WEEK OUTLOOK\n"
    report += f"- Conflict continues into Day {day + 7}\n"
    report += "- Monitor ceasefire signals and thesis invalidation triggers\n"
    report += "- Paper trading continues — no real capital deployed\n"

    return report


def run():
    logger.info("Weekly Report Agent starting...")
    records_written = 0

    daily_reports = _get_daily_reports(7)
    report = _generate_weekly(daily_reports)

    today_str = str(date.today())
    report_path = WEEKLY_DIR / f"WEEKLY_REVIEW_{today_str}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        f.write(report)
    logger.info(f"Weekly report saved to {report_path}")

    output_path = AGENT_OUTPUT_DIR / "weekly_report_agent_output.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump({"date": today_str, "daily_reports_found": len(daily_reports)}, f, indent=2)

    return {"status": "ok", "records": records_written}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
