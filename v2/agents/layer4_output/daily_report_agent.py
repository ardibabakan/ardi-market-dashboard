"""
Daily Report Agent — Layer 4 Output
Ardi Market Command Center v2

Reads all Layer 2+3 outputs, synthesizes into daily report.
Uses Claude API if available, otherwise generates fallback report.
"""
import json
import logging
import os
import sys
from pathlib import Path
from datetime import datetime, timezone, date

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import *
from lib.supabase_client import insert, select, get_client

logger = logging.getLogger("ardi.layer4.daily_report")


def _conflict_day():
    start = date.fromisoformat(CONFLICT_START_DATE)
    return (date.today() - start).days


def _load_output(name):
    try:
        p = AGENT_OUTPUT_DIR / f"{name}_output.json"
        if p.exists():
            with open(p) as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _build_data_package():
    """Collect all agent outputs into a single package."""
    pkg = {
        "date": str(date.today()),
        "conflict_day": _conflict_day(),
        "yahoo": _load_output("yahoo_agent"),
        "cboe": _load_output("cboe_agent"),
        "fred": _load_output("fred_agent"),
        "coingecko": _load_output("coingecko_agent"),
        "treasury": _load_output("treasury_agent"),
        "technical": _load_output("technical_agent"),
        "regime": _load_output("regime_agent"),
        "oil_premium": _load_output("oil_premium_agent"),
        "benchmark": _load_output("benchmark_agent"),
        "geopolitical": _load_output("geopolitical_scenario_agent"),
        "fallen_angel": _load_output("fallen_angel_agent"),
        "crypto_regime": _load_output("crypto_regime_agent"),
        "risk_simulation": _load_output("risk_simulation_agent"),
        "earnings": _load_output("earnings_agent"),
        "perplexity": _load_output("perplexity_agent"),
        "ceasefire_signals": _load_output("ceasefire_signal_agent"),
        "danger_signals": _load_output("danger_signal_agent"),
    }
    return pkg


def _generate_claude_report(data_package):
    """Use Claude API for polished report synthesis."""
    import requests
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return None

    system_prompt = """You are the Ardi Market Command Center daily report writer.
You write in plain English for a beginner investor named Ardi.
No jargon. Every term explained. Every action is specific.
You are direct and honest — never sugarcoat bad news.

The report follows this EXACT structure:
1. TODAY'S ACTION (one clear sentence at the very top)
2. BLACK SWAN CHECK (only if something unusual detected)
3. PORTFOLIO STATUS (value, change, vs SPY benchmark)
4. SIGNALS (ceasefire count, danger count, details)
5. WAR UPDATE (conflict day, oil premium, scenario probabilities)
6. MARKET REGIME (current regime, implications)
7. TECHNICAL ANALYSIS (summary for each holding)
8. OPPORTUNITIES (fallen angels, momentum)
9. CRYPTO UPDATE (XRP first, then others)
10. RISK ASSESSMENT (VaR, correlations, concentration)
11. EARNINGS CALENDAR (upcoming dates)
12. PERPLEXITY MORNING PROMPT (copy-pasteable)

For TODAY'S ACTION use this priority:
1. Black Swan -> "Move to 50% cash"
2. Danger signal -> "Do not trade today"
3. Stop loss hit -> "STOP LOSS on [TICKER] — review immediately"
4. 2+ ceasefire signals -> "Buy DAL and RCL now — Phase B triggered"
5. Profit target hit -> "Take profits on [TICKER]"
6. Earnings within 7 days -> "Earnings warning for [TICKER]"
7. Strong opportunity -> "New opportunity: [TICKER]"
8. Default -> "HOLD. No trades needed today."
"""

    user_prompt = f"""Here is today's complete data package:

{json.dumps(data_package, indent=2, default=str)[:12000]}

Write the daily report following the exact structure in your instructions.
Include the conflict day number, oil premium calculation, and benchmark comparison.
End with the Perplexity morning prompt customized for today's conflict day."""

    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 6000,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
            },
            timeout=120,
        )
        if response.status_code == 200:
            data = response.json()
            return data["content"][0]["text"]
        else:
            logger.warning(f"Claude API returned {response.status_code}")
            return None
    except Exception as e:
        logger.warning(f"Claude API call failed: {e}")
        return None


def _generate_fallback_report(pkg):
    """Template-based report when Claude API is unavailable."""
    day = pkg.get("conflict_day", 0)
    today = pkg.get("date", str(date.today()))

    # Extract key data
    cboe = pkg.get("cboe", {})
    vix = cboe.get("vix", "N/A")
    regime = cboe.get("regime", "N/A")

    oil = pkg.get("oil_premium", {})
    oil_price = oil.get("current_price", "N/A")
    war_premium = oil.get("war_premium", "N/A")

    benchmark = pkg.get("benchmark", {})
    spy_change = benchmark.get("spy_change_pct", "N/A")
    port_change = benchmark.get("portfolio_change_pct", "N/A")

    ceasefire = pkg.get("ceasefire_signals", {})
    cf_count = ceasefire.get("total_fired", 0)
    danger = pkg.get("danger_signals", {})
    dg_count = danger.get("total_fired", 0)

    # Determine action
    if dg_count > 0:
        action = "DANGER SIGNAL FIRED — Do not trade today."
    elif cf_count >= 2:
        action = "CEASEFIRE SIGNALS FIRED (2+) — Phase B triggered. Buy DAL + RCL."
    else:
        action = "HOLD. No trades needed today."

    report = f"""# DAILY REPORT — {today}
## Iran-US-Israel Conflict: Day {day}

## TODAY'S ACTION
**{action}**

## SIGNALS
- Ceasefire signals fired: {cf_count}/6
- Danger signals fired: {dg_count}/7

## MARKET STATUS
- VIX: {vix} (Regime: {regime})
- Oil (WTI): ${oil_price}
- War premium: ${war_premium}

## BENCHMARK
- SPY change since conflict: {spy_change}%
- Portfolio change (estimated): {port_change}%

## PORTFOLIO HOLDINGS
"""

    # Add technical data for each ticker
    tech = pkg.get("technical", {})
    if isinstance(tech, dict):
        for ticker, data in tech.items():
            if isinstance(data, dict):
                score = data.get("overall_score", "N/A")
                rsi = data.get("rsi", "N/A")
                report += f"- {ticker}: Score={score}, RSI={rsi}\n"

    # Crypto
    crypto = pkg.get("coingecko", {})
    coins = crypto.get("coins", {})
    if coins:
        report += "\n## CRYPTO\n"
        for coin_id, data in coins.items():
            if isinstance(data, dict):
                sym = data.get("symbol", coin_id)
                price = data.get("price", "N/A")
                change = data.get("pct_from_baseline", "N/A")
                report += f"- {sym}: ${price} ({change}% from baseline)\n"

    # Perplexity prompt
    tickers = ", ".join(PLANNED_POSITIONS.keys())
    crypto_list = ", ".join(v["symbol"] for v in CRYPTO_HOLDINGS.values())
    report += f"""
## PERPLEXITY MORNING PROMPT
```
Scan all global news from the last 12 hours.
I track: {tickers}
Watching: DAL, RCL
Crypto: {crypto_list} (XRP largest)
Active conflicts: Iran-US-Israel (Day {day}), Russia-Ukraine (Year 4)

Tell me:
1. Every significant global event
2. Ceasefire signals: peace language, mediators, Trump statement?
3. Danger signals: escalation, new attacks, new countries?
4. XRP/SEC news
5. Fed news
6. Oil news — OPEC, Hormuz
7. Fallen angel candidates
```
"""
    return report


def run():
    logger.info("Daily Report Agent starting...")
    records_written = 0

    pkg = _build_data_package()

    # Try Claude API first
    report = _generate_claude_report(pkg)
    source = "claude_api"
    if not report:
        report = _generate_fallback_report(pkg)
        source = "fallback_template"

    today_str = str(date.today())

    # Save to file
    report_path = DAILY_DIR / f"STOCKS_{today_str}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        f.write(report)
    logger.info(f"Daily report saved to {report_path}")

    # Save broad universe report
    broad = _generate_broad_universe(pkg)
    broad_path = DAILY_DIR / f"BROAD_UNIVERSE_{today_str}.md"
    with open(broad_path, "w") as f:
        f.write(broad)

    # Save to Supabase
    try:
        client = get_client()
        client.table("daily_reports").upsert({
            "report_date": today_str,
            "report_markdown": report[:10000],
            "broad_universe_markdown": broad[:10000],
            "conflict_day": _conflict_day(),
            "action_today": "HOLD" if "HOLD" in report[:200] else "ALERT",
        }, on_conflict="report_date").execute()
        records_written += 1
    except Exception as e:
        logger.error(f"Supabase write failed: {e}")

    # Local JSON output
    output_path = AGENT_OUTPUT_DIR / "daily_report_agent_output.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump({"date": today_str, "source": source, "report_length": len(report)}, f, indent=2)

    logger.info(f"Daily Report Agent complete. Source: {source}")
    return {"status": "ok", "records": records_written}


def _generate_broad_universe(pkg):
    """Generate broad universe report focusing on global events and opportunities."""
    today_str = str(date.today())
    day = pkg.get("conflict_day", 0)

    report = f"# BROAD UNIVERSE SCAN — {today_str}\n## Conflict Day {day}\n\n"

    # Global events from perplexity
    perp = pkg.get("perplexity", {})
    if perp.get("raw_response"):
        report += "## GLOBAL EVENTS (Perplexity Scan)\n"
        report += perp["raw_response"][:3000] + "\n\n"

    # Fallen angels
    fa = pkg.get("fallen_angel", {})
    if isinstance(fa, dict) and fa.get("fallen_angels"):
        report += "## FALLEN ANGELS\n"
        for angel in fa["fallen_angels"][:10]:
            if isinstance(angel, dict):
                report += f"- {angel.get('ticker', '?')}: {angel.get('quality_score', '?')} — dropped {angel.get('drop_pct', '?')}% from 52w high\n"
        report += "\n"

    # Crypto
    crypto = pkg.get("crypto_regime", {})
    if isinstance(crypto, dict):
        report += "## CRYPTO REGIME\n"
        report += json.dumps(crypto, indent=2, default=str)[:1000] + "\n\n"

    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
