"""
Task management functionality for Clockify CLI.
"""
from typing import List, Optional, Dict, Set
from collections import OrderedDict
from .api_client import ClockifyAPI
from .config import ClockifyConfig
from .project_manager import ProjectManager
from .utils import get_user_selection


class TaskManager:
    """Handles task selection from time entry history."""
    
    def __init__(self, api: ClockifyAPI, config: ClockifyConfig, project_manager: ProjectManager):
        self.api = api
        self.config = config
        self.project_manager = project_manager
    
    def get_project_tasks(self, project_id: str) -> List[dict]:
        """Get formal tasks for a specific project."""
        try:
            return self.api.get_project_tasks(project_id)
        except Exception:
            return []
    
    def get_task_names_from_history(self, limit: int = 50, all_projects: bool = False) -> List[tuple]:
        """Get unique task names from time entry history.
        
        Args:
            limit: Number of entries to retrieve
            all_projects: If True, get tasks from all projects; if False, only current project
            
        Returns:
            List of tuples: (task_name, project_id, project_name)
        """
        if not all_projects:
            current_project = self.project_manager.get_current_project()
            if not current_project:
                print("No current project found. Set a project first.")
                return []
        
        entries = self.api.get_time_entries(limit)
        projects = {p["id"]: p["name"] for p in self.api.get_projects()}
        
        if not entries:
            return []
        
        # Use OrderedDict to maintain order while removing duplicates
        # Key: (task_name, project_id), Value: timestamp
        task_info = OrderedDict()
        
        # Process entries
        for entry in entries:
            project_id = entry.get("projectId")
            description = entry.get("description", "").strip()
            
            if not project_id or not description:
                continue
                
            # Filter by current project if not showing all projects
            if not all_projects:
                current_project = self.project_manager.get_current_project()
                if project_id != current_project["id"]:
                    continue
            
            # Create unique key for task+project combination
            key = (description, project_id)
            task_info[key] = entry.get("timeInterval", {}).get("start")
        
        # Convert to list of tuples: (task_name, project_id, project_name)
        result = []
        for (task_name, project_id), _ in task_info.items():
            project_name = projects.get(project_id, "Unknown Project")
            result.append((task_name, project_id, project_name))
        
        return result
    
    def get_formal_task_names(self) -> List[str]:
        """Get formal task names from current project."""
        current_project = self.project_manager.get_current_project()
        if not current_project:
            return []
        
        tasks = self.get_project_tasks(current_project["id"])
        return [task["name"] for task in tasks if task.get("name")]
    
    def get_all_task_suggestions(self, limit: int = 50, all_projects: bool = False) -> List[tuple]:
        """Get all task suggestions (formal + from history).
        
        Returns:
            List of tuples: (task_name, project_id, project_name) or (task_name, None, None) for formal tasks
        """
        current_project = self.project_manager.get_current_project()
        if not current_project and not all_projects:
            return []
        
        combined = []
        seen = set()
        
        # Add formal tasks first (always include current project's formal tasks)
        if current_project:
            formal_tasks = self.get_formal_task_names()
            for task in formal_tasks:
                if task and task not in seen:
                    seen.add((task, current_project["id"]))
                    combined.append((task, current_project["id"], current_project["name"]))
        
        # Add history tasks
        history_tasks = self.get_task_names_from_history(limit, all_projects)
        for task_name, project_id, project_name in history_tasks:
            key = (task_name, project_id)
            if key not in seen:
                seen.add(key)
                combined.append((task_name, project_id, project_name))
        
        return combined
    
    def list_tasks(self, limit: int = 50, all_projects: bool = False) -> None:
        """List all available tasks."""
        if all_projects:
            print("Tasks from all projects:")
        else:
            current_project = self.project_manager.get_current_project()
            if not current_project:
                print("No current project found. Set a project first.")
                return
            print(f"Tasks for project: {current_project['name']}")
        
        print()
        
        # Get all tasks
        all_tasks = self.get_all_task_suggestions(limit, all_projects)
        
        if not all_tasks:
            print("No tasks found")
            return
        
        # Group by project if showing all projects
        if all_projects:
            by_project = {}
            for task_name, project_id, project_name in all_tasks:
                if project_name not in by_project:
                    by_project[project_name] = []
                by_project[project_name].append(task_name)
            
            for project_name, tasks in by_project.items():
                print(f"{project_name}:")
                for task in tasks:
                    print(f"  - {task}")
                print()
        else:
            # Show tasks for current project
            for task_name, _, _ in all_tasks:
                print(f"  - {task_name}")
    
    def select_task_interactive(self, limit: int = 50, all_projects: bool = True) -> Optional[tuple]:
        """Interactively select a task from available options or create a new one.
        
        Returns:
            Tuple of (task_name, project_id, project_changed) or None if cancelled
        """
        current_project = self.project_manager.get_current_project()
        if not current_project:
            print("No current project found. Set a project first.")
            return None
        
        # Get all available task suggestions
        task_suggestions = self.get_all_task_suggestions(limit, all_projects)
        
        if not task_suggestions:
            print("No tasks found")
            return None
        
        # Create display options with project info
        display_options = []
        for task_name, project_id, project_name in task_suggestions:
            if all_projects and project_id != current_project["id"]:
                display_options.append(f"{task_name} ({project_name})")
            else:
                display_options.append(task_name)
        
        # Add "Create new task" option
        display_options.append("[Create new task]")
        
        # Find current task for highlighting
        current_task_display = None
        current_task = self.config.task_name
        if current_task:
            for i, (task_name, project_id, project_name) in enumerate(task_suggestions):
                if task_name == current_task and project_id == current_project["id"]:
                    current_task_display = display_options[i]
                    break
        
        title = f"Tasks {'from all projects' if all_projects else 'for project: ' + current_project['name']}"
        selection_index = get_user_selection(display_options, title, current_task_display)
        
        if selection_index is not None:
            # If "Create new task" was selected
            if selection_index == len(task_suggestions):
                new_task = self._create_new_task_interactive(current_project)
                if new_task:
                    return (new_task, current_project["id"], False)
                return None
            else:
                # Regular task selected
                task_name, project_id, project_name = task_suggestions[selection_index]
                project_changed = project_id != current_project["id"]
                return (task_name, project_id, project_changed)
        
        return None
    
    def _create_new_task_interactive(self, project: dict) -> Optional[str]:
        """Interactive new task creation."""
        try:
            task_name = input("Enter new task name: ").strip()
            if not task_name:
                print("Task name cannot be empty.")
                return None
            
            print(f"Creating task '{task_name}' in project '{project['name']}'...")
            
            # Create the task via API
            try:
                created_task = self.api.create_task(project["id"], task_name)
                print(f"Task '{task_name}' created successfully!")
                return task_name
            except Exception as e:
                print(f"Warning: Could not create formal task via API: {e}")
                print(f"Using '{task_name}' as task description instead.")
                return task_name
        
        except KeyboardInterrupt:
            print("\nTask creation cancelled.")
            return None
    
    def set_current_task(self, task_name: str, project_id: Optional[str] = None, 
                         stop_timer: bool = True) -> None:
        """Set the current task name and optionally project in configuration.
        
        Args:
            task_name: The task name to set
            project_id: Optional project ID to switch to
            stop_timer: Whether to stop the current timer when switching
        """
        # Stop current timer and pause Pomodoro if requested
        if stop_timer:
            try:
                # Import here to avoid circular imports
                from .time_tracker import TimeTracker
                from .api_client import ClockifyAPI
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
                    print("Stopping current timer due to task switch...")
                    time_tracker.stop_tracking()
                
                # Pause Pomodoro if it was running
                if was_pomodoro_running:
                    print("Pausing Pomodoro timer...")
                    pomodoro.pause()
                
                # Store state for resuming later - resume if EITHER was running
                self._should_resume_tracking = was_tracking or was_pomodoro_running
                self._was_clockify_running = was_tracking
                self._was_pomodoro_running = was_pomodoro_running
                
            except Exception as e:
                print(f"Warning: Could not stop current timer: {e}")
                self._should_resume_tracking = False
        
        # Update project if provided
        if project_id and project_id != self.config.project_id:
            # Find project name for display
            project = self.project_manager.find_project_by_id(project_id)
            project_name = project["name"] if project else project_id
            
            self.config.project_id = project_id
            print(f"Project changed to: {project_name}")
        
        # Update task name
        self.config.task_name = task_name
        print(f"Task name set to: {task_name}")
        
        # Resume tracking if it was active before the switch
        if stop_timer and hasattr(self, '_should_resume_tracking') and self._should_resume_tracking:
            try:
                from .time_tracker import TimeTracker
                from .api_client import ClockifyAPI
                from .pomodoro import PomodoroIntegration
                
                api = ClockifyAPI(self.config.token, self.config.workspace_id)
                time_tracker = TimeTracker(api, self.config, self.project_manager)
                pomodoro = PomodoroIntegration()
                
                was_clockify_running = getattr(self, '_was_clockify_running', False)
                was_pomodoro_running = getattr(self, '_was_pomodoro_running', False)
                
                print("Resuming tracking with new task/project...")
                
                # Start Clockify timer if it was running or if Pomodoro was running
                clockify_started = False
                if was_clockify_running or was_pomodoro_running:
                    clockify_started = time_tracker.start_tracking()
                    if not clockify_started:
                        print("Failed to restart Clockify timer")
                
                # Resume Pomodoro timer if it was running
                if was_pomodoro_running and pomodoro.is_available():
                    print("Resuming Pomodoro timer...")
                    pomodoro.resume()
                
                # Status message
                if clockify_started and was_pomodoro_running:
                    print("Both timers resumed with new task/project")
                elif clockify_started:
                    print("Clockify timer started with new task/project") 
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
    
    def get_current_task_name(self) -> Optional[str]:
        """Get the current task name."""
        return self.config.task_name