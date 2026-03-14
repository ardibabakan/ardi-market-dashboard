"""
Alpha Vantage Agent — Layer 1 Data Collection (BACKUP)
Ardi Market Command Center v2

Backup source for price data. Only runs if yahoo fails.
Free tier: 25 calls/day — portfolio tickers only.
"""
import json
import logging
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import PLANNED_POSITIONS, ALPHA_VANTAGE_KEY, AGENT_OUTPUT_DIR
from lib.supabase_client import insert
from lib.data_validator import validate_price

logger = logging.getLogger("ardi.layer1.alpha_vantage")

AV_BASE = "https://www.alphavantage.co/query"


def run():
    """Main entry point."""
    logger.info("Alpha Vantage Agent starting...")

    if not ALPHA_VANTAGE_KEY:
        logger.warning("ALPHA_VANTAGE_KEY not set — skipping")
        return {"status": "skipped", "reason": "no_api_key", "records": 0}

    import requests
    results = {}
    records_written = 0

    for ticker in PLANNED_POSITIONS:
        try:
            time.sleep(1.5)  # rate limit: 5 calls/min on free tier
            resp = requests.get(AV_BASE, params={
                "function": "GLOBAL_QUOTE",
                "symbol": ticker,
                "apikey": ALPHA_VANTAGE_KEY,
            }, timeout=15)
            data = resp.json()
            quote = data.get("Global Quote", {})
            if not quote:
                logger.warning(f"No AV data for {ticker}")
                continue

            price = validate_price(quote.get("05. price"), ticker)
            if not price:
                continue

            info = {
                "ticker": ticker,
                "price": price,
                "prev_close": float(quote.get("08. previous close", 0)),
                "change_pct": float(quote.get("10. change percent", "0").rstrip("%")),
                "volume": int(quote.get("06. volume", 0)),
                "high_52w": None,
                "low_52w": None,
                "source": "alpha_vantage",
            }
            results[ticker] = info

            insert("price_snapshots", {
                "ticker": ticker,
                "price": info["price"],
                "prev_close": info["prev_close"],
                "change_pct": info["change_pct"],
                "volume": info["volume"],
                "source": "alpha_vantage",
            })
            records_written += 1

        except Exception as e:
            logger.warning(f"AV failed for {ticker}: {e}")

    # Write local JSON
    output_path = AGENT_OUTPUT_DIR / "alpha_vantage_agent_output.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info(f"Alpha Vantage Agent complete. {records_written} records.")
    return {"status": "ok", "records": records_written}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
