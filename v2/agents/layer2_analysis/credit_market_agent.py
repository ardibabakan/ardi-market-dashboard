"""
Credit Market Agent — Layer 2 Analysis
Ardi Market Command Center v2

Reads fred_agent_output.json for BAMLH0A0HYM2 (high-yield spread).
Calculates current spread, direction, and stress level.
Writes to macro_data Supabase table.
"""
import json, logging, sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import AGENT_OUTPUT_DIR, DANGER_CREDIT_SPREAD_WIDEN_BPS
from lib.supabase_client import insert
from lib.safe_scalar import safe_scalar

logger = logging.getLogger("ardi.layer2.credit_market")

# Historical context for high-yield spreads
# Normal: 3-4%, Elevated: 4-5%, Stressed: 5-7%, Crisis: 7%+
STRESS_LEVELS = [
    (7.0,  "CRISIS",   "Credit markets in crisis — risk of contagion"),
    (5.0,  "STRESSED", "Significant credit stress — flight to quality active"),
    (4.0,  "ELEVATED", "Credit conditions tightening — monitor closely"),
    (3.0,  "NORMAL",   "Credit conditions normal — risk appetite healthy"),
    (0.0,  "TIGHT",    "Spreads very tight — possible complacency"),
]


def _load_fred_data():
    path = AGENT_OUTPUT_DIR / "fred_agent_output.json"
    if not path.exists():
        logger.error("fred_agent_output.json not found")
        return None
    with open(path) as f:
        return json.load(f)


def _classify_stress(spread):
    """Classify credit stress level based on spread."""
    for threshold, level, description in STRESS_LEVELS:
        if spread >= threshold:
            return level, description
    return "UNKNOWN", "Unable to classify"


def run():
    """Main entry point."""
    logger.info("Credit Market Agent starting...")

    fred = _load_fred_data()
    if fred is None:
        return {"status": "error", "reason": "no FRED data"}

    hy_data = fred.get("BAMLH0A0HYM2")
    if hy_data is None:
        return {"status": "error", "reason": "no high-yield spread data in FRED output"}

    current_spread = safe_scalar(hy_data.get("value"))
    previous_spread = safe_scalar(hy_data.get("previous_value"))
    direction = hy_data.get("direction", "flat")

    if current_spread == 0:
        return {"status": "error", "reason": "invalid spread value"}

    stress_level, stress_desc = _classify_stress(current_spread)

    # Calculate basis point change
    spread_change_bps = round((current_spread - previous_spread) * 100, 1) if previous_spread else 0
    danger_flag = spread_change_bps >= DANGER_CREDIT_SPREAD_WIDEN_BPS

    # Portfolio implications
    implications = []
    if stress_level in ("CRISIS", "STRESSED"):
        implications.append("Reduce equity exposure — favour GLD and treasuries")
        implications.append("Defence names typically outperform in credit stress")
    if direction == "up" and spread_change_bps > 50:
        implications.append("Rapid credit deterioration — avoid new positions")
    if stress_level == "TIGHT":
        implications.append("Tight spreads may signal complacency — maintain stops")

    result = {
        "series_id": "BAMLH0A0HYM2",
        "series_name": "High-Yield Credit Spread (OAS)",
        "current_spread": round(current_spread, 4),
        "previous_spread": round(previous_spread, 4) if previous_spread else None,
        "direction": direction,
        "change_bps": spread_change_bps,
        "stress_level": stress_level,
        "stress_description": stress_desc,
        "danger_flag": danger_flag,
        "implications": implications,
    }

    # Write to Supabase macro_data
    insert("macro_data", {
        "series_id": "credit_market_analysis",
        "series_name": "Credit Market Stress Analysis",
        "value": current_spread,
        "previous_value": previous_spread,
        "change_direction": direction,
        "significance": f"{stress_level}: {stress_desc}" + (
            f" | DANGER: spread widened {spread_change_bps:.0f} bps" if danger_flag else ""),
    })

    # Write local JSON
    output_path = AGENT_OUTPUT_DIR / "credit_market_agent_output.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2, default=str)

    logger.info(f"Credit Market Agent complete. Stress: {stress_level}, Spread: {current_spread:.2f}%")
    return {"status": "ok", "data": result}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
