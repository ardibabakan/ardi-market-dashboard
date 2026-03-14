"""
Finnhub Agent — Layer 1 Data Collection
Ardi Market Command Center v2

Collects: Real-time quotes, company news, market status.
"""
import json
import logging
import sys
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import PLANNED_POSITIONS, FINNHUB_KEY, AGENT_OUTPUT_DIR
from lib.supabase_client import insert
from lib.data_validator import validate_price

logger = logging.getLogger("ardi.layer1.finnhub")


def run():
    """Main entry point."""
    logger.info("Finnhub Agent starting...")

    if not FINNHUB_KEY:
        logger.warning("FINNHUB_KEY not set — skipping")
        return {"status": "skipped", "reason": "no_api_key", "records": 0}

    import finnhub
    client = finnhub.Client(api_key=FINNHUB_KEY)
    results = {"quotes": {}, "news": [], "market_status": None}
    records_written = 0

    # Market status
    try:
        status = client.market_status(exchange="US")
        results["market_status"] = status
        logger.info(f"US market status: {status}")
    except Exception as e:
        logger.warning(f"Market status failed: {e}")

    today = datetime.now(timezone.utc)
    week_ago = today - timedelta(days=7)
    from_date = week_ago.strftime("%Y-%m-%d")
    to_date = today.strftime("%Y-%m-%d")

    for ticker in PLANNED_POSITIONS:
        # Quote
        try:
            time.sleep(0.2)
            quote = client.quote(ticker)
            if quote and quote.get("c"):
                price = validate_price(quote["c"], ticker)
                if price:
                    info = {
                        "ticker": ticker,
                        "price": price,
                        "high": quote.get("h"),
                        "low": quote.get("l"),
                        "open": quote.get("o"),
                        "prev_close": quote.get("pc"),
                        "change_pct": round(((price - quote.get("pc", price)) / quote.get("pc", price)) * 100, 2) if quote.get("pc") else 0,
                    }
                    results["quotes"][ticker] = info
                    insert("price_snapshots", {
                        "ticker": ticker,
                        "price": price,
                        "prev_close": quote.get("pc"),
                        "change_pct": info["change_pct"],
                        "source": "finnhub",
                    })
                    records_written += 1
        except Exception as e:
            logger.warning(f"Finnhub quote failed for {ticker}: {e}")

        # Company news
        try:
            time.sleep(0.2)
            news = client.company_news(ticker, _from=from_date, to=to_date)
            if news:
                for article in news[:5]:  # top 5 per ticker
                    event = {
                        "event_type": "corporate",
                        "headline": article.get("headline", "")[:500],
                        "summary": article.get("summary", "")[:1000],
                        "source": article.get("source", "finnhub"),
                        "affected_tickers": ticker,
                        "severity": "minor",
                    }
                    results["news"].append(event)
                    insert("events", event)
                    records_written += 1
        except Exception as e:
            logger.warning(f"Finnhub news failed for {ticker}: {e}")

    # Write local JSON
    output_path = AGENT_OUTPUT_DIR / "finnhub_agent_output.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info(f"Finnhub Agent complete. {records_written} records.")
    return {"status": "ok", "records": records_written}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
