"""
Agent 20: Rebalance Agent
Reads positions from Supabase. Reads yahoo_agent_output.json for current prices.
Calculates current allocation vs target (equal weight by default for planned).
Flags defense concentration if LMT+RTX+ITA+BAESY > 50%.
Flags if GLD < 15% of portfolio.
Writes to events Supabase table.
"""
import json, logging, sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import *
from lib.supabase_client import insert, select
from lib.safe_scalar import safe_scalar

logger = logging.getLogger("ardi.rebalance")

YAHOO_OUTPUT = AGENT_OUTPUT_DIR / "yahoo_agent_output.json"
LOCAL_OUTPUT = AGENT_OUTPUT_DIR / "rebalance_output.json"

DEFENSE_TICKERS = {"LMT", "RTX", "ITA", "BAESY"}
GOLD_TICKER = "GLD"
DEFENSE_MAX_PCT = 50.0
GOLD_MIN_PCT = 15.0


def _load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load {path}: {e}")
        return {}


def run():
    logger.info("Rebalance Agent starting")
    now = datetime.now(timezone.utc).isoformat()

    yahoo_data = _load_json(YAHOO_OUTPUT)

    # Read positions from Supabase
    try:
        positions = select("positions") or []
    except Exception as e:
        logger.warning(f"Could not read positions: {e}")
        positions = []

    portfolio_tickers = list(PLANNED_POSITIONS.keys())
    num_positions = len(portfolio_tickers)
    target_weight = round(100.0 / num_positions, 2) if num_positions > 0 else 0
    budget_per = PORTFOLIO_BUDGET / num_positions if num_positions > 0 else 0

    # Build position map from Supabase or planned
    position_map = {}
    for pos in positions:
        ticker = pos.get("ticker")
        if ticker:
            position_map[ticker] = pos

    allocations = []
    total_value = 0.0
    ticker_values = {}

    for ticker in portfolio_tickers:
        entry = yahoo_data.get(ticker, {})
        current_price = safe_scalar(
            entry.get("price") or entry.get("current_price") or entry.get("close"), None
        )

        # For planned positions, use budget_per as the value
        pos = position_map.get(ticker, {})
        shares = safe_scalar(pos.get("shares") or pos.get("planned_shares"), 0)

        if current_price and shares > 0:
            value = current_price * shares
        else:
            # Paper trading: use planned allocation
            value = budget_per

        ticker_values[ticker] = value
        total_value += value

    # Calculate actual weights and deviations
    alerts = []
    for ticker in portfolio_tickers:
        value = ticker_values.get(ticker, 0)
        actual_weight = round((value / total_value) * 100, 2) if total_value > 0 else 0
        deviation = round(actual_weight - target_weight, 2)

        alloc = {
            "ticker": ticker,
            "name": PLANNED_POSITIONS[ticker].get("name", ticker),
            "sector": PLANNED_POSITIONS[ticker].get("sector", "unknown"),
            "value": round(value, 2),
            "actual_weight_pct": actual_weight,
            "target_weight_pct": target_weight,
            "deviation_pct": deviation,
            "needs_rebalance": abs(deviation) > 5.0,
        }
        allocations.append(alloc)

        if abs(deviation) > 5.0:
            direction = "overweight" if deviation > 0 else "underweight"
            alerts.append(f"{ticker} is {direction} by {abs(deviation):.1f}%")

    # --- Defense concentration check ---
    defense_value = sum(ticker_values.get(t, 0) for t in DEFENSE_TICKERS if t in ticker_values)
    defense_pct = round((defense_value / total_value) * 100, 2) if total_value > 0 else 0
    defense_concentrated = defense_pct > DEFENSE_MAX_PCT

    if defense_concentrated:
        alerts.append(f"DEFENSE CONCENTRATION: {defense_pct:.1f}% > {DEFENSE_MAX_PCT}% threshold (LMT+RTX+ITA+BAESY)")

    # --- Gold minimum check ---
    gold_value = ticker_values.get(GOLD_TICKER, 0)
    gold_pct = round((gold_value / total_value) * 100, 2) if total_value > 0 else 0
    gold_underweight = gold_pct < GOLD_MIN_PCT

    if gold_underweight:
        alerts.append(f"GOLD UNDERWEIGHT: GLD at {gold_pct:.1f}% < {GOLD_MIN_PCT}% minimum")

    result = {
        "agent": "rebalance",
        "timestamp": now,
        "portfolio_budget": PORTFOLIO_BUDGET,
        "total_value": round(total_value, 2),
        "num_positions": num_positions,
        "target_weight_pct": target_weight,
        "allocations": allocations,
        "defense_concentration": {
            "tickers": list(DEFENSE_TICKERS & set(portfolio_tickers)),
            "total_pct": defense_pct,
            "threshold_pct": DEFENSE_MAX_PCT,
            "alert": defense_concentrated,
        },
        "gold_allocation": {
            "ticker": GOLD_TICKER,
            "pct": gold_pct,
            "minimum_pct": GOLD_MIN_PCT,
            "alert": gold_underweight,
        },
        "alerts": alerts,
        "needs_rebalance": len(alerts) > 0,
    }

    # Write local output
    try:
        LOCAL_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        with open(LOCAL_OUTPUT, "w") as f:
            json.dump(result, f, indent=2)
        logger.info(f"Wrote {LOCAL_OUTPUT}")
    except Exception as e:
        logger.error(f"Failed to write local output: {e}")

    # Write to Supabase events table (valid columns only)
    try:
        severity = "low"
        if defense_concentrated or gold_underweight:
            severity = "high"
        elif alerts:
            severity = "medium"

        headline = f"Rebalance: {len(alerts)} alerts" if alerts else "Rebalance: portfolio balanced"

        row = {
            "event_type": "rebalance",
            "headline": headline,
            "summary": json.dumps({
                "alerts": alerts,
                "defense_pct": defense_pct,
                "gold_pct": gold_pct,
                "allocations": allocations,
            }),
            "severity": severity,
        }
        insert("events", row)
        logger.info("Wrote rebalance to Supabase events")
    except Exception as e:
        logger.error(f"Supabase write failed: {e}")

    logger.info(f"Rebalance Agent complete: {len(alerts)} alerts")
    result["status"] = "ok"
    result["records"] = result.get("records", 0)
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
