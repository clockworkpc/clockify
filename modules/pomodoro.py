"""
Pomodoro timer integration via D-Bus for Gnome Pomodoro.
"""
import subprocess
from typing import Optional


class PomodoroError(Exception):
    """Exception raised for Pomodoro integration errors."""
    pass


class PomodoroIntegration:
    """Integration with Gnome Pomodoro timer via D-Bus."""
    
    def __init__(self):
        self.dbus_dest = "org.gnome.Pomodoro"
        self.dbus_path = "/org/gnome/Pomodoro"
        self.dbus_interface = "org.gnome.Pomodoro"
    
    def _call_dbus(self, method: str, *args) -> str:
        """Make D-Bus call to Gnome Pomodoro."""
        cmd = [
            "gdbus", "call", "--session",
            "--dest", self.dbus_dest,
            "--object-path", self.dbus_path,
            "--method", f"{self.dbus_interface}.{method}"
        ]
        cmd.extend(str(arg) for arg in args)
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise PomodoroError(f"D-Bus call failed: {e.stderr}")
        except FileNotFoundError:
            raise PomodoroError("gdbus command not found. Is D-Bus installed?")
    
    def _get_property(self, property_name: str) -> str:
        """Get a property from Gnome Pomodoro."""
        cmd = [
            "gdbus", "call", "--session",
            "--dest", self.dbus_dest,
            "--object-path", self.dbus_path,
            "--method", "org.freedesktop.DBus.Properties.Get",
            self.dbus_interface, property_name
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise PomodoroError(f"Property get failed: {e.stderr}")
    
    def start(self) -> None:
        """Start a work session (Pomodoro)."""
        self._call_dbus("Start")
    
    def stop(self) -> None:
        """Stop the current session."""
        self._call_dbus("Stop")
    
    def pause(self) -> None:
        """Pause the current session."""
        self._call_dbus("Pause")
    
    def resume(self) -> None:
        """Resume the current session."""
        self._call_dbus("Resume")
    
    def skip(self) -> None:
        """Skip to next session (e.g., from work to break)."""
        self._call_dbus("Skip")
    
    def set_short_break(self) -> None:
        """Switch immediately to a short break."""
        self._call_dbus("SetState", "'short-break'", "0.0")
    
    def set_work_duration(self, minutes: int = 20) -> None:
        """Set work (pomodoro) length in minutes."""
        seconds = minutes * 60
        self._call_dbus("SetStateDuration", "'pomodoro'", f"{seconds}.0")
    
    def get_current_state(self) -> Optional[str]:
        """Get current pomodoro state."""
        try:
            result = self._get_property("State")
            # Extract state from D-Bus variant format like "(<'pomodoro'>,)"
            if "'" in result:
                state = result.split("'")[1]
                return state
            return None
        except PomodoroError:
            return None
    
    def is_running(self) -> bool:
        """Check if pomodoro timer is in work state."""
        state = self.get_current_state()
        return state == "pomodoro"
    
    def is_available(self) -> bool:
        """Check if Gnome Pomodoro is available."""
        try:
            self.get_current_state()
            return True
        except PomodoroError:
            return False
    
    def get_all_properties(self) -> str:
        """Get all properties from Gnome Pomodoro (for debugging)."""
        cmd = [
            "gdbus", "call", "--session",
            "--dest", self.dbus_dest,
            "--object-path", self.dbus_path,
            "--method", "org.freedesktop.DBus.Properties.GetAll",
            self.dbus_interface
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise PomodoroError(f"Get all properties failed: {e.stderr}")