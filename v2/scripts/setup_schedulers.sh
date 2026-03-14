#!/bin/bash
# Ardi Market Command Center v2 — Scheduler Setup
# Creates and loads macOS LaunchAgents for daily, signal, and weekly runs.

set -e

SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
LAUNCH_DIR="$HOME/Library/LaunchAgents"
UID_NUM=$(id -u)

echo "=== Ardi V2 Scheduler Setup ==="
echo "Scripts dir: $SCRIPTS_DIR"
echo "LaunchAgents dir: $LAUNCH_DIR"
echo ""

# --- Unload old V1 schedulers (ignore errors) ---
echo "Unloading old V1 schedulers (if any)..."
launchctl bootout "gui/$UID_NUM/com.ardi.dailyrunner" 2>/dev/null || true
launchctl bootout "gui/$UID_NUM/com.ardi.signalchecker" 2>/dev/null || true

# --- Unload old V2 schedulers (ignore errors) ---
echo "Unloading old V2 schedulers (if any)..."
launchctl bootout "gui/$UID_NUM/com.ardi.v2.daily" 2>/dev/null || true
launchctl bootout "gui/$UID_NUM/com.ardi.v2.signals" 2>/dev/null || true
launchctl bootout "gui/$UID_NUM/com.ardi.v2.weekly" 2>/dev/null || true

mkdir -p "$LAUNCH_DIR"

# --- 1. Daily plist: runs at 3:00 AM Pacific every day ---
cat > "$LAUNCH_DIR/com.ardi.v2.daily.plist" << 'PLIST_EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ardi.v2.daily</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>SCRIPTS_PLACEHOLDER/run_daily.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>3</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/ardi.v2.daily.stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/ardi.v2.daily.stderr.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin</string>
        <key>TZ</key>
        <string>America/Los_Angeles</string>
    </dict>
</dict>
</plist>
PLIST_EOF

# --- 2. Signals plist: runs every 7200 seconds (2 hours) ---
cat > "$LAUNCH_DIR/com.ardi.v2.signals.plist" << 'PLIST_EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ardi.v2.signals</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>SCRIPTS_PLACEHOLDER/run_signals.sh</string>
    </array>
    <key>StartInterval</key>
    <integer>7200</integer>
    <key>StandardOutPath</key>
    <string>/tmp/ardi.v2.signals.stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/ardi.v2.signals.stderr.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin</string>
        <key>TZ</key>
        <string>America/Los_Angeles</string>
    </dict>
</dict>
</plist>
PLIST_EOF

# --- 3. Weekly plist: runs at 6:00 AM on Sundays (day 7) ---
cat > "$LAUNCH_DIR/com.ardi.v2.weekly.plist" << 'PLIST_EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ardi.v2.weekly</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>SCRIPTS_PLACEHOLDER/run_weekly.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key>
        <integer>7</integer>
        <key>Hour</key>
        <integer>6</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/ardi.v2.weekly.stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/ardi.v2.weekly.stderr.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin</string>
        <key>TZ</key>
        <string>America/Los_Angeles</string>
    </dict>
</dict>
</plist>
PLIST_EOF

# --- Replace placeholder paths with actual scripts dir ---
sed -i '' "s|SCRIPTS_PLACEHOLDER|$SCRIPTS_DIR|g" "$LAUNCH_DIR/com.ardi.v2.daily.plist"
sed -i '' "s|SCRIPTS_PLACEHOLDER|$SCRIPTS_DIR|g" "$LAUNCH_DIR/com.ardi.v2.signals.plist"
sed -i '' "s|SCRIPTS_PLACEHOLDER|$SCRIPTS_DIR|g" "$LAUNCH_DIR/com.ardi.v2.weekly.plist"

# --- Load all 3 plists ---
echo "Loading V2 schedulers..."
launchctl bootstrap "gui/$UID_NUM" "$LAUNCH_DIR/com.ardi.v2.daily.plist"
launchctl bootstrap "gui/$UID_NUM" "$LAUNCH_DIR/com.ardi.v2.signals.plist"
launchctl bootstrap "gui/$UID_NUM" "$LAUNCH_DIR/com.ardi.v2.weekly.plist"

# --- Verify ---
echo ""
echo "=== Loaded Ardi schedulers ==="
launchctl list | grep ardi
echo ""
echo "Setup complete. Three V2 schedulers are now active:"
echo "  com.ardi.v2.daily    — runs at 3:00 AM Pacific daily"
echo "  com.ardi.v2.signals  — runs every 2 hours"
echo "  com.ardi.v2.weekly   — runs at 6:00 AM on Sundays"
