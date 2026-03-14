"""
Earnings Momentum Agent — Layer 2 Analysis
Ardi Market Command Center v2

Reads earnings_agent_output.json and classifies EPS revision
direction as UP/DOWN/FLAT for each portfolio ticker.
"""
import json, logging, sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import PLANNED_POSITIONS, AGENT_OUTPUT_DIR
from lib.supabase_client import insert
from lib.safe_scalar import safe_scalar

logger = logging.getLogger("ardi.layer2.earnings_momentum")

PORTFOLIO_TICKERS = list(PLANNED_POSITIONS.keys())


def _load_earnings_data():
    path = AGENT_OUTPUT_DIR / "earnings_agent_output.json"
    if not path.exists():
        logger.error("earnings_agent_output.json not found")
        return None
    with open(path) as f:
        return json.load(f)


def _classify_eps_revision(ticker_data):
    """Classify EPS revision direction from earnings data."""
    if not ticker_data:
        return "FLAT", "No earnings data available", {}

    # Try multiple data structures the earnings agent might produce
    estimates = ticker_data.get("estimates", {})
    actuals = ticker_data.get("actuals", {})
    surprises = ticker_data.get("surprises", [])
    eps_trend = ticker_data.get("eps_trend", {})

    direction = "FLAT"
    reasoning = []
    details = {}

    # Check EPS trend if available
    if eps_trend:
        current = eps_trend.get("current")
        previous = eps_trend.get("previous") or eps_trend.get("30d_ago")
        if current is not None and previous is not None:
            current = safe_scalar(current)
            previous = safe_scalar(previous)
            if previous != 0:
                change_pct = ((current - previous) / abs(previous)) * 100
                details["eps_change_pct"] = round(change_pct, 2)
                if change_pct > 2:
                    direction = "UP"
                    reasoning.append(f"EPS estimate revised up {change_pct:.1f}%")
                elif change_pct < -2:
                    direction = "DOWN"
                    reasoning.append(f"EPS estimate revised down {change_pct:.1f}%")
                else:
                    reasoning.append(f"EPS estimate stable ({change_pct:+.1f}%)")

    # Check surprise history
    if surprises and isinstance(surprises, list):
        positive_surprises = sum(1 for s in surprises if safe_scalar(s.get("surprise_pct", 0)) > 0)
        total = len(surprises)
        details["positive_surprises"] = positive_surprises
        details["total_reports"] = total
        if total > 0:
            beat_rate = positive_surprises / total
            details["beat_rate"] = round(beat_rate, 2)
            if beat_rate >= 0.75 and direction == "FLAT":
                direction = "UP"
                reasoning.append(f"Strong beat rate: {positive_surprises}/{total}")
            elif beat_rate <= 0.25 and direction == "FLAT":
                direction = "DOWN"
                reasoning.append(f"Poor beat rate: {positive_surprises}/{total}")

    # Check for recent earnings beat/miss
    if actuals:
        actual_eps = actuals.get("eps")
        estimated_eps = estimates.get("eps")
        if actual_eps is not None and estimated_eps is not None:
            actual_eps = safe_scalar(actual_eps)
            estimated_eps = safe_scalar(estimated_eps)
            if estimated_eps != 0:
                surprise = ((actual_eps - estimated_eps) / abs(estimated_eps)) * 100
                details["last_surprise_pct"] = round(surprise, 2)
                if surprise > 5:
                    if direction == "FLAT":
                        direction = "UP"
                    reasoning.append(f"Last earnings beat by {surprise:.1f}%")
                elif surprise < -5:
                    if direction == "FLAT":
                        direction = "DOWN"
                    reasoning.append(f"Last earnings missed by {abs(surprise):.1f}%")

    if not reasoning:
        reasoning.append("Insufficient data for momentum classification")

    return direction, "; ".join(reasoning), details


def run():
    """Main entry point."""
    logger.info("Earnings Momentum Agent starting...")

    earnings_data = _load_earnings_data()
    if earnings_data is None:
        return {"status": "error", "reason": "no earnings data"}

    results = {}
    records_written = 0

    for ticker in PORTFOLIO_TICKERS:
        ticker_data = earnings_data.get(ticker, {})
        direction, reasoning, details = _classify_eps_revision(ticker_data)

        entry = {
            "ticker": ticker,
            "eps_direction": direction,
            "reasoning": reasoning,
            "details": details,
        }
        results[ticker] = entry

        insert("events", {
            "event_type": "earnings_momentum",
            "ticker": ticker,
            "summary": json.dumps(entry),
            "severity": "warning" if direction == "DOWN" else "info",
        })
        records_written += 1

    # Write local JSON
    output_path = AGENT_OUTPUT_DIR / "earnings_momentum_agent_output.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info(f"Earnings Momentum Agent complete. {records_written} tickers classified.")
    return {"status": "ok", "records": records_written, "data": results}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
