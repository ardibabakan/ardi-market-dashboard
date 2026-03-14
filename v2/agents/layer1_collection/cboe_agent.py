"""
CBOE/VIX Agent — Layer 1 Data Collection
Ardi Market Command Center v2

Collects: VIX term structure, regime classification.
KEY ceasefire/danger indicator.
"""
import json
import logging
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import AGENT_OUTPUT_DIR
from lib.supabase_client import insert
from lib.data_validator import validate_vix
from lib.safe_scalar import safe_scalar

logger = logging.getLogger("ardi.layer1.cboe")


def run():
    """Main entry point."""
    logger.info("CBOE/VIX Agent starting...")
    import yfinance as yf
    import time

    results = {}
    records_written = 0

    # VIX 30-day
    time.sleep(0.3)
    try:
        vix_data = yf.Ticker("^VIX")
        vix_info = vix_data.info or {}
        vix_price = safe_scalar(vix_info.get("regularMarketPrice") or vix_info.get("previousClose"))
        vix_price = validate_vix(vix_price)
    except Exception as e:
        logger.warning(f"VIX fetch failed: {e}")
        vix_price = None

    # VIX3M (3-month)
    time.sleep(0.3)
    try:
        vix3m_data = yf.Ticker("^VIX3M")
        vix3m_info = vix3m_data.info or {}
        vix3m_price = safe_scalar(vix3m_info.get("regularMarketPrice") or vix3m_info.get("previousClose"))
        vix3m_price = validate_vix(vix3m_price)
    except Exception as e:
        logger.warning(f"VIX3M fetch failed: {e}")
        vix3m_price = None

    # Analysis
    term_structure = None
    regime = None

    if vix_price and vix3m_price:
        if vix_price > vix3m_price:
            term_structure = "backwardation"  # near-term crisis expected
        else:
            term_structure = "contango"  # prolonged stress

    if vix_price:
        if vix_price < 15:
            regime = "CALM"
        elif vix_price < 25:
            regime = "NORMAL"
        elif vix_price < 35:
            regime = "ELEVATED"
        else:
            regime = "EXTREME"

    results = {
        "vix": vix_price,
        "vix3m": vix3m_price,
        "term_structure": term_structure,
        "regime": regime,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Write VIX to market_data
    if vix_price:
        insert("market_data", {
            "symbol": "^VIX",
            "name": "VIX 30-Day",
            "value": vix_price,
            "data_type": "index",
        })
        records_written += 1

    if vix3m_price:
        insert("market_data", {
            "symbol": "^VIX3M",
            "name": "VIX 3-Month",
            "value": vix3m_price,
            "data_type": "index",
        })
        records_written += 1

    # Write local JSON
    output_path = AGENT_OUTPUT_DIR / "cboe_agent_output.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info(f"CBOE Agent complete. VIX={vix_price}, VIX3M={vix3m_price}, structure={term_structure}, regime={regime}")
    return {"status": "ok", "records": records_written, "vix": vix_price, "regime": regime}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
