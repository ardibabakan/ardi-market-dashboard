"""
FRED Agent — Layer 1 Data Collection
Ardi Market Command Center v2

Collects: Macro data from Federal Reserve FRED.
Oil, credit spreads, yields, CPI, unemployment, etc.
"""
import json
import logging
import sys
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta
from io import StringIO

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import AGENT_OUTPUT_DIR, DANGER_CREDIT_SPREAD_WIDEN_BPS
from lib.supabase_client import insert
from lib.data_validator import validate_price

logger = logging.getLogger("ardi.layer1.fred")

FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"

SERIES = {
    "DCOILWTICO":   "WTI Crude Oil Daily",
    "DCOILBRENTEU": "Brent Crude Daily",
    "BAMLH0A0HYM2": "High-Yield Credit Spread",
    "DGS10":        "10-Year Treasury Yield",
    "DGS2":         "2-Year Treasury Yield",
    "T10Y2Y":       "Yield Curve 2s10s Spread",
    "DTWEXBGS":     "USD Trade-Weighted Index",
    "FEDFUNDS":     "Federal Funds Rate",
    "UNRATE":       "Unemployment Rate",
    "CPIAUCSL":     "CPI All Urban Consumers",
    "UMCSENT":      "Consumer Sentiment",
    "VIXCLS":       "VIX Daily Close",
}


def _fetch_fred_series(series_id, days_back=90):
    """Download a FRED series as CSV and return recent values."""
    import requests
    import pandas as pd

    end = datetime.now()
    start = end - timedelta(days=days_back)

    try:
        resp = requests.get(FRED_CSV_URL, params={
            "id": series_id,
            "cosd": start.strftime("%Y-%m-%d"),
            "coed": end.strftime("%Y-%m-%d"),
        }, timeout=15)
        resp.raise_for_status()

        df = pd.read_csv(StringIO(resp.text))
        if df.empty:
            return None, None

        # FRED uses "." for missing values
        col = df.columns[-1]
        df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=[col])

        if df.empty:
            return None, None

        current = float(df[col].iloc[-1])
        # Get value from ~30 days ago for comparison
        if len(df) > 20:
            previous = float(df[col].iloc[-21])
        elif len(df) > 1:
            previous = float(df[col].iloc[0])
        else:
            previous = current

        return current, previous

    except Exception as e:
        logger.warning(f"FRED fetch failed for {series_id}: {e}")
        return None, None


def run():
    """Main entry point."""
    logger.info("FRED Agent starting...")
    results = {}
    records_written = 0

    for series_id, series_name in SERIES.items():
        time.sleep(0.5)
        current, previous = _fetch_fred_series(series_id)

        if current is None:
            logger.warning(f"No data for {series_id}")
            continue

        # Direction
        if previous:
            diff = current - previous
            if abs(diff) < 0.001:
                direction = "flat"
            elif diff > 0:
                direction = "up"
            else:
                direction = "down"
        else:
            direction = "flat"

        # Significance check
        significance = None
        if series_id == "BAMLH0A0HYM2" and previous:
            spread_change_bps = (current - previous) * 100
            if spread_change_bps >= DANGER_CREDIT_SPREAD_WIDEN_BPS:
                significance = "DANGER: credit spread widened 100+ bps"
            elif spread_change_bps >= 50:
                significance = "WARNING: credit stress — spread widened 50+ bps"

        if series_id == "VIXCLS" and current:
            if current > 40:
                significance = "DANGER: VIX above 40"
            elif current > 30:
                significance = "ELEVATED: VIX above 30"

        entry = {
            "series_id": series_id,
            "series_name": series_name,
            "value": round(current, 4),
            "previous_value": round(previous, 4) if previous else None,
            "direction": direction,
            "significance": significance,
        }
        results[series_id] = entry

        insert("macro_data", {
            "series_id": series_id,
            "series_name": series_name,
            "value": entry["value"],
            "previous_value": entry["previous_value"],
            "change_direction": direction,
            "significance": significance,
        })
        records_written += 1

    # Write local JSON
    output_path = AGENT_OUTPUT_DIR / "fred_agent_output.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info(f"FRED Agent complete. {records_written} records.")
    return {"status": "ok", "records": records_written}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
