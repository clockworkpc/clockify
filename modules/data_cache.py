import os

"""
Data caching system for Clockify CLI.
Loads all data once at startup to avoid repeated API calls during menu interactions.
"""
from typing import List, Dict, Any, Optional
from .api_client import ClockifyAPI


class DataCache:
    """Caches all Clockify data fetched at startup."""

    def __init__(self, api: ClockifyAPI):
        self.api = api
        self._clients: List[Dict[str, Any]] = []
        self._projects: List[Dict[str, Any]] = []
        self._tasks_by_project: Dict[str, List[Dict[str, Any]]] = {}
        self._time_entries: List[Dict[str, Any]] = []
        self._user_id: Optional[str] = None
        self._loaded = False

    def load_all(self, time_entries_limit: int = 100) -> None:
        """Load all data from API at once."""
        print("Loading workspace data...", end=" ", flush=True)

        # Load user ID
        self._user_id = self.api.get_user_id()

        # Load clients
        self._clients = self.api.get_clients()

        # Load projects
        self._projects = self.api.get_projects()

        # Load tasks for each project
        for project in self._projects:
            try:
                tasks = self.api.get_project_tasks(project["id"])
                self._tasks_by_project[project["id"]] = tasks
            except Exception:
                self._tasks_by_project[project["id"]] = []

        # Load recent time entries
        self._time_entries = self.api.get_time_entries(limit=time_entries_limit)

        self._loaded = True
        print("Done!")

        # clear the console after loading
        os.system("cls" if os.name == "nt" else "clear")

    def refresh(self, time_entries_limit: int = 100) -> None:
        """Refresh all cached data."""
        self.load_all(time_entries_limit)

    def get_clients(self) -> List[Dict[str, Any]]:
        """Get cached clients."""
        if not self._loaded:
            self._clients = self.api.get_clients()
        return self._clients

    def get_projects(self) -> List[Dict[str, Any]]:
        """Get cached projects."""
        if not self._loaded:
            self._projects = self.api.get_projects()
        return self._projects

    def get_project_tasks(self, project_id: str) -> List[Dict[str, Any]]:
        """Get cached tasks for a project."""
        if not self._loaded or project_id not in self._tasks_by_project:
            tasks = self.api.get_project_tasks(project_id)
            self._tasks_by_project[project_id] = tasks
            return tasks
        return self._tasks_by_project[project_id]

    def get_time_entries(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get cached time entries."""
        if not self._loaded:
            self._time_entries = self.api.get_time_entries(limit)
        return self._time_entries

    def get_user_id(self) -> str:
        """Get cached user ID."""
        if not self._user_id:
            self._user_id = self.api.get_user_id()
        return self._user_id

    def invalidate_tasks(self, project_id: str) -> None:
        """Invalidate cached tasks for a specific project (e.g., after creating/deleting a task)."""
        if project_id in self._tasks_by_project:
            del self._tasks_by_project[project_id]

    def invalidate_time_entries(self) -> None:
        """Invalidate cached time entries (e.g., after creating a new entry)."""
        self._time_entries = []

    def is_loaded(self) -> bool:
        """Check if cache has been loaded."""
        return self._loaded
