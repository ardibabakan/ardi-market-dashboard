#!/bin/bash
# Ardi Daily Market Runner — runs automatically at 3 AM Pacific
# To run manually: bash run_daily.sh
# To stop the scheduler: launchctl unload ~/Library/LaunchAgents/com.ardi.dailyrunner.plist

ARDI_DIR="$HOME/Library/Mobile Documents/com~apple~CloudDocs/_ARDI"
cd "$ARDI_DIR"

LOG_DIR="MISC/Stock_Market/Daily"
mkdir -p "$LOG_DIR"

LOG_FILE="$LOG_DIR/runner_log.txt"
DATE=$(date '+%Y-%m-%d %H:%M:%S')
DAY=$(date '+%A')

# Skip weekends
if [ "$DAY" = "Saturday" ] || [ "$DAY" = "Sunday" ]; then
    echo "$DATE: Skipping — $DAY (markets closed)" >> "$LOG_FILE"
    exit 0
fi

echo "" >> "$LOG_FILE"
echo "======================================" >> "$LOG_FILE"
echo "$DATE: Daily runner starting" >> "$LOG_FILE"
echo "======================================" >> "$LOG_FILE"

# Use the correct path to claude CLI
CLAUDE_BIN="$HOME/.npm-global/bin/claude"

if [ ! -f "$CLAUDE_BIN" ]; then
    echo "$DATE: ERROR — claude CLI not found at $CLAUDE_BIN" >> "$LOG_FILE"
    exit 1
fi

"$CLAUDE_BIN" --dangerously-skip-permissions \
  --print "$(cat MISC/Stock_Market/DAILY_RUNNER_PROMPT.txt)" \
  >> "$LOG_FILE" 2>&1

echo "$DATE: Daily runner complete" >> "$LOG_FILE"

# Push updated files to GitHub so dashboard updates online
echo "$(date): Pushing updates to GitHub..." >> "$LOG_FILE"
bash "$HOME/Library/Mobile Documents/com~apple~CloudDocs/_ARDI/MISC/Stock_Market/push_to_github.sh"
echo "$(date): Dashboard updated on the internet" >> "$LOG_FILE"
