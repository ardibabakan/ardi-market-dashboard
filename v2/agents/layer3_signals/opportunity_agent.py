"""
Opportunity Agent — Layer 3 Signals
Ardi Market Command Center v2

Reads fallen_angel_agent_output.json for STRONG quality candidates.
If found, sends opportunity alert.
"""
import json, logging, sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import *
from lib.supabase_client import insert, select
from lib.ntfy_client import send_opportunity_alert, send_alert
from lib.safe_scalar import safe_scalar

logger = logging.getLogger("ardi.layer3.opportunity")


def _load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load {path}: {e}")
        return {}


def run():
    logger.info("Opportunity agent starting...")
    now_str = datetime.now(timezone.utc).isoformat()
    results = {"timestamp": now_str, "opportunities": []}
    records_written = 0
    alerts_sent = 0

    # Read fallen angel output
    fa_data = _load_json(AGENT_OUTPUT_DIR / "fallen_angel_agent_output.json")
    candidates = fa_data.get("candidates", fa_data.get("fallen_angels", []))

    if isinstance(candidates, dict):
        # Sometimes output is {ticker: {...}, ...}
        candidate_list = []
        for ticker, info in candidates.items():
            if isinstance(info, dict):
                info["ticker"] = ticker
                candidate_list.append(info)
        candidates = candidate_list

    strong_candidates = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        quality = (candidate.get("quality") or candidate.get("quality_score") or "").upper()
        if quality == "STRONG":
            strong_candidates.append(candidate)

    for candidate in strong_candidates:
        ticker = candidate.get("ticker", "UNKNOWN")
        drop_pct = safe_scalar(candidate.get("drop_pct") or candidate.get("drop_from_high"), 0)
        reason = candidate.get("reason") or candidate.get("assessment") or "Strong quality fallen angel"
        sector = candidate.get("sector", "unknown")
        price = safe_scalar(candidate.get("price") or candidate.get("current_price"), 0)

        opportunity = {
            "ticker": ticker,
            "quality": "STRONG",
            "drop_pct": round(drop_pct, 2),
            "price": price,
            "sector": sector,
            "reason": reason,
        }
        results["opportunities"].append(opportunity)

        signal_record = {
            "signal_type": "opportunity",
            "signal_name": f"fallen_angel_{ticker}",
            "status": "fired",
            "confidence": 0.7,
            "details": f"{ticker} ({sector}): STRONG quality, down {drop_pct:.1f}% from 52w high. {reason}",
            "source": "opportunity_agent",
            "second_source": "fallen_angel_agent",
            "action_required": "evaluate_for_purchase",
        }
        insert("signals", signal_record)
        records_written += 1

        send_opportunity_alert(
            ticker=ticker,
            reason=f"Fallen angel STRONG candidate: {ticker} ({sector})\nDown {drop_pct:.1f}% from 52w high, current ${price:.2f}\n{reason}",
        )
        alerts_sent += 1
        logger.info(f"Opportunity alert: {ticker} — STRONG fallen angel")

    results["alerts_sent"] = alerts_sent
    results["strong_count"] = len(strong_candidates)

    # Write local JSON
    output_path = AGENT_OUTPUT_DIR / "opportunity_agent_output.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info(f"Opportunity agent done — {len(strong_candidates)} STRONG candidates, {alerts_sent} alerts sent")
    return {"status": "ok", "records": records_written, "alerts": alerts_sent}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
