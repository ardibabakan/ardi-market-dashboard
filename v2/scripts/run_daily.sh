#!/bin/bash
BASE="$HOME/Library/Mobile Documents/com~apple~CloudDocs/_ARDI"
V2="$BASE/MISC/Stock_Market/v2"
LOG="$V2/Daily/runner_log.txt"
DAY=$(date +%u)

# Skip weekends
if [ "$DAY" -ge 6 ]; then
    echo "$(date): Weekend — skipping" >> "$LOG"
    exit 0
fi

echo "$(date): V2 Daily runner starting" >> "$LOG"
cd "$V2"
python3 orchestrator.py --mode daily >> "$LOG" 2>&1

# Push to GitHub
cd "$BASE/MISC/Stock_Market"
git add v2/Daily/ v2/data/
git commit -m "Daily update: $(date +%Y-%m-%d)" 2>> "$LOG"
git push origin main 2>> "$LOG"

echo "$(date): V2 Daily runner complete" >> "$LOG"
