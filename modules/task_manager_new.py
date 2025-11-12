"""
Task and Description management functionality for Clockify CLI.
Handles the hierarchy: Client > Project > Task > Description
"""
from typing import List, Optional, Dict, Tuple
from .api_client import ClockifyAPI
from .config import ClockifyConfig
from .project_manager import ProjectManager
from .utils import get_user_selection


class TaskDescriptionManager:
    """Handles task selection and description management."""

    def __init__(self, api: ClockifyAPI, config: ClockifyConfig, project_manager: ProjectManager, cache=None):
        self.api = api
        self.config = config
        self.project_manager = project_manager
        self.cache = cache

    def get_formal_tasks_for_project(self, project_id: str) -> List[Dict]:
        """Get all formal tasks for a specific project."""
        try:
            if self.cache:
                return self.cache.get_project_tasks(project_id)
            return self.api.get_project_tasks(project_id)
        except Exception:
            return []

    def get_descriptions_for_task(self, project_id: str, task_id: str, task_name: str, limit: int = 100) -> List[str]:
        """Get unique descriptions used with a specific task."""
        # Get time entries from cache if available
        if self.cache:
            entries = self.cache.get_time_entries(limit)
        else:
            entries = self.api.get_time_entries(limit)

        # Process entries to extract descriptions
        descriptions = set()
        for entry in entries:
            entry_project_id = entry.get("projectId")
            entry_task_id = entry.get("taskId")
            entry_description = entry.get("description", "").strip()

            # Must be from the same project and have a description
            if entry_project_id != project_id or not entry_description:
                continue

            # Include entries that either:
            # 1. Have the matching task ID, OR
            # 2. Have no task ID (legacy entries from before formal tasks were assigned)
            if entry_task_id == task_id or entry_task_id is None:
                descriptions.add(entry_description)

        return sorted(list(descriptions))

    def get_recent_combinations(self, limit: int = 5) -> List[Dict]:
        """Get the N most recent unique client-project-task-description combinations.

        Returns:
            List of dicts with keys: client_id, client_name, project_id, project_name,
            task_id, task_name, description, timestamp
        """
        # Get time entries from cache if available
        if self.cache:
            entries = self.cache.get_time_entries(100)  # Get more entries to find unique combinations
        else:
            entries = self.api.get_time_entries(100)

        # Track unique combinations (keyed by tuple to detect duplicates)
        seen_combinations = set()
        recent_combinations = []

        # Iterate through entries (already sorted by most recent first from API)
        for entry in entries:
            # Skip entries without required fields
            description = entry.get("description", "").strip()
            if not description:
                continue

            project_id = entry.get("projectId")
            if not project_id:
                continue

            # Get timestamp from entry
            time_interval = entry.get("timeInterval", {})
            timestamp = time_interval.get("start") or time_interval.get("end")
            if not timestamp:
                continue

            # Get task info
            task_id = entry.get("taskId")
            task_name = None

            # Get project info
            project = self.project_manager.find_project_by_id(project_id)
            if not project:
                continue
            project_name = project.get("name", "Unknown")

            # Get client info
            client_id = project.get("clientId")
            client_name = None
            if client_id:
                # Get client name from ClientManager
                clients = self.api.get_clients() if not self.cache else self.cache.get_clients()
                for client in clients:
                    if client.get("id") == client_id:
                        client_name = client.get("name", "Unknown")
                        break

            # Get task name if task_id exists
            if task_id:
                try:
                    tasks = self.get_formal_tasks_for_project(project_id)
                    for task in tasks:
                        if task.get("id") == task_id:
                            task_name = task.get("name")
                            break
                except Exception:
                    pass

            # Create unique key (combination of all relevant fields)
            combination_key = (client_id, project_id, task_id, description)

            # Skip if we've already seen this exact combination
            if combination_key in seen_combinations:
                continue

            seen_combinations.add(combination_key)
            recent_combinations.append({
                "client_id": client_id,
                "client_name": client_name,
                "project_id": project_id,
                "project_name": project_name,
                "task_id": task_id,
                "task_name": task_name,
                "description": description,
                "timestamp": timestamp
            })

            # Stop once we have enough unique combinations
            if len(recent_combinations) >= limit:
                break

        return recent_combinations
    
    def select_task_interactive(self) -> Optional[Tuple[str, str, str]]:
        """Interactively select a task from current project.

        Returns:
            Tuple of (task_id, task_name, project_id) or None if cancelled
            Returns ("BACK", None, None) if user wants to go back to project selection
        """
        current_project = self.project_manager.get_current_project()
        if not current_project:
            print("No current project found. Set a project first.")
            return None

        # Get formal tasks for current project
        formal_tasks = self.get_formal_tasks_for_project(current_project["id"])

        # Create display options - add back option, then tasks, then create option
        task_names = ["[Go back to Projects]"]
        task_names.extend([task["name"] for task in formal_tasks])
        task_names.append("[Create new task]")

        # Find current task for highlighting
        current_task_name = None
        if self.config.task_id:
            for task in formal_tasks:
                if task["id"] == self.config.task_id:
                    current_task_name = task["name"]
                    break

        result = get_user_selection(
            task_names,
            f"Formal tasks for project: {current_project['name']}",
            current_task_name
        )

        if result is not None:
            selection_index, user_input = result
            # If "Go back to Projects" was selected
            if selection_index == 0:
                return ("BACK", None, None)
            # If "Create new task" was selected
            elif selection_index == len(task_names) - 1:
                # If user provided input via auto-select, use it
                if user_input:
                    return self._create_new_task_with_name(current_project, user_input)
                else:
                    return self._create_new_task_interactive(current_project)
            else:
                # Regular task selection (adjust index for the back option)
                selected_task = formal_tasks[selection_index - 1]
                return (selected_task["id"], selected_task["name"], current_project["id"])

        return None
    
    def select_description_interactive(self, task_id: str, task_name: str, project_id: str) -> Optional[str]:
        """Interactively select or create a description for a task.

        Returns:
            Selected or created description, or None if cancelled
            Returns "BACK" if user wants to go back to task selection
        """
        # Get existing descriptions for this task
        existing_descriptions = self.get_descriptions_for_task(project_id, task_id, task_name)

        # Create options - add back option, then descriptions, then new description option
        options = ["[Go back to Tasks]"]
        options.extend(existing_descriptions)
        options.append("[Enter new description]")

        # Find current description for highlighting
        current_description = self.config.description

        result = get_user_selection(
            options,
            f"Descriptions for task: {task_name}",
            current_description
        )

        if result is not None:
            selection_index, user_input = result
            # If "Go back to Tasks" was selected
            if selection_index == 0:
                return "BACK"
            # If "Enter new description" was selected
            elif selection_index == len(options) - 1:
                # If user provided input via auto-select, use it directly
                if user_input:
                    return user_input
                else:
                    return self._create_new_description_interactive(task_name)
            else:
                # Regular description selection (adjust index for the back option)
                return existing_descriptions[selection_index - 1]

        return None
    
    def _create_new_description_interactive(self, task_name: str) -> Optional[str]:
        """Interactive new description creation."""
        try:
            description = input(f"Enter new description for task '{task_name}': ").strip()
            if not description:
                print("Description cannot be empty.")
                return None
            return description
        except KeyboardInterrupt:
            print("\nDescription creation cancelled.")
            return None

    def _create_new_task_with_name(self, current_project: Dict, task_name: str) -> Optional[Tuple[str, str, str]]:
        """Create a new task with a provided name.

        Returns:
            Tuple of (task_id, task_name, project_id) or None if failed
        """
        if not task_name or not task_name.strip():
            print("Task name cannot be empty.")
            return None

        task_name = task_name.strip()

        # Create the task using the existing create_formal_task method
        success = self.create_formal_task(task_name)
        if not success:
            return None

        # Find the newly created task to return its details
        formal_tasks = self.get_formal_tasks_for_project(current_project["id"])
        for task in formal_tasks:
            if task["name"] == task_name:
                return (task["id"], task["name"], current_project["id"])

        print("Error: Could not find the newly created task")
        return None

    def _create_new_task_interactive(self, current_project: Dict) -> Optional[Tuple[str, str, str]]:
        """Interactive new task creation.

        Returns:
            Tuple of (task_id, task_name, project_id) or None if cancelled/failed
        """
        try:
            task_name = input(f"Enter name for new task in project '{current_project['name']}': ").strip()
            if not task_name:
                print("Task name cannot be empty.")
                return None

            # Create the task using the existing create_formal_task method
            success = self.create_formal_task(task_name)
            if not success:
                return None

            # Find the newly created task to return its details
            formal_tasks = self.get_formal_tasks_for_project(current_project["id"])
            for task in formal_tasks:
                if task["name"] == task_name:
                    return (task["id"], task["name"], current_project["id"])

            print("Error: Could not find the newly created task")
            return None

        except KeyboardInterrupt:
            print("\nTask creation cancelled.")
            return None
    
    def select_task_and_description_interactive(self) -> Optional[Tuple[str, str, str]]:
        """Full interactive selection: Task -> Description.

        Returns:
            Tuple of (task_id, task_name, description) or None if cancelled
            Returns ("BACK", None, None) if user wants to go back to project selection
        """
        while True:
            # Step 1: Select task
            task_result = self.select_task_interactive()
            if not task_result:
                return None

            task_id, task_name, project_id = task_result

            # Check if user wants to go back to project selection
            if task_id == "BACK":
                return ("BACK", None, None)

            print(f"\nSelected task: {task_name}")
            print()

            # Step 2: Select description (loop until valid selection or cancel)
            while True:
                description = self.select_description_interactive(task_id, task_name, project_id)
                if not description:
                    return None

                # Check if user wants to go back to task selection
                if description == "BACK":
                    print()
                    break  # Break inner loop to go back to task selection

                # Valid description selected
                return (task_id, task_name, description)
    
    def set_current_task_and_description(self, task_id: Optional[str], task_name: Optional[str], description: str,
                                       project_id: Optional[str] = None, client_id: Optional[str] = None,
                                       stop_timer: bool = True, save_previous_state: bool = True) -> None:
        """Set the current task and description in configuration.

        Args:
            task_id: The formal task ID (None for description-only entries)
            task_name: The task name (for display, None for description-only entries)
            description: The time entry description
            project_id: Optional project ID to switch to
            client_id: Optional client ID to switch to
            stop_timer: Whether to stop the current timer when switching
            save_previous_state: Whether to save current state as previous (False when called from switch)
        """
        # Save current task state as previous task before switching
        # Only save if there is a current task set AND we're not being called from switch
        if save_previous_state and (self.config.task_id or self.config.task_name or self.config.description):
            previous_state = {
                "client_id": self.config.client_id,
                "project_id": self.config.project_id,
                "task_id": self.config.task_id,
                "task_name": self.config.task_name,
                "description": self.config.description
            }
            self.config.previous_task = previous_state

        # Stop current timer and pause Pomodoro if requested
        if stop_timer:
            try:
                # Import here to avoid circular imports
                from .time_tracker import TimeTracker
                from .pomodoro import PomodoroIntegration
                
                # Create instances
                api = ClockifyAPI(self.config.token, self.config.workspace_id)
                time_tracker = TimeTracker(api, self.config, self.project_manager)
                pomodoro = PomodoroIntegration()
                
                was_tracking = time_tracker.is_tracking()
                was_pomodoro_running = False
                
                if pomodoro.is_available():
                    was_pomodoro_running = pomodoro.is_running()
                
                # Stop Clockify timer
                if was_tracking:
                    print("Stopping current timer due to task/description change...")
                    time_tracker.stop_tracking()
                
                # Pause Pomodoro if it was running
                if was_pomodoro_running:
                    print("Pausing Pomodoro timer...")
                    pomodoro.pause()
                
                # Store state for resuming later
                self._should_resume_tracking = was_tracking or was_pomodoro_running
                self._was_clockify_running = was_tracking
                self._was_pomodoro_running = was_pomodoro_running
                
            except Exception as e:
                print(f"Warning: Could not stop current timer: {e}")
                self._should_resume_tracking = False

        # Update client if provided
        if client_id and client_id != self.config.client_id:
            self.config.client_id = client_id
            # Note: We don't resolve client name here to keep this method lightweight

        # Update project if provided
        if project_id and project_id != self.config.project_id:
            # Find project name for display
            project = self.project_manager.find_project_by_id(project_id)
            project_name = project["name"] if project else project_id
            
            self.config.project_id = project_id
            print(f"Project changed to: {project_name}")
        
        # Update task and description
        self.config.task_id = task_id
        self.config.task_name = task_name
        self.config.description = description

        if task_name:
            print(f"Task set to: {task_name}")
        else:
            print("Task cleared (description-only entry)")
        print(f"Description set to: {description}")
        
        # Resume tracking if it was active before the switch
        if stop_timer and hasattr(self, '_should_resume_tracking') and self._should_resume_tracking:
            try:
                from .time_tracker import TimeTracker
                from .pomodoro import PomodoroIntegration
                
                api = ClockifyAPI(self.config.token, self.config.workspace_id)
                time_tracker = TimeTracker(api, self.config, self.project_manager)
                pomodoro = PomodoroIntegration()
                
                was_clockify_running = getattr(self, '_was_clockify_running', False)
                was_pomodoro_running = getattr(self, '_was_pomodoro_running', False)

                print("Resuming tracking with new task/description...")

                # Resume Pomodoro timer FIRST if it was running
                # This must happen before starting Clockify because start_tracking()
                # checks the Pomodoro state and will refuse to start if not in work state
                if was_pomodoro_running and pomodoro.is_available():
                    print("Resuming Pomodoro timer...")
                    pomodoro.resume()

                # Start Clockify timer if it was running or if Pomodoro was running
                clockify_started = False
                if was_clockify_running or was_pomodoro_running:
                    clockify_started = time_tracker.start_tracking()
                    if not clockify_started:
                        print("Failed to restart Clockify timer")
                
                # Status message
                if clockify_started and was_pomodoro_running:
                    print("Both timers resumed with new task/description")
                elif clockify_started:
                    print("Clockify timer started with new task/description") 
                elif was_pomodoro_running:
                    print("Pomodoro timer resumed")
                
                # Clean up the flags
                if hasattr(self, '_should_resume_tracking'):
                    delattr(self, '_should_resume_tracking')
                if hasattr(self, '_was_clockify_running'):
                    delattr(self, '_was_clockify_running')
                if hasattr(self, '_was_pomodoro_running'):
                    delattr(self, '_was_pomodoro_running')
                
            except Exception as e:
                print(f"Warning: Could not resume tracking: {e}")
    
    def list_tasks_and_descriptions(self) -> None:
        """List all formal tasks for current project with their descriptions."""
        current_project = self.project_manager.get_current_project()
        if not current_project:
            print("No current project found. Set a project first.")
            return
        
        print(f"Formal tasks for project: {current_project['name']}")
        print()
        
        formal_tasks = self.get_formal_tasks_for_project(current_project["id"])
        
        if not formal_tasks:
            print("No formal tasks found for this project")
            return
        
        for task in formal_tasks:
            print(f"Task: {task['name']}")
            descriptions = self.get_descriptions_for_task(current_project["id"], task["id"], task["name"])
            if descriptions:
                for desc in descriptions:
                    print(f"  - {desc}")
            else:
                print("  (no descriptions used yet)")
            print()
    
    def create_formal_task(self, task_name: str) -> bool:
        """Create a new formal task in the current project."""
        current_project = self.project_manager.get_current_project()
        if not current_project:
            print("No current project found. Set a project first.")
            return False
        
        # Check if task already exists
        existing_tasks = self.get_formal_tasks_for_project(current_project["id"])
        for task in existing_tasks:
            if task["name"] == task_name:
                print(f"Task '{task_name}' already exists in project '{current_project['name']}'")
                return False
        
        try:
            print(f"Creating formal task '{task_name}' in project '{current_project['name']}'...")
            new_task = self.api.create_task(current_project["id"], task_name)

            if new_task and new_task.get("id"):
                print(f"Task '{task_name}' created successfully!")
                print(f"Task ID: {new_task['id']}")

                # Invalidate cache for this project's tasks
                if self.cache:
                    self.cache.invalidate_tasks(current_project["id"])

                return True
            else:
                print(f"Error: Failed to create task '{task_name}'")
                return False

        except Exception as e:
            print(f"Error creating task '{task_name}': {e}")
            return False

    def delete_formal_task(self, task_name: str) -> bool:
        """Delete a formal task from the current project."""
        current_project = self.project_manager.get_current_project()
        if not current_project:
            print("No current project found. Set a project first.")
            return False
        
        # Find the task to delete
        existing_tasks = self.get_formal_tasks_for_project(current_project["id"])
        task_to_delete = None
        for task in existing_tasks:
            if task["name"] == task_name:
                task_to_delete = task
                break
        
        if not task_to_delete:
            print(f"Task '{task_name}' not found in project '{current_project['name']}'")
            return False
        
        # Confirm deletion
        print(f"Warning: Deleting task '{task_name}' will remove it permanently.")
        print("All time entries for this task will become without a task (but retain the project).")
        try:
            confirm = input("Are you sure you want to delete this task? (y/N): ").strip().lower()
            if confirm not in ['y', 'yes']:
                print("Task deletion cancelled.")
                return False
        except KeyboardInterrupt:
            print("\nTask deletion cancelled.")
            return False
        
        try:
            print(f"Deleting task '{task_name}' from project '{current_project['name']}'...")
            success = self.api.delete_task(current_project["id"], task_to_delete["id"])

            if success:
                print(f"Task '{task_name}' deleted successfully!")

                # Invalidate cache for this project's tasks
                if self.cache:
                    self.cache.invalidate_tasks(current_project["id"])

                # Clear current task if it was the deleted one
                if self.config.task_id == task_to_delete["id"]:
                    self.config.task_id = None
                    self.config.task_name = None
                    print("Cleared current task setting as it was deleted.")

                return True
            else:
                print(f"Error: Failed to delete task '{task_name}'")
                return False

        except Exception as e:
            print(f"Error deleting task '{task_name}': {e}")
            return False
    
    def get_current_task_info(self) -> Dict[str, Optional[str]]:
        """Get current task and description info."""
        return {
            "task_id": self.config.task_id,
            "task_name": self.config.task_name,
            "description": self.config.description
        }

    def switch_to_previous_task(self) -> bool:
        """Switch back to the previously selected task (like 'cd -' or 'git checkout -').

        Returns:
            True if successfully switched, False otherwise
        """
        previous_task = self.config.previous_task

        if not previous_task:
            print("No previous task found.")
            print("Set a task first to create a history.")
            return False

        # Get CURRENT state from API (source of truth), not from config file
        # The config file might be stale or incorrect
        current_entry = self.api.get_current_time_entry()

        if current_entry:
            # Extract current state from running time entry
            current_description = current_entry.get("description")
            current_project_id = current_entry.get("projectId")
            current_task_id = current_entry.get("taskId")

            # Get task name if task_id exists
            current_task_name = None
            if current_task_id and current_project_id:
                try:
                    tasks = self.api.get_project_tasks(current_project_id)
                    for task in tasks:
                        if task["id"] == current_task_id:
                            current_task_name = task["name"]
                            break
                except Exception:
                    pass

            # Get client_id from project
            current_client_id = None
            if current_project_id:
                project = self.project_manager.find_project_by_id(current_project_id)
                if project:
                    current_client_id = project.get("clientId")

            # Save current API state as previous_task for future switches
            current_state = {
                "client_id": current_client_id,
                "project_id": current_project_id,
                "task_id": current_task_id,
                "task_name": current_task_name,
                "description": current_description
            }
            self.config.previous_task = current_state

            print("Current state captured from running time entry (source of truth)")
        else:
            # No timer running - use config but warn user it might be stale
            print("Warning: No timer currently running")
            print("Using last known state from config (might be stale)")
            print()

            # Save current config state for next switch
            if self.config.task_id or self.config.task_name or self.config.description:
                current_state = {
                    "client_id": self.config.client_id,
                    "project_id": self.config.project_id,
                    "task_id": self.config.task_id,
                    "task_name": self.config.task_name,
                    "description": self.config.description
                }
                self.config.previous_task = current_state

        # Extract previous task details (the task we're switching TO)
        prev_client_id = previous_task.get("client_id")
        prev_project_id = previous_task.get("project_id")
        prev_task_id = previous_task.get("task_id")
        prev_task_name = previous_task.get("task_name")
        prev_description = previous_task.get("description")

        # Validate that we have at least task information
        if not prev_task_id and not prev_task_name and not prev_description:
            print("Previous task state is incomplete.")
            return False

        print(f"Switching back to previous task...")
        print(f"  Client: {prev_client_id or '(not set)'}")
        print(f"  Project: {prev_project_id or '(not set)'}")
        print(f"  Task: {prev_task_name or '(not set)'}")
        print(f"  Description: {prev_description or '(not set)'}")
        print()

        # Validate that the project still exists (if specified)
        if prev_project_id:
            project = self.project_manager.find_project_by_id(prev_project_id)
            if not project:
                print(f"Error: Previous project (ID: {prev_project_id}) no longer exists")
                return False

        # Switch to the previous task (at minimum we need a description)
        if prev_description:
            # Validate that the task still exists before switching (if task_id is present)
            if prev_project_id and prev_task_id:
                try:
                    tasks = self.api.get_project_tasks(prev_project_id)
                    task_exists = any(task['id'] == prev_task_id for task in tasks)
                    if not task_exists:
                        print(f"Warning: Previous task '{prev_task_name}' no longer exists in the project")
                        print("Switching to description only (without formal task)...")
                        prev_task_id = None
                        prev_task_name = None
                except Exception as e:
                    print(f"Warning: Could not validate previous task: {e}")

            self.set_current_task_and_description(
                prev_task_id,
                prev_task_name,
                prev_description,
                prev_project_id,
                prev_client_id,
                save_previous_state=False  # Already saved above from API
            )
            return True
        else:
            print("Error: Previous task information is incomplete (no description)")
            return False