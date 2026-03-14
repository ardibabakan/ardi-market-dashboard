"""
Agent 11: Currency Flow Agent
Reads DX-Y.NYB, EURUSD=X, USDJPY=X from yahoo_agent_output.json
and DTWEXBGS from fred_agent_output.json.
Calculates USD direction, JPY safe haven flow, EUR direction.
Flags petrodollar disruption if USD weakening while VIX elevated.
Writes to macro_data Supabase table.
"""
import json, logging, sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import *
from lib.supabase_client import insert
from lib.safe_scalar import safe_scalar

logger = logging.getLogger("ardi.currency_flow")

YAHOO_OUTPUT = AGENT_OUTPUT_DIR / "yahoo_agent_output.json"
FRED_OUTPUT = AGENT_OUTPUT_DIR / "fred_agent_output.json"
LOCAL_OUTPUT = AGENT_OUTPUT_DIR / "currency_flow_output.json"


def _load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load {path}: {e}")
        return {}


def _get_price(yahoo_data, symbol):
    """Extract current price for a symbol from yahoo output."""
    if isinstance(yahoo_data, dict):
        entry = yahoo_data.get(symbol, {})
        if isinstance(entry, dict):
            return safe_scalar(entry.get("price") or entry.get("current_price") or entry.get("close"), None)
    return None


def _get_prev_close(yahoo_data, symbol):
    """Extract previous close for a symbol from yahoo output."""
    if isinstance(yahoo_data, dict):
        entry = yahoo_data.get(symbol, {})
        if isinstance(entry, dict):
            return safe_scalar(entry.get("prev_close") or entry.get("previous_close"), None)
    return None


def _classify_direction(current, previous):
    """Return direction string and pct change."""
    if current is None or previous is None or previous == 0:
        return "UNKNOWN", 0.0
    pct = ((current - previous) / previous) * 100
    if pct > 0.1:
        return "STRENGTHENING", round(pct, 3)
    elif pct < -0.1:
        return "WEAKENING", round(pct, 3)
    return "FLAT", round(pct, 3)


def run():
    logger.info("Currency Flow Agent starting")
    now = datetime.now(timezone.utc).isoformat()

    yahoo_data = _load_json(YAHOO_OUTPUT)
    fred_data = _load_json(FRED_OUTPUT)

    # --- USD Index (DX-Y.NYB) ---
    dxy_price = _get_price(yahoo_data, "DX-Y.NYB")
    dxy_prev = _get_prev_close(yahoo_data, "DX-Y.NYB")
    usd_direction, usd_change_pct = _classify_direction(dxy_price, dxy_prev)

    # USD strengthening = risk-off, weakening = risk-on
    usd_risk_signal = "RISK_OFF" if usd_direction == "STRENGTHENING" else (
        "RISK_ON" if usd_direction == "WEAKENING" else "NEUTRAL"
    )

    # --- EUR/USD ---
    eur_price = _get_price(yahoo_data, "EURUSD=X")
    eur_prev = _get_prev_close(yahoo_data, "EURUSD=X")
    eur_direction, eur_change_pct = _classify_direction(eur_price, eur_prev)

    # --- USD/JPY ---
    jpy_price = _get_price(yahoo_data, "USDJPY=X")
    jpy_prev = _get_prev_close(yahoo_data, "USDJPY=X")
    jpy_direction, jpy_change_pct = _classify_direction(jpy_price, jpy_prev)

    # JPY strengthening (USDJPY falling) = safe haven flow
    jpy_safe_haven = False
    if jpy_direction == "WEAKENING":
        jpy_safe_haven = True  # USDJPY falling means JPY strengthening

    # --- FRED broad USD index ---
    dtwexbgs = None
    if isinstance(fred_data, dict):
        tw_entry = fred_data.get("DTWEXBGS", {})
        if isinstance(tw_entry, dict):
            dtwexbgs = safe_scalar(tw_entry.get("value") or tw_entry.get("latest_value"), None)

    # --- VIX for petrodollar disruption check ---
    vix_price = _get_price(yahoo_data, "^VIX")
    petrodollar_disruption = False
    if usd_direction == "WEAKENING" and vix_price is not None and vix_price > 25:
        petrodollar_disruption = True

    result = {
        "agent": "currency_flow",
        "timestamp": now,
        "usd_index": {
            "price": dxy_price,
            "prev_close": dxy_prev,
            "direction": usd_direction,
            "change_pct": usd_change_pct,
            "risk_signal": usd_risk_signal,
        },
        "eur_usd": {
            "price": eur_price,
            "prev_close": eur_prev,
            "direction": eur_direction,
            "change_pct": eur_change_pct,
        },
        "usd_jpy": {
            "price": jpy_price,
            "prev_close": jpy_prev,
            "direction": jpy_direction,
            "change_pct": jpy_change_pct,
            "jpy_safe_haven_flow": jpy_safe_haven,
        },
        "fred_broad_usd": dtwexbgs,
        "petrodollar_disruption": petrodollar_disruption,
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
            "series_id": "currency_flow",
            "series_name": "Currency Flow Analysis",
            "value": dxy_price,
            "previous_value": dxy_prev,
            "change_direction": usd_direction,
            "significance": f"USD {usd_risk_signal}; JPY safe-haven={jpy_safe_haven}; petrodollar disruption={petrodollar_disruption}",
        }
        insert("macro_data", row)
        logger.info("Wrote currency_flow to Supabase macro_data")
    except Exception as e:
        logger.error(f"Supabase write failed: {e}")

    result["status"] = "ok"
    result["records"] = result.get("records", 0)
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
