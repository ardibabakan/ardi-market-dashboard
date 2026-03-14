"""
GPR Agent — Layer 1 Data Collection
Ardi Market Command Center v2

Collects: Geopolitical Risk Index from FRED or direct source.
"""
import json
import logging
import sys
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta
from io import StringIO

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import AGENT_OUTPUT_DIR
from lib.supabase_client import insert

logger = logging.getLogger("ardi.layer1.gpr")

# Historical GPR benchmarks
GPR_BENCHMARKS = {
    "gulf_war_1991": 350,
    "9_11_2001": 450,
    "ukraine_2022": 400,
    "normal_range": "50-150",
}


def run():
    """Main entry point."""
    logger.info("GPR Agent starting...")
    import requests
    import pandas as pd

    results = {"gpr_current": None, "benchmarks": GPR_BENCHMARKS}
    records_written = 0

    # Try FRED first (GPRC series)
    try:
        end = datetime.now()
        start = end - timedelta(days=90)
        resp = requests.get(
            "https://fred.stlouisfed.org/graph/fredgraph.csv",
            params={
                "id": "GPRH",
                "cosd": start.strftime("%Y-%m-%d"),
                "coed": end.strftime("%Y-%m-%d"),
            },
            timeout=15
        )

        if resp.status_code == 200 and "DATE" in resp.text:
            df = pd.read_csv(StringIO(resp.text))
            col = df.columns[-1]
            df[col] = pd.to_numeric(df[col], errors="coerce")
            df = df.dropna(subset=[col])

            if not df.empty:
                current = float(df[col].iloc[-1])
                previous = float(df[col].iloc[-21]) if len(df) > 20 else float(df[col].iloc[0])

                # Classify
                if current > 300:
                    level = "EXTREME"
                elif current > 200:
                    level = "VERY_HIGH"
                elif current > 150:
                    level = "HIGH"
                elif current > 100:
                    level = "ELEVATED"
                else:
                    level = "NORMAL"

                results["gpr_current"] = current
                results["gpr_previous"] = previous
                results["gpr_level"] = level

                insert("macro_data", {
                    "series_id": "GPR",
                    "series_name": "Geopolitical Risk Index",
                    "value": current,
                    "previous_value": previous,
                    "change_direction": "up" if current > previous else "down" if current < previous else "flat",
                    "significance": f"GPR level: {level}" if level in ("EXTREME", "VERY_HIGH") else None,
                })
                records_written += 1
        else:
            logger.warning("FRED GPR series not available — trying alternate")

    except Exception as e:
        logger.warning(f"GPR FRED fetch failed: {e}")

    # If no data from FRED, note it
    if results["gpr_current"] is None:
        results["note"] = "GPR data unavailable from FRED. Manual check at matteoiacoviello.com/gpr.htm"

    # Write local JSON
    output_path = AGENT_OUTPUT_DIR / "gpr_agent_output.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info(f"GPR Agent complete. {records_written} records.")
    return {"status": "ok", "records": records_written}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
