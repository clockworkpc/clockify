#!/bin/bash

set -e

CONFIG_DIR="$HOME/.config/clockify"
CONFIG_FILE="$CONFIG_DIR/clockifyrc"

usage() {
  echo "Usage: $0 [options]"
  echo ""
  echo "Interactive task selection for current Clockify project"
  echo ""
  echo "Options:"
  echo "  --token <token>           Clockify API token"
  echo "  --workspace-id <id>       Workspace ID"
  echo "  --limit <number>          Number of entries to retrieve (default: 50)"
  echo "  --list-only               Only list task names without interactive selection"
  echo "  --help                    Show this help message"
  echo ""
  echo "Examples:"
  echo "  $0                        # Interactive task selection from last 50 entries"
  echo "  $0 --limit 100            # Interactive task selection from last 100 entries"
  echo "  $0 --list-only            # Only list unique task names"
  echo "  $0 --token <token> --workspace-id <id>  # Use custom config"
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

get_projects() {
  curl -s -H "X-Api-Key: $CLOCKIFY_TOKEN" \
    "https://api.clockify.me/api/v1/workspaces/$CLOCKIFY_WORKSPACE_ID/projects"
}

get_current_time_entry() {
  local user_id=$(get_user_id)
  curl -s -H "X-Api-Key: $CLOCKIFY_TOKEN" \
    "https://api.clockify.me/api/v1/workspaces/$CLOCKIFY_WORKSPACE_ID/user/$user_id/time-entries?in-progress=true"
}

get_current_project_id() {
  # Try to get project ID from active time entry first
  local current_entry=$(get_current_time_entry)
  if [[ "$current_entry" != "[]" && -n "$current_entry" ]]; then
    local project_id=$(echo "$current_entry" | sed -n 's/.*"projectId":"\([^"]*\)".*/\1/p')
    if [[ -n "$project_id" ]]; then
      echo "$project_id"
      return 0
    fi
  fi

  # Fall back to configured project ID
  if [[ -n "$CLOCKIFY_PROJECT_ID" ]]; then
    echo "$CLOCKIFY_PROJECT_ID"
    return 0
  fi

  return 1
}

get_current_project_name() {
  local current_project_id=$(get_current_project_id)
  if [[ -z "$current_project_id" ]]; then
    return 1
  fi
  
  local projects=$(get_projects)
  local project_name=$(echo "$projects" | sed -n 's/.*"id":"'$current_project_id'".*"name":"\([^"]*\)".*/\1/p')
  
  if [[ -n "$project_name" ]]; then
    echo "$project_name"
    return 0
  fi
  
  return 1
}

get_all_time_entries() {
  local user_id=$(get_user_id)
  local limit=${1:-50}
  
  if [[ -z "$user_id" ]]; then
    echo "Error: Could not get user ID. Check your token." >&2
    return 1
  fi

  # Get time entries (not just in-progress ones)
  curl -s -H "X-Api-Key: $CLOCKIFY_TOKEN" \
    "https://api.clockify.me/api/v1/workspaces/$CLOCKIFY_WORKSPACE_ID/user/$user_id/time-entries?page-size=$limit"
}

format_duration() {
  local start_time="$1"
  local end_time="$2"
  
  if [[ -z "$end_time" || "$end_time" == "null" ]]; then
    echo "In Progress"
    return
  fi

  # Convert ISO 8601 to Unix timestamp and calculate duration
  local start_epoch=$(date -d "$start_time" +%s 2>/dev/null || echo "0")
  local end_epoch=$(date -d "$end_time" +%s 2>/dev/null || echo "0")
  local duration_seconds=$((end_epoch - start_epoch))
  
  if [[ $duration_seconds -le 0 ]]; then
    echo "Unknown"
    return
  fi

  local hours=$((duration_seconds / 3600))
  local minutes=$(((duration_seconds % 3600) / 60))
  
  if [[ $hours -gt 0 ]]; then
    printf "%dh %dm" $hours $minutes
  else
    printf "%dm" $minutes
  fi
}

get_unique_time_entry_names() {
  local limit=${1:-50}
  
  # Check required parameters
  if [[ -z "$CLOCKIFY_TOKEN" || -z "$CLOCKIFY_WORKSPACE_ID" ]]; then
    echo "Error: Missing required configuration:" >&2
    [[ -z "$CLOCKIFY_TOKEN" ]] && echo "  - token" >&2
    [[ -z "$CLOCKIFY_WORKSPACE_ID" ]] && echo "  - workspace_id" >&2
    exit 1
  fi

  # Get current project name
  local current_project_name=$(get_current_project_name)
  if [[ -z "$current_project_name" ]]; then
    echo "Error: No current project found. Either start a time entry or configure a project ID." >&2
    return 1
  fi

  local entries=$(get_all_time_entries "$limit")
  local projects=$(get_projects)

  if [[ "$entries" == "[]" || -z "$entries" ]]; then
    echo "No time entries found"
    return 0
  fi

  # Parse entries and filter by current project name, preserving chronological order
  # Create temporary arrays to track task names and their timestamps
  declare -A task_timestamps
  declare -a task_order
  
  # Process entries in chronological order (newest first from API)
  while IFS= read -r entry; do
    # Extract project ID, description, and start time from this entry
    local project_id=$(echo "$entry" | sed -n 's/.*"projectId":"\([^"]*\)".*/\1/p')
    local description=$(echo "$entry" | sed -n 's/.*"description":"\([^"]*\)".*/\1/p')
    local start_time=$(echo "$entry" | sed -n 's/.*"start":"\([^"]*\)".*/\1/p')
    
    if [[ -n "$project_id" && -n "$description" && -n "$start_time" ]]; then
      # Get project name for this entry
      local project_name=$(echo "$projects" | sed -n 's/.*"id":"'$project_id'".*"name":"\([^"]*\)".*/\1/p')
      
      # Only process entries that match current project
      if [[ "$project_name" == "$current_project_name" ]]; then
        # If this is the first time we see this task, add it to the order array
        if [[ -z "${task_timestamps[$description]}" ]]; then
          task_order+=("$description")
        fi
        # Always update the timestamp (keeping the most recent)
        task_timestamps["$description"]="$start_time"
      fi
    fi
  done < <(echo "$entries" | grep -o '"id":"[^"]*"[^}]*}')
  
  # Output tasks in chronological order (oldest first)
  for task in "${task_order[@]}"; do
    echo "$task"
  done
}

select_task_interactively() {
  local limit=${1:-50}
  
  # Get current project name for display
  local current_project_name=$(get_current_project_name)
  if [[ -z "$current_project_name" ]]; then
    echo "Error: No current project found. Either start a time entry or configure a project ID." >&2
    return 1
  fi
  
  # Get task list
  local tasks=()
  while IFS= read -r task; do
    if [[ -n "$task" ]]; then
      tasks+=("$task")
    fi
  done < <(get_unique_time_entry_names "$limit")
  
  if [[ ${#tasks[@]} -eq 0 ]]; then
    echo "No tasks found for current project: $current_project_name" >&2
    return 1
  fi
  
  # Display tasks with numbers (to stderr so it doesn't interfere with return value)
  echo "Tasks for project: $current_project_name" >&2
  echo "" >&2
  for i in "${!tasks[@]}"; do
    printf "%2d. %s\n" $((i+1)) "${tasks[i]}" >&2
  done
  echo "" >&2
  
  # Get user selection
  while true; do
    read -p "Select a task (1-${#tasks[@]}): " selection
    
    # Check if input is a valid number
    if [[ "$selection" =~ ^[0-9]+$ ]] && [[ "$selection" -ge 1 ]] && [[ "$selection" -le ${#tasks[@]} ]]; then
      # Return the selected task name to stdout
      echo "${tasks[$((selection-1))]}"
      return 0
    else
      echo "Invalid selection. Please enter a number between 1 and ${#tasks[@]}." >&2
    fi
  done
}

main() {
  # Parse arguments
  local LIMIT=50
  local LIST_ONLY=false

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
      --limit)
        LIMIT="$2"
        shift 2
        ;;
      --list-only)
        LIST_ONLY=true
        shift
        ;;
      --help)
        usage
        ;;
      *)
        echo "Unknown option: $1" >&2
        usage
        ;;
    esac
  done

  # Load config
  load_config

  if [[ "$LIST_ONLY" == "true" ]]; then
    get_unique_time_entry_names "$LIMIT"
  else
    local selected_task=$(select_task_interactively "$LIMIT")
    
    if [[ $? -eq 0 && -n "$selected_task" ]]; then
      # Update task name in config
      CLOCKIFY_TASK_NAME="$selected_task"
      save_config
      echo "Task name set to: $CLOCKIFY_TASK_NAME"
      # Also return the selected task name for use by other scripts
      echo "$selected_task"
    else
      echo "Task selection cancelled or failed." >&2
      return 1
    fi
  fi
}

# Only execute main if script is run directly (not sourced)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main "$@"
fi