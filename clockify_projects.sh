#!/bin/bash

set -e

CONFIG_DIR="$HOME/.config/clockify"
CONFIG_FILE="$CONFIG_DIR/clockifyrc"

usage() {
  echo "Usage: $0 [options]"
  echo ""
  echo "Interactive project selection for Clockify workspace"
  echo ""
  echo "Options:"
  echo "  --token <token>           Clockify API token"
  echo "  --workspace-id <id>       Workspace ID"
  echo "  --list-only               Only list project names without interactive selection"
  echo "  --help                    Show this help message"
  echo ""
  echo "Examples:"
  echo "  $0                        # Interactive project selection"
  echo "  $0 --list-only            # Only list project names"
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

get_projects() {
  curl -s -H "X-Api-Key: $CLOCKIFY_TOKEN" \
    "https://api.clockify.me/api/v1/workspaces/$CLOCKIFY_WORKSPACE_ID/projects"
}

get_project_names() {
  # Check required parameters
  if [[ -z "$CLOCKIFY_TOKEN" || -z "$CLOCKIFY_WORKSPACE_ID" ]]; then
    echo "Error: Missing required configuration:" >&2
    [[ -z "$CLOCKIFY_TOKEN" ]] && echo "  - token" >&2
    [[ -z "$CLOCKIFY_WORKSPACE_ID" ]] && echo "  - workspace_id" >&2
    exit 1
  fi

  local projects=$(get_projects)

  if [[ "$projects" == "[]" || -z "$projects" ]]; then
    echo "No projects found"
    return 0
  fi

  # Parse projects and extract names
  echo "$projects" | grep -o '"id":"[^"]*","name":"[^"]*"' | while read -r line; do
    local project_name=$(echo "$line" | cut -d'"' -f8)
    echo "$project_name"
  done
}

select_project_interactively() {
  # Check required parameters
  if [[ -z "$CLOCKIFY_TOKEN" || -z "$CLOCKIFY_WORKSPACE_ID" ]]; then
    echo "Error: Missing required configuration:" >&2
    [[ -z "$CLOCKIFY_TOKEN" ]] && echo "  - token" >&2
    [[ -z "$CLOCKIFY_WORKSPACE_ID" ]] && echo "  - workspace_id" >&2
    exit 1
  fi
  
  local projects=$(get_projects)
  
  if [[ "$projects" == "[]" || -z "$projects" ]]; then
    echo "No projects found" >&2
    return 1
  fi
  
  # Create arrays to store project IDs and names
  local project_ids=()
  local project_names=()
  
  # Parse projects and populate arrays
  while IFS= read -r line; do
    local project_id=$(echo "$line" | cut -d'"' -f4)
    local project_name=$(echo "$line" | cut -d'"' -f8)
    if [[ -n "$project_id" && -n "$project_name" ]]; then
      project_ids+=("$project_id")
      project_names+=("$project_name")
    fi
  done < <(echo "$projects" | grep -o '"id":"[^"]*","name":"[^"]*"')
  
  if [[ ${#project_names[@]} -eq 0 ]]; then
    echo "No projects found" >&2
    return 1
  fi
  
  # Display projects with numbers (to stderr so it doesn't interfere with return value)
  echo "Available Projects:" >&2
  echo "" >&2
  for i in "${!project_names[@]}"; do
    # Mark current project if it matches
    local marker=""
    if [[ "${project_ids[i]}" == "$CLOCKIFY_PROJECT_ID" ]]; then
      marker=" (current)"
    fi
    printf "%2d. %s%s\n" $((i+1)) "${project_names[i]}" "$marker" >&2
  done
  echo "" >&2
  
  # Get user selection
  while true; do
    read -p "Select a project (1-${#project_names[@]}): " selection
    
    # Check if input is a valid number
    if [[ "$selection" =~ ^[0-9]+$ ]] && [[ "$selection" -ge 1 ]] && [[ "$selection" -le ${#project_names[@]} ]]; then
      # Return both project ID and name to stdout (separated by tab)
      echo -e "${project_ids[$((selection-1))]}\t${project_names[$((selection-1))]}"
      return 0
    else
      echo "Invalid selection. Please enter a number between 1 and ${#project_names[@]}." >&2
    fi
  done
}

main() {
  # Parse arguments
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
    get_project_names
  else
    local selection_result=$(select_project_interactively)
    
    if [[ $? -eq 0 && -n "$selection_result" ]]; then
      # Parse the tab-separated result
      local selected_project_id=$(echo "$selection_result" | cut -f1)
      local selected_project_name=$(echo "$selection_result" | cut -f2)
      
      # Update project ID in config
      CLOCKIFY_PROJECT_ID="$selected_project_id"
      save_config
      echo "Current project set to: $selected_project_name"
      # Also return the selected project info for use by other scripts
      echo "$selection_result"
    else
      echo "Project selection cancelled or failed." >&2
      return 1
    fi
  fi
}

# Only execute main if script is run directly (not sourced)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main "$@"
fi