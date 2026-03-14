"""
Factor Decomposition Agent — Layer 2 Analysis
Ardi Market Command Center v2

Decomposes portfolio ticker returns into market beta,
sector exposure, and idiosyncratic alpha using SPY as
the market benchmark.
"""
import json, logging, sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import PLANNED_POSITIONS, CACHE_DIR, AGENT_OUTPUT_DIR
from lib.supabase_client import insert
from lib.safe_scalar import safe_scalar

import pandas as pd
import numpy as np

logger = logging.getLogger("ardi.layer2.factor")

PORTFOLIO_TICKERS = list(PLANNED_POSITIONS.keys())


def _load_history(ticker):
    """Load cached price history for a ticker (JSON: list of dicts with date, close, etc.)."""
    path = CACHE_DIR / f"{ticker}_hist.json"
    if not path.exists():
        return None
    try:
        with open(path) as f:
            raw = json.load(f)
        if not raw:
            return None
        df = pd.DataFrame(raw)
        df.columns = [c.lower() for c in df.columns]
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")
        else:
            df.index = pd.to_datetime(df.index)
        return df.sort_index()
    except Exception as e:
        logger.warning(f"Failed to load {ticker}: {e}")
        return None


def _compute_beta_alpha(ticker_returns, market_returns):
    """OLS regression of ticker returns on market returns."""
    aligned = pd.concat([ticker_returns, market_returns], axis=1, join="inner").dropna()
    if len(aligned) < 30:
        return None, None, None

    aligned.columns = ["ticker", "market"]
    x = aligned["market"].values
    y = aligned["ticker"].values

    x_mean = np.mean(x)
    y_mean = np.mean(y)
    cov_xy = np.sum((x - x_mean) * (y - y_mean))
    var_x = np.sum((x - x_mean) ** 2)

    if var_x == 0:
        return None, None, None

    beta = cov_xy / var_x
    alpha = y_mean - beta * x_mean

    y_pred = alpha + beta * x
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - y_mean) ** 2)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

    return float(beta), float(alpha), float(r_squared)


def run():
    """Main entry point."""
    logger.info("Factor Agent starting...")

    # Load SPY benchmark from cache
    spy_df = _load_history("SPY")
    if spy_df is None or "close" not in spy_df.columns:
        logger.warning("No cached SPY data available")
        return {"status": "ok", "records": 0}

    spy_returns = spy_df["close"].pct_change().dropna()

    results = {}
    records_written = 0

    for ticker in PORTFOLIO_TICKERS:
        df = _load_history(ticker)
        if df is None or "close" not in df.columns:
            continue

        ticker_returns = df["close"].pct_change().dropna()
        beta, alpha, r_squared = _compute_beta_alpha(ticker_returns, spy_returns)

        if beta is None:
            logger.warning(f"Insufficient data for factor decomposition: {ticker}")
            continue

        alpha_annual = alpha * 252

        sector = PLANNED_POSITIONS.get(ticker, {}).get("sector", "unknown")
        market_exposure_pct = round(r_squared * 100, 1)
        idiosyncratic_pct = round((1 - r_squared) * 100, 1)

        entry = {
            "ticker": ticker,
            "sector": sector,
            "beta": round(beta, 3),
            "alpha_daily": round(alpha, 6),
            "alpha_annual": round(alpha_annual, 4),
            "r_squared": round(r_squared, 4),
            "market_exposure_pct": market_exposure_pct,
            "idiosyncratic_pct": idiosyncratic_pct,
        }
        results[ticker] = entry

        # Write to Supabase events table (valid columns only)
        try:
            insert("events", {
                "event_type": "factor_decomposition",
                "headline": f"Factor decomposition for {ticker}",
                "summary": json.dumps(entry),
                "affected_tickers": ticker,
                "severity": "info",
            })
            records_written += 1
        except Exception as e:
            logger.error(f"Supabase write failed for {ticker}: {e}")

    # Write local JSON
    output_path = AGENT_OUTPUT_DIR / "factor_agent_output.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info(f"Factor Agent complete. {records_written} tickers decomposed.")
    return {"status": "ok", "records": records_written, "data": results}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
