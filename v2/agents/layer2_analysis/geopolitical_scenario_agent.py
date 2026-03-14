"""
Agent 13: Geopolitical Scenario Agent
Reads from Supabase events and signals tables.
Uses CONFLICT_START_DATE to calculate conflict day.
Updates scenario probabilities for 4 scenarios.
Writes to scenarios Supabase table.
"""
import json, logging, sys
from pathlib import Path
from datetime import datetime, timezone, date

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import *
from lib.supabase_client import insert, select
from lib.safe_scalar import safe_scalar

logger = logging.getLogger("ardi.geopolitical_scenario")

LOCAL_OUTPUT = AGENT_OUTPUT_DIR / "geopolitical_scenario_output.json"

# Base probabilities
SCENARIOS = {
    "A": {"name": "Rapid Ceasefire", "base_probability": 35.0},
    "B": {"name": "Prolonged Stalemate", "base_probability": 40.0},
    "C": {"name": "Major Escalation", "base_probability": 20.0},
    "D": {"name": "Regime Change", "base_probability": 5.0},
}

MARKET_IMPACT = {
    "A": "Bullish equities, oil drops 10-15%, defense sells off, travel/airlines rally",
    "B": "Sideways chop, elevated VIX, defense steady, energy elevated",
    "C": "Sharp equity sell-off, oil spikes 20%+, gold surges, flight to safety",
    "D": "Extreme volatility, all bets off, massive uncertainty premium",
}


def _conflict_day():
    """Days since conflict start."""
    try:
        start = date.fromisoformat(CONFLICT_START_DATE)
        today = date.fromisoformat("2026-03-14")  # use current date
        return (today - start).days
    except Exception:
        return 0


def _count_signals(signals, signal_type):
    """Count signals of a specific type."""
    count = 0
    for s in signals:
        if isinstance(s, dict):
            st = s.get("signal_type", "") or s.get("type", "")
            if signal_type.lower() in st.lower():
                count += 1
    return count


def run():
    logger.info("Geopolitical Scenario Agent starting")
    now = datetime.now(timezone.utc).isoformat()
    day = _conflict_day()

    # Read events from Supabase (events table has event_type column, not category)
    try:
        events = select("events") or []
    except Exception as e:
        logger.warning(f"Could not read events: {e}")
        events = []

    # Filter geopolitical events by event_type
    geo_events = [e for e in events if isinstance(e, dict) and
                  "geopolitical" in (e.get("event_type", "") or "").lower()]

    # Build a combined list using event_type as signal_type for counting
    all_signals = []
    for e in events:
        if isinstance(e, dict):
            all_signals.append({"signal_type": e.get("event_type", "")})

    # Count signal types
    ceasefire_count = _count_signals(all_signals, "ceasefire")
    danger_count = _count_signals(all_signals, "danger")
    escalation_count = _count_signals(all_signals + geo_events, "escalation")

    # --- Scenario A: Rapid Ceasefire ---
    prob_a = 35.0
    reason_a = "base probability"
    # Each ceasefire signal adds 3%, capped
    if ceasefire_count > 0:
        boost = min(ceasefire_count * 3.0, 20.0)
        prob_a += boost
        reason_a = f"+{boost:.0f}% from {ceasefire_count} ceasefire signals"
    # Decrease if many days pass without ceasefire
    if day > 30 and ceasefire_count == 0:
        decay = min((day - 30) * 0.5, 15.0)
        prob_a -= decay
        reason_a = f"decayed {decay:.0f}% (day {day}, no ceasefire signals)"
    prob_a = max(5.0, min(prob_a, 60.0))

    # --- Scenario B: Prolonged Stalemate ---
    prob_b = 40.0
    reason_b = "base probability"
    # Increases as days pass without resolution
    if day > 14:
        stalemate_boost = min((day - 14) * 0.3, 20.0)
        prob_b += stalemate_boost
        reason_b = f"+{stalemate_boost:.1f}% (day {day}, no resolution)"
    # Decrease if ceasefire signals appear
    if ceasefire_count >= 3:
        prob_b -= 10.0
        reason_b += "; -10% (multiple ceasefire signals)"
    prob_b = max(10.0, min(prob_b, 65.0))

    # --- Scenario C: Major Escalation ---
    prob_c = 20.0
    reason_c = "base probability"
    if danger_count > 0:
        escalation_boost = min(danger_count * 4.0, 30.0)
        prob_c += escalation_boost
        reason_c = f"+{escalation_boost:.0f}% from {danger_count} danger signals"
    if escalation_count > 0:
        extra = min(escalation_count * 3.0, 15.0)
        prob_c += extra
        reason_c += f"; +{extra:.0f}% from {escalation_count} escalation events"
    prob_c = max(5.0, min(prob_c, 50.0))

    # --- Scenario D: Regime Change ---
    prob_d = 5.0
    reason_d = "mostly static (low probability tail risk)"
    # Only adjust if explicit regime-change signals
    regime_count = _count_signals(all_signals + events, "regime")
    if regime_count > 0:
        prob_d += min(regime_count * 2.0, 10.0)
        reason_d = f"+{min(regime_count * 2.0, 10.0):.0f}% from regime signals"
    prob_d = max(2.0, min(prob_d, 15.0))

    # Normalize to 100%
    total = prob_a + prob_b + prob_c + prob_d
    if total > 0:
        prob_a = round((prob_a / total) * 100, 1)
        prob_b = round((prob_b / total) * 100, 1)
        prob_c = round((prob_c / total) * 100, 1)
        prob_d = round(100.0 - prob_a - prob_b - prob_c, 1)

    scenarios_output = [
        {
            "scenario_id": "A",
            "scenario_name": "Rapid Ceasefire",
            "probability": prob_a,
            "previous_probability": 35.0,
            "change_reason": reason_a,
            "market_impact": MARKET_IMPACT["A"],
        },
        {
            "scenario_id": "B",
            "scenario_name": "Prolonged Stalemate",
            "probability": prob_b,
            "previous_probability": 40.0,
            "change_reason": reason_b,
            "market_impact": MARKET_IMPACT["B"],
        },
        {
            "scenario_id": "C",
            "scenario_name": "Major Escalation",
            "probability": prob_c,
            "previous_probability": 20.0,
            "change_reason": reason_c,
            "market_impact": MARKET_IMPACT["C"],
        },
        {
            "scenario_id": "D",
            "scenario_name": "Regime Change",
            "probability": prob_d,
            "previous_probability": 5.0,
            "change_reason": reason_d,
            "market_impact": MARKET_IMPACT["D"],
        },
    ]

    result = {
        "agent": "geopolitical_scenario",
        "timestamp": now,
        "conflict_day": day,
        "ceasefire_signals": ceasefire_count,
        "danger_signals": danger_count,
        "escalation_events": escalation_count,
        "scenarios": scenarios_output,
    }

    # Write local output
    try:
        LOCAL_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        with open(LOCAL_OUTPUT, "w") as f:
            json.dump(result, f, indent=2)
        logger.info(f"Wrote {LOCAL_OUTPUT}")
    except Exception as e:
        logger.error(f"Failed to write local output: {e}")

    # Write to Supabase scenarios table (valid columns only)
    for s in scenarios_output:
        try:
            row = {
                "scenario_id": s["scenario_id"],
                "scenario_name": s["scenario_name"],
                "probability": s["probability"],
                "previous_probability": s["previous_probability"],
                "change_reason": s["change_reason"],
                "market_impact": s["market_impact"],
            }
            insert("scenarios", row)
        except Exception as e:
            logger.error(f"Supabase write failed for scenario {s['scenario_id']}: {e}")

    logger.info("Geopolitical Scenario Agent complete")
    result["status"] = "ok"
    result["records"] = result.get("records", 0)
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
