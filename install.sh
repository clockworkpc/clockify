#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLOCKIFY_SCRIPT="$SCRIPT_DIR/clockify.sh"
OLD_ENV_FILE="$SCRIPT_DIR/.env"

# Installation directories
BIN_DIR="$HOME/.local/bin"
CONFIG_DIR="$HOME/.config/clockify"
CONFIG_FILE="$CONFIG_DIR/clockifyrc"

echo "Installing Clockify CLI tool..."

# Create directories if they don't exist
mkdir -p "$BIN_DIR"
mkdir -p "$CONFIG_DIR"

# Copy the script to ~/.local/bin/clockify
if [[ -f "$CLOCKIFY_SCRIPT" ]]; then
    cp "$CLOCKIFY_SCRIPT" "$BIN_DIR/clockify"
    chmod +x "$BIN_DIR/clockify"
    echo "✓ Installed clockify to $BIN_DIR/clockify"
else
    echo "Error: clockify.sh not found in $SCRIPT_DIR" >&2
    exit 1
fi

# Migrate existing configuration from .env if it exists
if [[ -f "$OLD_ENV_FILE" && ! -f "$CONFIG_FILE" ]]; then
    echo "✓ Migrating existing configuration..."
    cp "$OLD_ENV_FILE" "$CONFIG_FILE"
    echo "✓ Configuration migrated to $CONFIG_FILE"
elif [[ -f "$CONFIG_FILE" ]]; then
    echo "✓ Configuration file already exists at $CONFIG_FILE"
else
    echo "ℹ  No existing configuration found. Run 'clockify start --help' for setup instructions."
fi

# Check if ~/.local/bin is in PATH
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo ""
    echo "⚠️  WARNING: $HOME/.local/bin is not in your PATH"
    echo "   Add the following line to your ~/.bashrc or ~/.zshrc:"
    echo "   export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
    echo "   Or restart your shell after running:"
    echo "   echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc"
    echo "   source ~/.bashrc"
fi

echo ""
echo "🎉 Installation complete!"
echo ""
echo "Usage:"
echo "  clockify start                                    # Use stored config"
echo "  clockify start --task-name \"New Task\"            # New task, same project"
echo "  clockify start --project-id <id> --task-name <name>  # New project and task"
echo "  clockify stop                                     # Stop current entry"
echo ""
echo "Configuration file: $CONFIG_FILE"
echo ""
echo "First time setup:"
echo "  clockify start --token <token> --workspace-id <id> --project-id <id> --task-name <name>"