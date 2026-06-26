#!/bin/bash

# Configuration
PLIST_NAME="com.liquorbond.automation.plist"
DEST_DIR="$HOME/Library/LaunchAgents"
DEST_PLIST="$DEST_DIR/$PLIST_NAME"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Ensure we are in the correct directory
cd "$PROJECT_ROOT"

echo "📂 Generating $PLIST_NAME in $DEST_DIR..."
mkdir -p "$DEST_DIR"

# Generate Plist with CORRECT PATHS
cat <<EOF > "$DEST_PLIST"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.liquorbond.automation</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$PROJECT_ROOT/scripts/run_automation.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <array>
        <!-- 11:00 AM -->
        <dict><key>Hour</key><integer>11</integer><key>Minute</key><integer>0</integer></dict>
        <!-- 11:45 AM -->
        <dict><key>Hour</key><integer>11</integer><key>Minute</key><integer>45</integer></dict>
        <!-- 12:30 PM -->
        <dict><key>Hour</key><integer>12</integer><key>Minute</key><integer>30</integer></dict>
        <!-- 1:15 PM -->
        <dict><key>Hour</key><integer>13</integer><key>Minute</key><integer>15</integer></dict>
        <!-- 2:00 PM -->
        <dict><key>Hour</key><integer>14</integer><key>Minute</key><integer>0</integer></dict>
        <!-- 2:45 PM -->
        <dict><key>Hour</key><integer>14</integer><key>Minute</key><integer>45</integer></dict>
        <!-- 3:30 PM -->
        <dict><key>Hour</key><integer>15</integer><key>Minute</key><integer>30</integer></dict>
        <!-- 4:15 PM -->
        <dict><key>Hour</key><integer>16</integer><key>Minute</key><integer>15</integer></dict>
        <!-- 5:00 PM -->
        <dict><key>Hour</key><integer>17</integer><key>Minute</key><integer>0</integer></dict>
        <!-- 5:45 PM -->
        <dict><key>Hour</key><integer>17</integer><key>Minute</key><integer>45</integer></dict>
        <!-- 6:30 PM -->
        <dict><key>Hour</key><integer>18</integer><key>Minute</key><integer>30</integer></dict>
        <!-- 7:15 PM -->
        <dict><key>Hour</key><integer>19</integer><key>Minute</key><integer>15</integer></dict>
        <!-- 8:00 PM -->
        <dict><key>Hour</key><integer>20</integer><key>Minute</key><integer>0</integer></dict>
        <!-- 8:45 PM -->
        <dict><key>Hour</key><integer>20</integer><key>Minute</key><integer>45</integer></dict>
        <!-- 9:30 PM (Cumulative Report) -->
        <dict><key>Hour</key><integer>21</integer><key>Minute</key><integer>30</integer></dict>
        <!-- 10:15 PM -->
        <dict><key>Hour</key><integer>22</integer><key>Minute</key><integer>15</integer></dict>
        <!-- 11:00 PM (Cumulative Report) -->
        <dict><key>Hour</key><integer>23</integer><key>Minute</key><integer>0</integer></dict>
        <!-- 11:45 PM (Last Run) -->
        <dict><key>Hour</key><integer>23</integer><key>Minute</key><integer>45</integer></dict>
    </array>
    <key>StandardOutPath</key>
    <string>$PROJECT_ROOT/automation.log</string>
    <key>StandardErrorPath</key>
    <string>$PROJECT_ROOT/automation.log</string>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
EOF

# Unload and Reload
echo "🔄 Reloading LaunchAgent..."
launchctl unload "$DEST_PLIST" 2>/dev/null
launchctl load "$DEST_PLIST"

echo "✅ Launchd service updated to run from: $PROJECT_ROOT"
echo "   - Plist: $DEST_PLIST"
echo "   - Log: $PROJECT_ROOT/automation.log"
