"""
Project management functionality for Clockify CLI.
"""
from typing import List, Optional, Tuple
from .api_client import ClockifyAPI
from .config import ClockifyConfig
from .utils import get_user_selection


class ProjectManager:
    """Handles project selection and management."""
    
    def __init__(self, api: ClockifyAPI, config: ClockifyConfig):
        self.api = api
        self.config = config
    
    def get_projects(self) -> List[dict]:
        """Get all projects from the workspace."""
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
        """Get the current project from active time entry or config."""
        # First, try to get from active time entry
        current_entry = self.api.get_current_time_entry()
        if current_entry and current_entry.get("projectId"):
            project = self.find_project_by_id(current_entry["projectId"])
            if project:
                return project
        
        # Fall back to configured project
        if self.config.project_id:
            project = self.find_project_by_id(self.config.project_id)
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
        projects = self.get_projects()
        if not projects:
            print("No projects found")
            return None
        
        project_names = [project["name"] for project in projects]
        current_project_name = self.get_current_project_name()
        
        selection_index = get_user_selection(
            project_names, 
            "Available Projects",
            current_project_name
        )
        
        if selection_index is not None:
            selected_project = projects[selection_index]
            return selected_project["id"], selected_project["name"]
        
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