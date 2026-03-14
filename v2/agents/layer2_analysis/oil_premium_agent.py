"""
Oil War Premium Agent — Layer 2 Analysis
Ardi Market Command Center v2

Reads yahoo_agent_output.json for CL=F (WTI crude) price.
Uses config.OIL_BASELINE (pre-conflict WTI) to calculate
war premium, scenario projections, and portfolio impact.
"""
import json, logging, sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import (
    OIL_BASELINE, AGENT_OUTPUT_DIR, PLANNED_POSITIONS,
    DANGER_OIL_SPIKE_PCT, CEASEFIRE_OIL_DROP_PCT,
)
from lib.supabase_client import insert
from lib.safe_scalar import safe_scalar

logger = logging.getLogger("ardi.layer2.oil_premium")

# How each holding is affected by oil prices
OIL_SENSITIVITY = {
    "LMT":   {"direction": "low",      "note": "Minor oil sensitivity — defence ops"},
    "RTX":   {"direction": "low",      "note": "Minor oil sensitivity — defence ops"},
    "LNG":   {"direction": "positive", "note": "LNG revenues rise with energy prices"},
    "GLD":   {"direction": "positive", "note": "Gold benefits from inflation/uncertainty"},
    "ITA":   {"direction": "low",      "note": "Defence ETF — mixed sensitivity"},
    "XOM":   {"direction": "positive", "note": "Direct oil revenue beneficiary"},
    "CEG":   {"direction": "neutral",  "note": "Nuclear — indirect benefit if fossil costs rise"},
    "BAESY": {"direction": "low",      "note": "EU defence — minor oil sensitivity"},
}


def _load_yahoo_data():
    path = AGENT_OUTPUT_DIR / "yahoo_agent_output.json"
    if not path.exists():
        logger.error("yahoo_agent_output.json not found")
        return None
    with open(path) as f:
        return json.load(f)


def _get_oil_price(yahoo_data):
    """Extract CL=F price from yahoo agent output."""
    # Try various structures
    if "CL=F" in yahoo_data:
        entry = yahoo_data["CL=F"]
        if isinstance(entry, dict):
            return safe_scalar(entry.get("price") or entry.get("close") or entry.get("value"))
        return safe_scalar(entry)

    # Search in commodities section
    commodities = yahoo_data.get("commodities", {})
    if "CL=F" in commodities:
        entry = commodities["CL=F"]
        if isinstance(entry, dict):
            return safe_scalar(entry.get("price") or entry.get("close") or entry.get("value"))
        return safe_scalar(entry)

    return None


def run():
    """Main entry point."""
    logger.info("Oil Premium Agent starting...")

    yahoo_data = _load_yahoo_data()
    if yahoo_data is None:
        return {"status": "error", "reason": "no Yahoo data"}

    current_oil = _get_oil_price(yahoo_data)
    if current_oil is None or current_oil <= 0:
        return {"status": "error", "reason": "could not extract CL=F price"}

    # War premium calculation
    premium_dollar = round(current_oil - OIL_BASELINE, 2)
    premium_pct = round((premium_dollar / OIL_BASELINE) * 100, 2)

    # Scenario projections
    scenarios = {
        "ceasefire": {
            "projected_oil": round(OIL_BASELINE * 1.02, 2),  # slight premium remains
            "change_pct": round(((OIL_BASELINE * 1.02 - current_oil) / current_oil) * 100, 2),
            "description": "Oil returns near pre-conflict baseline with small residual premium",
        },
        "escalation_moderate": {
            "projected_oil": round(current_oil * 1.15, 2),
            "change_pct": 15.0,
            "description": "15% spike on supply disruption fears",
        },
        "escalation_severe": {
            "projected_oil": round(current_oil * 1.30, 2),
            "change_pct": 30.0,
            "description": "30% spike on major supply disruption or strait closure",
        },
        "status_quo": {
            "projected_oil": round(current_oil, 2),
            "change_pct": 0.0,
            "description": "Current premium maintained — conflict continues at current intensity",
        },
    }

    # Signal flags
    is_danger_spike = premium_pct >= DANGER_OIL_SPIKE_PCT
    is_ceasefire_signal = premium_pct <= -CEASEFIRE_OIL_DROP_PCT

    # Portfolio impact assessment
    holdings_impact = {}
    for ticker, sensitivity in OIL_SENSITIVITY.items():
        impact = "neutral"
        if premium_pct > 10:
            if sensitivity["direction"] == "positive":
                impact = "benefit"
            elif sensitivity["direction"] == "low":
                impact = "minor_drag"
        elif premium_pct < -5:
            if sensitivity["direction"] == "positive":
                impact = "headwind"
            elif sensitivity["direction"] == "low":
                impact = "minor_benefit"
        holdings_impact[ticker] = {
            "impact": impact,
            "sensitivity": sensitivity["direction"],
            "note": sensitivity["note"],
        }

    result = {
        "current_oil": current_oil,
        "baseline_oil": OIL_BASELINE,
        "war_premium_dollar": premium_dollar,
        "war_premium_pct": premium_pct,
        "danger_spike": is_danger_spike,
        "ceasefire_signal": is_ceasefire_signal,
        "scenarios": scenarios,
        "holdings_impact": holdings_impact,
    }

    # Write to Supabase macro_data
    significance = None
    if is_danger_spike:
        significance = f"DANGER: Oil war premium {premium_pct:.1f}% above baseline"
    elif is_ceasefire_signal:
        significance = f"CEASEFIRE SIGNAL: Oil dropped {abs(premium_pct):.1f}% below baseline"
    elif premium_pct > 5:
        significance = f"ELEVATED: Oil premium {premium_pct:.1f}% above pre-conflict"

    insert("macro_data", {
        "series_id": "oil_war_premium",
        "series_name": "Oil War Premium Analysis",
        "value": current_oil,
        "previous_value": OIL_BASELINE,
        "change_direction": "up" if premium_pct > 0 else "down",
        "significance": significance,
    })

    # Write local JSON
    output_path = AGENT_OUTPUT_DIR / "oil_premium_agent_output.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2, default=str)

    logger.info(f"Oil Premium Agent complete. WTI: ${current_oil}, Premium: {premium_pct:.1f}%")
    return {"status": "ok", "data": result}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
