#!/bin/bash
# Automatically pushes daily report files to GitHub
# This runs after the daily runner completes each morning

BASE="$HOME/Library/Mobile Documents/com~apple~CloudDocs/_ARDI"
STOCK_DIR="$BASE/MISC/Stock_Market"
LOG="$STOCK_DIR/Daily/runner_log.txt"

cd "$STOCK_DIR"

TODAY=$(date +%Y-%m-%d)
echo "$(date): Pushing to GitHub for $TODAY" >> "$LOG"

# Add all daily report files and foundation data
git add Daily/STOCKS_${TODAY}.md 2>> "$LOG"
git add Daily/BROAD_UNIVERSE_${TODAY}.md 2>> "$LOG"
git add dashboard.py 2>> "$LOG"
git add AGENT_9_FOUNDATION_PATCH.json 2>> "$LOG"

# Commit with today's date
git commit -m "Daily update: $TODAY" 2>> "$LOG"

# Push to GitHub
git push origin main 2>> "$LOG"

echo "$(date): GitHub push complete" >> "$LOG"
