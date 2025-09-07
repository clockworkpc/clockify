"""
Configuration management for Clockify CLI.
"""
import os
import json
from typing import Optional, Dict, Any
from pathlib import Path


class ClockifyConfig:
    """Manages Clockify configuration storage and retrieval."""
    
    def __init__(self, config_dir: Optional[str] = None):
        if config_dir:
            self.config_dir = Path(config_dir)
        else:
            self.config_dir = Path.home() / ".config" / "clockify"
        
        self.config_file = self.config_dir / "config.json"
        self.state_file = self.config_dir / "state.json"
        
        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        self._config = self._load_config()
        self._state = self._load_state()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {}
    
    def _load_state(self) -> Dict[str, Any]:
        """Load state from file."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {}
    
    def save_config(self) -> None:
        """Save configuration to file."""
        with open(self.config_file, 'w') as f:
            json.dump(self._config, f, indent=2)
    
    def save_state(self) -> None:
        """Save state to file."""
        with open(self.state_file, 'w') as f:
            json.dump(self._state, f, indent=2)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        return self._config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set configuration value."""
        self._config[key] = value
        self.save_config()
    
    def get_state(self, key: str, default: Any = None) -> Any:
        """Get state value."""
        return self._state.get(key, default)
    
    def set_state(self, key: str, value: Any) -> None:
        """Set state value."""
        self._state[key] = value
        self.save_state()
    
    @property
    def token(self) -> Optional[str]:
        """Get Clockify API token."""
        return self.get("token")
    
    @token.setter
    def token(self, value: str) -> None:
        """Set Clockify API token."""
        self.set("token", value)
    
    @property
    def workspace_id(self) -> Optional[str]:
        """Get workspace ID."""
        return self.get("workspace_id")
    
    @workspace_id.setter
    def workspace_id(self, value: str) -> None:
        """Set workspace ID."""
        self.set("workspace_id", value)
    
    @property
    def project_id(self) -> Optional[str]:
        """Get project ID."""
        return self.get("project_id")
    
    @project_id.setter
    def project_id(self, value: str) -> None:
        """Set project ID."""
        self.set("project_id", value)
    
    @property
    def task_name(self) -> Optional[str]:
        """Get task name."""
        return self.get("task_name")
    
    @task_name.setter
    def task_name(self, value: str) -> None:
        """Set task name."""
        self.set("task_name", value)
    
    @property
    def task_id(self) -> Optional[str]:
        """Get formal task ID."""
        return self.get("task_id")
    
    @task_id.setter
    def task_id(self, value: Optional[str]) -> None:
        """Set formal task ID."""
        if value:
            self.set("task_id", value)
        else:
            self._config.pop("task_id", None)
            self.save_config()
    
    @property
    def description(self) -> Optional[str]:
        """Get time entry description."""
        return self.get("description")
    
    @description.setter
    def description(self, value: str) -> None:
        """Set time entry description."""
        self.set("description", value)
    
    @property
    def current_entry_id(self) -> Optional[str]:
        """Get current time entry ID from state."""
        return self.get_state("current_entry_id")
    
    @current_entry_id.setter
    def current_entry_id(self, value: Optional[str]) -> None:
        """Set current time entry ID in state."""
        if value is None:
            self._state.pop("current_entry_id", None)
        else:
            self.set_state("current_entry_id", value)
    
    def is_configured(self) -> bool:
        """Check if basic configuration is present."""
        return bool(self.token and self.workspace_id)
    
    def get_missing_config(self) -> list[str]:
        """Get list of missing required configuration keys."""
        missing = []
        if not self.token:
            missing.append("token")
        if not self.workspace_id:
            missing.append("workspace_id")
        return missing