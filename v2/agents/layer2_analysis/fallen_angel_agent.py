"""
Agent 14: Fallen Angel Agent
Reads yahoo_agent_output.json for prices.
For stocks in first 30 of ALL_TICKERS, checks 52-week high drop.
If drop >= 30%: candidate. Quality score: STRONG / WATCH / AVOID.
Writes to fallen_angels Supabase table.
"""
import json, logging, sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import *
from lib.supabase_client import insert
from lib.safe_scalar import safe_scalar

logger = logging.getLogger("ardi.fallen_angel")

YAHOO_OUTPUT = AGENT_OUTPUT_DIR / "yahoo_agent_output.json"
LOCAL_OUTPUT = AGENT_OUTPUT_DIR / "fallen_angel_output.json"

# Map tickers to sectors from SCAN_UNIVERSE
TICKER_SECTOR = {}
for sector, tickers in SCAN_UNIVERSE.items():
    for t in tickers:
        TICKER_SECTOR[t] = sector
for t, info in PLANNED_POSITIONS.items():
    TICKER_SECTOR[t] = info.get("sector", "unknown")


def _load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load {path}: {e}")
        return {}


def _assess_quality(ticker_data, drop_pct):
    """
    Simplified quality assessment based on available data.
    STRONG: solid fundamentals, drop likely overdone.
    WATCH: uncertain, needs more investigation.
    AVOID: deteriorating fundamentals.
    """
    if not isinstance(ticker_data, dict):
        return "WATCH", "insufficient data for assessment"

    pe = safe_scalar(ticker_data.get("pe_ratio") or ticker_data.get("trailingPE"), None)
    market_cap = safe_scalar(ticker_data.get("market_cap") or ticker_data.get("marketCap"), None)
    volume = safe_scalar(ticker_data.get("volume"), None)

    # Large cap with moderate PE and big drop = likely overdone
    if market_cap and market_cap > 10e9 and pe and 5 < pe < 25:
        return "STRONG", "large cap, reasonable PE, drop may be overdone"

    # Very high PE or negative earnings
    if pe is not None and (pe > 50 or pe < 0):
        return "AVOID", "elevated/negative PE suggests deteriorating fundamentals"

    # Extreme drop (>50%) is usually a warning
    if drop_pct > 50:
        return "AVOID", "extreme drop >50% suggests fundamental problems"

    return "WATCH", "moderate signals, needs further analysis"


def run():
    logger.info("Fallen Angel Agent starting")
    now = datetime.now(timezone.utc).isoformat()

    yahoo_data = _load_json(YAHOO_OUTPUT)
    if not yahoo_data:
        logger.warning("No yahoo data available")
        return {"status": "ok", "records": 0}

    # Scan first 30 of ALL_TICKERS
    try:
        scan_tickers = ALL_TICKERS[:30]
    except Exception:
        scan_tickers = list(PLANNED_POSITIONS.keys())
    fallen_angels = []

    for ticker in scan_tickers:
        entry = yahoo_data.get(ticker, {})
        if not isinstance(entry, dict):
            continue

        current_price = safe_scalar(
            entry.get("price") or entry.get("current_price") or entry.get("close"), None
        )
        high_52w = safe_scalar(
            entry.get("52w_high") or entry.get("fiftyTwoWeekHigh") or entry.get("high_52w"), None
        )

        if current_price is None or high_52w is None or high_52w == 0:
            continue

        drop_pct = round(((high_52w - current_price) / high_52w) * 100, 2)

        if drop_pct >= 30:
            quality_score, reason = _assess_quality(entry, drop_pct)

            # Determine recovery trigger
            if quality_score == "STRONG":
                recovery_trigger = "Buy on stabilization or positive catalyst"
            elif quality_score == "WATCH":
                recovery_trigger = "Wait for earnings clarity or sector rotation"
            else:
                recovery_trigger = "Avoid until fundamentals improve"

            company_name = entry.get("name") or entry.get("shortName") or ticker
            sector = TICKER_SECTOR.get(ticker, "unknown")

            angel = {
                "ticker": ticker,
                "company": company_name,
                "sector": sector,
                "current_price": current_price,
                "high_52w": high_52w,
                "drop_pct": drop_pct,
                "reason": reason,
                "recovery_trigger": recovery_trigger,
                "quality_score": quality_score,
            }
            fallen_angels.append(angel)
            logger.info(f"Fallen angel: {ticker} down {drop_pct:.1f}% from 52w high ({quality_score})")

    result = {
        "agent": "fallen_angel",
        "timestamp": now,
        "tickers_scanned": len(scan_tickers),
        "fallen_angels_found": len(fallen_angels),
        "fallen_angels": fallen_angels,
    }

    # Write local output
    try:
        LOCAL_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        with open(LOCAL_OUTPUT, "w") as f:
            json.dump(result, f, indent=2)
        logger.info(f"Wrote {LOCAL_OUTPUT}")
    except Exception as e:
        logger.error(f"Failed to write local output: {e}")

    # Write to Supabase fallen_angels table (valid columns only)
    records_written = 0
    for angel in fallen_angels:
        try:
            row = {
                "ticker": angel["ticker"],
                "company": angel["company"],
                "sector": angel["sector"],
                "current_price": angel["current_price"],
                "high_52w": angel["high_52w"],
                "drop_pct": angel["drop_pct"],
                "reason": angel["reason"],
                "recovery_trigger": angel["recovery_trigger"],
                "quality_score": angel["quality_score"],
                "earnings_revisions": angel.get("earnings_revisions"),
            }
            insert("fallen_angels", row)
            records_written += 1
        except Exception as e:
            logger.error(f"Supabase write failed for {angel['ticker']}: {e}")

    logger.info(f"Fallen Angel Agent complete: {len(fallen_angels)} candidates found")
    result["status"] = "ok"
    result["records"] = result.get("records", 0)
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
