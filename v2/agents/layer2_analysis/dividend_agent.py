"""
Agent 18: Dividend Agent
Reads yahoo_agent_output.json for dividend yield data.
For each portfolio ticker: annual dividend yield, estimated annual income at planned size.
Total portfolio expected annual dividend income.
Writes to events Supabase table.
"""
import json, logging, sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import *
from lib.supabase_client import insert
from lib.safe_scalar import safe_scalar

logger = logging.getLogger("ardi.dividend")

YAHOO_OUTPUT = AGENT_OUTPUT_DIR / "yahoo_agent_output.json"
LOCAL_OUTPUT = AGENT_OUTPUT_DIR / "dividend_output.json"


def _load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load {path}: {e}")
        return {}


def run():
    logger.info("Dividend Agent starting")
    now = datetime.now(timezone.utc).isoformat()

    yahoo_data = _load_json(YAHOO_OUTPUT)

    portfolio_tickers = list(PLANNED_POSITIONS.keys())
    num_positions = len(portfolio_tickers)
    budget_per_position = PORTFOLIO_BUDGET / num_positions if num_positions > 0 else 0

    dividend_data = []
    total_annual_income = 0.0

    for ticker in portfolio_tickers:
        entry = yahoo_data.get(ticker, {})
        if not isinstance(entry, dict):
            dividend_data.append({
                "ticker": ticker,
                "name": PLANNED_POSITIONS[ticker].get("name", ticker),
                "status": "no_data",
            })
            continue

        current_price = safe_scalar(
            entry.get("price") or entry.get("current_price") or entry.get("close"), None
        )
        div_yield = safe_scalar(
            entry.get("dividend_yield") or entry.get("dividendYield") or entry.get("yield"), None
        )
        # Some sources return yield as percentage, others as decimal
        if div_yield is not None and div_yield > 1:
            div_yield = div_yield / 100.0  # convert from percentage

        annual_dividend_per_share = safe_scalar(
            entry.get("dividendRate") or entry.get("annual_dividend") or entry.get("dividend_rate"), None
        )

        # Calculate yield from dividend rate if not directly available
        if div_yield is None and annual_dividend_per_share and current_price and current_price > 0:
            div_yield = annual_dividend_per_share / current_price

        # Estimate shares at planned budget
        estimated_shares = 0
        if current_price and current_price > 0:
            estimated_shares = budget_per_position / current_price

        # Estimated annual income
        estimated_annual_income = 0.0
        if div_yield and div_yield > 0:
            estimated_annual_income = round(budget_per_position * div_yield, 2)
        elif annual_dividend_per_share and estimated_shares > 0:
            estimated_annual_income = round(annual_dividend_per_share * estimated_shares, 2)

        total_annual_income += estimated_annual_income

        item = {
            "ticker": ticker,
            "name": PLANNED_POSITIONS[ticker].get("name", ticker),
            "sector": PLANNED_POSITIONS[ticker].get("sector", "unknown"),
            "current_price": current_price,
            "dividend_yield_pct": round(div_yield * 100, 2) if div_yield else 0.0,
            "annual_dividend_per_share": annual_dividend_per_share,
            "planned_allocation": round(budget_per_position, 2),
            "estimated_shares": round(estimated_shares, 2),
            "estimated_annual_income": estimated_annual_income,
        }
        dividend_data.append(item)
        if div_yield:
            logger.info(f"{ticker}: yield={div_yield*100:.2f}%, est income=${estimated_annual_income:.2f}")

    # Portfolio yield
    portfolio_yield_pct = round((total_annual_income / PORTFOLIO_BUDGET) * 100, 2) if PORTFOLIO_BUDGET > 0 else 0

    result = {
        "agent": "dividend",
        "timestamp": now,
        "portfolio_budget": PORTFOLIO_BUDGET,
        "positions_analyzed": len(dividend_data),
        "total_estimated_annual_income": round(total_annual_income, 2),
        "portfolio_yield_pct": portfolio_yield_pct,
        "quarterly_estimate": round(total_annual_income / 4, 2),
        "monthly_estimate": round(total_annual_income / 12, 2),
        "dividend_details": dividend_data,
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
        row = {
            "event_type": "dividend_analysis",
            "headline": f"Portfolio dividend yield: {portfolio_yield_pct:.2f}% (est ${total_annual_income:.2f}/yr)",
            "summary": json.dumps({
                "total_annual_income": result["total_estimated_annual_income"],
                "portfolio_yield_pct": portfolio_yield_pct,
                "top_yielders": sorted(
                    [d for d in dividend_data if d.get("dividend_yield_pct", 0) > 0],
                    key=lambda x: x.get("dividend_yield_pct", 0),
                    reverse=True
                )[:5],
            }),
            "severity": "low",
        }
        insert("events", row)
        logger.info("Wrote dividend analysis to Supabase events")
    except Exception as e:
        logger.error(f"Supabase write failed: {e}")

    logger.info("Dividend Agent complete")
    result["status"] = "ok"
    result["records"] = result.get("records", 0)
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
