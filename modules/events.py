"""
Pomodoro event logging and extraction from journalctl.
"""
import subprocess
import json
import re
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path


class PomodoroEventExtractor:
    """Extracts pomodoro events from system journal."""

    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize event extractor.

        Args:
            config_dir: Optional config directory path. Defaults to ~/.config/clockify
        """
        if config_dir:
            self.config_dir = config_dir
        else:
            self.config_dir = Path.home() / ".config" / "clockify"

        self.events_file = self.config_dir / "events.json"
        self.events = []

        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def extract_events(self, since: str = "1 day ago") -> List[Dict[str, Any]]:
        """Extract pomodoro events from journalctl.

        Args:
            since: Time period to search (e.g., "1 day ago", "1 week ago", "today")

        Returns:
            List of event dictionaries
        """
        cmd = [
            "journalctl",
            "--user",
            "--since", since,
            "--output=short-iso"
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            self._parse_journal(result.stdout)
            return self.events
        except subprocess.CalledProcessError as e:
            print(f"Error running journalctl: {e}")
            return []

    def _parse_journal(self, journal_output: str) -> None:
        """Parse journal output and extract pomodoro events."""
        lines = journal_output.split('\n')
        current_event = {}

        for line in lines:
            # Skip empty lines
            if not line.strip():
                continue

            # Match timestamp and process lines
            timestamp_match = re.match(
                r'^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2})\s+\S+\s+gnome-pomodoro\[\d+\]:\s+(.+)$',
                line
            )
            if not timestamp_match:
                continue

            timestamp_str = timestamp_match.group(1)
            message = timestamp_match.group(2)

            # Parse timestamp
            try:
                # Parse ISO format with timezone
                timestamp = datetime.fromisoformat(timestamp_str)
                # Convert to naive datetime (remove timezone)
                timestamp = timestamp.replace(tzinfo=None)
            except ValueError:
                continue

            # Check for command execution (DEBUG: Raw argv=...)
            if "DEBUG: Raw argv=" in message:
                # Save previous event if it exists
                if current_event:
                    self._add_event(current_event)

                # Start new event
                current_event = {
                    "timestamp": timestamp.isoformat(),
                    "date": timestamp.strftime("%Y-%m-%d"),
                    "time": timestamp.strftime("%H:%M:%S"),
                }

            # Extract command type
            elif "DEBUG: Command=" in message and current_event:
                cmd_match = re.search(r"Command=(\w+)", message)
                if cmd_match:
                    current_event["event_type"] = cmd_match.group(1)

            # Extract description from "Starting time entry:" line
            elif message.startswith("Starting time entry:") and current_event:
                desc_match = re.search(r"Starting time entry:\s+(.+?)(?:\s+\(Task:.+\))?$", message)
                if desc_match:
                    current_event["description"] = desc_match.group(1).strip()

            # Extract description detail
            elif "description:" in message and current_event:
                desc_match = re.search(r"description:\s+(.+)$", message)
                if desc_match:
                    current_event["description"] = desc_match.group(1).strip()

            # Extract project ID
            elif "projectId:" in message and current_event:
                proj_match = re.search(r"projectId:\s+(\S+)$", message)
                if proj_match:
                    current_event["project_id"] = proj_match.group(1).strip()

            # Extract task ID
            elif "taskId:" in message and current_event:
                task_match = re.search(r"taskId:\s+(\S+)$", message)
                if task_match:
                    current_event["task_id"] = task_match.group(1).strip()

            # Extract entry ID (started)
            elif "Time entry started successfully" in message and current_event:
                entry_match = re.search(r"ID:\s+(\S+)\)", message)
                if entry_match:
                    current_event["entry_id"] = entry_match.group(1).strip()

            # Extract entry ID (stopped)
            elif "Time entry stopped successfully" in message and current_event:
                entry_match = re.search(r"ID:\s+(\S+)\)", message)
                if entry_match:
                    current_event["entry_id"] = entry_match.group(1).strip()

        # Add final event
        if current_event:
            self._add_event(current_event)

    def _add_event(self, event: Dict[str, Any]) -> None:
        """Add event to list if it has required fields."""
        if "event_type" in event and "timestamp" in event:
            self.events.append(event)

    def save_to_file(self, filename: Optional[str] = None, merge: bool = True) -> None:
        """Save events to JSON file.

        Args:
            filename: Path to output JSON file (defaults to ~/.config/clockify/events.json)
            merge: If True, merge with existing events and deduplicate
        """
        if filename is None:
            filename = str(self.events_file)

        events_to_save = self.events

        if merge and os.path.exists(filename):
            # Load existing events
            try:
                with open(filename, 'r') as f:
                    existing_events = json.load(f)
            except (json.JSONDecodeError, IOError):
                existing_events = []

            # Merge events and deduplicate by timestamp
            all_events = existing_events + self.events
            seen_timestamps = set()
            unique_events = []

            for event in all_events:
                timestamp = event.get("timestamp")
                if timestamp and timestamp not in seen_timestamps:
                    seen_timestamps.add(timestamp)
                    unique_events.append(event)

            # Sort by timestamp
            unique_events.sort(key=lambda e: e.get("timestamp", ""))
            events_to_save = unique_events

        with open(filename, 'w') as f:
            json.dump(events_to_save, f, indent=2)

    def get_saved_events(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get events from saved file.

        Args:
            limit: Optional limit on number of events to return

        Returns:
            List of events (most recent first)
        """
        if not self.events_file.exists():
            return []

        try:
            with open(self.events_file, 'r') as f:
                events = json.load(f)
            events.reverse()  # Most recent first

            if limit:
                return events[:limit]
            return events
        except (json.JSONDecodeError, IOError):
            return []

    def clear_events(self) -> None:
        """Clear all logged events from file."""
        if self.events_file.exists():
            with open(self.events_file, 'w') as f:
                json.dump([], f)
