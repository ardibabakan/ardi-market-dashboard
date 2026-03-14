"""
Agent 16: Risk Simulation Agent
Reads cached price history from v2/data/cache/ for portfolio tickers.
Runs simplified Monte Carlo: 90-day daily returns, 1000 paths over 30 days.
Calculates VaR (5th percentile), Expected Shortfall, probability of 15% drawdown.
Writes to events Supabase table.
"""
import json, logging, sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import *
from lib.supabase_client import insert
from lib.safe_scalar import safe_scalar

logger = logging.getLogger("ardi.risk_simulation")

LOCAL_OUTPUT = AGENT_OUTPUT_DIR / "risk_simulation_output.json"

NUM_SIMULATIONS = 1000
SIMULATION_DAYS = 30
LOOKBACK_DAYS = 90
DRAWDOWN_THRESHOLD = 0.15  # 15%


def _load_cache(ticker):
    """Load cached price history JSON for a ticker."""
    try:
        import pandas as pd
        cache_path = CACHE_DIR / f"{ticker}_hist.json"
        if not cache_path.exists():
            return None
        with open(cache_path) as f:
            raw = json.load(f)
        if not raw:
            return None
        df = pd.DataFrame(raw)
        df.columns = [c.lower() for c in df.columns]
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")
        return df.sort_index()
    except Exception as e:
        logger.warning(f"Could not load cache for {ticker}: {e}")
        return None


def _compute_daily_returns(df, lookback=LOOKBACK_DAYS):
    """Extract last N days of daily returns from price history."""
    try:
        import numpy as np
        # Use 'Close' or 'Adj Close' column
        close_col = None
        for col in ["Close", "Adj Close", "close", "adj_close"]:
            if col in df.columns:
                close_col = col
                break
        if close_col is None and len(df.columns) == 1:
            close_col = df.columns[0]
        if close_col is None:
            return None

        prices = df[close_col].dropna().tail(lookback)
        if len(prices) < 20:
            return None

        returns = prices.pct_change().dropna().values
        return returns
    except Exception as e:
        logger.warning(f"Could not compute returns: {e}")
        return None


def _run_monte_carlo(returns, budget, n_sims=NUM_SIMULATIONS, n_days=SIMULATION_DAYS):
    """Run Monte Carlo simulation using historical returns."""
    import numpy as np

    mean_return = np.mean(returns)
    std_return = np.std(returns)

    if std_return == 0:
        return None

    # Simulate paths
    np.random.seed(42)
    simulated_returns = np.random.normal(mean_return, std_return, (n_sims, n_days))
    cumulative = np.cumprod(1 + simulated_returns, axis=1)

    final_values = budget * cumulative[:, -1]
    final_returns = (final_values - budget) / budget

    # VaR at 5th percentile (loss)
    var_5 = float(np.percentile(final_returns, 5))

    # Expected Shortfall (average of worst 5%)
    cutoff = np.percentile(final_returns, 5)
    tail = final_returns[final_returns <= cutoff]
    expected_shortfall = float(np.mean(tail)) if len(tail) > 0 else var_5

    # Probability of 15% drawdown
    prob_drawdown = float(np.mean(final_returns <= -DRAWDOWN_THRESHOLD))

    # Max drawdown across all paths (worst path intra-period)
    worst_path_return = float(np.min(final_returns))

    # Median and best case
    median_return = float(np.median(final_returns))
    best_return = float(np.max(final_returns))

    return {
        "var_5pct": round(var_5 * 100, 2),
        "var_5pct_dollars": round(var_5 * budget, 2),
        "expected_shortfall_pct": round(expected_shortfall * 100, 2),
        "expected_shortfall_dollars": round(expected_shortfall * budget, 2),
        "prob_15pct_drawdown": round(prob_drawdown * 100, 2),
        "median_return_pct": round(median_return * 100, 2),
        "worst_return_pct": round(worst_path_return * 100, 2),
        "best_return_pct": round(best_return * 100, 2),
        "simulations": n_sims,
        "horizon_days": n_days,
        "lookback_days": len(returns),
        "daily_mean_return": round(mean_return * 100, 4),
        "daily_std_return": round(std_return * 100, 4),
    }


def run():
    logger.info("Risk Simulation Agent starting")
    now = datetime.now(timezone.utc).isoformat()

    try:
        import numpy as np
        import pandas as pd
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        return {"agent": "risk_simulation", "error": str(e)}

    portfolio_tickers = list(PLANNED_POSITIONS.keys())
    budget_per_ticker = PORTFOLIO_BUDGET / len(portfolio_tickers) if portfolio_tickers else 0

    ticker_results = {}
    all_returns = []

    for ticker in portfolio_tickers:
        df = _load_cache(ticker)
        if df is None:
            logger.warning(f"No cached data for {ticker}, skipping")
            ticker_results[ticker] = {"status": "no_data"}
            continue

        returns = _compute_daily_returns(df)
        if returns is None:
            logger.warning(f"Insufficient return data for {ticker}")
            ticker_results[ticker] = {"status": "insufficient_data"}
            continue

        mc = _run_monte_carlo(returns, budget_per_ticker)
        if mc:
            ticker_results[ticker] = mc
            all_returns.append(returns)
            logger.info(
                f"{ticker}: VaR(5%)={mc['var_5pct']:.1f}%, "
                f"ES={mc['expected_shortfall_pct']:.1f}%, "
                f"P(15% DD)={mc['prob_15pct_drawdown']:.1f}%"
            )
        else:
            ticker_results[ticker] = {"status": "simulation_failed"}

    # Portfolio-level simulation using average returns
    portfolio_mc = None
    if all_returns:
        avg_returns = np.mean(all_returns, axis=0) if len(all_returns) > 1 else all_returns[0]
        portfolio_mc = _run_monte_carlo(avg_returns, PORTFOLIO_BUDGET)

    result = {
        "agent": "risk_simulation",
        "timestamp": now,
        "portfolio_budget": PORTFOLIO_BUDGET,
        "tickers_analyzed": len([t for t in ticker_results if isinstance(ticker_results[t], dict) and "var_5pct" in ticker_results[t]]),
        "tickers_skipped": len([t for t in ticker_results if isinstance(ticker_results[t], dict) and "status" in ticker_results[t]]),
        "individual_results": ticker_results,
        "portfolio_simulation": portfolio_mc,
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
        headline = "Risk simulation complete"
        if portfolio_mc:
            if portfolio_mc["prob_15pct_drawdown"] > 10:
                severity = "high"
                headline = f"HIGH RISK: {portfolio_mc['prob_15pct_drawdown']:.1f}% chance of 15% drawdown"
            elif portfolio_mc["prob_15pct_drawdown"] > 5:
                severity = "medium"
                headline = f"ELEVATED RISK: {portfolio_mc['prob_15pct_drawdown']:.1f}% chance of 15% drawdown"
            else:
                headline = f"Risk OK: VaR(5%)={portfolio_mc['var_5pct']:.1f}%, P(15%DD)={portfolio_mc['prob_15pct_drawdown']:.1f}%"

        row = {
            "event_type": "risk_simulation",
            "headline": headline,
            "summary": json.dumps({
                "portfolio_simulation": portfolio_mc,
                "tickers_analyzed": result["tickers_analyzed"],
            }),
            "severity": severity,
        }
        insert("events", row)
        logger.info("Wrote risk simulation to Supabase events")
    except Exception as e:
        logger.error(f"Supabase write failed: {e}")

    logger.info("Risk Simulation Agent complete")
    result["status"] = "ok"
    result["records"] = result.get("records", 0)
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
