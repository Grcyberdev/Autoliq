#!/bin/bash

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Run the main automation script with the --daily flag
# This forces the generation of a full day report regardless of new rows
echo "🚀 Starting Day End Report Generation..."
"$SCRIPT_DIR/run_automation.sh" --daily "$@"
