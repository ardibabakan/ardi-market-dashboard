"""
Regime Classification Agent — Layer 2 Analysis
Ardi Market Command Center v2

Classifies the macro environment into one of four regimes:
RISK_ON_GROWTH, RISK_OFF_CONTRACTION, INFLATIONARY_SHOCK, DEFLATIONARY_SHOCK.
"""
import json, logging, sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import AGENT_OUTPUT_DIR
from lib.supabase_client import insert
from lib.safe_scalar import safe_scalar

logger = logging.getLogger("ardi.layer2.regime")


def _load_fred_data():
    path = AGENT_OUTPUT_DIR / "fred_agent_output.json"
    if not path.exists():
        logger.error("fred_agent_output.json not found")
        return None
    with open(path) as f:
        return json.load(f)


def _get_value(fred, series_id, field="value"):
    entry = fred.get(series_id)
    if entry is None:
        return None
    return entry.get(field)


def _classify_regime(fred):
    """Classify the current market regime based on FRED data."""
    evidence = []

    # Credit spread
    hy_spread = _get_value(fred, "BAMLH0A0HYM2")
    hy_dir = _get_value(fred, "BAMLH0A0HYM2", "direction")

    # Yield curve
    yc = _get_value(fred, "T10Y2Y")
    yc_dir = _get_value(fred, "T10Y2Y", "direction")

    # VIX
    vix = _get_value(fred, "VIXCLS")

    # Oil
    oil = _get_value(fred, "DCOILWTICO")
    oil_dir = _get_value(fred, "DCOILWTICO", "direction")

    # CPI
    cpi_dir = _get_value(fred, "CPIAUCSL", "direction")

    # Scoring
    risk_off_score = 0
    inflation_score = 0
    deflation_score = 0
    growth_score = 0

    # Credit spread analysis
    if hy_spread is not None:
        if hy_spread > 5.0:
            risk_off_score += 2
            evidence.append(f"High-yield spread elevated at {hy_spread:.2f}%")
        elif hy_spread < 3.0:
            growth_score += 1
            evidence.append(f"Credit spreads tight at {hy_spread:.2f}%")
    if hy_dir == "up":
        risk_off_score += 1
        evidence.append("Credit spreads widening")
    elif hy_dir == "down":
        growth_score += 1
        evidence.append("Credit spreads narrowing")

    # Yield curve
    if yc is not None:
        if yc < 0:
            risk_off_score += 1
            evidence.append(f"Yield curve inverted: {yc:.2f}%")
        else:
            growth_score += 1
            evidence.append(f"Yield curve positive: {yc:.2f}%")

    # VIX
    if vix is not None:
        if vix > 30:
            risk_off_score += 2
            evidence.append(f"VIX elevated at {vix:.1f}")
        elif vix > 20:
            risk_off_score += 1
            evidence.append(f"VIX moderately elevated at {vix:.1f}")
        else:
            growth_score += 1
            evidence.append(f"VIX calm at {vix:.1f}")

    # Oil
    if oil_dir == "up":
        inflation_score += 1
        evidence.append("Oil prices rising")
    elif oil_dir == "down":
        deflation_score += 1
        evidence.append("Oil prices falling")

    # CPI
    if cpi_dir == "up":
        inflation_score += 2
        evidence.append("CPI trending up — inflationary pressure")
    elif cpi_dir == "down":
        deflation_score += 1
        evidence.append("CPI trending down — disinflationary")

    # Determine regime
    scores = {
        "RISK_ON_GROWTH": growth_score,
        "RISK_OFF_CONTRACTION": risk_off_score,
        "INFLATIONARY_SHOCK": inflation_score,
        "DEFLATIONARY_SHOCK": deflation_score,
    }
    regime = max(scores, key=scores.get)
    max_score = scores[regime]
    total = sum(scores.values()) or 1
    confidence = round(max_score / total, 2)

    # Implications
    implications_map = {
        "RISK_ON_GROWTH": "Favor equities over safe havens. Defence names may underperform broad market.",
        "RISK_OFF_CONTRACTION": "Favor GLD, reduce equity exposure. Defence holds relative value.",
        "INFLATIONARY_SHOCK": "Favor energy (XOM, LNG), commodities, GLD. Avoid long-duration bonds.",
        "DEFLATIONARY_SHOCK": "Favor treasuries, reduce energy. Defence budget risk if recession deepens.",
    }

    return {
        "regime_type": regime,
        "confidence": confidence,
        "supporting_evidence": evidence,
        "implications": implications_map.get(regime, ""),
        "scores": scores,
    }


def run():
    """Main entry point."""
    logger.info("Regime Agent starting...")

    fred = _load_fred_data()
    if fred is None:
        return {"status": "error", "reason": "no FRED data"}

    result = _classify_regime(fred)

    # Write to Supabase
    insert("regime", {
        "regime_type": result["regime_type"],
        "confidence": result["confidence"],
        "supporting_evidence": json.dumps(result["supporting_evidence"]),
        "implications": result["implications"],
    })

    # Write local JSON
    output_path = AGENT_OUTPUT_DIR / "regime_agent_output.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2, default=str)

    logger.info(f"Regime Agent complete. Regime: {result['regime_type']}")
    return {"status": "ok", "data": result}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
