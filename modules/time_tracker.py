"""
Time tracking functionality for Clockify CLI.
"""
from typing import Optional, Dict, Any
import time
from .api_client import ClockifyAPI, ClockifyAPIError
from .config import ClockifyConfig
from .project_manager import ProjectManager
from .pomodoro import PomodoroIntegration, PomodoroError
from .utils import show_notification, format_duration, calculate_elapsed_minutes


class TimeTracker:
    """Handles time entry start/stop operations and info display."""

    def __init__(self, api: ClockifyAPI, config: ClockifyConfig, project_manager: ProjectManager):
        self.api = api
        self.config = config
        self.project_manager = project_manager
        self.pomodoro = PomodoroIntegration()
        self._last_stop_time = None
    
    def is_tracking(self) -> bool:
        """Check if currently tracking time."""
        try:
            current_entry = self.api.get_current_time_entry()
            return current_entry is not None
        except ClockifyAPIError:
            return False
    
    def get_current_entry(self) -> Optional[Dict[str, Any]]:
        """Get current active time entry."""
        try:
            return self.api.get_current_time_entry()
        except ClockifyAPIError as e:
            print(f"Error getting current time entry: {e}")
            return None
    
    def start_tracking(self, description: Optional[str] = None, project_id: Optional[str] = None, task_id: Optional[str] = None) -> bool:
        """Start time tracking."""
        # Check if already tracking
        if self.is_tracking():
            print("Time tracking is already active")
            return False
        
        # Use provided description or get from config
        if description:
            self.config.description = description
        elif not self.config.description:
            print("No description specified. Use --description or run 'task select' command first.")
            return False
        
        # Use provided project ID or get from config
        if project_id:
            self.config.project_id = project_id
        elif not self.config.project_id:
            print("No project specified. Use --project-id or run 'project select' command first.")
            return False
        
        # Use provided task ID or get from config (optional)
        if task_id:
            self.config.task_id = task_id
        # task_id is optional - can be None for entries without formal tasks

        # Validate that task_id belongs to project_id if task_id is provided
        if self.config.task_id:
            try:
                tasks = self.api.get_project_tasks(self.config.project_id)
                task_exists = any(task['id'] == self.config.task_id for task in tasks)
                if not task_exists:
                    print(f"Warning: Task ID {self.config.task_id} does not exist in project {self.config.project_id}")
                    print(f"         Task name: {self.config.task_name}")
                    print("This task may have been deleted or moved to another project.")
                    print("Starting time entry without a formal task...")
                    self.config.task_id = None
                    self.config.task_name = None
            except ClockifyAPIError as e:
                print(f"Warning: Could not validate task: {e}")
                print("Continuing with the provided task ID...")

        # For Pomodoro integration: only prevent start if actively in break state
        if self.pomodoro.is_available():
            current_state = self.pomodoro.get_current_state()
            # Only block if actively in a break state (short-break or long-break)
            # Allow starting if state is null/None (idle) or already "pomodoro"
            if current_state in ["short-break", "long-break"]:
                print(f"Pomodoro in break state ({current_state}), skipping Clockify start")
                return False

            # Prevent spurious resume: if we stopped recently and state is null,
            # it's likely Gnome Pomodoro auto-detecting activity after manual stop
            if current_state is None or current_state == "null":
                last_stop = self.config.last_stop_time
                if last_stop:
                    time_since_stop = time.time() - last_stop
                    if time_since_stop < 10:  # Within 10 seconds
                        print(f"Ignoring resume request {time_since_stop:.1f}s after stop (likely spurious)")
                        return False
        
        try:
            description_text = self.config.description
            task_info = f" (Task: {self.config.task_name})" if self.config.task_name else ""
            print(f"Starting time entry: {description_text}{task_info}")
            
            entry = self.api.start_time_entry(
                description=description_text, 
                project_id=self.config.project_id,
                task_id=self.config.task_id
            )
            
            if entry and entry.get("id"):
                self.config.current_entry_id = entry["id"]
                self.config.last_stop_time = None  # Clear stop time cooldown
                print(f"Time entry started successfully (ID: {entry['id']})")
                show_notification(f"Time entry started: {description_text}")
                return True
            else:
                print("Error: Failed to start time entry")
                return False
        
        except ClockifyAPIError as e:
            print(f"Error starting time entry: {e}")
            return False
    
    def stop_tracking(self) -> bool:
        """Stop time tracking."""
        if not self.is_tracking():
            print("No active time entry found")
            return False
        
        try:
            print("Stopping time entry...")
            
            result = self.api.stop_time_entry()
            
            if result and result.get("id"):
                self.config.current_entry_id = None  # Clear state
                self.config.last_stop_time = time.time()  # Record stop time for cooldown
                description = result.get('description', 'Unknown')
                print(f"Time entry stopped successfully (ID: {result['id']})")
                show_notification(f"Time entry stopped: {description}")
                return True
            else:
                print("Error: Failed to stop time entry")
                return False
        
        except ClockifyAPIError as e:
            print(f"Error stopping time entry: {e}")
            # Clear state file even if API call failed
            self.config.current_entry_id = None
            self.config.last_stop_time = time.time()  # Record stop time for cooldown
            return False
    
    def change_description(self, new_description: str) -> bool:
        """Change description, restarting tracking if active."""
        was_tracking = self.is_tracking()
        pomodoro_was_running = False
        
        if self.pomodoro.is_available():
            pomodoro_was_running = self.pomodoro.is_running()
        
        # Stop current tracking if active
        if was_tracking:
            print("Stopping current time entry...")
            if not self.stop_tracking():
                print("Warning: Failed to stop current entry, continuing...")
            
            # Pause Pomodoro if it was running
            if pomodoro_was_running:
                try:
                    print("Pausing Pomodoro timer...")
                    self.pomodoro.pause()
                except PomodoroError as e:
                    print(f"Warning: Failed to pause Pomodoro: {e}")
        
        # Update description
        self.config.description = new_description
        print(f"Description updated to: {new_description}")
        
        # Restart tracking if it was active
        if was_tracking and pomodoro_was_running:
            print("Restarting time entry with new description...")
            if self.start_tracking():
                try:
                    print("Resuming Pomodoro timer...")
                    self.pomodoro.resume()
                    print("Both timers resumed with new description")
                except PomodoroError as e:
                    print(f"Warning: Failed to resume Pomodoro: {e}")
            else:
                print("Error: Failed to restart time entry")
                return False
        elif was_tracking:
            print("Use 'start' command to begin tracking with the new description.")
        
        return True
    
    def show_info(self) -> None:
        """Display comprehensive tracking information."""
        try:
            # Get workspace info
            workspaces = self.api.get_workspaces()
            workspace_name = "Unknown"
            for ws in workspaces:
                if ws["id"] == self.api.workspace_id:
                    workspace_name = ws["name"]
                    break
            
            # Show workspace
            print("Workspace:")
            print(f"{self.api.workspace_id} {workspace_name}")
            print()
            
            # Show projects
            projects = self.api.get_projects()
            print("Projects:")
            for project in projects:
                print(f"{project['id']} {project['name']}")
            print()
            
            # Show current project and task info
            current_project = self.project_manager.get_current_project()
            if current_project:
                print(f"Current Project: {current_project['name']}")
                
                # Show current task if set
                if self.config.task_id and self.config.task_name:
                    print(f"Current Task: {self.config.task_name}")
                else:
                    print("Current Task: None")
                
                # Show current description if set
                if self.config.description:
                    print(f"Current Description: {self.config.description}")
                else:
                    print("Current Description: None")
                
                # Show available formal tasks
                try:
                    tasks = self.api.get_project_tasks(current_project['id'])
                    if tasks:
                        print()
                        print("Available Formal Tasks:")
                        for task in tasks:
                            marker = " (current)" if task['id'] == self.config.task_id else ""
                            print(f"  - {task['name']}{marker}")
                    else:
                        print("  No formal tasks found for this project")
                except ClockifyAPIError:
                    print("  Could not fetch tasks for this project")
            else:
                print("Current Project: None")
            
            print()
            
            # Show current time entry
            current_entry = self.get_current_entry()
            if current_entry:
                print("Plugin       Clockify")
                print("Type         Time Entry")
                print(f"Name         {current_entry.get('description', 'Unknown')}")
                
                # Calculate elapsed time
                start_time = current_entry.get('timeInterval', {}).get('start')
                if start_time:
                    elapsed_minutes = calculate_elapsed_minutes(start_time)
                    print(f"Elapsed      {elapsed_minutes:.2f} Min")
                else:
                    print("Elapsed      Unknown")
                
                print(f"Workspace    {workspace_name}")
                
                # Show project for current entry
                project_id = current_entry.get('projectId')
                if project_id:
                    for project in projects:
                        if project['id'] == project_id:
                            print(f"Project      {project['name']}")
                            break
            else:
                print("No active time entry")
            
            # Show Pomodoro status if available
            if self.pomodoro.is_available():
                try:
                    state = self.pomodoro.get_current_state()
                    if state:
                        print(f"Pomodoro     {state}")
                except PomodoroError:
                    pass
        
        except ClockifyAPIError as e:
            print(f"Error retrieving information: {e}")
    
    def sync_with_pomodoro(self) -> None:
        """Synchronize Clockify with Pomodoro state."""
        if not self.pomodoro.is_available():
            print("Pomodoro integration not available")
            return
        
        try:
            pomodoro_running = self.pomodoro.is_running()
            clockify_running = self.is_tracking()
            
            if pomodoro_running and not clockify_running:
                print("Pomodoro is running but Clockify is not. Starting Clockify...")
                self.start_tracking()
            elif not pomodoro_running and clockify_running:
                print("Clockify is running but Pomodoro is not. Stopping Clockify...")
                self.stop_tracking()
            else:
                print("Pomodoro and Clockify are in sync")
        
        except (ClockifyAPIError, PomodoroError) as e:
            print(f"Error syncing with Pomodoro: {e}")
