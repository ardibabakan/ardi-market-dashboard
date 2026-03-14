#!/bin/bash
BASE="$HOME/Library/Mobile Documents/com~apple~CloudDocs/_ARDI"
V2="$BASE/MISC/Stock_Market/v2"
LOG="$V2/Weekly/weekly_log.txt"

echo "$(date): Weekly review starting" >> "$LOG"
cd "$V2"
python3 orchestrator.py --mode weekly >> "$LOG" 2>&1
echo "$(date): Weekly review complete" >> "$LOG"
