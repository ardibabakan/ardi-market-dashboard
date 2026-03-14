"""
Perplexity Agent — Layer 1 Data Collection
Ardi Market Command Center v2

AI-powered global news intelligence scan.
Detects ceasefire signals, danger signals, and market events.
"""
import json
import logging
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import (
    PERPLEXITY_KEY, AGENT_OUTPUT_DIR, CONFLICT_START_DATE,
    PLANNED_POSITIONS, PHASE_B_POSITIONS, CRYPTO_HOLDINGS
)
from lib.supabase_client import insert

logger = logging.getLogger("ardi.layer1.perplexity")

PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"


def _calculate_conflict_day():
    from datetime import date
    start = date.fromisoformat(CONFLICT_START_DATE)
    return (date.today() - start).days


def _call_perplexity(prompt):
    import requests
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "sonar",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 2000,
    }
    resp = requests.post(PERPLEXITY_URL, json=payload, headers=headers, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def _parse_signals(text):
    """Extract ceasefire and danger signals from Perplexity response."""
    signals = []
    text_lower = text.lower()

    # Ceasefire keywords
    ceasefire_keywords = [
        "ceasefire", "peace talk", "diplomatic", "negotiation",
        "de-escalation", "truce", "peace deal", "mediator",
    ]
    for kw in ceasefire_keywords:
        if kw in text_lower:
            signals.append({
                "signal_type": "ceasefire",
                "signal_name": f"perplexity_detected_{kw.replace(' ', '_')}",
                "status": "unconfirmed",
                "details": f"Perplexity detected '{kw}' in news scan. Needs Exa confirmation.",
                "source": "perplexity",
            })

    # Danger keywords
    danger_keywords = [
        "nuclear", "tactical nuclear", "china taiwan invasion",
        "carrier attacked", "us base attacked", "escalation",
        "iran nuclear weapon", "martial law",
    ]
    for kw in danger_keywords:
        if kw in text_lower:
            signals.append({
                "signal_type": "danger",
                "signal_name": f"perplexity_detected_{kw.replace(' ', '_')}",
                "status": "unconfirmed",
                "details": f"Perplexity detected '{kw}' in news scan. Needs Exa confirmation.",
                "source": "perplexity",
            })

    return signals


def run():
    """Main entry point."""
    logger.info("Perplexity Agent starting...")

    if not PERPLEXITY_KEY:
        logger.warning("PERPLEXITY_KEY not set — skipping")
        return {"status": "skipped", "reason": "no_api_key", "records": 0}

    conflict_day = _calculate_conflict_day()
    tickers = ", ".join(PLANNED_POSITIONS.keys())
    phase_b = ", ".join(PHASE_B_POSITIONS.keys())
    crypto = ", ".join(f"{v['symbol']}" for v in CRYPTO_HOLDINGS.values())

    prompt = f"""Scan all global news from the last 12 hours.
I track these investments: {tickers}
Watching: {phase_b}
Crypto: {crypto} (XRP is largest holding)
Active conflicts: Iran-US-Israel (Day {conflict_day}), Russia-Ukraine (Year 4)

Tell me:
1. Every significant global event in the last 12 hours
2. Ceasefire signals: Iranian peace language? Mediator? Trump statement?
3. Danger signals: escalation? new attacks? new countries joining?
4. XRP/Ripple SEC news
5. Federal Reserve news
6. Oil market news — OPEC, Hormuz, supply disruptions
7. Any stock that crashed for temporary reasons (fallen angel candidate)

Be specific with sources and dates. If no significant events, say so."""

    results = {"raw_response": "", "events": [], "signals": []}
    records_written = 0

    try:
        response = _call_perplexity(prompt)
        results["raw_response"] = response

        # Parse signals
        signals = _parse_signals(response)
        results["signals"] = signals

        for sig in signals:
            insert("signals", sig)
            records_written += 1

        # Store the full scan as an event
        insert("events", {
            "event_type": "geopolitical",
            "headline": f"Perplexity news scan — Day {conflict_day}",
            "summary": response[:2000],
            "source": "perplexity",
            "severity": "moderate" if signals else "minor",
        })
        records_written += 1

    except Exception as e:
        logger.error(f"Perplexity scan failed: {e}")
        return {"status": "error", "error": str(e)}

    # Write local JSON
    output_path = AGENT_OUTPUT_DIR / "perplexity_agent_output.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info(f"Perplexity Agent complete. {records_written} records, {len(signals)} signals detected.")
    return {"status": "ok", "records": records_written, "signals_found": len(signals)}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
