#!/bin/bash

# Ensure PATH includes Homebrew and local binaries for launchd environment
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Navigate to project root
cd "$PROJECT_ROOT"

# Log file path
LOG_FILE="$PROJECT_ROOT/automation_log.txt"
# PREVENT OVERLAP: Simple Directory Lock (Works on Mac & Linux)
LOCK_DIR="/tmp/liquor_automation.lock.d"

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    # Lock directory exists. Check if the process is actually running.
    # If the PID inside is not running, assume stale lock and removing it.
    if [ -f "$LOCK_DIR/pid" ]; then
        PID=$(cat "$LOCK_DIR/pid")
        if ps -p "$PID" > /dev/null 2>&1; then
             echo "⚠️ Skipping run: Previous instance (PID $PID) is still running." >> "$LOG_FILE"
             exit 1
        else
             echo "⚠️ Removing stale lock for PID $PID." >> "$LOG_FILE"
             rm -rf "$LOCK_DIR"
             mkdir "$LOCK_DIR"
        fi
    else
        # Found directory but no PID file? Assume stale if very old, but for safety let's just abort or assume stale.
        # Simple approach: If mkdir fails, we abort. User can clear manually if needed.
        echo "⚠️ Skipping run: Lock directory $LOCK_DIR exists." >> "$LOG_FILE"
        exit 1
    fi
fi

# Ensure lock is removed on exit
trap "rm -rf '$LOCK_DIR'" EXIT

# Save current PID
echo $$ > "$LOCK_DIR/pid"

echo "===========================================" >> "$LOG_FILE"
echo "🚀 Starting Scheduled Automation Run: $(date)" >> "$LOG_FILE"
echo "-------------------------------------------" >> "$LOG_FILE"

# Run IMFL Script
echo "Starting IMFL Automation..." >> "$LOG_FILE"
./env/bin/python scripts/main_imfl.py --auto --headless "$@" >> "$LOG_FILE" 2>&1
if [ $? -eq 0 ]; then
    echo "✅ IMFL Script Completed Successfully." >> "$LOG_FILE"
else
    echo "❌ IMFL Script Failed." >> "$LOG_FILE"
fi

echo "-------------------------------------------" >> "$LOG_FILE"
echo "♻️ Cleanup between scripts..." >> "$LOG_FILE"
# OS-Dependent Cleanup to protect user browser on Mac
OS_NAME=$(uname)
if [ "$OS_NAME" == "Darwin" ]; then
    echo "🍎 Mac detected: Safe cleanup (Killing chromedriver only)..." >> "$LOG_FILE"
    pkill -f chromedriver >> "$LOG_FILE" 2>&1
else
    echo "🐧 Linux detected: Aggressive cleanup..." >> "$LOG_FILE"
    pkill -f chrome >> "$LOG_FILE" 2>&1
    pkill -f chromium >> "$LOG_FILE" 2>&1
fi
echo "-------------------------------------------" >> "$LOG_FILE"

# Run CS Script
echo "Starting Country Spirit Automation..." >> "$LOG_FILE"
./env/bin/python scripts/main_cs.py --auto --headless "$@" >> "$LOG_FILE" 2>&1
if [ $? -eq 0 ]; then
    echo "✅ CS Script Completed Successfully." >> "$LOG_FILE"
else
    echo "❌ CS Script Failed." >> "$LOG_FILE"
fi

echo "-------------------------------------------" >> "$LOG_FILE"
echo "🏁 Automation Run Finished: $(date)" >> "$LOG_FILE"
echo "===========================================" >> "$LOG_FILE"
