#!/bin/python
"""
Clockify System Tray Application
Displays current Clockify timer status in the system tray.
"""
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('AppIndicator3', '0.1')
from gi.repository import Gtk, AppIndicator3, GLib
import subprocess
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add modules directory to path
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from modules.config import ClockifyConfig
from modules.api_client import ClockifyAPI, ClockifyAPIError


class ClockifyTray:
    """System tray application for Clockify timer."""

    def __init__(self):
        """Initialize the tray application."""
        # Load configuration
        try:
            self.config = ClockifyConfig()
            self.api = ClockifyAPI(self.config.token, self.config.workspace_id)
        except Exception as e:
            print(f"Error loading Clockify configuration: {e}")
            sys.exit(1)

        # Create indicator
        self.indicator = AppIndicator3.Indicator.new(
            "clockify-timer",
            "clockify",  # Use Clockify icon
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS
        )
        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)

        # Initial state
        self.current_entry = None
        self.elapsed_time = "00:00:00"
        self.is_tracking = False
        self.last_start_time = None
        self.last_description = None
        self.error_count = 0

        # Create menu
        self.menu = self.create_menu()
        self.indicator.set_menu(self.menu)

        # Update from API immediately and then every 30 seconds
        self.update_from_api()
        GLib.timeout_add_seconds(30, self.update_from_api)

        # Update display every second for live timer
        GLib.timeout_add_seconds(1, self.update_display)

    def create_menu(self):
        """Create the system tray menu."""
        menu = Gtk.Menu()

        # Timer status item (not clickable)
        self.status_item = Gtk.MenuItem(label="Loading...")
        self.status_item.set_sensitive(False)
        menu.append(self.status_item)

        # Separator
        menu.append(Gtk.SeparatorMenuItem())

        # Project/Task info
        self.project_item = Gtk.MenuItem(label="No project selected")
        self.project_item.set_sensitive(False)
        menu.append(self.project_item)

        self.task_item = Gtk.MenuItem(label="No task selected")
        self.task_item.set_sensitive(False)
        menu.append(self.task_item)

        # Separator
        menu.append(Gtk.SeparatorMenuItem())

        # Start/Stop button
        self.toggle_item = Gtk.MenuItem(label="Start Timer")
        self.toggle_item.connect("activate", self.toggle_timer)
        menu.append(self.toggle_item)

        # Open Clockify Web
        open_item = Gtk.MenuItem(label="Open Clockify Web")
        open_item.connect("activate", self.open_clockify_web)
        menu.append(open_item)

        # Separator
        menu.append(Gtk.SeparatorMenuItem())

        # Refresh
        refresh_item = Gtk.MenuItem(label="Refresh Now")
        refresh_item.connect("activate", lambda x: self.update_timer())
        menu.append(refresh_item)

        # Quit
        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", self.quit)
        menu.append(quit_item)

        menu.show_all()
        return menu

    def update_display(self):
        """Update the display every second (local calculation only)."""
        # If we're tracking and have a start time, update the elapsed display
        if self.last_start_time:
            now = datetime.now(self.last_start_time.tzinfo)
            elapsed = now - self.last_start_time

            hours, remainder = divmod(int(elapsed.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            self.elapsed_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

            # Update label
            self.indicator.set_label(f"{self.elapsed_time}", "")

        return True  # Continue updating

    def update_from_api(self):
        """Fetch current state from Clockify API."""
        try:
            # Get current time entry
            self.current_entry = self.api.get_current_time_entry()

            # Reset error count on successful fetch
            self.error_count = 0

            if self.current_entry:
                self.is_tracking = True

                # Cache start time for live updates
                start_time = datetime.fromisoformat(
                    self.current_entry['timeInterval']['start'].replace('Z', '+00:00')
                )
                self.last_start_time = start_time

                # Get and cache description
                description = self.current_entry.get('description', 'No description')
                self.last_description = description

                # Update tooltip
                self.indicator.set_title(f"Clockify: {description}")

                # Update menu items
                self.status_item.set_label(f"Tracking: {description}")
                self.toggle_item.set_label("⏸ Stop Timer")

                # Update project info
                project_name = self.get_project_name(self.current_entry.get('projectId'))
                if project_name:
                    self.project_item.set_label(f"Project: {project_name}")
                else:
                    self.project_item.set_label("No project")

                # Update task info
                task_id = self.current_entry.get('taskId')
                if task_id:
                    task_name = self.config.task_name or "Unknown task"
                    self.task_item.set_label(f"Task: {task_name}")
                else:
                    self.task_item.set_label("No task")

            else:
                self.is_tracking = False
                self.elapsed_time = "00:00:00"
                self.last_start_time = None

                # Update label and clear tooltip
                self.indicator.set_label("--:--:--", "")
                self.indicator.set_title("Clockify: Not tracking")

                # Update menu items
                self.status_item.set_label("Not tracking")
                self.toggle_item.set_label("▶ Start Timer")

                # Show current project/task from config
                if self.config.project_id:
                    project_name = self.get_project_name(self.config.project_id)
                    self.project_item.set_label(f"Project: {project_name or 'Unknown'}")
                else:
                    self.project_item.set_label("No project selected")

                if self.config.description:
                    self.task_item.set_label(f"Task: {self.config.description}")
                else:
                    self.task_item.set_label("No task selected")

        except Exception as e:
            # Network error - use cached state if available
            self.error_count += 1

            # Only log errors occasionally (every 10th error)
            if self.error_count % 10 == 1:
                print(f"Network error (count: {self.error_count}): Connection issue")

            # If we were tracking, update status to show offline
            # (timer continues via update_display())
            if self.last_start_time:
                self.status_item.set_label(f"Tracking: {self.last_description or 'Unknown'} (offline)")
            else:
                # No cached state, show offline
                self.status_item.set_label("Offline - check network")

        # Continue updating
        return True

    def get_project_name(self, project_id):
        """Get project name from ID."""
        if not project_id:
            return None

        try:
            projects = self.api.get_projects()
            for project in projects:
                if project['id'] == project_id:
                    return project['name']
        except:
            pass

        return None

    def toggle_timer(self, widget):
        """Start or stop the timer."""
        try:
            app_path = SCRIPT_DIR / "app.py"

            if self.is_tracking:
                # Stop timer
                subprocess.run(["/bin/python", str(app_path), "stop"],
                             capture_output=True, text=True)
            else:
                # Start timer
                subprocess.run(["/bin/python", str(app_path), "start"],
                             capture_output=True, text=True)

            # Update from API immediately after toggling
            GLib.timeout_add(500, self.update_from_api)

        except Exception as e:
            print(f"Error toggling timer: {e}")

    def open_clockify_web(self, widget):
        """Open Clockify web interface in browser."""
        subprocess.Popen(["xdg-open", "https://app.clockify.me/tracker"])

    def quit(self, widget):
        """Quit the application."""
        Gtk.main_quit()


def main():
    """Main entry point."""
    # Check if already running
    lock_file = Path.home() / ".config" / "clockify" / "tray.lock"
    lock_file.parent.mkdir(parents=True, exist_ok=True)

    if lock_file.exists():
        try:
            with open(lock_file) as f:
                pid = int(f.read().strip())

            # Check if process is still running
            try:
                os.kill(pid, 0)
                print("Clockify tray is already running")
                sys.exit(1)
            except OSError:
                # Process not running, remove stale lock file
                lock_file.unlink()
        except:
            pass

    # Create lock file
    with open(lock_file, 'w') as f:
        f.write(str(os.getpid()))

    try:
        # Start the tray application
        app = ClockifyTray()
        Gtk.main()
    finally:
        # Clean up lock file
        try:
            lock_file.unlink()
        except:
            pass


if __name__ == "__main__":
    main()
