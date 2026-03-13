#!/bin/bash
# Push daily report files to GitHub after each morning run

BASE="$HOME/Library/Mobile Documents/com~apple~CloudDocs/_ARDI"
STOCK_DIR="$BASE/MISC/Stock_Market"
LOG="$STOCK_DIR/Daily/runner_log.txt"

cd "$STOCK_DIR" || { echo "ERROR: Cannot cd to $STOCK_DIR" >> "$LOG"; exit 1; }

TODAY=$(date +%Y-%m-%d)
echo "$(date '+%Y-%m-%d %H:%M:%S'): Pushing to GitHub for $TODAY" >> "$LOG"

# Add all daily report files, dashboard, and foundation data
git add Daily/STOCKS_*.md 2>> "$LOG"
git add Daily/BROAD_UNIVERSE_*.md 2>> "$LOG"
git add dashboard.py 2>> "$LOG"
git add AGENT_9_FOUNDATION_PATCH.json 2>> "$LOG"
git add requirements.txt 2>> "$LOG"
git add DAILY_RUNNER_PROMPT.txt 2>> "$LOG"
git add SYSTEM_AUDIT_*.md 2>> "$LOG"
git add .gitignore 2>> "$LOG"

# Only commit if there are staged changes
if git diff --cached --quiet 2>/dev/null; then
    echo "$(date '+%Y-%m-%d %H:%M:%S'): No changes to commit" >> "$LOG"
else
    git commit -m "Daily update: $TODAY" >> "$LOG" 2>&1
    git push origin main >> "$LOG" 2>&1
    PUSH_EXIT=$?
    if [ $PUSH_EXIT -eq 0 ]; then
        echo "$(date '+%Y-%m-%d %H:%M:%S'): GitHub push SUCCESS" >> "$LOG"
    else
        echo "$(date '+%Y-%m-%d %H:%M:%S'): GitHub push FAILED (exit $PUSH_EXIT)" >> "$LOG"
    fi
fi
