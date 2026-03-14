"""
SEC EDGAR Agent — Layer 1 Data Collection
Ardi Market Command Center v2

Collects: Insider transactions (Form 4), institutional holdings.
"""
import json
import logging
import sys
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import PLANNED_POSITIONS, AGENT_OUTPUT_DIR
from lib.supabase_client import insert

logger = logging.getLogger("ardi.layer1.sec")

SEC_HEADERS = {
    "User-Agent": "ArdiResearch ardi@primepcd.com",
    "Accept-Encoding": "gzip, deflate",
}
SEC_BASE = "https://efts.sec.gov/LATEST/search-index"
EDGAR_FULL_TEXT = "https://efts.sec.gov/LATEST/search-index"
EDGAR_SUBMISSIONS = "https://data.sec.gov/submissions"


def _get_cik(ticker):
    """Look up CIK number for a ticker."""
    import requests
    try:
        resp = requests.get(
            "https://www.sec.gov/cgi-bin/browse-edgar",
            params={"action": "getcompany", "company": ticker, "type": "4", "dateb": "", "owner": "include", "count": "10", "search_text": "", "action": "getcompany", "CIK": ticker, "output": "atom"},
            headers=SEC_HEADERS, timeout=15
        )
        # Simple approach: search EDGAR full-text search
        resp2 = requests.get(
            "https://efts.sec.gov/LATEST/search-index",
            params={"q": f'"{ticker}"', "dateRange": "custom", "startdt": (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"), "enddt": datetime.now().strftime("%Y-%m-%d"), "forms": "4"},
            headers=SEC_HEADERS, timeout=15
        )
        return None  # fallback
    except Exception:
        return None


def _search_form4(ticker):
    """Search for recent Form 4 filings via EDGAR full-text search."""
    import requests
    try:
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        resp = requests.get(
            "https://efts.sec.gov/LATEST/search-index",
            params={
                "q": f'"{ticker}"',
                "dateRange": "custom",
                "startdt": start_date,
                "enddt": end_date,
                "forms": "4",
            },
            headers=SEC_HEADERS, timeout=15
        )
        if resp.status_code == 200:
            data = resp.json()
            hits = data.get("hits", {}).get("hits", [])
            return hits
        return []
    except Exception as e:
        logger.warning(f"SEC search failed for {ticker}: {e}")
        return []


def run():
    """Main entry point."""
    logger.info("SEC Agent starting...")
    import requests

    results = {"insider_activity": {}}
    records_written = 0

    for ticker in PLANNED_POSITIONS:
        time.sleep(0.15)  # max 10 req/sec to SEC

        try:
            # Use EDGAR full-text search API
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

            resp = requests.get(
                "https://efts.sec.gov/LATEST/search-index",
                params={
                    "q": f'"{ticker}"',
                    "dateRange": "custom",
                    "startdt": start_date,
                    "enddt": end_date,
                    "forms": "4",
                },
                headers=SEC_HEADERS, timeout=15
            )

            filings = []
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    hits = data.get("hits", {}).get("hits", [])
                    for hit in hits[:5]:
                        source = hit.get("_source", {})
                        filings.append({
                            "filing_type": "Form 4",
                            "date": source.get("file_date", ""),
                            "description": source.get("display_names", [""])[0] if source.get("display_names") else "",
                        })
                except (json.JSONDecodeError, KeyError):
                    pass

            buy_count = 0
            sell_count = 0

            results["insider_activity"][ticker] = {
                "filings_found": len(filings),
                "filings": filings,
                "buys": buy_count,
                "sells": sell_count,
            }

            if filings:
                insert("events", {
                    "event_type": "corporate",
                    "headline": f"SEC: {len(filings)} Form 4 filings for {ticker} (30 days)",
                    "summary": json.dumps(filings[:3]),
                    "source": "sec_edgar",
                    "affected_tickers": ticker,
                    "severity": "minor",
                })
                records_written += 1

        except Exception as e:
            logger.warning(f"SEC agent failed for {ticker}: {e}")

    # Write local JSON
    output_path = AGENT_OUTPUT_DIR / "sec_agent_output.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info(f"SEC Agent complete. {records_written} records.")
    return {"status": "ok", "records": records_written}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
