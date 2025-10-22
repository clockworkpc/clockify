"""
Utility functions for Clockify CLI.
"""
import subprocess
from datetime import datetime
from typing import Optional


def format_duration(start_time: str, end_time: Optional[str] = None) -> str:
    """Format duration between two ISO 8601 timestamps."""
    if not end_time:
        return "In Progress"
    
    try:
        start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        
        duration = end_dt - start_dt
        total_seconds = int(duration.total_seconds())
        
        if total_seconds <= 0:
            return "Unknown"
        
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        
        if hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
    
    except (ValueError, TypeError):
        return "Unknown"


def calculate_elapsed_minutes(start_time: str) -> float:
    """Calculate elapsed minutes from start time to now."""
    try:
        start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        now_dt = datetime.now(start_dt.tzinfo)
        
        duration = now_dt - start_dt
        return duration.total_seconds() / 60
    
    except (ValueError, TypeError):
        return 0.0


def show_notification(message: str) -> None:
    """Show desktop notification using xcowsay if available."""
    try:
        subprocess.run(['xcowsay', '--time=0.75', message], check=False, capture_output=True)
    except FileNotFoundError:
        # xcowsay not available, try notify-send
        try:
            subprocess.run(['notify-send', 'Clockify', message], check=False, capture_output=True)
        except FileNotFoundError:
            # No notification system available, just print
            print(f"Notification: {message}")


def get_user_selection(items: list, prompt: str = "Select an item", current_item: str = None) -> Optional[tuple]:
    """Interactive user selection from a list of items.

    Returns:
        Tuple of (index, user_input) where user_input is the text entered by the user
        when auto-selecting the "Enter new" option, or None otherwise.
        Returns None if selection is cancelled.
    """
    if not items:
        print("No items to select from.")
        return None

    # Auto-select if there's only one option
    if len(items) == 1:
        print(f"\nAuto-selected: {items[0]}")
        return (0, None)

    print(f"\n{prompt}:\n")

    for i, item in enumerate(items, 1):
        marker = " (current)" if current_item and item == current_item else ""
        print(f"{i:2d}. {item}{marker}")

    print()

    while True:
        try:
            selection = input(f"Select an item (1-{len(items)}): ").strip()

            if not selection:
                # If there's a current item, auto-select it
                if current_item and current_item in items:
                    index = items.index(current_item)
                    print(f"Auto-selecting current: {current_item}")
                    return (index, None)
                continue

            # Handle "None" input to select current item
            if selection.lower() == "none" and current_item:
                # Find the index of the current item
                try:
                    index = items.index(current_item)
                    print(f"Auto-selecting current: {current_item}")
                    return (index, None)
                except ValueError:
                    print(f"Current item '{current_item}' not found in list.")
                    continue

            index = int(selection) - 1

            if 0 <= index < len(items):
                return (index, None)
            else:
                print(f"Invalid selection. Please enter a number between 1 and {len(items)}.")

        except ValueError:
            # Check if user entered a descriptive string (> 5 chars)
            # and last item is an "Enter new" or "Create new" option
            if len(selection) > 5 and len(items) > 0:
                last_item = items[-1].lower()
                if "[enter new" in last_item or "[create new" in last_item:
                    # Auto-select the last option and pass the user's input
                    print(f"Auto-selecting: {items[-1]}")
                    print(f"Using: {selection}")
                    return (len(items) - 1, selection)

            print("Please enter a valid number.")
        except KeyboardInterrupt:
            print("\nSelection cancelled.")
            return None
