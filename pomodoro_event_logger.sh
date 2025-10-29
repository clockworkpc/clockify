#!/bin/bash
# Gnome Pomodoro event logger
# This script is called by Gnome Pomodoro custom actions to update the events.json file
# Usage: pomodoro_event_logger.sh <event_type>
# Where event_type is: start, pause, resume, or complete

# Get the directory where this script lives
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Path to the app.py script
APP="$SCRIPT_DIR/app.py"

# Config directory
CONFIG_DIR="$HOME/.config/clockify"

# Ensure config directory exists
mkdir -p "$CONFIG_DIR"

# Extract recent events from journalctl (last 5 minutes)
# This ensures we capture the event that just triggered this script
python3 "$APP" events extract --since "5 minutes ago" 2>/dev/null

# Exit successfully
exit 0
