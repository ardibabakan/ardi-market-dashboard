"""
Earnings Agent — Layer 1 Data Collection
Ardi Market Command Center v2

Collects: Earnings dates, analyst estimates, revision trends.
"""
import json
import logging
import sys
from pathlib import Path
from datetime import datetime, timezone, date

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import PLANNED_POSITIONS, PHASE_B_POSITIONS, AGENT_OUTPUT_DIR
from lib.supabase_client import insert

logger = logging.getLogger("ardi.layer1.earnings")


def run():
    """Main entry point."""
    logger.info("Earnings Agent starting...")
    import yfinance as yf
    import time

    results = {}
    records_written = 0
    all_tickers = list(PLANNED_POSITIONS.keys()) + list(PHASE_B_POSITIONS.keys())

    for ticker in all_tickers:
        time.sleep(0.3)
        try:
            t = yf.Ticker(ticker)
            cal = t.calendar
            info = t.info or {}

            # Next earnings date
            earnings_date = None
            days_until = None

            if cal is not None:
                if isinstance(cal, dict):
                    ed = cal.get("Earnings Date")
                    if ed:
                        if isinstance(ed, list) and len(ed) > 0:
                            earnings_date = str(ed[0])
                        else:
                            earnings_date = str(ed)

            if earnings_date:
                try:
                    ed_date = datetime.strptime(earnings_date[:10], "%Y-%m-%d").date()
                    days_until = (ed_date - date.today()).days
                except (ValueError, TypeError):
                    pass

            # Analyst recommendations
            rec = info.get("recommendationKey", "")
            target_mean = info.get("targetMeanPrice")
            target_high = info.get("targetHighPrice")
            target_low = info.get("targetLowPrice")
            num_analysts = info.get("numberOfAnalystOpinions", 0)

            # Flags
            flags = []
            if days_until is not None and days_until < 7 and days_until >= 0:
                flags.append("URGENT: Earnings < 7 days away — no new purchases")
            if days_until is not None and days_until < 0:
                flags.append("Earnings already reported this period")

            entry = {
                "ticker": ticker,
                "next_earnings": earnings_date,
                "days_until_earnings": days_until,
                "recommendation": rec,
                "target_mean": target_mean,
                "target_high": target_high,
                "target_low": target_low,
                "num_analysts": num_analysts,
                "flags": flags,
            }
            results[ticker] = entry

            # Write earnings-near event if applicable
            if flags:
                for flag in flags:
                    insert("events", {
                        "event_type": "corporate",
                        "headline": f"Earnings: {ticker} — {flag}",
                        "summary": f"Next earnings: {earnings_date}. Analysts: {num_analysts}, target: ${target_mean}",
                        "source": "yfinance",
                        "affected_tickers": ticker,
                        "severity": "moderate" if "URGENT" in flag else "minor",
                    })
                    records_written += 1

        except Exception as e:
            logger.warning(f"Earnings fetch failed for {ticker}: {e}")

    # Write local JSON
    output_path = AGENT_OUTPUT_DIR / "earnings_agent_output.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info(f"Earnings Agent complete. {records_written} records.")
    return {"status": "ok", "records": records_written}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
