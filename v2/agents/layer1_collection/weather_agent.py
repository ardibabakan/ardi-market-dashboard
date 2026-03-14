"""
Weather Agent — Layer 1 Data Collection
Ardi Market Command Center v2

Collects: Natural disasters that could affect markets.
Hurricanes in Gulf (oil), major earthquakes, energy infrastructure events.
Safety net — often finds nothing, and that's fine.
"""
import json
import logging
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import AGENT_OUTPUT_DIR
from lib.supabase_client import insert

logger = logging.getLogger("ardi.layer1.weather")

USGS_EARTHQUAKE_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"


def run():
    """Main entry point."""
    logger.info("Weather Agent starting...")
    import requests

    results = {"earthquakes": [], "hurricanes": [], "status": "clear"}
    records_written = 0

    # USGS Earthquakes — significant events in last 24h
    try:
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=1)
        resp = requests.get(USGS_EARTHQUAKE_URL, params={
            "format": "geojson",
            "starttime": start.strftime("%Y-%m-%dT%H:%M:%S"),
            "endtime": end.strftime("%Y-%m-%dT%H:%M:%S"),
            "minmagnitude": 5.5,  # Only significant quakes
        }, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        features = data.get("features", [])
        for eq in features:
            props = eq.get("properties", {})
            mag = props.get("mag", 0)
            place = props.get("place", "Unknown")
            tsunami = props.get("tsunami", 0)

            entry = {
                "magnitude": mag,
                "location": place,
                "tsunami_warning": bool(tsunami),
                "time": props.get("time"),
            }
            results["earthquakes"].append(entry)

            if mag >= 6.5:
                results["status"] = "alert"
                insert("events", {
                    "event_type": "natural_disaster",
                    "headline": f"Earthquake: M{mag} — {place}",
                    "summary": f"Magnitude {mag} earthquake at {place}. Tsunami warning: {bool(tsunami)}",
                    "source": "usgs",
                    "severity": "major" if mag >= 7.0 else "moderate",
                })
                records_written += 1

    except Exception as e:
        logger.warning(f"USGS earthquake check failed: {e}")

    # NHC Active hurricanes check (Atlantic basin)
    try:
        resp = requests.get(
            "https://www.nhc.noaa.gov/CurrentSummaries.json",
            timeout=10
        )
        if resp.status_code == 200:
            nhc_data = resp.json()
            active = nhc_data.get("activeStorms", [])
            for storm in active:
                name = storm.get("name", "Unknown")
                category = storm.get("classification", "")
                results["hurricanes"].append({"name": name, "category": category})
                results["status"] = "alert"

                insert("events", {
                    "event_type": "natural_disaster",
                    "headline": f"Active hurricane: {name} ({category})",
                    "summary": f"Active storm in Atlantic basin — potential energy infrastructure impact",
                    "source": "nhc_noaa",
                    "severity": "moderate",
                })
                records_written += 1
    except Exception as e:
        logger.info(f"NHC check failed (may not have active storms): {e}")

    # Write local JSON
    output_path = AGENT_OUTPUT_DIR / "weather_agent_output.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info(f"Weather Agent complete. Status: {results['status']}. {records_written} records.")
    return {"status": "ok", "records": records_written, "weather_status": results["status"]}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
