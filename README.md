# Clockify CLI - Python Implementation

A comprehensive Python-based command-line interface for Clockify time tracking with advanced project and task management, plus seamless Gnome Pomodoro integration.

## Features

- **Time Tracking**: Start, stop, pause, resume, and skip time entries
- **Project Management**: Interactive project selection and management
- **Task Management**: Create, select, and manage formal tasks within projects
- **Description Management**: Smart description selection with history from previous time entries
- **Pomodoro Integration**: Full bidirectional sync with Gnome Pomodoro timer
- **Smart State Management**: JSON-based configuration and state persistence
- **Interactive Selection**: User-friendly menus for projects, tasks, and descriptions
- **Desktop Notifications**: Visual feedback via xcowsay or notify-send
- **Comprehensive Info**: Detailed status display with elapsed time tracking

## Architecture

The application is built with a modular Python architecture:

- **app.py**: Main CLI interface and argument parsing
- **api_client.py**: Core Clockify API client with full REST API support
- **config.py**: JSON-based configuration and state management
- **time_tracker.py**: Time entry operations and status display
- **project_manager.py**: Project selection and management
- **task_manager_new.py**: Task and description management
- **pomodoro.py**: Gnome Pomodoro integration via D-Bus
- **utils.py**: Utility functions for notifications and user interaction

## Dependencies

### System Requirements
```bash
# For desktop notifications
sudo apt install xcowsay notify-send

# For Pomodoro integration
sudo apt install gnome-pomodoro dbus
```

### Python Requirements
```bash
pip install requests
```

## Installation

1. **Clone or download the repository**:
   ```bash
   git clone <repository-url>
   cd clockify
   ```

2. **Install Python dependencies**:
   ```bash
   pip install requests
   ```

3. **Make the app executable** (optional, for direct execution):
   ```bash
   chmod +x app.py
   ```

4. **Create a system-wide command** (optional):
   ```bash
   mkdir -p ~/.local/bin
   ln -sf "$(pwd)/app.py" ~/.local/bin/clockify
   
   # Add ~/.local/bin to PATH if not already there
   echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
   source ~/.bashrc
   ```

5. **Get your Clockify credentials**:
   - Go to [Clockify Profile Settings](https://clockify.me/user/settings)
   - Generate an API key
   - Note your Workspace ID (found in URLs when browsing Clockify)
   - Project ID will be selected interactively during first use

## Configuration

### First Time Setup
```bash
# Initialize with basic credentials
python app.py start --token "YOUR_API_TOKEN" \
                   --workspace-id "YOUR_WORKSPACE_ID"

# Or set up interactively
python app.py project select    # Choose your project
python app.py task select       # Choose or create a task
python app.py start            # Start tracking
```

### Configuration Files
The application stores configuration in `~/.config/clockify/`:
- `config.json`: Main configuration (credentials, project, task settings)
- `state.json`: Runtime state (current time entry ID)

Example `config.json`:
```json
{
  "token": "your_api_token",
  "workspace_id": "your_workspace_id", 
  "project_id": "selected_project_id",
  "task_id": "selected_task_id",
  "task_name": "Selected Task Name",
  "description": "Current description"
}
```

## Usage

### Basic Time Tracking

**Start time tracking**:
```bash
python app.py start                      # Use saved configuration
python app.py start --description "New Task"   # Start with specific description
```

**Stop time tracking**:
```bash
python app.py stop
# Aliases: pause, complete
```

**Resume time tracking**:
```bash
python app.py resume
# Alias: start (when not currently tracking)
```

**Skip current session**:
```bash
python app.py skip                       # Stops Clockify and skips Pomodoro
```

**Show current status**:
```bash
python app.py info                       # Comprehensive tracking information
```

### Project Management

**List all projects**:
```bash
python app.py project list
python app.py projects                   # Legacy alias
```

**Interactively select project**:
```bash
python app.py project select
python app.py project                    # Default action
```

**Set project by name**:
```bash
python app.py project set "Project Name"
```

### Task Management

**List tasks and descriptions**:
```bash
python app.py task list                  # Show formal tasks and recent descriptions
python app.py tasks                      # Legacy alias
```

**Interactively select task and description**:
```bash
python app.py task select               # Choose task, then description
python app.py task                      # Default action
```

**Set description directly**:
```bash
python app.py task set "New Description"
```

**Create formal task**:
```bash
python app.py task create "Task Name"
```

**Delete formal task**:
```bash
python app.py task delete "Task Name"
```

### Pomodoro Integration

**Direct Pomodoro control**:
```bash
python app.py pomodoro start            # Start Pomodoro timer
python app.py pomodoro stop             # Stop Pomodoro timer
python app.py pomodoro pause            # Pause Pomodoro timer
python app.py pomodoro resume           # Resume Pomodoro timer
python app.py pomodoro skip             # Skip to next session
python app.py pomodoro status           # Show Pomodoro state
python app.py pomodoro sync             # Sync Clockify with Pomodoro
```

**Automatic Pomodoro triggers** (handled by Gnome Pomodoro):
- `"start enable"` → Starts Clockify time entry
- `"resume"` → Starts Clockify time entry  
- `"pause"` → Stops Clockify time entry
- `"skip"` → Stops Clockify time entry
- `"complete"` → Stops Clockify time entry

### Gnome Pomodoro Setup

To integrate with Gnome Pomodoro:

1. Install Gnome Pomodoro extension
2. In Pomodoro Preferences → Plugins → Custom Actions, add:
   ```bash
   /usr/bin/python3 /path/to/clockify/app.py "$(triggers)"
   ```
   
   Or if you created the system-wide command:
   ```bash
   /bin/sh -c 'clockify "$(triggers)"'
   ```

## Configuration Options

All configuration can be provided via command line arguments:

- `--token <token>`: Clockify API token
- `--workspace-id <id>`: Clockify workspace ID
- `--project-id <id>`: Clockify project ID (optional, can be selected interactively)
- `--description <text>`: Time entry description
- `--task-name <name>`: Legacy alias for --description

## File Locations

- **Configuration**: `~/.config/clockify/config.json`
- **State file**: `~/.config/clockify/state.json` (tracks current time entry ID)

## Advanced Features

### Smart Description History
The application maintains a history of descriptions used for each task, allowing quick selection from previous work sessions.

### Hierarchical Organization
- **Workspace** → **Project** → **Formal Task** → **Description**
- Formal tasks are optional but provide better organization
- Descriptions can be reused across tasks and sessions

### Desktop Integration
- Desktop notifications via xcowsay (preferred) or notify-send
- Visual feedback when starting/stopping time entries
- Cross-platform notification fallback

## Troubleshooting

### "No active time entry found"
This usually means:
1. No entry is currently running, or
2. The local state file is out of sync with Clockify

The application automatically syncs state with the Clockify API to resolve discrepancies.

### "Missing required configuration"
Basic requirements are token and workspace ID. Run:
```bash
python app.py start --token "YOUR_TOKEN" --workspace-id "YOUR_WORKSPACE_ID"
```

### Pomodoro Integration Issues
- Ensure Gnome Pomodoro extension is installed and running
- Check that D-Bus is available: `gdbus --version`
- Test Pomodoro connection: `python app.py pomodoro status`

### API Errors
- Verify your API token is correct and hasn't expired
- Check that workspace ID is valid (found in Clockify URLs)
- Ensure you have permissions to create time entries in selected projects

## Examples

### Initial Setup
```bash
# Set up with credentials only
python app.py start --token "your_api_token" --workspace-id "your_workspace_id"

# Interactive setup
python app.py project select         # Choose project
python app.py task select           # Choose or create task
python app.py start                 # Start tracking
```

### Daily Workflow
```bash
# Morning setup
python app.py project select        # Switch to today's project
python app.py task select          # Pick a task

# Start working
python app.py start                 # Begin time tracking
python app.py info                  # Check current status

# Task switching
python app.py task set "Code Review"  # Change description
python app.py task select           # Pick different task

# End of day
python app.py stop                  # Stop tracking
```

### Pomodoro Workflow
```bash
# Manual Pomodoro control
python app.py pomodoro start        # Start 25-minute timer
python app.py start                # Start Clockify tracking

# Automatic sync (when using Gnome Pomodoro integration)
# Pomodoro starts → Clockify starts automatically
# Pomodoro ends → Clockify stops automatically
```

### Project and Task Management
```bash
# Create project structure
python app.py project select        # Choose project
python app.py task create "Feature Development"  # Create formal task
python app.py task create "Bug Fixes"           # Create another task
python app.py task select          # Choose task to work on

# View available options
python app.py project list         # List all projects
python app.py task list           # List tasks and descriptions
```

## Migration from Bash Version

If migrating from the previous bash script version:

1. **Configuration**: The new version uses JSON format in `~/.config/clockify/config.json`
2. **Task Management**: Enhanced with formal tasks and description history
3. **Commands**: Most commands remain the same, with additional interactive options
4. **Pomodoro**: Improved integration with bidirectional sync

## License

This application is provided as-is for personal and educational use.
