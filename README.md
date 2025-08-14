# Clockify CLI Script

A bash script for controlling Clockify time tracking from the command line. Supports both manual time tracking and integration with Gnome Pomodoro for automated time tracking during pomodoro sessions.

## Features

- **Manual Time Tracking**: Start and stop time entries with `clockify start` and `clockify stop`
- **Task Management**: Change task names without starting new entries using `clockify --task_name "New Task"`
- **Pomodoro Integration**: Automatically handles Gnome Pomodoro triggers like `"start enable"`, `"pause"`, `"resume"`, etc.
- **Smart State Management**: Uses Clockify API to check for running entries and avoid 404 errors
- **Configuration Storage**: Saves API credentials and project settings for easy reuse
- **Error Handling**: Gracefully handles API errors and stale state files

## Dependencies

### Arch Linux
```bash
sudo pacman -S curl gawk
```

### Ubuntu/Debian
```bash
sudo apt update
sudo apt install curl gawk
```

### Optional (for notifications)
- **xcowsay** - Desktop notifications when starting/stopping entries
  - Arch: `sudo pacman -S xcowsay`
  - Ubuntu: `sudo apt install xcowsay`

## Installation

1. **Clone or download the script**:
   ```bash
   git clone <repository-url>
   cd clockify
   ```

2. **Make the script executable**:
   ```bash
   chmod +x clockify.sh
   ```

3. **Install the script** (optional, for system-wide access):
   ```bash
   mkdir -p ~/.local/bin
   ln -sf "$(pwd)/clockify.sh" ~/.local/bin/clockify
   
   # Add ~/.local/bin to PATH if not already there
   echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
   source ~/.bashrc
   ```

4. **Get your Clockify credentials**:
   - Go to [Clockify Profile Settings](https://clockify.me/user/settings)
   - Generate an API key
   - Note your Workspace ID and Project ID (can be found in URLs when browsing Clockify)

## Configuration

### First Time Setup
```bash
clockify start --token "YOUR_API_TOKEN" \
               --workspace-id "YOUR_WORKSPACE_ID" \
               --project-id "YOUR_PROJECT_ID" \
               --task-name "Your Task Name"
```

This saves your configuration to `~/.config/clockify/clockifyrc` for future use.

### Configuration File Location
The script stores configuration in `~/.config/clockify/clockifyrc`:
```bash
CLOCKIFY_TOKEN="your_api_token"
CLOCKIFY_WORKSPACE_ID="your_workspace_id"
CLOCKIFY_PROJECT_ID="your_project_id"
CLOCKIFY_TASK_NAME="your_default_task_name"
```

## Usage

### Basic Commands

**Start time tracking**:
```bash
clockify start                           # Use saved configuration
clockify start --task-name "New Task"    # Start with different task name
```

**Stop time tracking**:
```bash
clockify stop
```

**Change task name** (stops current entry if running, updates config, but doesn't start new entry):
```bash
clockify --task_name "New Task Name"
```

### Pomodoro Integration

The script handles Gnome Pomodoro triggers automatically:

- `"start enable"` → Starts time entry
- `"resume"` → Starts time entry
- `"pause"` → Stops time entry
- `"skip"` → Stops time entry
- `"skip disable"` → Stops time entry
- `"complete"` → Stops time entry
- Any other trigger → Stops time entry (fallback)

### Gnome Pomodoro Setup

To integrate with Gnome Pomodoro:

1. Install Gnome Pomodoro
2. In Gnome Pomodoro settings, set the command to:
   ```bash
   /bin/sh -lc '~/.local/bin/clockify "$(triggers)"'
   ```

## Configuration Options

All configuration can be provided via command line arguments or stored in the config file:

- `--token <token>`: Clockify API token
- `--workspace-id <id>`: Clockify workspace ID
- `--project-id <id>`: Clockify project ID  
- `--task-name <name>`: Task/description name

## File Locations

- **Configuration**: `~/.config/clockify/clockifyrc`
- **State file**: `~/.config/clockify/.clockify_state` (tracks currently running entry ID)

## Troubleshooting

### "No active time entry found"
This usually means:
1. No entry is currently running, or
2. The local state file is out of sync with Clockify

The script will automatically clean up stale state files when detecting 404 errors.

### "Missing required configuration"
Make sure you've run the initial setup command with all required parameters, or manually edit the config file at `~/.config/clockify/clockifyrc`.

### API Errors
- Verify your API token is correct and hasn't expired
- Check that workspace ID and project ID are valid
- Ensure you have permissions to create time entries in the specified project

## Examples

```bash
# Initial setup
clockify start --token "abc123" --workspace-id "ws456" --project-id "proj789" --task-name "Development Work"

# Start tracking with saved config
clockify start

# Change task without starting
clockify --task_name "Bug Fixes"

# Start with new task name
clockify start --task-name "Code Review"

# Stop current entry
clockify stop
```

## License

This script is provided as-is for personal and educational use.