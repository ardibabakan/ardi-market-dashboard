"""
EIA Agent — Layer 1 Data Collection
Ardi Market Command Center v2

Collects: US energy data — oil inventory, production, imports.
"""
import json
import logging
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import EIA_KEY, AGENT_OUTPUT_DIR
from lib.supabase_client import insert

logger = logging.getLogger("ardi.layer1.eia")

EIA_BASE = "https://api.eia.gov/v2/seriesid/"

SERIES = {
    "PET.WCESTUS1.W": {"name": "US Crude Oil Inventory (Weekly)"},
    "PET.WCRFPUS2.W": {"name": "US Crude Oil Production (Weekly)"},
    "PET.WCEIMUS2.W": {"name": "US Crude Oil Imports (Weekly)"},
}


def _fetch_eia_series(series_id):
    """Fetch a single EIA series via the v2 API."""
    import requests

    try:
        url = f"{EIA_BASE}{series_id}"
        resp = requests.get(url, params={
            "api_key": EIA_KEY,
            "out": "json",
        }, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        # v2 API returns response.data as list of [period, value] or similar
        records = data.get("response", {}).get("data", [])
        if not records:
            # Try legacy v1 API as fallback
            v1_url = f"https://api.eia.gov/series/?api_key={EIA_KEY}&series_id={series_id}"
            resp2 = requests.get(v1_url, timeout=15)
            if resp2.status_code == 200:
                v1_data = resp2.json()
                series_data = v1_data.get("series", [{}])[0].get("data", [])
                if series_data and len(series_data) >= 2:
                    return float(series_data[0][1]), float(series_data[1][1])
            return None, None

        current = float(records[0].get("value", 0))
        previous = float(records[1].get("value", 0)) if len(records) > 1 else None
        return current, previous
    except Exception as e:
        logger.warning(f"EIA fetch failed for {series_id}: {e}")
        return None, None


def run():
    """Main entry point."""
    logger.info("EIA Agent starting...")

    if not EIA_KEY:
        logger.warning("EIA_KEY not set — skipping")
        return {"status": "skipped", "reason": "no_api_key", "records": 0}

    results = {}
    records_written = 0

    for key, series_info in SERIES.items():
        time.sleep(0.5)
        current, previous = _fetch_eia_series(key)

        if current is None:
            logger.warning(f"No EIA data for {key}")
            continue

        change = None
        significance = None
        if previous:
            change = current - previous
            if key == "WCESTUS1":  # Inventory
                if change < -5000:  # draw > 5M barrels
                    significance = "BULLISH: Large inventory draw (>5M barrels)"
                elif change > 5000:  # build > 5M barrels
                    significance = "BEARISH: Large inventory build (>5M barrels)"

        entry = {
            "series_id": key,
            "series_name": series_info["name"],
            "value": current,
            "previous_value": previous,
            "weekly_change": change,
            "significance": significance,
        }
        results[key] = entry

        insert("macro_data", {
            "series_id": key,
            "series_name": series_info["name"],
            "value": current,
            "previous_value": previous,
            "change_direction": "draw" if change and change < 0 else "build" if change and change > 0 else "flat",
            "significance": significance,
        })
        records_written += 1

    # Write local JSON
    output_path = AGENT_OUTPUT_DIR / "eia_agent_output.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info(f"EIA Agent complete. {records_written} records.")
    return {"status": "ok", "records": records_written}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
