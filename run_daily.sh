#!/bin/bash
# Ardi Daily Market Runner — runs automatically at 3 AM Pacific
# To run manually: bash run_daily.sh
# To stop scheduler: launchctl unload ~/Library/LaunchAgents/com.ardi.dailyrunner.plist

set -e

ARDI_DIR="$HOME/Library/Mobile Documents/com~apple~CloudDocs/_ARDI"
cd "$ARDI_DIR" || { echo "ERROR: Cannot cd to $ARDI_DIR"; exit 1; }

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

# Find claude CLI
CLAUDE_BIN="$HOME/.npm-global/bin/claude"
if [ ! -f "$CLAUDE_BIN" ]; then
    CLAUDE_BIN=$(which claude 2>/dev/null || true)
fi
if [ -z "$CLAUDE_BIN" ] || [ ! -f "$CLAUDE_BIN" ]; then
    echo "$DATE: ERROR — claude CLI not found" >> "$LOG_FILE"
    exit 1
fi

PROMPT_FILE="MISC/Stock_Market/DAILY_RUNNER_PROMPT.txt"
if [ ! -f "$PROMPT_FILE" ]; then
    echo "$DATE: ERROR — Prompt file not found at $PROMPT_FILE" >> "$LOG_FILE"
    exit 1
fi

"$CLAUDE_BIN" --dangerously-skip-permissions \
  --model claude-opus-4-6 \
  --print "$(cat "$PROMPT_FILE")" \
  >> "$LOG_FILE" 2>&1

EXIT_CODE=$?
DATE=$(date '+%Y-%m-%d %H:%M:%S')

if [ $EXIT_CODE -eq 0 ]; then
    echo "$DATE: Daily runner complete (success)" >> "$LOG_FILE"
else
    echo "$DATE: Daily runner finished with exit code $EXIT_CODE" >> "$LOG_FILE"
fi

# Push updated files to GitHub so dashboard updates online
echo "$(date '+%Y-%m-%d %H:%M:%S'): Pushing updates to GitHub..." >> "$LOG_FILE"
bash "$ARDI_DIR/MISC/Stock_Market/push_to_github.sh" 2>> "$LOG_FILE" || {
    echo "$(date '+%Y-%m-%d %H:%M:%S'): GitHub push failed" >> "$LOG_FILE"
}
echo "$(date '+%Y-%m-%d %H:%M:%S'): Daily run fully complete" >> "$LOG_FILE"
