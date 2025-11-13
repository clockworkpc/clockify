#!/usr/bin/env python3
"""
Clockify CLI - Python implementation
A modular command-line interface for Clockify time tracking.
"""
import argparse
import sys
from typing import Optional

from modules.config import ClockifyConfig
from modules.api_client import ClockifyAPI, ClockifyAPIError
from modules.data_cache import DataCache
from modules.client_manager import ClientManager
from modules.project_manager import ProjectManager
from modules.task_manager_new import TaskDescriptionManager
from modules.time_tracker import TimeTracker
from modules.pomodoro import PomodoroIntegration, PomodoroError
from modules.events import PomodoroEventExtractor


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser with all commands and options."""
    parser = argparse.ArgumentParser(
        description="Clockify CLI - Time tracking and Pomodoro integration",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Global options
    parser.add_argument("--token", help="Clockify API token")
    parser.add_argument("--workspace-id", help="Workspace ID")
    parser.add_argument("--project-id", help="Project ID")
    parser.add_argument("--task-name", help="Task name (deprecated, use --description)")
    parser.add_argument("--description", help="Time entry description")
    
    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Start command
    start_parser = subparsers.add_parser("start", help="Start time tracking")
    start_parser.add_argument("enable", nargs="?", help="Pomodoro trigger (compatibility)")
    start_parser.add_argument("--enable", action="store_true", help="Pomodoro trigger (compatibility)")
    
    # Stop command
    stop_parser = subparsers.add_parser("stop", help="Stop time tracking")
    
    # Resume command (alias for start)
    resume_parser = subparsers.add_parser("resume", help="Resume time tracking")
    
    # Pause command (alias for stop)
    pause_parser = subparsers.add_parser("pause", help="Pause time tracking")
    
    # Skip command (stop with Pomodoro skip)
    skip_parser = subparsers.add_parser("skip", help="Skip current session")
    skip_parser.add_argument("disable", nargs="?", help="Disable after skip (compatibility)")
    skip_parser.add_argument("--disable", action="store_true", help="Disable after skip")
    
    # Complete command (alias for stop)
    complete_parser = subparsers.add_parser("complete", help="Complete current session")
    
    # Info command
    info_parser = subparsers.add_parser("info", help="Show current status")

    # Client commands
    client_parser = subparsers.add_parser("client", help="Client management")
    client_subparsers = client_parser.add_subparsers(dest="client_action")

    client_list_parser = client_subparsers.add_parser("list", help="List all clients")
    client_select_parser = client_subparsers.add_parser("select", help="Interactively select client")
    client_set_parser = client_subparsers.add_parser("set", help="Set client by name")
    client_set_parser.add_argument("name", help="Client name")

    # Project commands
    project_parser = subparsers.add_parser("project", help="Project management")
    project_subparsers = project_parser.add_subparsers(dest="project_action")
    
    project_list_parser = project_subparsers.add_parser("list", help="List all projects")
    project_select_parser = project_subparsers.add_parser("select", help="Interactively select project")
    project_set_parser = project_subparsers.add_parser("set", help="Set project by name")
    project_set_parser.add_argument("name", help="Project name")
    
    # Task commands
    task_parser = subparsers.add_parser("task", help="Task management")
    task_subparsers = task_parser.add_subparsers(dest="task_action")

    task_list_parser = task_subparsers.add_parser("list", help="List all tasks")
    task_list_parser.add_argument("--limit", type=int, default=50, help="Limit for history entries")
    task_list_parser.add_argument("--all-projects", action="store_true", help="Show tasks from all projects")
    task_select_parser = task_subparsers.add_parser("select", help="Interactively select task")
    task_select_parser.add_argument("--limit", type=int, default=50, help="Limit for history entries")
    task_set_parser = task_subparsers.add_parser("set", help="Set task name directly")
    task_set_parser.add_argument("name", help="Task name")
    task_create_parser = task_subparsers.add_parser("create", help="Create a new formal task")
    task_create_parser.add_argument("name", help="Task name")
    task_delete_parser = task_subparsers.add_parser("delete", help="Delete a formal task")
    task_delete_parser.add_argument("name", help="Task name")

    # Project-Task combined command
    project_task_parser = subparsers.add_parser("project-task", help="Select project and task (auto-updates client)")

    # Switch command - switch back to previous task
    switch_parser = subparsers.add_parser("switch", help="Switch back to previous task (like 'cd -' or 'git checkout -')")

    # Events commands
    events_parser = subparsers.add_parser("events", help="Pomodoro event logging")
    events_subparsers = events_parser.add_subparsers(dest="events_action")

    events_extract_parser = events_subparsers.add_parser("extract", help="Extract events from journalctl")
    events_extract_parser.add_argument("--since", default="1 day ago", help="Time period (e.g., '1 day ago', 'today', '1 week ago')")

    events_list_parser = events_subparsers.add_parser("list", help="List saved events")
    events_list_parser.add_argument("--limit", type=int, help="Limit number of events to show")

    events_clear_parser = events_subparsers.add_parser("clear", help="Clear all saved events")

    # Legacy command aliases for compatibility
    tasks_parser = subparsers.add_parser("tasks", help="List tasks (legacy alias)")
    projects_parser = subparsers.add_parser("projects", help="List projects (legacy alias)")
    
    # Pomodoro commands
    pomodoro_parser = subparsers.add_parser("pomodoro", help="Pomodoro timer control")
    pomodoro_subparsers = pomodoro_parser.add_subparsers(dest="pomodoro_action")
    
    pomodoro_start_parser = pomodoro_subparsers.add_parser("start", help="Start Pomodoro")
    pomodoro_stop_parser = pomodoro_subparsers.add_parser("stop", help="Stop Pomodoro")
    pomodoro_pause_parser = pomodoro_subparsers.add_parser("pause", help="Pause Pomodoro")
    pomodoro_resume_parser = pomodoro_subparsers.add_parser("resume", help="Resume Pomodoro")
    pomodoro_skip_parser = pomodoro_subparsers.add_parser("skip", help="Skip Pomodoro session")
    pomodoro_status_parser = pomodoro_subparsers.add_parser("status", help="Show Pomodoro status")
    pomodoro_sync_parser = pomodoro_subparsers.add_parser("sync", help="Sync Clockify with Pomodoro")
    
    return parser


def setup_components(args, load_data: bool = True) -> tuple:
    """Initialize all components with configuration.

    Args:
        args: Command line arguments
        load_data: If True, preload all workspace data. Set to False for simple
                   start/stop commands to improve performance.
    """
    # Load configuration
    config = ClockifyConfig()

    # Apply command line overrides
    if args.token:
        config.token = args.token
    if args.workspace_id:
        config.workspace_id = args.workspace_id
    if args.project_id:
        config.project_id = args.project_id
    if args.description:
        config.description = args.description
    elif args.task_name:  # Backward compatibility
        config.description = args.task_name

    # Check required configuration
    missing = config.get_missing_config()
    if missing:
        print("Error: Missing required configuration:")
        for item in missing:
            print(f"  - {item}")
        print("\nUse --token and --workspace-id options or configure them first.")
        sys.exit(1)

    # Initialize components
    try:
        api = ClockifyAPI(config.token, config.workspace_id)

        # Initialize cache and optionally load all data at startup
        cache = DataCache(api)
        if load_data:
            cache.load_all(time_entries_limit=100)

        client_manager = ClientManager(api, config, cache)
        project_manager = ProjectManager(api, config, cache)
        task_manager = TaskDescriptionManager(api, config, project_manager, cache)
        time_tracker = TimeTracker(api, config, project_manager)

        return config, api, client_manager, project_manager, task_manager, time_tracker

    except ClockifyAPIError as e:
        print(f"Error initializing Clockify API: {e}")
        sys.exit(1)


def handle_time_commands(args, time_tracker: TimeTracker) -> None:
    """Handle time tracking commands."""
    # Debug: Log the command and pomodoro state
    import sys
    pomodoro = PomodoroIntegration()
    if pomodoro.is_available():
        current_state = pomodoro.get_current_state()
        print(f"DEBUG: Command={args.command}, Pomodoro state={current_state}", file=sys.stderr)

    if args.command in ["start", "resume"]:
        success = time_tracker.start_tracking(args.task_name, args.project_id)
        if not success:
            sys.exit(1)

    elif args.command in ["stop", "pause", "complete"]:
        success = time_tracker.stop_tracking()
        if not success:
            sys.exit(1)
    
    elif args.command == "skip":
        # Handle Pomodoro skip
        pomodoro = PomodoroIntegration()
        if pomodoro.is_available():
            try:
                pomodoro.skip()
                print("Pomodoro session skipped")
            except PomodoroError as e:
                print(f"Error skipping Pomodoro: {e}")
        
        success = time_tracker.stop_tracking()
        if not success:
            sys.exit(1)


def handle_client_commands(args, client_manager: ClientManager) -> None:
    """Handle client management commands."""
    if not args.client_action:
        # Default to interactive selection
        result = client_manager.select_client_interactive()
        if result:
            client_id, client_name = result
            client_manager.set_current_client(client_id)
        else:
            print("Client selection cancelled")

    elif args.client_action == "list":
        client_manager.list_clients()

    elif args.client_action == "select":
        result = client_manager.select_client_interactive()
        if result:
            client_id, client_name = result
            client_manager.set_current_client(client_id)
        else:
            print("Client selection cancelled")

    elif args.client_action == "set":
        success = client_manager.set_current_client_by_name(args.name)
        if not success:
            sys.exit(1)


def handle_project_commands(args, project_manager: ProjectManager) -> None:
    """Handle project management commands."""
    if not args.project_action:
        # Default to interactive selection
        result = project_manager.select_project_interactive()
        if result:
            project_id, project_name = result
            project_manager.set_current_project(project_id)
        else:
            print("Project selection cancelled")
    
    elif args.project_action == "list":
        project_manager.list_projects()
    
    elif args.project_action == "select":
        result = project_manager.select_project_interactive()
        if result:
            project_id, project_name = result
            project_manager.set_current_project(project_id)
        else:
            print("Project selection cancelled")
    
    elif args.project_action == "set":
        success = project_manager.set_current_project_by_name(args.name)
        if not success:
            sys.exit(1)


def handle_task_commands(args, task_manager: TaskDescriptionManager) -> None:
    """Handle task and description management commands."""
    if not args.task_action:
        # Default to interactive task and description selection
        result = task_manager.select_task_and_description_interactive()
        if result:
            task_id, task_name, description = result
            task_manager.set_current_task_and_description(task_id, task_name, description)
        else:
            print("Task/description selection cancelled")
    
    elif args.task_action == "list":
        task_manager.list_tasks_and_descriptions()
    
    elif args.task_action == "select":
        result = task_manager.select_task_and_description_interactive()
        if result:
            task_id, task_name, description = result
            task_manager.set_current_task_and_description(task_id, task_name, description)
        else:
            print("Task/description selection cancelled")
    
    elif args.task_action == "set":
        # For backward compatibility - treat as description
        current_task_id = task_manager.config.task_id
        current_task_name = task_manager.config.task_name
        
        if current_task_id and current_task_name:
            task_manager.set_current_task_and_description(current_task_id, current_task_name, args.name)
        else:
            print("No current task set. Use 'task select' first.")
    
    elif args.task_action == "create":
        success = task_manager.create_formal_task(args.name)
        if not success:
            sys.exit(1)
    
    elif args.task_action == "delete":
        success = task_manager.delete_formal_task(args.name)
        if not success:
            sys.exit(1)


def handle_pomodoro_commands(args, time_tracker: TimeTracker) -> None:
    """Handle Pomodoro timer commands."""
    pomodoro = PomodoroIntegration()

    if not pomodoro.is_available():
        print("Pomodoro integration not available")
        return

    try:
        if args.pomodoro_action == "start":
            pomodoro.start()
            print("Pomodoro started")

        elif args.pomodoro_action == "stop":
            pomodoro.stop()
            print("Pomodoro stopped")

        elif args.pomodoro_action == "pause":
            pomodoro.pause()
            print("Pomodoro paused")

        elif args.pomodoro_action == "resume":
            pomodoro.resume()
            print("Pomodoro resumed")

        elif args.pomodoro_action == "skip":
            pomodoro.skip()
            print("Pomodoro session skipped")

        elif args.pomodoro_action == "status":
            state = pomodoro.get_current_state()
            print(f"Pomodoro state: {state or 'Unknown'}")

        elif args.pomodoro_action == "sync":
            time_tracker.sync_with_pomodoro()

    except PomodoroError as e:
        print(f"Pomodoro error: {e}")
        sys.exit(1)


def handle_events_commands(args) -> None:
    """Handle pomodoro event logging commands."""
    extractor = PomodoroEventExtractor()

    if not args.events_action or args.events_action == "extract":
        # Extract events from journalctl
        since = args.since if hasattr(args, 'since') else "1 day ago"
        events = extractor.extract_events(since=since)
        extractor.save_to_file()
        print(f"Extracted and saved {len(events)} events from journalctl (since {since})")

    elif args.events_action == "list":
        # List saved events
        limit = args.limit if hasattr(args, 'limit') else None
        events = extractor.get_saved_events(limit=limit)

        if not events:
            print("No saved events found")
            return

        print(f"\nPomodoro Events ({len(events)} total):")
        print("=" * 80)

        for event in events:
            event_type = event.get("event_type", "unknown")
            timestamp = event.get("timestamp", "")
            description = event.get("description", "")

            # Format output
            print(f"{timestamp:20} {event_type:10}", end="")
            if description:
                print(f" {description}", end="")
            print()

    elif args.events_action == "clear":
        # Clear all saved events
        extractor.clear_events()
        print("All saved events cleared")


def handle_project_task_commands(project_manager: ProjectManager,
                                 task_manager: TaskDescriptionManager,
                                 client_manager: ClientManager) -> None:
    """Handle combined project-task selection with automatic client update."""
    from modules.utils import get_user_selection, display_markdown

    # Step 0: Display recent combinations as a markdown table
    recent_combinations = task_manager.get_recent_combinations(limit=5)

    if recent_combinations:
        # Build markdown table
        markdown_table = "## Recent Client-Project-Task-Description Combinations\n\n"
        markdown_table += "| # | Description | Task | Project | Client |\n"
        # markdown_table += "| # | Client | Project | Task | Description |\n"
        markdown_table += "|--------|---------|------|-------------|---|\n"

        for idx, combo in enumerate(recent_combinations, 1):
            client = combo['client_name'] if combo['client_name'] else "(no client)"
            project = combo['project_name']
            task = combo['task_name'] if combo['task_name'] else "(no task)"
            desc = combo['description']

            markdown_table += f"| {idx} | {desc} | {task} | {project} | {client} |\n"

        # Display using bat if available
        display_markdown(markdown_table)
        print()

        # Show current configuration
        print("\nCurrent configuration:")
        current_client = "(not set)"
        current_project = "(not set)"
        current_task = "(not set)"
        current_description = "(not set)"

        if client_manager.config.client_id:
            client = client_manager.find_client_by_id(client_manager.config.client_id)
            if client:
                current_client = client.get('name', current_client)

        if project_manager.config.project_id:
            project = project_manager.find_project_by_id(project_manager.config.project_id)
            if project:
                current_project = project.get('name', current_project)

        if task_manager.config.task_name:
            current_task = task_manager.config.task_name

        if task_manager.config.description:
            current_description = task_manager.config.description

        print(f"  Client: {current_client}")
        print(f"  Project: {current_project}")
        print(f"  Task: {current_task}")
        print(f"  Description: {current_description}")
        print()

        # Prompt user to select from recent or continue with manual selection
        while True:
            try:
                choice = input(f"Select 1-{len(recent_combinations)} for quick selection, or press Enter for manual selection: ").strip()

                if not choice:
                    # User pressed Enter - continue with manual selection
                    print()
                    break

                # Try to parse as number
                try:
                    selection_num = int(choice)
                    if 1 <= selection_num <= len(recent_combinations):
                        # Valid selection - use this combination
                        combo = recent_combinations[selection_num - 1]

                        # Set all the configuration at once
                        task_manager.set_current_task_and_description(
                            combo['task_id'],
                            combo['task_name'],
                            combo['description'],
                            combo['project_id'],
                            combo['client_id']
                        )

                        print(f"\nQuick selection applied:")
                        print(f"  Client: {combo['client_name'] or '(none)'}")
                        print(f"  Project: {combo['project_name']}")
                        print(f"  Task: {combo['task_name'] or '(none)'}")
                        print(f"  Description: {combo['description']}")
                        return
                    else:
                        print(f"Please enter a number between 1 and {len(recent_combinations)}, or press Enter for manual selection.")
                except ValueError:
                    print(f"Please enter a number between 1 and {len(recent_combinations)}, or press Enter for manual selection.")

            except KeyboardInterrupt:
                print("\nSelection cancelled")
                return

    # Continue with normal project-task selection flow
    while True:
        # Step 1: Select project
        result = project_manager.select_project_interactive()
        if not result:
            print("Project selection cancelled")
            return

        project_id, project_name = result

        # Step 2: Check if project has a different client and update if needed
        project = project_manager.find_project_by_id(project_id)
        if project and project.get("clientId"):
            current_client_id = client_manager.config.client_id
            project_client_id = project["clientId"]

            # If the project belongs to a different client, update the client
            if current_client_id != project_client_id:
                client = client_manager.find_client_by_id(project_client_id)
                if client:
                    client_manager.config.client_id = project_client_id
                    print(f"Client automatically updated to: {client['name']}")

        # Step 3: Set the project
        project_manager.set_current_project(project_id)
        print()

        # Step 4: Select task and description
        result = task_manager.select_task_and_description_interactive()
        if not result:
            print("Task/description selection cancelled")
            return

        task_id, task_name, description = result

        # Check if user wants to go back to project selection
        if task_id == "BACK":
            print()
            continue  # Loop back to project selection

        # Valid task and description selected
        task_manager.set_current_task_and_description(task_id, task_name, description)
        break  # Exit the loop


def run_command(args, config, api, client_manager, project_manager, task_manager, time_tracker):
    """Execute a single command."""
    # Handle commands
    if args.command in ["start", "resume", "stop", "pause", "complete", "skip"]:
        handle_time_commands(args, time_tracker)

    elif args.command == "info":
        time_tracker.show_info()

    elif args.command == "client":
        handle_client_commands(args, client_manager)

    elif args.command == "project":
        handle_project_commands(args, project_manager)

    elif args.command == "task":
        handle_task_commands(args, task_manager)

    elif args.command == "project-task":
        handle_project_task_commands(project_manager, task_manager, client_manager)

    elif args.command == "switch":
        success = task_manager.switch_to_previous_task()
        if not success:
            sys.exit(1)

    elif args.command == "pomodoro":
        handle_pomodoro_commands(args, time_tracker)

    elif args.command == "events":
        handle_events_commands(args)

    # Legacy aliases
    elif args.command == "tasks":
        task_manager.list_tasks()

    elif args.command == "projects":
        project_manager.list_projects()

    else:
        print(f"Unknown command: {args.command}")
        sys.exit(1)


def main():
    """Main application entry point."""
    # Debug: Log raw command line arguments
    import sys
    if len(sys.argv) > 1:
        print(f"DEBUG: Raw argv={sys.argv}", file=sys.stderr)

    # Handle Pomodoro triggers - these come as single arguments with spaces
    # e.g., "start enable", "skip disable"
    if len(sys.argv) == 2 and ' ' in sys.argv[1]:
        trigger_parts = sys.argv[1].split()
        print(f"DEBUG: Parsed trigger parts={trigger_parts}", file=sys.stderr)
        sys.argv = [sys.argv[0]] + trigger_parts

    parser = create_parser()
    args = parser.parse_args()

    # Handle --description only (backward compatibility with --task-name)
    description_arg = args.description or args.task_name
    if (not args.command and description_arg and
        ((len(sys.argv) == 3 and sys.argv[1] == "--description") or
         (len(sys.argv) == 3 and sys.argv[1] == "--task-name"))):
        try:
            # Description change doesn't need full data loading
            config, api, client_manager, project_manager, task_manager, time_tracker = setup_components(args, load_data=False)
            time_tracker.change_description(description_arg)
            return
        except SystemExit:
            return

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Handle events command without requiring Clockify setup
    if args.command == "events":
        handle_events_commands(args)
        return

    # Determine if we need to load all workspace data
    # Simple time tracking commands don't need the full data cache
    simple_commands = ["start", "resume", "stop", "pause", "complete", "skip"]
    needs_data = args.command not in simple_commands

    # Setup components once (data loaded via HTTP only once if needed)
    config, api, client_manager, project_manager, task_manager, time_tracker = setup_components(args, load_data=needs_data)

    # Run the first command
    run_command(args, config, api, client_manager, project_manager, task_manager, time_tracker)

    # Loop to allow multiple commands without reloading data
    while True:
        try:
            print()
            continue_choice = input("Continue with another command? (y/n): ").strip().lower()
            if continue_choice not in ['y', 'yes']:
                print("Exiting...")
                break

            print("\nAvailable commands: project-task, start, stop, info, switch")
            command = input("Enter command: ").strip()

            if not command:
                continue

            # Create new args object with the command
            if command == "project-task":
                handle_project_task_commands(project_manager, task_manager, client_manager)
            elif command in ["start", "resume"]:
                time_tracker.start_tracking()
            elif command in ["stop", "pause", "complete"]:
                time_tracker.stop_tracking()
            elif command == "info":
                time_tracker.show_info()
            elif command == "switch":
                task_manager.switch_to_previous_task()
            else:
                print(f"Unknown command: {command}")
                print("Available: project-task, start, stop, info, switch")

        except KeyboardInterrupt:
            print("\n\nExiting...")
            break
        except EOFError:
            print("\nExiting...")
            break


if __name__ == "__main__":
    main()
