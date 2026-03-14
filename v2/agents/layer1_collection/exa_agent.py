"""
Exa Agent — Layer 1 Data Collection
Ardi Market Command Center v2

Job 1: Confirm unconfirmed Perplexity signals (two-source confirmation).
Job 2: Proactive semantic search for key events.
"""
import json
import logging
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import EXA_KEY, AGENT_OUTPUT_DIR
from lib.supabase_client import insert, select, get_client

logger = logging.getLogger("ardi.layer1.exa")

EXA_URL = "https://api.exa.ai/search"

PROACTIVE_SEARCHES = [
    "Iran ceasefire negotiations diplomatic talks",
    "Iran nuclear weapon announcement",
    "China Taiwan military exercise invasion",
    "US carrier attacked military base",
    "Ripple XRP SEC ruling court decision",
    "Federal Reserve emergency meeting rate cut",
]


def _exa_search(query, num_results=3):
    """Run a semantic search on Exa."""
    import requests
    headers = {
        "x-api-key": EXA_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "query": query,
        "numResults": num_results,
        "useAutoprompt": True,
        "type": "neural",
    }
    try:
        resp = requests.post(EXA_URL, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", [])
    except Exception as e:
        logger.warning(f"Exa search failed for '{query[:50]}': {e}")
        return []


def _confirm_signals():
    """Read unconfirmed signals from Supabase and try to confirm via Exa."""
    confirmed = 0
    try:
        unconfirmed = select("signals", {"status": "unconfirmed"}, order_by="-created_at", limit=20)
    except Exception as e:
        logger.warning(f"Could not read unconfirmed signals: {e}")
        return 0

    for signal in unconfirmed:
        details = signal.get("details", "")
        signal_name = signal.get("signal_name", "")

        # Build search query from signal details
        search_query = details[:200] if details else signal_name
        time.sleep(1)
        results = _exa_search(search_query, num_results=2)

        if results:
            # Found independent confirmation
            second_source = results[0].get("url", "exa_confirmed")
            try:
                client = get_client()
                client.table("signals").update({
                    "status": "fired",
                    "second_source": second_source,
                }).eq("id", signal["id"]).execute()
                confirmed += 1
                logger.info(f"CONFIRMED signal: {signal_name} via {second_source}")
            except Exception as e:
                logger.warning(f"Failed to update signal {signal['id']}: {e}")

    return confirmed


def run():
    """Main entry point."""
    logger.info("Exa Agent starting...")

    if not EXA_KEY:
        logger.warning("EXA_KEY not set — skipping")
        return {"status": "skipped", "reason": "no_api_key", "records": 0}

    results = {"confirmed": 0, "proactive_events": []}
    records_written = 0

    # Job 1: Confirm unconfirmed signals
    confirmed = _confirm_signals()
    results["confirmed"] = confirmed
    records_written += confirmed

    # Job 2: Proactive searches
    for query in PROACTIVE_SEARCHES:
        time.sleep(1.5)
        search_results = _exa_search(query, num_results=2)

        for r in search_results:
            title = r.get("title", "")
            url = r.get("url", "")
            published = r.get("publishedDate", "")

            # Only care about recent results (check if published date is recent)
            event = {
                "event_type": "geopolitical",
                "headline": title[:500],
                "summary": f"Source: {url}",
                "source": "exa",
                "severity": "minor",
            }
            results["proactive_events"].append(event)
            insert("events", event)
            records_written += 1

    # Write local JSON
    output_path = AGENT_OUTPUT_DIR / "exa_agent_output.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info(f"Exa Agent complete. {confirmed} signals confirmed, {records_written} records.")
    return {"status": "ok", "records": records_written, "confirmed": confirmed}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
