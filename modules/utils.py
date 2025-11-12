"""
Utility functions for Clockify CLI.
"""
import subprocess
import tempfile
import os
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


def prettify_markdown_table(table_text: str) -> str:
    """Prettify a markdown table by aligning columns evenly.

    Args:
        table_text: Markdown text containing a table

    Returns:
        Prettified markdown text with aligned columns
    """
    lines = table_text.strip().split('\n')

    # Find table lines (lines containing |)
    table_lines = []
    non_table_lines_before = []
    non_table_lines_after = []
    in_table = False
    table_ended = False

    for line in lines:
        if '|' in line:
            in_table = True
            table_lines.append(line)
        elif in_table and not table_ended:
            table_ended = True
            non_table_lines_after.append(line)
        elif table_ended:
            non_table_lines_after.append(line)
        else:
            non_table_lines_before.append(line)

    if not table_lines:
        return table_text

    # Parse table rows
    rows = []
    separator_idx = None
    for idx, line in enumerate(table_lines):
        # Split by | and clean up
        cells = [cell.strip() for cell in line.split('|')]
        # Remove empty first/last cells (from leading/trailing |)
        if cells and not cells[0]:
            cells = cells[1:]
        if cells and not cells[-1]:
            cells = cells[:-1]

        # Check if this is a separator line (contains ---)
        if cells and all('---' in cell or '--' in cell for cell in cells):
            separator_idx = idx

        rows.append(cells)

    if not rows:
        return table_text

    # Calculate max width for each column
    num_cols = max(len(row) for row in rows)
    col_widths = [0] * num_cols

    for row in rows:
        for i, cell in enumerate(row):
            if i < num_cols:
                col_widths[i] = max(col_widths[i], len(cell))

    # Format the table
    formatted_rows = []
    for idx, row in enumerate(rows):
        if idx == separator_idx:
            # Format separator row
            formatted_cells = []
            for i, cell in enumerate(row):
                width = col_widths[i] if i < len(col_widths) else len(cell)
                # Keep the dashes, pad to width
                if ':' in cell:
                    # Alignment indicators
                    formatted_cells.append(cell.ljust(width, '-'))
                else:
                    formatted_cells.append('-' * width)
            formatted_rows.append('| ' + ' | '.join(formatted_cells) + ' |')
        else:
            # Format data row
            formatted_cells = []
            for i in range(num_cols):
                cell = row[i] if i < len(row) else ''
                width = col_widths[i]
                formatted_cells.append(cell.ljust(width))
            formatted_rows.append('| ' + ' | '.join(formatted_cells) + ' |')

    # Reconstruct the full text
    result_lines = non_table_lines_before + formatted_rows + non_table_lines_after
    return '\n'.join(result_lines)


def display_markdown(content: str, language: str = "markdown", prettify: bool = True) -> None:
    """Display content using bat/batcat if available, otherwise print normally.

    Args:
        content: The markdown or other formatted content to display
        language: The language/syntax highlighting to use (default: markdown)
        prettify: Whether to prettify markdown tables (default: True)
    """
    # Prettify markdown tables if requested
    if prettify and language == "markdown":
        content = prettify_markdown_table(content)

    # Try batcat first (Debian/Ubuntu package name), then bat
    bat_cmd = None
    for cmd in ['batcat', 'bat']:
        try:
            result = subprocess.run([cmd, '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                bat_cmd = cmd
                break
        except FileNotFoundError:
            continue

    if bat_cmd:
        # Use bat to display with syntax highlighting
        try:
            # Create a temporary file with the content
            with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
                f.write(content)
                temp_file = f.name

            # Display using bat with markdown syntax highlighting
            subprocess.run([
                bat_cmd,
                '--style=plain',
                '--language', language,
                '--paging=never',
                temp_file
            ], check=False)

            # Clean up temp file
            os.unlink(temp_file)
        except Exception:
            # Fall back to regular print if bat fails
            print(content)
    else:
        # bat not available, use regular print
        print(content)


def get_user_selection(items: list, prompt: str = "Select an item", current_item: str = None, use_bat: bool = True) -> Optional[tuple]:
    """Interactive user selection from a list of items.

    Args:
        items: List of items to select from
        prompt: Prompt message to display
        current_item: Currently selected item (will be marked)
        use_bat: Whether to use bat for display (default: True)

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

    # Build formatted menu
    if use_bat:
        # Build markdown list for bat
        menu_md = f"## {prompt}\n\n"
        for i, item in enumerate(items, 1):
            marker = " ✓ **(current)**" if current_item and item == current_item else ""
            menu_md += f"{i:2d}. {item}{marker}\n"

        display_markdown(menu_md)
    else:
        # Traditional plain text display
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
