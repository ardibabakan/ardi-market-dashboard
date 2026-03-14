#!/bin/bash
BASE="$HOME/Library/Mobile Documents/com~apple~CloudDocs/_ARDI"
V2="$BASE/MISC/Stock_Market/v2"
LOG="$V2/Daily/checker_log.txt"
HOUR=$(date +%H)
DAY=$(date +%u)

# Skip weekends
if [ "$DAY" -ge 6 ]; then exit 0; fi
# Skip outside market hours
if [ "$HOUR" -lt 6 ] || [ "$HOUR" -ge 17 ]; then exit 0; fi

echo "$(date): Signal check running" >> "$LOG"
cd "$V2"
python3 orchestrator.py --mode signal >> "$LOG" 2>&1
echo "$(date): Signal check complete" >> "$LOG"
