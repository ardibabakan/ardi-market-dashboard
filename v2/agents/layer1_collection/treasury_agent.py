"""
Treasury Agent — Layer 1 Data Collection
Ardi Market Command Center v2

Collects: Treasury yield curve data, TLT/IEF ETF prices.
Includes petrodollar disruption check.
"""
import json
import logging
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import AGENT_OUTPUT_DIR
from lib.supabase_client import insert
from lib.data_validator import validate_price
from lib.safe_scalar import safe_scalar

logger = logging.getLogger("ardi.layer1.treasury")


def run():
    """Main entry point."""
    logger.info("Treasury Agent starting...")
    import yfinance as yf
    import time

    results = {}
    records_written = 0

    treasury_etfs = {
        "TLT": "iShares 20+ Year Treasury Bond ETF",
        "IEF": "iShares 7-10 Year Treasury Bond ETF",
        "SHY": "iShares 1-3 Year Treasury Bond ETF",
    }

    for ticker, name in treasury_etfs.items():
        time.sleep(0.3)
        try:
            t = yf.Ticker(ticker)
            info = t.info or {}
            price = safe_scalar(info.get("regularMarketPrice") or info.get("previousClose"))
            prev = safe_scalar(info.get("regularMarketPreviousClose") or info.get("previousClose"))

            if not validate_price(price, ticker):
                continue

            change_pct = round(((price - prev) / prev) * 100, 2) if prev else 0

            entry = {
                "ticker": ticker,
                "name": name,
                "price": price,
                "prev_close": prev,
                "change_pct": change_pct,
            }
            results[ticker] = entry

            insert("market_data", {
                "symbol": ticker,
                "name": name,
                "value": price,
                "change_pct": change_pct,
                "data_type": "treasury",
            })
            records_written += 1

        except Exception as e:
            logger.warning(f"Treasury fetch failed for {ticker}: {e}")

    # Petrodollar disruption check
    # Normal: VIX up -> TLT up (flight to safety)
    # Broken: VIX up -> TLT down (petrodollar disruption)
    time.sleep(0.3)
    try:
        vix_t = yf.Ticker("^VIX")
        vix_info = vix_t.info or {}
        vix = safe_scalar(vix_info.get("regularMarketPrice") or vix_info.get("previousClose"))

        tlt_data = results.get("TLT", {})
        tlt_change = tlt_data.get("change_pct", 0)

        petrodollar_flag = None
        if vix and vix > 25 and tlt_change < -0.5:
            petrodollar_flag = "ACTIVE: VIX elevated but TLT falling — petrodollar disruption thesis"
        elif vix and vix > 25 and tlt_change > 0:
            petrodollar_flag = "NORMAL: VIX elevated, TLT rising — standard flight to safety"
        else:
            petrodollar_flag = "INACTIVE: conditions not met"

        results["petrodollar_check"] = {
            "vix": vix,
            "tlt_change_pct": tlt_change,
            "flag": petrodollar_flag,
        }

    except Exception as e:
        logger.warning(f"Petrodollar check failed: {e}")

    # Write local JSON
    output_path = AGENT_OUTPUT_DIR / "treasury_agent_output.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info(f"Treasury Agent complete. {records_written} records.")
    return {"status": "ok", "records": records_written}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
