"""
Project management functionality for Clockify CLI.
"""
from typing import List, Optional, Tuple
from .api_client import ClockifyAPI
from .config import ClockifyConfig
from .utils import get_user_selection


class ProjectManager:
    """Handles project selection and management."""

    def __init__(self, api: ClockifyAPI, config: ClockifyConfig, cache=None):
        self.api = api
        self.config = config
        self.cache = cache

    def get_projects(self) -> List[dict]:
        """Get all projects from the workspace."""
        if self.cache:
            return self.cache.get_projects()
        return self.api.get_projects()
    
    def get_project_names(self) -> List[str]:
        """Get list of project names."""
        projects = self.get_projects()
        return [project["name"] for project in projects]
    
    def find_project_by_name(self, name: str) -> Optional[dict]:
        """Find project by name."""
        projects = self.get_projects()
        for project in projects:
            if project["name"] == name:
                return project
        return None
    
    def find_project_by_id(self, project_id: str) -> Optional[dict]:
        """Find project by ID."""
        projects = self.get_projects()
        for project in projects:
            if project["id"] == project_id:
                return project
        return None
    
    def get_current_project(self) -> Optional[dict]:
        """Get the current project from config or active time entry."""
        # First, try to get from configured project
        if self.config.project_id:
            project = self.find_project_by_id(self.config.project_id)
            if project:
                return project

        # Fall back to active time entry
        current_entry = self.api.get_current_time_entry()
        if current_entry and current_entry.get("projectId"):
            project = self.find_project_by_id(current_entry["projectId"])
            if project:
                return project

        return None
    
    def get_current_project_name(self) -> Optional[str]:
        """Get the current project name."""
        project = self.get_current_project()
        return project["name"] if project else None
    
    def list_projects(self) -> None:
        """List all projects."""
        projects = self.get_projects()
        if not projects:
            print("No projects found")
            return
        
        print("Available Projects:")
        for project in projects:
            print(f"  {project['id']} - {project['name']}")
    
    def select_project_interactive(self) -> Optional[Tuple[str, str]]:
        """Interactively select a project."""
        while True:
            projects = self.get_projects()
            if not projects:
                print("No projects found")
                return None

            # Filter projects by current client if one is set
            if self.config.client_id:
                filtered_projects = [
                    project for project in projects
                    if project.get("clientId") == self.config.client_id
                ]

                if not filtered_projects:
                    from .client_manager import ClientManager
                    client_manager = ClientManager(self.api, self.config, self.cache)
                    current_client = client_manager.get_current_client()
                    client_name = current_client["name"] if current_client else self.config.client_id
                    print(f"No projects found for client: {client_name}")
                    return None

                projects = filtered_projects

            project_names = [project["name"] for project in projects]
            current_project_name = self.get_current_project_name()

            # Display current client if set
            if self.config.client_id:
                from .client_manager import ClientManager
                client_manager = ClientManager(self.api, self.config, self.cache)
                current_client = client_manager.get_current_client()
                if current_client:
                    print(f"\nCurrent Client: {current_client['name']}")

            # Display projects with option 0 to select client
            print("\nAvailable Projects:\n")
            print(" 0. [Select Client]")
            for i, project_name in enumerate(project_names, 1):
                marker = " (current)" if current_project_name and project_name == current_project_name else ""
                print(f"{i:2d}. {project_name}{marker}")
            print()

            # Get user input
            try:
                selection = input(f"Select an item (0-{len(project_names)}): ").strip()

                if not selection:
                    # If there's a current project, auto-select it
                    if current_project_name and current_project_name in project_names:
                        index = project_names.index(current_project_name)
                        selected_project = projects[index]
                        print(f"Auto-selecting current project: {current_project_name}")
                        return selected_project["id"], selected_project["name"]
                    continue

                # Handle "0" to open client selection
                if selection == "0":
                    from .client_manager import ClientManager
                    client_manager = ClientManager(self.api, self.config, self.cache)
                    result = client_manager.select_client_interactive()
                    if result:
                        client_id, client_name = result
                        client_manager.set_current_client(client_id)
                        print()
                        # Loop back to project selection
                        continue
                    else:
                        # Client selection cancelled, return to project selection
                        continue

                # Handle regular project selection
                index = int(selection) - 1

                if 0 <= index < len(project_names):
                    selected_project = projects[index]
                    return selected_project["id"], selected_project["name"]
                else:
                    print(f"Invalid selection. Please enter a number between 0 and {len(project_names)}.")

            except ValueError:
                print("Please enter a valid number.")
            except KeyboardInterrupt:
                print("\nSelection cancelled.")
                return None
    
    def set_current_project(self, project_id: str) -> bool:
        """Set the current project in configuration."""
        project = self.find_project_by_id(project_id)
        if not project:
            print(f"Project with ID {project_id} not found")
            return False
        
        self.config.project_id = project_id
        print(f"Current project set to: {project['name']}")
        return True
    
    def set_current_project_by_name(self, project_name: str) -> bool:
        """Set the current project by name."""
        project = self.find_project_by_name(project_name)
        if not project:
            print(f"Project '{project_name}' not found")
            return False
        
        self.config.project_id = project["id"]
        print(f"Current project set to: {project['name']}")
        return True