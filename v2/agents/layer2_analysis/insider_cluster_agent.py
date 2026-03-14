"""
Insider Cluster Agent — Layer 2 Analysis
Ardi Market Command Center v2

Reads sec_agent_output.json, counts insider buys/sells per ticker
from Form 4 data. Flags cluster buys (3+ buys within 14 days).
"""
import json, logging, sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import PLANNED_POSITIONS, AGENT_OUTPUT_DIR
from lib.supabase_client import insert
from lib.safe_scalar import safe_scalar

logger = logging.getLogger("ardi.layer2.insider_cluster")

PORTFOLIO_TICKERS = list(PLANNED_POSITIONS.keys())
CLUSTER_THRESHOLD = 3   # 3+ buys
CLUSTER_WINDOW_DAYS = 14


def _load_sec_data():
    path = AGENT_OUTPUT_DIR / "sec_agent_output.json"
    if not path.exists():
        logger.error("sec_agent_output.json not found")
        return None
    with open(path) as f:
        return json.load(f)


def _parse_date(date_str):
    """Try to parse a date string from various formats."""
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%m/%d/%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(date_str, fmt)
        except (ValueError, TypeError):
            continue
    return None


def _analyze_insider_activity(ticker, sec_data):
    """Analyze Form 4 filings for a ticker."""
    ticker_data = sec_data.get(ticker, {})

    # Handle different possible structures from sec_agent
    filings = ticker_data.get("form4_filings", [])
    if not filings:
        filings = ticker_data.get("filings", [])
    if not filings:
        filings = ticker_data.get("insider_transactions", [])
    if not filings and isinstance(ticker_data, list):
        filings = ticker_data

    buys = []
    sells = []

    for filing in filings:
        if not isinstance(filing, dict):
            continue

        tx_type = str(filing.get("transaction_type", "") or
                      filing.get("type", "") or
                      filing.get("action", "")).upper()
        tx_date = _parse_date(
            filing.get("date") or filing.get("transaction_date") or
            filing.get("filing_date")
        )
        shares = safe_scalar(filing.get("shares", 0))
        value = safe_scalar(filing.get("value", 0))

        entry = {
            "date": tx_date.isoformat() if tx_date else None,
            "insider": filing.get("insider", filing.get("owner", "unknown")),
            "shares": shares,
            "value": value,
        }

        if any(kw in tx_type for kw in ["BUY", "PURCHASE", "P-PURCHASE", "ACQUISITION"]):
            buys.append({**entry, "parsed_date": tx_date})
        elif any(kw in tx_type for kw in ["SELL", "SALE", "DISPOSITION", "S-SALE"]):
            sells.append({**entry, "parsed_date": tx_date})

    # Detect cluster buys: 3+ distinct buys within 14-day window
    cluster_detected = False
    cluster_details = []

    if len(buys) >= CLUSTER_THRESHOLD:
        dated_buys = [b for b in buys if b.get("parsed_date")]
        dated_buys.sort(key=lambda x: x["parsed_date"])

        for i in range(len(dated_buys)):
            window_start = dated_buys[i]["parsed_date"]
            window_end = window_start + timedelta(days=CLUSTER_WINDOW_DAYS)
            window_buys = [
                b for b in dated_buys
                if window_start <= b["parsed_date"] <= window_end
            ]
            if len(window_buys) >= CLUSTER_THRESHOLD:
                cluster_detected = True
                cluster_details = [
                    {"insider": b["insider"], "date": b["date"], "value": b["value"]}
                    for b in window_buys
                ]
                break

    # Clean up parsed_date before returning
    for b in buys:
        b.pop("parsed_date", None)
    for s in sells:
        s.pop("parsed_date", None)

    return {
        "ticker": ticker,
        "total_buys": len(buys),
        "total_sells": len(sells),
        "net_sentiment": "BULLISH" if len(buys) > len(sells) else (
            "BEARISH" if len(sells) > len(buys) else "NEUTRAL"),
        "cluster_buy_detected": cluster_detected,
        "cluster_details": cluster_details if cluster_detected else [],
        "recent_buys": buys[:5],
        "recent_sells": sells[:5],
    }


def run():
    """Main entry point."""
    logger.info("Insider Cluster Agent starting...")

    sec_data = _load_sec_data()
    if sec_data is None:
        return {"status": "error", "reason": "no SEC data"}

    results = {}
    records_written = 0
    clusters_found = 0

    for ticker in PORTFOLIO_TICKERS:
        analysis = _analyze_insider_activity(ticker, sec_data)
        results[ticker] = analysis

        severity = "info"
        if analysis["cluster_buy_detected"]:
            severity = "warning"
            clusters_found += 1

        insert("events", {
            "event_type": "insider_activity",
            "ticker": ticker,
            "summary": json.dumps(analysis),
            "severity": severity,
        })
        records_written += 1

    # Write local JSON
    output_path = AGENT_OUTPUT_DIR / "insider_cluster_agent_output.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info(f"Insider Cluster Agent complete. {records_written} tickers, {clusters_found} clusters.")
    return {"status": "ok", "records": records_written, "clusters": clusters_found, "data": results}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
