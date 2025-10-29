#!/bin/bash
# Launcher for Clockify system tray application

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TRAY_SCRIPT="$SCRIPT_DIR/clockify_tray.py"

# Start the tray application in the background
/bin/python "$TRAY_SCRIPT" &

echo "Clockify system tray started"
