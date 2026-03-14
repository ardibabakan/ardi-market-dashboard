#!/usr/bin/env python3
"""
Import V1 agent output data into Supabase v1_historical table.
Also extracts planned positions and crypto baselines from AGENT_9.
"""
import json
import sys
from pathlib import Path

# Add parent to path for config imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import V1_DIR, PLANNED_POSITIONS, CRYPTO_HOLDINGS
from lib.supabase_client import insert, upsert

def load_json(filepath):
    """Load a JSON file, return None on failure."""
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"  WARNING: Could not load {filepath}: {e}")
        return None

def import_agent_outputs():
    """Import AGENT_0 through AGENT_9 output files."""
    imported = 0
    for i in list(range(8)) + [9]:
        if i == 8:
            continue  # No AGENT_8 file
        if i == 9:
            filename = f"AGENT_9_FOUNDATION_PATCH.json"
        else:
            filename = f"AGENT_{i}_OUTPUT.json"

        filepath = V1_DIR / filename
        if not filepath.exists():
            print(f"  SKIP: {filename} not found")
            continue

        data = load_json(filepath)
        if data is None:
            continue

        agent_id = f"agent_{i}"
        result = insert("v1_historical", {
            "agent_id": agent_id,
            "data": data,
        })

        if result:
            print(f"  OK: {filename} -> v1_historical (agent_id={agent_id})")
            imported += 1
        else:
            print(f"  FAIL: Could not insert {filename}")

    return imported

def import_planned_positions():
    """Create planned position rows from AGENT_9 and config."""
    filepath = V1_DIR / "AGENT_9_FOUNDATION_PATCH.json"
    data = load_json(filepath)

    count = 0
    for ticker, info in PLANNED_POSITIONS.items():
        position_data = {
            "id": ticker.lower(),
            "ticker": ticker,
            "company": info["name"],
            "sector": info["sector"],
            "status": "planned",
            "notes": "V2 planned position — no capital deployed yet",
        }

        # Try to extract entry price from AGENT_9 data if available
        if data:
            positions = data.get("positions", data.get("entry_prices", {}))
            if isinstance(positions, dict) and ticker in positions:
                pos = positions[ticker]
                if isinstance(pos, dict):
                    position_data["entry_price"] = pos.get("entry_price") or pos.get("price")
                elif isinstance(pos, (int, float)):
                    position_data["entry_price"] = pos

        result = upsert("positions", position_data)
        if result:
            count += 1
            print(f"  OK: Position {ticker} ({info['name']}) -> positions table")
        else:
            print(f"  FAIL: Could not upsert position {ticker}")

    return count

def verify_crypto_baselines():
    """Check that AGENT_9 crypto baselines match config.py."""
    filepath = V1_DIR / "AGENT_9_FOUNDATION_PATCH.json"
    data = load_json(filepath)
    if not data:
        print("  SKIP: No AGENT_9 data for crypto verification")
        return

    crypto_data = data.get("crypto_baselines", data.get("crypto", {}))
    if not crypto_data:
        print("  SKIP: No crypto data in AGENT_9")
        return

    for coin_id, info in CRYPTO_HOLDINGS.items():
        symbol = info["symbol"]
        baseline = info["baseline"]
        v1_val = None

        # Try to find matching data in various possible structures
        if isinstance(crypto_data, dict):
            for key, val in crypto_data.items():
                if symbol.lower() in key.lower() or coin_id.lower() in key.lower():
                    if isinstance(val, dict):
                        v1_val = val.get("baseline") or val.get("price")
                    elif isinstance(val, (int, float)):
                        v1_val = val
                    break

        if v1_val:
            match = abs(float(v1_val) - baseline) < 0.01 * baseline  # within 1%
            status = "MATCH" if match else "MISMATCH"
            print(f"  {status}: {symbol} config={baseline} v1={v1_val}")
        else:
            print(f"  INFO: {symbol} baseline={baseline} (no V1 comparison available)")

def main():
    print("=" * 60)
    print("V1 DATA IMPORT TO SUPABASE")
    print("=" * 60)

    print("\n--- Importing Agent Output Files ---")
    agent_count = import_agent_outputs()

    print("\n--- Importing Planned Positions ---")
    position_count = import_planned_positions()

    print("\n--- Verifying Crypto Baselines ---")
    verify_crypto_baselines()

    print("\n" + "=" * 60)
    print(f"IMPORT COMPLETE")
    print(f"  Agent files imported: {agent_count}")
    print(f"  Positions created:    {position_count}")
    print("=" * 60)

if __name__ == "__main__":
    main()
