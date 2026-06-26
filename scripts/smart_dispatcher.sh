#!/bin/bash

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$(dirname "$SCRIPT_DIR")/automation_log.txt"

# Get Current Time (Hour and Minute)
CURRENT_HHMM=$(date +%H%M)

# LOGIC:
# We no longer trigger a forced "Daily Summary" at 21:30 or 23:00.
# Just run the regular check.
echo "⏰ Time is $(date +%H:%M). Triggering REGULAR CHECK (Incremental)..." >> "$LOG_FILE"
"$SCRIPT_DIR/run_automation.sh" "$@"
