"""
Yahoo Finance Agent — Layer 1 Data Collection
Ardi Market Command Center v2

Collects: Current prices, 52-week ranges, volumes, market caps
for all portfolio tickers, indices, commodities, currencies.
Also caches 30/90-day historical data for technical analysis.
"""
import json
import logging
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import (
    PLANNED_POSITIONS, PHASE_B_POSITIONS, INDICES, COMMODITIES,
    CURRENCIES, TREASURIES, AGENT_OUTPUT_DIR, CACHE_DIR
)
from lib.supabase_client import insert
from lib.data_validator import validate_price, validate_gold_price
from lib.rate_limiter import rate_limited_download
from lib.safe_scalar import safe_scalar

logger = logging.getLogger("ardi.layer1.yahoo")


def _get_ticker_info(ticker):
    """Pull current quote data for a single ticker."""
    import yfinance as yf
    import time
    time.sleep(0.3)
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        return {
            "ticker": ticker,
            "price": safe_scalar(info.get("regularMarketPrice") or info.get("previousClose")),
            "prev_close": safe_scalar(info.get("regularMarketPreviousClose") or info.get("previousClose")),
            "change_pct": safe_scalar(info.get("regularMarketChangePercent")),
            "volume": info.get("regularMarketVolume") or info.get("volume"),
            "high_52w": safe_scalar(info.get("fiftyTwoWeekHigh")),
            "low_52w": safe_scalar(info.get("fiftyTwoWeekLow")),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "dividend_yield": info.get("dividendYield"),
        }
    except Exception as e:
        logger.warning(f"Failed to get info for {ticker}: {e}")
        return None


def _cache_historical(ticker, period="90d"):
    """Download and cache historical data for technical analysis."""
    data = rate_limited_download(ticker, period=period)
    if data is None or data.empty:
        return
    cache_path = CACHE_DIR / f"{ticker.replace('^','').replace('=','_')}_hist.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    records = []
    for date, row in data.iterrows():
        records.append({
            "date": str(date.date()) if hasattr(date, 'date') else str(date),
            "open": safe_scalar(row.get("Open")),
            "high": safe_scalar(row.get("High")),
            "low": safe_scalar(row.get("Low")),
            "close": safe_scalar(row.get("Close")),
            "volume": safe_scalar(row.get("Volume")),
        })
    with open(cache_path, "w") as f:
        json.dump(records, f, indent=2)
    logger.info(f"Cached {len(records)} days for {ticker}")


def run():
    """Main entry point. Called by orchestrator."""
    logger.info("Yahoo Agent starting...")
    results = {"prices": {}, "indices": {}, "commodities": {}, "currencies": {}, "treasuries": {}}
    records_written = 0

    # Portfolio tickers + Phase B
    all_tickers = list(PLANNED_POSITIONS.keys()) + list(PHASE_B_POSITIONS.keys())

    for ticker in all_tickers:
        info = _get_ticker_info(ticker)
        if info and validate_price(info["price"], ticker):
            results["prices"][ticker] = info

            # Gold special handling
            if ticker == "GLD":
                gold_est = validate_gold_price(info["price"])
                if gold_est:
                    info["gold_estimate"] = gold_est

            # Write to Supabase
            row = {
                "ticker": ticker,
                "price": info["price"],
                "prev_close": info["prev_close"],
                "change_pct": info["change_pct"],
                "volume": info.get("volume"),
                "high_52w": info["high_52w"],
                "low_52w": info["low_52w"],
                "market_cap": info.get("market_cap"),
                "source": "yahoo",
            }
            if insert("price_snapshots", row):
                records_written += 1
        else:
            logger.warning(f"Skipped {ticker} — no valid price")

    # Cache historical data for portfolio tickers
    for ticker in list(PLANNED_POSITIONS.keys()):
        try:
            _cache_historical(ticker)
        except Exception as e:
            logger.warning(f"Cache failed for {ticker}: {e}")

    # Indices
    for symbol in INDICES:
        info = _get_ticker_info(symbol)
        if info and info["price"]:
            results["indices"][symbol] = info
            insert("market_data", {
                "symbol": symbol,
                "name": symbol,
                "value": info["price"],
                "change_pct": info["change_pct"],
                "data_type": "index",
            })
            records_written += 1

    # Commodities
    for symbol in COMMODITIES:
        info = _get_ticker_info(symbol)
        if info and info["price"]:
            results["commodities"][symbol] = info
            insert("market_data", {
                "symbol": symbol,
                "name": symbol,
                "value": info["price"],
                "change_pct": info["change_pct"],
                "data_type": "commodity",
            })
            records_written += 1

    # Currencies
    for symbol in CURRENCIES:
        info = _get_ticker_info(symbol)
        if info and info["price"]:
            results["currencies"][symbol] = info
            insert("market_data", {
                "symbol": symbol,
                "name": symbol,
                "value": info["price"],
                "change_pct": info["change_pct"],
                "data_type": "currency",
            })
            records_written += 1

    # Treasuries
    for symbol in TREASURIES:
        info = _get_ticker_info(symbol)
        if info and info["price"]:
            results["treasuries"][symbol] = info
            insert("market_data", {
                "symbol": symbol,
                "name": symbol,
                "value": info["price"],
                "change_pct": info["change_pct"],
                "data_type": "treasury",
            })
            records_written += 1

    # Write local JSON
    output_path = AGENT_OUTPUT_DIR / "yahoo_agent_output.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info(f"Yahoo Agent complete. {records_written} records written.")
    return {"status": "ok", "records": records_written}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
