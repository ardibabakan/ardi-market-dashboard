#!/usr/bin/env python3
"""
Test runner for all Layer 2 analysis agents.
"""
import json
import sys
import time
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

AGENTS = [
    ("technical_agent",            "agents.layer2_analysis.technical_agent"),
    ("regime_agent",               "agents.layer2_analysis.regime_agent"),
    ("correlation_agent",          "agents.layer2_analysis.correlation_agent"),
    ("factor_agent",               "agents.layer2_analysis.factor_agent"),
    ("relative_strength_agent",    "agents.layer2_analysis.relative_strength_agent"),
    ("earnings_momentum_agent",    "agents.layer2_analysis.earnings_momentum_agent"),
    ("insider_cluster_agent",      "agents.layer2_analysis.insider_cluster_agent"),
    ("options_flow_agent",         "agents.layer2_analysis.options_flow_agent"),
    ("credit_market_agent",        "agents.layer2_analysis.credit_market_agent"),
    ("oil_premium_agent",          "agents.layer2_analysis.oil_premium_agent"),
    ("currency_flow_agent",        "agents.layer2_analysis.currency_flow_agent"),
    ("crypto_regime_agent",        "agents.layer2_analysis.crypto_regime_agent"),
    ("geopolitical_scenario_agent","agents.layer2_analysis.geopolitical_scenario_agent"),
    ("fallen_angel_agent",         "agents.layer2_analysis.fallen_angel_agent"),
    ("squeeze_agent",              "agents.layer2_analysis.squeeze_agent"),
    ("risk_simulation_agent",      "agents.layer2_analysis.risk_simulation_agent"),
    ("tax_agent",                  "agents.layer2_analysis.tax_agent"),
    ("dividend_agent",             "agents.layer2_analysis.dividend_agent"),
    ("benchmark_agent",            "agents.layer2_analysis.benchmark_agent"),
    ("rebalance_agent",            "agents.layer2_analysis.rebalance_agent"),
]


def run_all():
    results = {}
    print("\nPHASE 3 — TESTING ALL LAYER 2 AGENTS")
    print("=" * 55)
    print(f"{'Agent':<30} {'Status':<10} {'Records':<10} {'Time'}")
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
            print(f"{name:<30} {status_str:<10} {records:<10} {elapsed:.1f}s")
            results[name] = {"status": status_str, "records": records, "time": round(elapsed, 1)}
        except Exception as e:
            elapsed = time.time() - start
            print(f"{name:<30} {'FAIL':<10} {'0':<10} {elapsed:.1f}s  ERROR: {e}")
            results[name] = {"status": "FAIL", "records": 0, "time": round(elapsed, 1), "error": str(e)}

    ok = sum(1 for r in results.values() if r["status"] == "OK")
    skip = sum(1 for r in results.values() if r["status"] == "SKIP")
    fail = sum(1 for r in results.values() if r["status"] == "FAIL")
    total_records = sum(r["records"] for r in results.values())

    print("=" * 55)
    print(f"OK: {ok}  SKIP: {skip}  FAIL: {fail}  Total records: {total_records}")
    return results


if __name__ == "__main__":
    run_all()
