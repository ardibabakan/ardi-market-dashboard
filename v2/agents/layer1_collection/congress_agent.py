"""
Congress Agent — Layer 1 Data Collection
Ardi Market Command Center v2

Collects: Defence spending bills, sanctions legislation, crypto regulation.
Lightweight agent — flags new relevant bills.
"""
import json
import logging
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import AGENT_OUTPUT_DIR
from lib.supabase_client import insert

logger = logging.getLogger("ardi.layer1.congress")

CONGRESS_API = "https://api.congress.gov/v3"

SEARCH_TERMS = [
    "defense spending",
    "military appropriations",
    "Iran sanctions",
    "Taiwan",
    "cryptocurrency regulation",
]


def run():
    """Main entry point."""
    logger.info("Congress Agent starting...")
    import requests

    results = {"bills_found": []}
    records_written = 0

    for term in SEARCH_TERMS:
        time.sleep(1)
        try:
            # Use congress.gov search (no API key required for basic search)
            resp = requests.get(
                "https://api.congress.gov/v3/bill",
                params={
                    "query": term,
                    "limit": 3,
                    "sort": "updateDate+desc",
                    "format": "json",
                },
                headers={"Accept": "application/json"},
                timeout=15
            )

            if resp.status_code == 200:
                data = resp.json()
                bills = data.get("bills", [])
                for bill in bills[:2]:
                    title = bill.get("title", "")[:500]
                    bill_type = bill.get("type", "")
                    number = bill.get("number", "")
                    update = bill.get("updateDate", "")

                    entry = {
                        "term": term,
                        "title": title,
                        "bill_id": f"{bill_type}{number}",
                        "updated": update,
                    }
                    results["bills_found"].append(entry)

                    insert("events", {
                        "event_type": "regulatory",
                        "headline": f"Congress: {title[:200]}",
                        "summary": f"Bill {bill_type}{number}, search term: '{term}', updated: {update}",
                        "source": "congress_gov",
                        "severity": "minor",
                    })
                    records_written += 1

            elif resp.status_code == 403:
                logger.info(f"Congress API requires key for '{term}' — skipping")
            else:
                logger.warning(f"Congress API returned {resp.status_code} for '{term}'")

        except Exception as e:
            logger.warning(f"Congress search failed for '{term}': {e}")

    # Write local JSON
    output_path = AGENT_OUTPUT_DIR / "congress_agent_output.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info(f"Congress Agent complete. {records_written} records.")
    return {"status": "ok", "records": records_written}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
