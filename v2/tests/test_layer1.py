#!/usr/bin/env python3
"""
Test runner for all Layer 1 data collection agents.
Runs each agent and reports status.
"""
import json
import sys
import time
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

AGENTS = [
    ("yahoo_agent",         "agents.layer1_collection.yahoo_agent"),
    ("alpha_vantage_agent", "agents.layer1_collection.alpha_vantage_agent"),
    ("finnhub_agent",       "agents.layer1_collection.finnhub_agent"),
    ("fred_agent",          "agents.layer1_collection.fred_agent"),
    ("coingecko_agent",     "agents.layer1_collection.coingecko_agent"),
    ("eia_agent",           "agents.layer1_collection.eia_agent"),
    ("cboe_agent",          "agents.layer1_collection.cboe_agent"),
    ("treasury_agent",      "agents.layer1_collection.treasury_agent"),
    ("perplexity_agent",    "agents.layer1_collection.perplexity_agent"),
    ("exa_agent",           "agents.layer1_collection.exa_agent"),
    ("sec_agent",           "agents.layer1_collection.sec_agent"),
    ("earnings_agent",      "agents.layer1_collection.earnings_agent"),
    ("congress_agent",      "agents.layer1_collection.congress_agent"),
    ("weather_agent",       "agents.layer1_collection.weather_agent"),
    ("gpr_agent",           "agents.layer1_collection.gpr_agent"),
]


def run_all():
    results = {}
    print("\nPHASE 2 — TESTING ALL LAYER 1 AGENTS")
    print("=" * 55)
    print(f"{'Agent':<25} {'Status':<10} {'Records':<10} {'Time'}")
    print("-" * 55)

    for name, module_path in AGENTS:
        start = time.time()
        try:
            mod = __import__(module_path, fromlist=["run"])
            result = mod.run()
            elapsed = time.time() - start
            status = result.get("status", "unknown")
            records = result.get("records", 0)
            status_str = "OK" if status in ("ok", "skipped") else "FAIL"
            if status == "skipped":
                status_str = "SKIP"
            print(f"{name:<25} {status_str:<10} {records:<10} {elapsed:.1f}s")
            results[name] = {"status": status_str, "records": records, "time": round(elapsed, 1)}
        except Exception as e:
            elapsed = time.time() - start
            print(f"{name:<25} {'FAIL':<10} {'0':<10} {elapsed:.1f}s  ERROR: {e}")
            results[name] = {"status": "FAIL", "records": 0, "time": round(elapsed, 1), "error": str(e)}

    # Summary
    ok = sum(1 for r in results.values() if r["status"] == "OK")
    skip = sum(1 for r in results.values() if r["status"] == "SKIP")
    fail = sum(1 for r in results.values() if r["status"] == "FAIL")
    total_records = sum(r["records"] for r in results.values())

    print("=" * 55)
    print(f"OK: {ok}  SKIP: {skip}  FAIL: {fail}  Total records: {total_records}")

    # Check local JSON files
    from config import AGENT_OUTPUT_DIR
    json_files = list(AGENT_OUTPUT_DIR.glob("*_output.json"))
    print(f"Local JSON files written: {len(json_files)}")

    return results


if __name__ == "__main__":
    run_all()
