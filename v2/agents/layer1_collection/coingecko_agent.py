"""
CoinGecko Agent — Layer 1 Data Collection
Ardi Market Command Center v2

Collects: Crypto prices, market data, Fear & Greed index.
"""
import json
import logging
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import CRYPTO_HOLDINGS, AGENT_OUTPUT_DIR
from lib.supabase_client import insert
from lib.data_validator import validate_price

logger = logging.getLogger("ardi.layer1.coingecko")

CG_BASE = "https://api.coingecko.com/api/v3"


def run():
    """Main entry point."""
    logger.info("CoinGecko Agent starting...")
    import requests

    results = {"coins": {}, "global": {}, "fear_greed": None}
    records_written = 0

    # Coin prices
    coin_ids = ",".join(CRYPTO_HOLDINGS.keys())
    try:
        resp = requests.get(f"{CG_BASE}/simple/price", params={
            "ids": coin_ids,
            "vs_currencies": "usd",
            "include_24hr_change": "true",
            "include_7d_change": "true",
            "include_market_cap": "true",
            "include_24hr_vol": "true",
        }, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        for coin_id, config_info in CRYPTO_HOLDINGS.items():
            coin_data = data.get(coin_id, {})
            if not coin_data:
                logger.warning(f"No CoinGecko data for {coin_id}")
                continue

            price = coin_data.get("usd")
            if not validate_price(price, config_info["symbol"]):
                continue

            baseline = config_info["baseline"]
            pct_change_from_baseline = round(((price - baseline) / baseline) * 100, 2)

            entry = {
                "coin_id": coin_id,
                "symbol": config_info["symbol"],
                "price": price,
                "change_24h_pct": coin_data.get("usd_24h_change"),
                "change_7d_pct": coin_data.get("usd_7d_change"),
                "market_cap": int(coin_data["usd_market_cap"]) if coin_data.get("usd_market_cap") else None,
                "volume_24h": int(coin_data["usd_24h_vol"]) if coin_data.get("usd_24h_vol") else None,
                "baseline": baseline,
                "pct_from_baseline": pct_change_from_baseline,
            }
            results["coins"][coin_id] = entry

            insert("crypto_snapshots", {
                "coin_id": coin_id,
                "symbol": config_info["symbol"],
                "price": price,
                "change_24h_pct": coin_data.get("usd_24h_change"),
                "change_7d_pct": coin_data.get("usd_7d_change"),
                "market_cap": int(coin_data["usd_market_cap"]) if coin_data.get("usd_market_cap") else None,
                "volume_24h": int(coin_data["usd_24h_vol"]) if coin_data.get("usd_24h_vol") else None,
                "baseline": baseline,
            })
            records_written += 1

            # XRP alert check
            if config_info["symbol"] == "XRP" and coin_data.get("usd_24h_change"):
                if abs(coin_data["usd_24h_change"]) >= 5.0:
                    logger.warning(f"XRP moved {coin_data['usd_24h_change']:.1f}% in 24h — flagging")
                    insert("events", {
                        "event_type": "corporate",
                        "headline": f"XRP large move: {coin_data['usd_24h_change']:.1f}% in 24h",
                        "summary": f"XRP at ${price:.4f}, baseline ${baseline}. Change from baseline: {pct_change_from_baseline:.1f}%",
                        "source": "coingecko",
                        "affected_tickers": "XRP",
                        "severity": "moderate",
                    })

    except Exception as e:
        logger.error(f"CoinGecko price fetch failed: {e}")

    # Global crypto market
    time.sleep(1)
    try:
        resp = requests.get(f"{CG_BASE}/global", timeout=15)
        resp.raise_for_status()
        gdata = resp.json().get("data", {})
        results["global"] = {
            "total_market_cap_usd": gdata.get("total_market_cap", {}).get("usd"),
            "btc_dominance": gdata.get("market_cap_percentage", {}).get("btc"),
            "market_cap_change_24h_pct": gdata.get("market_cap_change_percentage_24h_usd"),
        }
    except Exception as e:
        logger.warning(f"CoinGecko global fetch failed: {e}")

    # Fear & Greed Index
    time.sleep(1)
    try:
        resp = requests.get("https://api.alternative.me/fng/?limit=14", timeout=10)
        resp.raise_for_status()
        fg_data = resp.json().get("data", [])
        if fg_data:
            results["fear_greed"] = {
                "current": int(fg_data[0].get("value", 0)),
                "classification": fg_data[0].get("value_classification", ""),
                "history_14d": [{"value": int(d["value"]), "class": d["value_classification"]} for d in fg_data],
            }
    except Exception as e:
        logger.warning(f"Fear & Greed fetch failed (alternative.me often down): {e}")

    # Write local JSON
    output_path = AGENT_OUTPUT_DIR / "coingecko_agent_output.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info(f"CoinGecko Agent complete. {records_written} records.")
    return {"status": "ok", "records": records_written}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
