#!/bin/bash

# Configuration
PLIST_NAME="com.liquorbond.automation.plist"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PLIST_SOURCE="$SCRIPT_DIR/$PLIST_NAME"
PLIST_DEST="$HOME/Library/LaunchAgents/$PLIST_NAME"

echo "🔧 Setting up Liquor Bond Automation..."

# 1. Copy plist template to LaunchAgents
echo "   - Copying plist template to $PLIST_DEST..."
cp "$PLIST_SOURCE" "$PLIST_DEST"

# 2. Update paths in the copied plist at the destination
echo "   - Updating paths in $PLIST_DEST..."
# Using specialized sed for macOS (requires empty string for backup extension)
sed -i '' "s|REPLACE_ME_PATH_TO_SCRIPT|$PROJECT_ROOT/scripts|g" "$PLIST_DEST"
sed -i '' "s|REPLACE_ME_PATH_TO_PROJECT|$PROJECT_ROOT|g" "$PLIST_DEST"

# 3. Unload existing if present, then Load
if launchctl list | grep -q "com.liquorbond.automation"; then
    echo "   - Unloading existing task..."
    launchctl unload "$PLIST_DEST"
fi

echo "   - Loading new task..."
launchctl load "$PLIST_DEST"

# 4. Schedule Power Management (Wake Up)
echo "⏰ Configuring Power Management to wake up ensuring execution..."
echo "   - NOTE: You may be prompted for your password for 'sudo pmset'."

# Schedule a repeating event to wake or power on every day at 21:25:00 (5 mins before 21:30 Daily Report)
# Note: For 15-min interval, waking every 15 mins is aggressive. 
# We prioritize the MAJOR 9:30 PM report for wake-up.
sudo pmset repeat wakeorpoweron MTWRFSU 21:25:00

echo ""
echo "✅ Automation Scheduled!"
echo "   - Script: $PROJECT_ROOT/scripts/smart_dispatcher.sh"
echo "   - Interval: Every 15 minutes (00, 15, 30, 45)"
echo "   - Special Rule: Full Daily Report at 9:30 PM (21:30)"
echo "   - Wake Config: Daily at 9:25 PM (Ensures Daily Report runs)"
echo "   - Log: $PROJECT_ROOT/automation_log.txt"
echo "   - Debug Log: $PROJECT_ROOT/launchd_stderr.log"
