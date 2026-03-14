"""
Ardi Market Command Center v2 — Orchestrator
Runs all agents in the correct order.

Usage:
  python3 orchestrator.py --mode daily    # Full 3 AM run (all layers)
  python3 orchestrator.py --mode signal   # 2-hour signal check (layers 1+3 only)
  python3 orchestrator.py --mode weekly   # Sunday weekly review
"""
import argparse
import importlib
import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import *
from lib.supabase_client import insert
from lib.ntfy_client import send_system_health

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(DAILY_DIR / "orchestrator_log.txt", mode="a")
    ]
)
logger = logging.getLogger("ardi.orchestrator")

LAYER_1_AGENTS = [
    "agents.layer1_collection.yahoo_agent",
    "agents.layer1_collection.finnhub_agent",
    "agents.layer1_collection.fred_agent",
    "agents.layer1_collection.coingecko_agent",
    "agents.layer1_collection.eia_agent",
    "agents.layer1_collection.cboe_agent",
    "agents.layer1_collection.treasury_agent",
    "agents.layer1_collection.earnings_agent",
    "agents.layer1_collection.sec_agent",
    "agents.layer1_collection.gpr_agent",
    "agents.layer1_collection.perplexity_agent",
    "agents.layer1_collection.exa_agent",
    "agents.layer1_collection.congress_agent",
    "agents.layer1_collection.weather_agent",
    "agents.layer1_collection.alpha_vantage_agent",
]

LAYER_2_AGENTS = [
    "agents.layer2_analysis.technical_agent",
    "agents.layer2_analysis.regime_agent",
    "agents.layer2_analysis.correlation_agent",
    "agents.layer2_analysis.benchmark_agent",
    "agents.layer2_analysis.oil_premium_agent",
    "agents.layer2_analysis.currency_flow_agent",
    "agents.layer2_analysis.credit_market_agent",
    "agents.layer2_analysis.crypto_regime_agent",
    "agents.layer2_analysis.fallen_angel_agent",
    "agents.layer2_analysis.relative_strength_agent",
    "agents.layer2_analysis.earnings_momentum_agent",
    "agents.layer2_analysis.insider_cluster_agent",
    "agents.layer2_analysis.options_flow_agent",
    "agents.layer2_analysis.squeeze_agent",
    "agents.layer2_analysis.geopolitical_scenario_agent",
    "agents.layer2_analysis.risk_simulation_agent",
    "agents.layer2_analysis.factor_agent",
    "agents.layer2_analysis.rebalance_agent",
    "agents.layer2_analysis.tax_agent",
    "agents.layer2_analysis.dividend_agent",
]

LAYER_3_AGENTS = [
    "agents.layer3_signals.ceasefire_signal_agent",
    "agents.layer3_signals.danger_signal_agent",
    "agents.layer3_signals.stop_loss_agent",
    "agents.layer3_signals.profit_target_agent",
    "agents.layer3_signals.thesis_invalidation_agent",
    "agents.layer3_signals.black_swan_agent",
    "agents.layer3_signals.opportunity_agent",
    "agents.layer3_signals.event_detection_agent",
    "agents.layer3_signals.regime_change_agent",
]

LAYER_4_AGENTS = [
    "agents.layer4_output.daily_report_agent",
    "agents.layer4_output.dashboard_data_agent",
    "agents.layer4_output.alert_priority_agent",
]

def run_agent(module_path, run_id):
    agent_name = module_path.split(".")[-1]
    started = datetime.now(timezone.utc)
    try:
        module = importlib.import_module(module_path)
        # Reload to get fresh data each run
        importlib.reload(module)
        result = module.run()
        status = result.get("status", "unknown") if isinstance(result, dict) else "unknown"
        records = result.get("records", 0) if isinstance(result, dict) else 0
        error = result.get("error", None) if isinstance(result, dict) else None
    except Exception as e:
        status = "failed"
        records = 0
        error = str(e)
        logger.error(f"Agent {agent_name} CRASHED: {e}")

    completed = datetime.now(timezone.utc)
    duration = (completed - started).total_seconds()

    insert("agent_runs", {
        "run_id": run_id,
        "agent_name": agent_name,
        "layer": int(module_path.split("layer")[1][0]) if "layer" in module_path else 0,
        "status": "completed" if status in ("ok", "skipped") else "failed",
        "records_written": records,
        "error_message": error,
        "started_at": started.isoformat(),
        "completed_at": completed.isoformat(),
    })

    icon = "+" if status in ("ok", "skipped") else "X"
    logger.info(f"  {icon} {agent_name}: {status} ({duration:.1f}s, {records} records)")
    return status in ("ok", "skipped")

def run_layer(agents, layer_name, run_id):
    logger.info(f"\n{'='*50}")
    logger.info(f"LAYER: {layer_name}")
    logger.info(f"{'='*50}")
    results = {"ok": 0, "failed": 0}
    for agent_path in agents:
        success = run_agent(agent_path, run_id)
        results["ok" if success else "failed"] += 1
    logger.info(f"{layer_name}: {results['ok']} ok, {results['failed']} failed")
    return results

def run_daily():
    run_id = str(uuid.uuid4())[:8]
    logger.info(f"\n{'#'*60}")
    logger.info(f"DAILY RUN — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    logger.info(f"Run ID: {run_id}")
    logger.info(f"{'#'*60}")
    r1 = run_layer(LAYER_1_AGENTS, "Layer 1: Data Collection", run_id)
    r2 = run_layer(LAYER_2_AGENTS, "Layer 2: Analysis", run_id)
    r3 = run_layer(LAYER_3_AGENTS, "Layer 3: Signals", run_id)
    r4 = run_layer(LAYER_4_AGENTS, "Layer 4: Output", run_id)
    total_ok = r1["ok"] + r2["ok"] + r3["ok"] + r4["ok"]
    total_fail = r1["failed"] + r2["failed"] + r3["failed"] + r4["failed"]
    logger.info(f"\n{'='*60}")
    logger.info(f"DAILY RUN COMPLETE: {total_ok} ok, {total_fail} failed")
    logger.info(f"{'='*60}")
    if total_fail > 0:
        send_system_health(f"Daily run: {total_fail} agents failed", ok=False)

def run_signal_check():
    run_id = f"sig-{str(uuid.uuid4())[:6]}"
    logger.info(f"SIGNAL CHECK — {datetime.now().strftime('%H:%M')}")
    quick_agents = [
        "agents.layer1_collection.yahoo_agent",
        "agents.layer1_collection.cboe_agent",
    ]
    run_layer(quick_agents, "Quick Price Update", run_id)
    run_layer(LAYER_3_AGENTS, "Signal Check", run_id)

def run_weekly():
    run_id = f"wk-{str(uuid.uuid4())[:6]}"
    logger.info(f"WEEKLY REVIEW — {datetime.now().strftime('%Y-%m-%d')}")
    run_daily()
    run_agent("agents.layer4_output.weekly_report_agent", run_id)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["daily", "signal", "weekly"], default="daily")
    args = parser.parse_args()
    if args.mode == "daily":
        run_daily()
    elif args.mode == "signal":
        run_signal_check()
    elif args.mode == "weekly":
        run_weekly()
