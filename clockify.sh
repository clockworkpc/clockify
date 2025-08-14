#!/bin/bash

set -e

CONFIG_DIR="$HOME/.config/clockify"
CONFIG_FILE="$CONFIG_DIR/clockifyrc"
STATE_FILE="$CONFIG_DIR/.clockify_state"

usage() {
  echo "Usage: $0 start|stop|start enable|resume|pause|skip|complete [options...]"
  echo ""
  echo "Commands:"
  echo "  start              - Start a new time entry"
  echo "  stop               - Stop the current time entry"
  echo "  start enable       - Start a new time entry (pomodoro trigger)"
  echo "  resume             - Start a new time entry (pomodoro trigger)"
  echo "  pause              - Stop the current time entry (pomodoro trigger)"
  echo "  skip               - Stop the current time entry (pomodoro trigger)"
  echo "  skip disable       - Stop the current time entry (pomodoro trigger)"
  echo "  complete           - Stop the current time entry (pomodoro trigger)"
  echo ""
  echo "Options can be provided in any combination:"
  echo "  --token <token>           Clockify API token"
  echo "  --workspace-id <id>       Workspace ID"
  echo "  --project-id <id>         Project ID"
  echo "  --task-name <name>        Task/description name"
  echo ""
  echo "Examples:"
  echo "  $0 start                                    # Use all stored config"
  echo "  $0 start --task-name \"New Task\"            # New task, same project"
  echo "  $0 start --project-id <id> --task-name <name>  # New project and task"
  echo "  $0 start --token <token> --workspace-id <id> --project-id <id> --task-name <name>  # Full config"
  echo "  $0 stop                                     # Stop current entry"
  echo "  $0 --task-name \"New Task\"                  # Change task name only"
  exit 1
}

load_config() {
  if [[ -f "$CONFIG_FILE" ]]; then
    source "$CONFIG_FILE"
  fi
}

save_config() {
  # Create config directory if it doesn't exist
  mkdir -p "$CONFIG_DIR"

  cat >"$CONFIG_FILE" <<EOF
CLOCKIFY_TOKEN="$CLOCKIFY_TOKEN"
CLOCKIFY_WORKSPACE_ID="$CLOCKIFY_WORKSPACE_ID"
CLOCKIFY_PROJECT_ID="$CLOCKIFY_PROJECT_ID"
CLOCKIFY_TASK_NAME="$CLOCKIFY_TASK_NAME"
EOF
  echo "Configuration saved to $CONFIG_FILE"
}

get_user_id() {
  curl -s -H "X-Api-Key: $CLOCKIFY_TOKEN" \
    "https://api.clockify.me/api/v1/user" |
    grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4
}

get_current_time_entry() {
  curl -s -H "X-Api-Key: $CLOCKIFY_TOKEN" \
    "https://api.clockify.me/api/v1/workspaces/$CLOCKIFY_WORKSPACE_ID/timeEntries/inProgress"
}

start_time_entry() {
  local start_time=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  local user_id=$(get_user_id)

  if [[ -z "$user_id" ]]; then
    echo "Error: Could not get user ID. Check your token." >&2
    exit 1
  fi

  echo "Starting time entry: $CLOCKIFY_TASK_NAME"

  local response=$(curl -s -X POST \
    -H "X-Api-Key: $CLOCKIFY_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{
            \"start\": \"$start_time\",
            \"description\": \"$CLOCKIFY_TASK_NAME\",
            \"projectId\": \"$CLOCKIFY_PROJECT_ID\"
        }" \
    "https://api.clockify.me/api/v1/workspaces/$CLOCKIFY_WORKSPACE_ID/time-entries")

  local entry_id=$(echo "$response" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)

  if [[ -n "$entry_id" ]]; then
    echo "Time entry started successfully (ID: $entry_id)"
    echo "$entry_id" >"$STATE_FILE"
  else
    echo "Error starting time entry:" >&2
    echo "$response" >&2
    exit 1
  fi
}

stop_time_entry() {
  if [[ ! -f "$STATE_FILE" ]]; then
    echo "No active time entry found in state file" >&2
    return 1
  fi

  local entry_id=$(cat "$STATE_FILE")
  local end_time=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  local user_id=$(get_user_id)

  echo "Stopping time entry: $entry_id"

  # Use the stop current time entry endpoint
  local response=$(curl -s -X PATCH \
    -H "X-Api-Key: $CLOCKIFY_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"end\": \"$end_time\"}" \
    "https://api.clockify.me/api/v1/workspaces/$CLOCKIFY_WORKSPACE_ID/user/$user_id/time-entries")

  local stopped_id=$(echo "$response" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)

  if [[ -n "$stopped_id" ]]; then
    echo "Time entry stopped successfully (ID: $stopped_id)"
    rm -f "$STATE_FILE"
  else
    # Check if it's a 404 error (entry doesn't exist)
    if echo "$response" | grep -q '"code":404'; then
      echo "Time entry no longer exists, clearing state file"
      rm -f "$STATE_FILE"
    else
      echo "Error stopping time entry:" >&2
      echo "$response" >&2
      return 1
    fi
  fi
}

# Parse arguments
parse_args() {
  local command="$1"
  shift

  # Parse named arguments
  while [[ $# -gt 0 ]]; do
    case $1 in
    --token)
      CLOCKIFY_TOKEN="$2"
      shift 2
      ;;
    --workspace-id)
      CLOCKIFY_WORKSPACE_ID="$2"
      shift 2
      ;;
    --project-id)
      CLOCKIFY_PROJECT_ID="$2"
      shift 2
      ;;
    --task-name)
      CLOCKIFY_TASK_NAME="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      ;;
    esac
  done

  # Save any new configuration
  local config_changed=false
  if [[ -n "$CLOCKIFY_TOKEN" || -n "$CLOCKIFY_WORKSPACE_ID" || -n "$CLOCKIFY_PROJECT_ID" || -n "$CLOCKIFY_TASK_NAME" ]]; then
    config_changed=true
  fi

  if [[ "$config_changed" == "true" ]]; then
    save_config
  fi

  return 0
}

# Main script logic
if [[ $# -eq 0 ]]; then
  usage
fi

load_config

# Check if only --task_name is provided (task name change only)
if [[ $# -eq 2 && "$1" == "--task_name" ]]; then
  # Check for required config
  if [[ -z "$CLOCKIFY_TOKEN" || -z "$CLOCKIFY_WORKSPACE_ID" ]]; then
    echo "Error: Missing required configuration:" >&2
    [[ -z "$CLOCKIFY_TOKEN" ]] && echo "  - token" >&2
    [[ -z "$CLOCKIFY_WORKSPACE_ID" ]] && echo "  - workspace_id" >&2
    exit 1
  fi

  # Check if there's a current time entry running
  current_entry=$(get_current_time_entry)
  if [[ "$current_entry" != "null" && -n "$current_entry" ]]; then
    echo "Stopping current time entry before changing task name..."
    entry_id=$(echo "$current_entry" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
    if [[ -n "$entry_id" ]]; then
      echo "$entry_id" >"$STATE_FILE"
      stop_time_entry || echo "Continuing with task name update..."
    fi
  else
    echo "No active time entry found."
    # Clean up state file if it exists but no entry is running
    [[ -f "$STATE_FILE" ]] && rm -f "$STATE_FILE"
  fi

  # Update task name in config
  CLOCKIFY_TASK_NAME="$2"
  save_config
  echo "Task name updated to: $CLOCKIFY_TASK_NAME"
  echo "Use 'clockify start' to begin tracking with the new task name."
  exit 0
fi

case "$1" in
"start")
  parse_args "$@"

  # Check required parameters for starting
  if [[ -z "$CLOCKIFY_TOKEN" || -z "$CLOCKIFY_WORKSPACE_ID" || -z "$CLOCKIFY_PROJECT_ID" || -z "$CLOCKIFY_TASK_NAME" ]]; then
    echo "Error: Missing required configuration:" >&2
    [[ -z "$CLOCKIFY_TOKEN" ]] && echo "  - token (--token)" >&2
    [[ -z "$CLOCKIFY_WORKSPACE_ID" ]] && echo "  - workspace_id (--workspace-id)" >&2
    [[ -z "$CLOCKIFY_PROJECT_ID" ]] && echo "  - project_id (--project-id)" >&2
    [[ -z "$CLOCKIFY_TASK_NAME" ]] && echo "  - task_name (--task-name)" >&2
    exit 1
  fi

  start_time_entry
  ;;
"stop")
  parse_args "$@"

  # Check required parameters for stopping
  if [[ -z "$CLOCKIFY_TOKEN" || -z "$CLOCKIFY_WORKSPACE_ID" ]]; then
    echo "Error: Missing required configuration:" >&2
    [[ -z "$CLOCKIFY_TOKEN" ]] && echo "  - token (--token)" >&2
    [[ -z "$CLOCKIFY_WORKSPACE_ID" ]] && echo "  - workspace_id (--workspace-id)" >&2
    exit 1
  fi

  stop_time_entry
  ;;
"start enable")
  # Pomodoro triggers that should start a time entry
  # Check required parameters for starting
  if [[ -z "$CLOCKIFY_TOKEN" || -z "$CLOCKIFY_WORKSPACE_ID" || -z "$CLOCKIFY_PROJECT_ID" || -z "$CLOCKIFY_TASK_NAME" ]]; then
    echo "Error: Missing required configuration:" >&2
    [[ -z "$CLOCKIFY_TOKEN" ]] && echo "  - token" >&2
    [[ -z "$CLOCKIFY_WORKSPACE_ID" ]] && echo "  - workspace_id" >&2
    [[ -z "$CLOCKIFY_PROJECT_ID" ]] && echo "  - project_id" >&2
    [[ -z "$CLOCKIFY_TASK_NAME" ]] && echo "  - task_name" >&2
    exit 1
  fi

  start_time_entry
  ;;
"pause" | "skip" | "skip disable" | "complete" | "resume")
  # Pomodoro triggers that should stop a time entry
  # Check required parameters for stopping
  if [[ -z "$CLOCKIFY_TOKEN" || -z "$CLOCKIFY_WORKSPACE_ID" ]]; then
    echo "Error: Missing required configuration:" >&2
    [[ -z "$CLOCKIFY_TOKEN" ]] && echo "  - token" >&2
    [[ -z "$CLOCKIFY_WORKSPACE_ID" ]] && echo "  - workspace_id" >&2
    exit 1
  fi

  stop_time_entry
  ;;
*)
  # Default case - treat anything else as stop
  if [[ -z "$CLOCKIFY_TOKEN" || -z "$CLOCKIFY_WORKSPACE_ID" ]]; then
    echo "Error: Missing required configuration:" >&2
    [[ -z "$CLOCKIFY_TOKEN" ]] && echo "  - token" >&2
    [[ -z "$CLOCKIFY_WORKSPACE_ID" ]] && echo "  - workspace_id" >&2
    exit 1
  fi

  stop_time_entry
  ;;
esac
