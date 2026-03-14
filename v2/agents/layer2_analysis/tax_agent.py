"""
Agent 17: Tax Agent
Reads positions from Supabase positions table.
During paper trading (all status='planned'): reports theoretical tax implications.
Tracks holding periods, flags positions approaching 365 days for long-term gains.
Identifies tax-loss harvesting opportunities. Warns about wash-sale rule.
Writes to events Supabase table.
"""
import json, logging, sys
from pathlib import Path
from datetime import datetime, timezone, date, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import *
from lib.supabase_client import insert, select
from lib.safe_scalar import safe_scalar

logger = logging.getLogger("ardi.tax")

YAHOO_OUTPUT = AGENT_OUTPUT_DIR / "yahoo_agent_output.json"
LOCAL_OUTPUT = AGENT_OUTPUT_DIR / "tax_output.json"

LONG_TERM_DAYS = 365
LONG_TERM_WARNING_DAYS = 30  # warn when within 30 days of long-term threshold


def _load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load {path}: {e}")
        return {}


def run():
    logger.info("Tax Agent starting")
    now = datetime.now(timezone.utc).isoformat()
    today = date.fromisoformat("2026-03-14")

    # Read positions from Supabase
    try:
        positions = select("positions") or []
    except Exception as e:
        logger.warning(f"Could not read positions: {e}")
        positions = []

    yahoo_data = _load_json(YAHOO_OUTPUT)

    is_paper_trading = all(
        p.get("status", "planned") == "planned" for p in positions
    ) if positions else True

    tax_items = []
    harvesting_opportunities = []
    long_term_approaching = []
    wash_sale_warnings = []

    for pos in positions:
        ticker = pos.get("ticker", "UNKNOWN")
        entry_price = safe_scalar(pos.get("entry_price") or pos.get("planned_price"), None)
        entry_date_str = pos.get("entry_date") or pos.get("created_at", "")
        status = pos.get("status", "planned")
        shares = safe_scalar(pos.get("shares") or pos.get("planned_shares"), 0)

        # Get current price from yahoo data
        yahoo_entry = yahoo_data.get(ticker, {})
        current_price = safe_scalar(
            yahoo_entry.get("price") or yahoo_entry.get("current_price") or yahoo_entry.get("close"),
            None
        )

        # Parse entry date
        entry_date = None
        try:
            if entry_date_str:
                entry_date = date.fromisoformat(entry_date_str[:10])
        except (ValueError, TypeError):
            pass

        # Holding period
        holding_days = (today - entry_date).days if entry_date else 0
        is_long_term = holding_days >= LONG_TERM_DAYS

        # Unrealized P&L
        unrealized_pnl = None
        unrealized_pnl_pct = None
        if entry_price and current_price and shares:
            unrealized_pnl = round((current_price - entry_price) * shares, 2)
            unrealized_pnl_pct = round(((current_price - entry_price) / entry_price) * 100, 2)

        item = {
            "ticker": ticker,
            "status": status,
            "entry_price": entry_price,
            "current_price": current_price,
            "shares": shares,
            "holding_days": holding_days,
            "is_long_term": is_long_term,
            "tax_treatment": "long-term capital gains" if is_long_term else "short-term capital gains",
            "unrealized_pnl": unrealized_pnl,
            "unrealized_pnl_pct": unrealized_pnl_pct,
        }
        tax_items.append(item)

        # Flag positions approaching long-term threshold
        days_to_long_term = LONG_TERM_DAYS - holding_days
        if 0 < days_to_long_term <= LONG_TERM_WARNING_DAYS:
            approaching = {
                "ticker": ticker,
                "days_to_long_term": days_to_long_term,
                "date_becomes_long_term": (entry_date + timedelta(days=LONG_TERM_DAYS)).isoformat() if entry_date else None,
                "advice": f"HOLD {days_to_long_term} more days for long-term capital gains rate",
            }
            long_term_approaching.append(approaching)

        # Tax-loss harvesting: unrealized loss > 5%
        if unrealized_pnl is not None and unrealized_pnl < 0 and unrealized_pnl_pct and unrealized_pnl_pct < -5:
            harvest = {
                "ticker": ticker,
                "unrealized_loss": unrealized_pnl,
                "loss_pct": unrealized_pnl_pct,
                "advice": f"Consider selling {ticker} to harvest ${abs(unrealized_pnl):.2f} tax loss",
                "wash_sale_warning": f"Cannot repurchase {ticker} or substantially identical security for 30 days",
            }
            harvesting_opportunities.append(harvest)

            # Wash sale warning for same-sector stocks
            sector = PLANNED_POSITIONS.get(ticker, {}).get("sector", "")
            similar = [t for t, info in PLANNED_POSITIONS.items()
                      if info.get("sector") == sector and t != ticker]
            if similar:
                wash_sale_warnings.append({
                    "ticker": ticker,
                    "similar_tickers": similar,
                    "warning": f"Buying {similar} within 30 days of selling {ticker} may trigger wash-sale rule (same sector: {sector})",
                })

    # Summary
    total_unrealized = sum(
        i["unrealized_pnl"] for i in tax_items if i["unrealized_pnl"] is not None
    )
    total_gains = sum(
        i["unrealized_pnl"] for i in tax_items if i["unrealized_pnl"] is not None and i["unrealized_pnl"] > 0
    )
    total_losses = sum(
        i["unrealized_pnl"] for i in tax_items if i["unrealized_pnl"] is not None and i["unrealized_pnl"] < 0
    )

    result = {
        "agent": "tax",
        "timestamp": now,
        "paper_trading": is_paper_trading,
        "note": "All values are theoretical (paper trading)" if is_paper_trading else "Live positions",
        "positions_analyzed": len(tax_items),
        "summary": {
            "total_unrealized_pnl": round(total_unrealized, 2),
            "total_unrealized_gains": round(total_gains, 2),
            "total_unrealized_losses": round(total_losses, 2),
            "net_tax_offset_potential": round(abs(total_losses), 2) if total_losses < 0 else 0,
        },
        "tax_items": tax_items,
        "long_term_approaching": long_term_approaching,
        "harvesting_opportunities": harvesting_opportunities,
        "wash_sale_warnings": wash_sale_warnings,
    }

    # Write local output
    try:
        LOCAL_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        with open(LOCAL_OUTPUT, "w") as f:
            json.dump(result, f, indent=2)
        logger.info(f"Wrote {LOCAL_OUTPUT}")
    except Exception as e:
        logger.error(f"Failed to write local output: {e}")

    # Write to Supabase events table (valid columns only)
    try:
        alerts = []
        if long_term_approaching:
            alerts.append(f"{len(long_term_approaching)} positions approaching long-term threshold")
        if harvesting_opportunities:
            alerts.append(f"{len(harvesting_opportunities)} tax-loss harvesting opportunities")
        if wash_sale_warnings:
            alerts.append(f"{len(wash_sale_warnings)} wash-sale warnings")

        headline = "Tax analysis: " + ("; ".join(alerts) if alerts else "no actionable items")
        prefix = "[PAPER] " if is_paper_trading else ""

        row = {
            "event_type": "tax_analysis",
            "headline": prefix + headline,
            "summary": json.dumps({
                "summary": result["summary"],
                "long_term_approaching": long_term_approaching,
                "harvesting_opportunities": harvesting_opportunities,
                "wash_sale_warnings": wash_sale_warnings,
            }),
            "severity": "medium" if alerts else "low",
        }
        insert("events", row)
        logger.info("Wrote tax analysis to Supabase events")
    except Exception as e:
        logger.error(f"Supabase write failed: {e}")

    logger.info("Tax Agent complete")
    result["status"] = "ok"
    result["records"] = result.get("records", 0)
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
