"""
Agent 12: Crypto Regime Agent
Reads coingecko_agent_output.json.
Calculates BTC dominance direction, Fear & Greed regime, XRP vs baseline.
Writes to macro_data Supabase table.
"""
import json, logging, sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import *
from lib.supabase_client import insert
from lib.safe_scalar import safe_scalar

logger = logging.getLogger("ardi.crypto_regime")

COINGECKO_OUTPUT = AGENT_OUTPUT_DIR / "coingecko_agent_output.json"
LOCAL_OUTPUT = AGENT_OUTPUT_DIR / "crypto_regime_output.json"


def _load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load {path}: {e}")
        return {}


def _classify_fear_greed(value):
    """Classify Fear & Greed index value (0-100)."""
    if value is None:
        return "UNKNOWN"
    v = safe_scalar(value, -1)
    if v < 0:
        return "UNKNOWN"
    if v <= 10:
        return "EXTREME_FEAR"
    if v <= 30:
        return "FEAR"
    if v <= 55:
        return "NEUTRAL"
    if v <= 80:
        return "GREED"
    return "EXTREME_GREED"


def run():
    logger.info("Crypto Regime Agent starting")
    now = datetime.now(timezone.utc).isoformat()

    cg_data = _load_json(COINGECKO_OUTPUT)

    # --- BTC dominance ---
    btc_data = cg_data.get("bitcoin", {})
    btc_price = safe_scalar(btc_data.get("price") or btc_data.get("current_price"), None)
    btc_dominance = safe_scalar(btc_data.get("market_cap_dominance") or btc_data.get("dominance"), None)
    btc_24h_change = safe_scalar(btc_data.get("price_change_24h_pct") or btc_data.get("change_24h"), None)

    btc_dominance_direction = "UNKNOWN"
    if btc_dominance is not None:
        if btc_dominance > 55:
            btc_dominance_direction = "HIGH_DOMINANCE"
        elif btc_dominance > 45:
            btc_dominance_direction = "MODERATE"
        else:
            btc_dominance_direction = "ALT_SEASON"

    # --- Fear & Greed ---
    fear_greed_value = safe_scalar(
        cg_data.get("fear_greed_index") or cg_data.get("fear_greed", {}).get("value"),
        None
    )
    fear_greed_regime = _classify_fear_greed(fear_greed_value)

    # --- XRP vs baseline ---
    xrp_baseline = CRYPTO_HOLDINGS.get("ripple", {}).get("baseline", 1.40)
    xrp_data = cg_data.get("ripple", {})
    xrp_price = safe_scalar(xrp_data.get("price") or xrp_data.get("current_price"), None)

    xrp_vs_baseline = None
    xrp_vs_baseline_pct = None
    if xrp_price is not None and xrp_baseline > 0:
        xrp_vs_baseline_pct = round(((xrp_price - xrp_baseline) / xrp_baseline) * 100, 2)
        if xrp_vs_baseline_pct > 5:
            xrp_vs_baseline = "ABOVE_BASELINE"
        elif xrp_vs_baseline_pct < -5:
            xrp_vs_baseline = "BELOW_BASELINE"
        else:
            xrp_vs_baseline = "AT_BASELINE"

    # --- Other holdings vs baseline ---
    holdings_status = {}
    for coin_id, info in CRYPTO_HOLDINGS.items():
        coin_data = cg_data.get(coin_id, {})
        price = safe_scalar(coin_data.get("price") or coin_data.get("current_price"), None)
        baseline = info.get("baseline", 0)
        if price is not None and baseline > 0:
            pct = round(((price - baseline) / baseline) * 100, 2)
            holdings_status[info["symbol"]] = {
                "price": price,
                "baseline": baseline,
                "vs_baseline_pct": pct,
            }

    result = {
        "agent": "crypto_regime",
        "timestamp": now,
        "btc": {
            "price": btc_price,
            "dominance": btc_dominance,
            "dominance_direction": btc_dominance_direction,
            "change_24h_pct": btc_24h_change,
        },
        "fear_greed": {
            "value": fear_greed_value,
            "regime": fear_greed_regime,
        },
        "xrp": {
            "price": xrp_price,
            "baseline": xrp_baseline,
            "vs_baseline": xrp_vs_baseline,
            "vs_baseline_pct": xrp_vs_baseline_pct,
        },
        "holdings_status": holdings_status,
    }

    # Write local output
    try:
        LOCAL_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        with open(LOCAL_OUTPUT, "w") as f:
            json.dump(result, f, indent=2)
        logger.info(f"Wrote {LOCAL_OUTPUT}")
    except Exception as e:
        logger.error(f"Failed to write local output: {e}")

    # Write to Supabase macro_data (valid columns only)
    try:
        row = {
            "series_id": "crypto_regime",
            "series_name": "Crypto Regime Analysis",
            "value": btc_price,
            "previous_value": None,
            "change_direction": btc_dominance_direction,
            "significance": f"Fear/Greed: {fear_greed_regime}; BTC dominance: {btc_dominance}",
        }
        insert("macro_data", row)
        logger.info("Wrote crypto_regime to Supabase macro_data")
    except Exception as e:
        logger.error(f"Supabase write failed: {e}")

    result["status"] = "ok"
    result["records"] = result.get("records", 0)
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
