#!/usr/bin/env python3
"""
Extract pomodoro events from journalctl.
Parses gnome-pomodoro logs and outputs events in JSON format.
"""
import subprocess
import json
import re
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
import argparse


class PomodoroEventExtractor:
    """Extracts pomodoro events from system journal."""

    def __init__(self):
        self.events = []
        self.current_event = {}

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
            print(f"Error running journalctl: {e}", file=sys.stderr)
            return []

    def _parse_journal(self, journal_output: str) -> None:
        """Parse journal output and extract pomodoro events."""
        lines = journal_output.split('\n')
        current_timestamp = None
        current_event = {}

        for line in lines:
            # Skip empty lines
            if not line.strip():
                continue

            # Match timestamp and process lines
            timestamp_match = re.match(r'^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2})\s+\S+\s+gnome-pomodoro\[\d+\]:\s+(.+)$', line)
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
                current_timestamp = timestamp

            # Extract command type
            elif "DEBUG: Command=" in message and current_event:
                cmd_match = re.search(r"Command=(\w+)", message)
                if cmd_match:
                    current_event["event_type"] = cmd_match.group(1)

            # Extract description
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

            # Extract entry ID
            elif "Time entry started successfully" in message and current_event:
                entry_match = re.search(r"ID:\s+(\S+)\)", message)
                if entry_match:
                    current_event["entry_id"] = entry_match.group(1).strip()

            # Extract stopped entry ID
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

    def save_to_file(self, filename: str, merge: bool = True) -> None:
        """Save events to JSON file.

        Args:
            filename: Path to output JSON file
            merge: If True, merge with existing events and deduplicate
        """
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


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Extract pomodoro events from journalctl"
    )
    parser.add_argument(
        "--since",
        default="1 day ago",
        help="Time period to extract (e.g., '1 day ago', 'today', '1 week ago')"
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output JSON file path (default: ~/.config/clockify/events.json)"
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty print JSON to stdout"
    )

    args = parser.parse_args()

    extractor = PomodoroEventExtractor()
    events = extractor.extract_events(since=args.since)

    if args.pretty:
        print(json.dumps(events, indent=2))
    elif args.output:
        extractor.save_to_file(args.output)
        print(f"Saved {len(events)} events to {args.output}")
    else:
        # Default: save to ~/.config/clockify/events.json
        import os
        config_dir = os.path.expanduser("~/.config/clockify")
        os.makedirs(config_dir, exist_ok=True)
        output_file = os.path.join(config_dir, "events.json")
        extractor.save_to_file(output_file)
        print(f"Saved {len(events)} events to {output_file}")


if __name__ == "__main__":
    import sys
    main()
