"""
Regime Change Agent — Layer 3 Signals
Ardi Market Command Center v2

Reads regime_agent_output.json. Compares to previous regime.
If the macro regime has changed, sends alert.
"""
import json, logging, sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import *
from lib.supabase_client import insert, select, get_client
from lib.ntfy_client import send_alert
from lib.safe_scalar import safe_scalar

logger = logging.getLogger("ardi.layer3.regime_change")


def _load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load {path}: {e}")
        return {}


def _get_previous_regime():
    """Get the most recent regime change signal to find the last known regime."""
    rows = select("signals", {"signal_type": "regime_change"}, order_by="-created_at", limit=1)
    if rows:
        details = rows[0].get("details", "")
        # Parse "Regime: X" or "New regime: X" from details
        for prefix in ("new regime: ", "regime: ", "current regime: "):
            if prefix in details.lower():
                idx = details.lower().index(prefix) + len(prefix)
                regime = details[idx:].split(".")[0].split(",")[0].strip()
                return regime
    return None


def run():
    logger.info("Regime change agent starting...")
    now_str = datetime.now(timezone.utc).isoformat()
    results = {"timestamp": now_str}
    records_written = 0

    # Read current regime from regime_agent output
    regime_data = _load_json(AGENT_OUTPUT_DIR / "regime_agent_output.json")
    current_regime = regime_data.get("regime") or regime_data.get("current_regime") or regime_data.get("classification")

    if not current_regime:
        logger.warning("Could not determine current regime from regime_agent_output.json")
        results["status"] = "no_data"
        results["current_regime"] = None

        output_path = AGENT_OUTPUT_DIR / "regime_change_agent_output.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2, default=str)
        return {"status": "ok", "records": 0, "regime_changed": False}

    # Get previous regime
    previous_regime = _get_previous_regime()
    regime_changed = previous_regime is not None and current_regime != previous_regime

    confidence_score = safe_scalar(regime_data.get("confidence") or regime_data.get("confidence_score"), 0.5)
    evidence = regime_data.get("evidence") or regime_data.get("factors") or []

    results["current_regime"] = current_regime
    results["previous_regime"] = previous_regime
    results["regime_changed"] = regime_changed
    results["confidence"] = confidence_score

    if isinstance(evidence, list):
        evidence_str = "; ".join(str(e) for e in evidence[:5])
    elif isinstance(evidence, dict):
        evidence_str = "; ".join(f"{k}: {v}" for k, v in list(evidence.items())[:5])
    else:
        evidence_str = str(evidence)[:200]

    # Always write current regime to signals for tracking
    if regime_changed:
        details = f"REGIME CHANGED: {previous_regime} -> {current_regime}. Evidence: {evidence_str}"
        status = "fired"
    else:
        details = f"Current regime: {current_regime}. No change from previous. Evidence: {evidence_str}"
        status = "not_fired"

    signal_record = {
        "signal_type": "regime_change",
        "signal_name": "regime_shift",
        "status": status,
        "confidence": confidence_score,
        "details": details,
        "source": "regime_change_agent",
        "second_source": "regime_agent",
        "action_required": "rebalance_review" if regime_changed else "none",
    }
    insert("signals", signal_record)
    records_written += 1

    # Send alert if regime changed
    if regime_changed:
        # Map regimes to action guidance
        regime_actions = {
            "RISK_ON_GROWTH": "Consider increasing equity exposure. Growth/tech favored.",
            "RISK_OFF_CONTRACTION": "Reduce risk. Increase cash/gold. Defensive sectors.",
            "INFLATIONARY_SHOCK": "Energy/commodities favored. Avoid long-duration bonds.",
            "DEFLATIONARY_SHOCK": "Bonds rally. Cash is king. Avoid commodities.",
        }
        action_guidance = regime_actions.get(current_regime, "Review portfolio allocation.")

        send_alert(
            title=f"REGIME CHANGE: {previous_regime} -> {current_regime}",
            message=f"Market regime has shifted.\n\nNew regime: {current_regime}\nPrevious: {previous_regime}\nConfidence: {confidence_score:.0%}\n\nAction: {action_guidance}\n\nEvidence: {evidence_str}",
            priority="high",
            tags=["warning", "chart_with_upwards_trend"],
        )
        logger.warning(f"Regime change detected: {previous_regime} -> {current_regime}")

    # Write local JSON
    output_path = AGENT_OUTPUT_DIR / "regime_change_agent_output.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info(f"Regime change agent done — changed: {regime_changed}, {records_written} records written")
    return {"status": "ok", "records": records_written, "regime_changed": regime_changed}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
