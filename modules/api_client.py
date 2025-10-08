"""
Core Clockify API client for making HTTP requests to the Clockify API.
"""
import requests
from typing import Optional, Dict, List, Any
from datetime import datetime


class ClockifyAPIError(Exception):
    """Exception raised for Clockify API errors."""
    pass


class ClockifyAPI:
    """Core API client for Clockify interactions."""
    
    def __init__(self, token: str, workspace_id: str):
        self.token = token
        self.workspace_id = workspace_id
        self.base_url = "https://api.clockify.me/api/v1"
        self.headers = {
            "X-Api-Key": token,
            "Content-Type": "application/json"
        }
    
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Any:
        """Make HTTP request to Clockify API."""
        url = f"{self.base_url}/{endpoint}"

        try:
            response = requests.request(method, url, headers=self.headers, json=data)
            response.raise_for_status()

            # DELETE requests often return empty content
            if response.status_code == 204 or not response.content:
                return None

            return response.json()
        except requests.exceptions.RequestException as e:
            raise ClockifyAPIError(f"API request failed: {e}")
    
    def get_user(self) -> Dict[str, Any]:
        """Get current user information."""
        return self._make_request("GET", "user")
    
    def get_user_id(self) -> str:
        """Get current user ID."""
        user = self.get_user()
        return user["id"]
    
    def get_workspaces(self) -> List[Dict[str, Any]]:
        """Get all workspaces."""
        return self._make_request("GET", "workspaces")
    
    def get_clients(self) -> List[Dict[str, Any]]:
        """Get all clients in the workspace."""
        return self._make_request("GET", f"workspaces/{self.workspace_id}/clients")

    def get_projects(self) -> List[Dict[str, Any]]:
        """Get all projects in the workspace."""
        return self._make_request("GET", f"workspaces/{self.workspace_id}/projects")
    
    def get_project_tasks(self, project_id: str) -> List[Dict[str, Any]]:
        """Get all tasks for a specific project."""
        return self._make_request("GET", f"workspaces/{self.workspace_id}/projects/{project_id}/tasks")
    
    def get_current_time_entry(self) -> Optional[Dict[str, Any]]:
        """Get current active time entry."""
        user_id = self.get_user_id()
        entries = self._make_request("GET", f"workspaces/{self.workspace_id}/user/{user_id}/time-entries?in-progress=true")
        return entries[0] if entries else None
    
    def get_time_entries(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent time entries."""
        user_id = self.get_user_id()
        return self._make_request("GET", f"workspaces/{self.workspace_id}/user/{user_id}/time-entries?page-size={limit}")
    
    def start_time_entry(self, description: str, project_id: str, task_id: Optional[str] = None) -> Dict[str, Any]:
        """Start a new time entry."""
        start_time = datetime.utcnow().isoformat() + "Z"
        data = {
            "start": start_time,
            "description": description,
            "projectId": project_id
        }
        if task_id:
            data["taskId"] = task_id
        return self._make_request("POST", f"workspaces/{self.workspace_id}/time-entries", data)
    
    def stop_time_entry(self) -> Dict[str, Any]:
        """Stop the current time entry."""
        user_id = self.get_user_id()
        end_time = datetime.utcnow().isoformat() + "Z"
        data = {"end": end_time}
        return self._make_request("PATCH", f"workspaces/{self.workspace_id}/user/{user_id}/time-entries", data)
    
    def create_task(self, project_id: str, task_name: str) -> Dict[str, Any]:
        """Create a new task in the specified project."""
        data = {
            "name": task_name
        }
        return self._make_request("POST", f"workspaces/{self.workspace_id}/projects/{project_id}/tasks", data)
    
    def delete_task(self, project_id: str, task_id: str) -> bool:
        """Delete a task from a project."""
        try:
            self._make_request("DELETE", f"workspaces/{self.workspace_id}/projects/{project_id}/tasks/{task_id}")
            return True
        except ClockifyAPIError:
            return False

    def delete_time_entry(self, entry_id: str) -> bool:
        """Delete a time entry."""
        try:
            self._make_request("DELETE", f"workspaces/{self.workspace_id}/time-entries/{entry_id}")
            # If no exception was raised, deletion was successful
            return True
        except ClockifyAPIError:
            return False
    
    def create_time_entry(self, project_id: str, task_id: Optional[str], description: str, 
                         start_time: str, end_time: str) -> Dict[str, Any]:
        """Create a time entry with specified start and end times."""
        data = {
            "start": start_time,
            "end": end_time,
            "description": description,
            "projectId": project_id
        }
        if task_id:
            data["taskId"] = task_id
            
        return self._make_request("POST", f"workspaces/{self.workspace_id}/time-entries", data)
    
    def find_project_by_name(self, project_name: str) -> Optional[Dict[str, Any]]:
        """Find project by name."""
        projects = self.get_projects()
        for project in projects:
            if project["name"] == project_name:
                return project
        return None
    
    def find_task_by_name(self, project_id: str, task_name: str) -> Optional[Dict[str, Any]]:
        """Find task by name in a specific project."""
        try:
            tasks = self.get_project_tasks(project_id)
            for task in tasks:
                if task["name"] == task_name:
                    return task
            return None
        except Exception:
            return None
    
    def get_descriptions_for_task(self, project_id: str, task_id: str, task_name: str, limit: int = 50) -> List[str]:
        """Get unique descriptions used with a specific task."""
        try:
            entries = self.get_time_entries(limit)
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
        except Exception as e:
            print(f"Error getting descriptions for task: {e}")
            return []