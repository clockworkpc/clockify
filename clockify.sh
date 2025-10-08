#!/bin/bash

set -e

CONFIG_DIR="$HOME/.config/clockify"
CONFIG_FILE="$CONFIG_DIR/clockifyrc"
STATE_FILE="$CONFIG_DIR/.clockify_state"

usage() {
  echo "Usage: $0 start|stop|start enable|resume|pause|skip|complete|info|tasks|task [options...]"
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
  echo "  info               - Show pomodoro work and pause status"
  echo "  tasks              - List all tasks for the current project"
  echo "  task               - Interactively select and set task name from previous entries"
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
  echo "  $0 task                                     # Interactively select task name"
  echo "  $0 --task-name \"New Task\"                  # Change task name only"
  exit 1
}

start_pomodoro() {
  # Start a work session (Pomodoro)
  gdbus call --session \
    --dest org.gnome.Pomodoro \
    --object-path /org/gnome/Pomodoro \
    --method org.gnome.Pomodoro.Start
}

stop_pomodoro() {
  # Stop the current session
  gdbus call --session \
    --dest org.gnome.Pomodoro \
    --object-path /org/gnome/Pomodoro \
    --method org.gnome.Pomodoro.Stop
}

pause_pomodoro() {
  # Pause the current session
  gdbus call --session \
    --dest org.gnome.Pomodoro \
    --object-path /org/gnome/Pomodoro \
    --method org.gnome.Pomodoro.Pause
}

resume_pomodoro() {
  # Resume the current session
  gdbus call --session \
    --dest org.gnome.Pomodoro \
    --object-path /org/gnome/Pomodoro \
    --method org.gnome.Pomodoro.Resume
}

skip_pomodoro() {
  # Skip to next session (e.g., from work to break)
  gdbus call --session \
    --dest org.gnome.Pomodoro \
    --object-path /org/gnome/Pomodoro \
    --method org.gnome.Pomodoro.Skip
}

short_break() {
  # Switch immediately to a short break
  gdbus call --session \
    --dest org.gnome.Pomodoro \
    --object-path /org/gnome/Pomodoro \
    --method org.gnome.Pomodoro.SetState 'short-break' 0.0
}

set_work_duration() {
  # Set work (pomodoro) length to 20 minutes
  gdbus call --session \
    --dest org.gnome.Pomodoro \
    --object-path /org/gnome/Pomodoro \
    --method org.gnome.Pomodoro.SetStateDuration 'pomodoro' 1200.0
}

get_all_properties() {
  # All properties
  gdbus call --session \
    --dest org.gnome.Pomodoro \
    --object-path /org/gnome/Pomodoro \
    --method org.freedesktop.DBus.Properties.GetAll org.gnome.Pomodoro
}

get_current_state() {
  # Single property (current state)
  gdbus call --session \
    --dest org.gnome.Pomodoro \
    --object-path /org/gnome/Pomodoro \
    --method org.freedesktop.DBus.Properties.Get \
    org.gnome.Pomodoro State
}

is_pomodoro_running() {
  local state=$(get_current_state 2>/dev/null | grep -o "'[^']*'" | tr -d "'")
  [[ "$state" == "pomodoro" ]]
}

is_clockify_running() {
  local current_entry=$(get_current_time_entry)
  [[ "$current_entry" != "[]" && -n "$current_entry" ]]
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
  local user_id=$(get_user_id)
  curl -s -H "X-Api-Key: $CLOCKIFY_TOKEN" \
    "https://api.clockify.me/api/v1/workspaces/$CLOCKIFY_WORKSPACE_ID/user/$user_id/time-entries?in-progress=true"
}

get_workspaces() {
  curl -s -H "X-Api-Key: $CLOCKIFY_TOKEN" \
    "https://api.clockify.me/api/v1/workspaces"
}

get_projects() {
  curl -s -H "X-Api-Key: $CLOCKIFY_TOKEN" \
    "https://api.clockify.me/api/v1/workspaces/$CLOCKIFY_WORKSPACE_ID/projects"
}

get_current_project_id() {
  # Try configured project ID first
  if [[ -n "$CLOCKIFY_PROJECT_ID" ]]; then
    echo "$CLOCKIFY_PROJECT_ID"
    return 0
  fi

  # Fall back to project ID from active time entry
  local current_entry=$(get_current_time_entry)
  if [[ "$current_entry" != "[]" && -n "$current_entry" ]]; then
    local project_id=$(echo "$current_entry" | jq -r '.[0].projectId // empty' 2>/dev/null)
    if [[ -z "$project_id" ]]; then
      project_id=$(echo "$current_entry" | sed -n 's/.*"projectId":"\([^"]*\)".*/\1/p')
    fi
    if [[ -n "$project_id" ]]; then
      echo "$project_id"
      return 0
    fi
  fi

  return 1
}

get_tasks() {
  local project_id="$1"
  if [[ -z "$project_id" ]]; then
    project_id=$(get_current_project_id)
    if [[ -z "$project_id" ]]; then
      return 1
    fi
  fi

  # Project ID required to list tasks:
  # https://api.clockify.me/api/v1/workspaces/{workspaceId}/projects/{projectId}/tasks
  curl -s -H "X-Api-Key: $CLOCKIFY_TOKEN" \
    "https://api.clockify.me/api/v1/workspaces/$CLOCKIFY_WORKSPACE_ID/projects/$project_id/tasks"
}

get_task_names() {
  local project_id="$1"
  if [[ -z "$project_id" ]]; then
    project_id=$(get_current_project_id)
    if [[ -z "$project_id" ]]; then
      return 1
    fi
  fi

  local tasks_json=$(get_tasks "$project_id")
  
  if [[ "$tasks_json" == "[]" || -z "$tasks_json" ]]; then
    return 0
  fi

  # Extract just the task names from the JSON response
  echo "$tasks_json" | grep -o '"name":"[^"]*"' | cut -d'"' -f4
}

show_info() {
  # Check required parameters
  if [[ -z "$CLOCKIFY_TOKEN" || -z "$CLOCKIFY_WORKSPACE_ID" ]]; then
    echo "Error: Missing required configuration:" >&2
    [[ -z "$CLOCKIFY_TOKEN" ]] && echo "  - token" >&2
    [[ -z "$CLOCKIFY_WORKSPACE_ID" ]] && echo "  - workspace_id" >&2
    exit 1
  fi

  # Show workspaces and projects (equivalent to -w)
  workspaces=$(get_workspaces)
  projects=$(get_projects)
  local current_project_id=$(get_current_project_id)
  if [[ -n "$current_project_id" ]]; then
    tasks=$(get_tasks "$current_project_id")
  else
    tasks="[]"
  fi

  echo "Workspace:"
  # Extract and display workspace info
  workspace_id=$(echo "$workspaces" | grep -o '"id":"'$CLOCKIFY_WORKSPACE_ID'"' | cut -d'"' -f4)
  workspace_name=$(echo "$workspaces" | sed -n 's/.*"id":"'$CLOCKIFY_WORKSPACE_ID'".*"name":"\([^"]*\)".*/\1/p')
  echo "$CLOCKIFY_WORKSPACE_ID $workspace_name"

  echo ""
  echo "Projects:"
  # Extract and display project info
  echo "$projects" | grep -o '"id":"[^"]*","name":"[^"]*"' | while read -r line; do
    project_id=$(echo "$line" | cut -d'"' -f4)
    project_name=$(echo "$line" | cut -d'"' -f8)
    echo "$project_id $project_name"
  done

  # Extract and display task info
  echo "$tasks" | grep -o '"id":"[^"]*","name":"[^"]*"' | while read -r line; do
    task_id=$(echo "$line" | cut -d'"' -f4)
    task_name=$(echo "$line" | cut -d'"' -f8)
    echo "$task_id $task_name"
  done

  echo ""

  current_workspace="$workspace_name"
  if [[ -z "$current_workspace" ]]; then
    current_workspace="Unknown"
  fi

  # Show current project
  if [[ -n "$current_project_id" ]]; then
    current_project_name=$(echo "$projects" | grep -o '"id":"'$current_project_id'"[^}]*"name":"[^"]*"' | cut -d'"' -f8)
    echo "Current Project: ${current_project_name:-$current_project_id}"
    
    # Show available tasks for current project
    local task_names=$(get_task_names "$current_project_id")
    if [[ -n "$task_names" ]]; then
      echo ""
      echo "Available Tasks:"
      echo "$task_names" | while read -r task_name; do
        if [[ -n "$task_name" ]]; then
          echo "  - $task_name"
        fi
      done
    else
      echo "  No tasks found for this project"
    fi
  else
    echo "Current Project: None"
  fi

  # Show current time entry info (equivalent to -p)
  current_entries=$(get_current_time_entry)

  # Check if the response is an empty array or contains no entries
  if [[ "$current_entries" == "[]" || -z "$current_entries" ]]; then
    echo "No active time entry"
  else
    # Debug: show the raw JSON response
    echo "DEBUG: Current entry JSON:"
    echo "$current_entries"
    echo "---"

    # Extract the first (and should be only) entry from the array
    current_entry=$(echo "$current_entries" | jq -r '.[0]' 2>/dev/null)
    if [[ "$current_entry" == "null" || -z "$current_entry" ]]; then
      echo "No active time entry"
    else
      echo "Plugin       Clockify"
      echo "Type         Time Entry"

      # Extract description/task name
      description=$(echo "$current_entry" | jq -r '.description // empty' 2>/dev/null)
      if [[ -z "$description" ]]; then
        description=$(echo "$current_entry" | sed -n 's/.*"description":"\([^"]*\)".*/\1/p')
      fi
      echo "Name         $description"

      # Calculate elapsed time
      start_time=$(echo "$current_entry" | jq -r '.timeInterval.start // empty' 2>/dev/null)
      if [[ -z "$start_time" ]]; then
        start_time=$(echo "$current_entry" | sed -n 's/.*"start":"\([^"]*\)".*/\1/p')
      fi

      if [[ -n "$start_time" ]]; then
        # Convert ISO 8601 to Unix timestamp and calculate elapsed minutes
        start_epoch=$(date -d "$start_time" +%s 2>/dev/null || echo "0")
        current_epoch=$(date +%s)
        elapsed_seconds=$((current_epoch - start_epoch))
        elapsed_minutes=$(echo "scale=2; $elapsed_seconds / 60" | bc -l 2>/dev/null || echo "0")
        echo "Elapsed      $elapsed_minutes Min"
      else
        echo "Elapsed      Unknown"
      fi

      echo "Workspace    $workspace_name"

      # Get project name for current entry
      project_id=$(echo "$current_entry" | jq -r '.projectId // empty' 2>/dev/null)
      if [[ -z "$project_id" ]]; then
        project_id=$(echo "$current_entry" | sed -n 's/.*"projectId":"\([^"]*\)".*/\1/p')
      fi
      if [[ -n "$project_id" ]]; then
        project_name=$(echo "$projects" | sed -n 's/.*"id":"'$project_id'".*"name":"\([^"]*\)".*/\1/p')
        echo "Project      $project_name"
      fi
    fi
  fi
}

start_time_entry() {
  # Check if a timer is already running
  if is_clockify_running; then
    echo "Clockify timer is already running, skipping start"
    return 0
  fi

  # For pomodoro integration: only start if pomodoro is actually in work state
  # This prevents 5-second entries when break ends but work hasn't actually started
  local pomodoro_state=$(get_current_state 2>/dev/null | grep -o "'[^']*'" | tr -d "'")
  if [[ -n "$pomodoro_state" && "$pomodoro_state" != "pomodoro" ]]; then
    echo "Pomodoro not in work state ($pomodoro_state), skipping Clockify start"
    return 0
  fi

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
    xcowsay "Time entry started: $CLOCKIFY_TASK_NAME"
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

# Check if only --task-name is provided (task name change only)
if [[ $# -eq 2 && "$1" == "--task-name" ]]; then
  # Check for required config
  if [[ -z "$CLOCKIFY_TOKEN" || -z "$CLOCKIFY_WORKSPACE_ID" ]]; then
    echo "Error: Missing required configuration:" >&2
    [[ -z "$CLOCKIFY_TOKEN" ]] && echo "  - token" >&2
    [[ -z "$CLOCKIFY_WORKSPACE_ID" ]] && echo "  - workspace_id" >&2
    exit 1
  fi

  # Check if both timers are running
  pomodoro_running=false
  clockify_running=false

  if is_pomodoro_running; then
    pomodoro_running=true
    echo "Pomodoro timer is running"
  fi

  if is_clockify_running; then
    clockify_running=true
    echo "Clockify timer is running"
  fi

  # Always stop clockify timer if running
  if [[ "$clockify_running" == "true" ]]; then
    echo "Stopping Clockify timer..."
    current_entry=$(get_current_time_entry)
    entry_id=$(echo "$current_entry" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
    if [[ -n "$entry_id" ]]; then
      echo "$entry_id" >"$STATE_FILE"
      stop_time_entry || echo "Continuing with task name update..."
    fi
  fi

  # If both were running, pause pomodoro (instead of stopping)
  if [[ "$pomodoro_running" == "true" && "$clockify_running" == "true" ]]; then
    echo "Pausing Pomodoro timer..."
    pause_pomodoro
  elif [[ "$pomodoro_running" == "true" ]]; then
    echo "Stopping Pomodoro timer..."
    stop_pomodoro
  fi

  # Update task name in config
  CLOCKIFY_TASK_NAME="$2"
  save_config
  echo "Task name updated to: $CLOCKIFY_TASK_NAME"

  # If both were running, resume pomodoro and start clockify
  if [[ "$pomodoro_running" == "true" && "$clockify_running" == "true" ]]; then
    echo "Resuming Pomodoro timer and starting Clockify timer with new task name..."
    if [[ -n "$CLOCKIFY_PROJECT_ID" ]]; then
      start_time_entry
      sleep 1 # Give clockify time to start before pomodoro resumes
      resume_pomodoro
      echo "Both timers resumed/started with new task name"
    else
      echo "Error: Missing project_id, cannot restart Clockify timer"
      exit 1
    fi
  else
    echo "Use 'clockify start' to begin tracking with the new task name."
  fi

  exit 0
fi

# Function to check for required parameters
check_required() {
  local missing_params=()
  for param in "$@"; do
    if [[ -z "${!param}" ]]; then
      missing_params+=("$param")
    fi
  done

  if [[ ${#missing_params[@]} -ne 0 ]]; then
    echo "Error: Missing required configuration:" >&2
    for missing in "${missing_params[@]}"; do
      echo "  - $missing" >&2
    done
    exit 1
  fi
}

start() {
  if [[ $# -gt 0 ]]; then
    parse_args "start" "$@"
  fi
  check_required CLOCKIFY_TOKEN CLOCKIFY_WORKSPACE_ID CLOCKIFY_PROJECT_ID CLOCKIFY_TASK_NAME
  start_time_entry
}

stop() {
  if [[ $# -gt 0 ]]; then
    parse_args "stop" "$@"
  fi
  check_required CLOCKIFY_TOKEN CLOCKIFY_WORKSPACE_ID
  stop_time_entry
}

info() {
  show_info
}

tasks() {
  check_required CLOCKIFY_TOKEN CLOCKIFY_WORKSPACE_ID

  local current_project_id=$(get_current_project_id)
  if [[ -z "$current_project_id" ]]; then
    echo "Error: No current project found. Either start a time entry or configure a project ID." >&2
    return 1
  fi

  # Get project name to show which project we're listing tasks for
  local projects=$(get_projects)
  local project_name=$(echo "$projects" | sed -n 's/.*"id":"'$current_project_id'".*"name":"\([^"]*\)".*/\1/p')

  echo "Tasks for project: ${project_name:-$current_project_id}"

  local tasks_json=$(get_tasks "$current_project_id")

  if [[ "$tasks_json" == "[]" || -z "$tasks_json" ]]; then
    echo "No tasks found for this project"
    return 0
  fi

  # Parse and display tasks
  echo "$tasks_json" | grep -o '"id":"[^"]*","name":"[^"]*"' | while read -r line; do
    task_id=$(echo "$line" | cut -d'"' -f4)
    task_name=$(echo "$line" | cut -d'"' -f8)
    echo "$task_id $task_name"
  done
}

task() {
  check_required CLOCKIFY_TOKEN CLOCKIFY_WORKSPACE_ID

  # Source the clockify_tasks.sh script to access its functions
  local script_dir="$(dirname "${BASH_SOURCE[0]}")"
  source "$script_dir/clockify_tasks.sh"

  # Run the interactive task selection (which will save the config)
  main
}

default() {
  check_required CLOCKIFY_TOKEN CLOCKIFY_WORKSPACE_ID
  stop_time_entry
}

case "$1" in
"start" | "start enable" | "resume")
  start
  ;;
"stop" | "pause" | "skip" | "skip disable" | "complete")
  stop
  ;;
"info")
  info
  ;;
"tasks")
  tasks
  ;;
"task")
  task
  ;;
*)
  default
  ;;
esac
