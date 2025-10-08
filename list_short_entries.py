#!/usr/bin/env python3
"""
List or delete Clockify time entries under 10 seconds.

Usage:
  ./list_short_entries.py              # List all short entries
  ./list_short_entries.py --delete     # Delete with confirmation
  ./list_short_entries.py --delete -y  # Delete without confirmation
"""
import argparse
from datetime import datetime
from modules.config import ClockifyConfig
from modules.api_client import ClockifyAPI, ClockifyAPIError


def parse_iso_datetime(iso_string):
    """Parse ISO 8601 datetime string."""
    if iso_string.endswith('Z'):
        iso_string = iso_string[:-1] + '+00:00'
    return datetime.fromisoformat(iso_string)


def calculate_duration_seconds(start_str, end_str):
    """Calculate duration in seconds between start and end times."""
    if not end_str:
        return None  # Entry is still in progress

    start = parse_iso_datetime(start_str)
    end = parse_iso_datetime(end_str)
    return (end - start).total_seconds()


def get_short_entries(api, limit=200):
    """Fetch and return all time entries under 10 seconds."""
    print("Fetching time entries...")
    try:
        entries = api.get_time_entries(limit=limit)
    except ClockifyAPIError as e:
        print(f"Error fetching time entries: {e}")
        return []

    # Filter entries under 10 seconds
    short_entries = []
    for entry in entries:
        time_interval = entry.get('timeInterval', {})
        start = time_interval.get('start')
        end = time_interval.get('end')

        if start and end:
            duration = calculate_duration_seconds(start, end)
            if duration is not None and duration < 10:
                short_entries.append({
                    'id': entry.get('id'),
                    'description': entry.get('description', '(no description)'),
                    'duration': duration,
                    'start': start,
                    'end': end,
                    'project': entry.get('projectId')
                })

    # Sort by duration
    short_entries.sort(key=lambda x: x['duration'])
    return short_entries


def display_entries(short_entries):
    """Display short entries in a formatted table."""
    if not short_entries:
        print("\nNo time entries under 10 seconds found.")
        return

    print(f"\nFound {len(short_entries)} time entries under 10 seconds:\n")
    print(f"{'Duration':<12} {'Description':<40} {'Start Time':<25}")
    print("-" * 80)

    for entry in short_entries:
        duration_str = f"{entry['duration']:.2f}s"
        desc = entry['description'][:37] + '...' if len(entry['description']) > 40 else entry['description']
        start_time = entry['start'][:19].replace('T', ' ')
        print(f"{duration_str:<12} {desc:<40} {start_time:<25}")


def delete_short_entries(api, short_entries, skip_confirm=False):
    """Delete all short entries with confirmation."""
    if not short_entries:
        print("\nNo time entries under 10 seconds found to delete.")
        return

    print(f"\nFound {len(short_entries)} time entries under 10 seconds to delete:\n")
    display_entries(short_entries)

    if not skip_confirm:
        print(f"\nAre you sure you want to delete these {len(short_entries)} entries? (yes/no): ", end='')
        confirmation = input().strip().lower()
        if confirmation not in ['yes', 'y']:
            print("Deletion cancelled.")
            return

    print("\nDeleting entries...")
    deleted = 0
    failed = 0

    for entry in short_entries:
        try:
            if api.delete_time_entry(entry['id']):
                deleted += 1
                print(f"✓ Deleted: {entry['description'][:50]} ({entry['duration']:.2f}s)")
            else:
                failed += 1
                print(f"✗ Failed to delete: {entry['description'][:50]}")
        except ClockifyAPIError as e:
            failed += 1
            print(f"✗ Error deleting {entry['description'][:50]}: {e}")

    print(f"\nDeleted: {deleted}, Failed: {failed}")


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="List or delete Clockify time entries under 10 seconds"
    )
    parser.add_argument(
        '--delete',
        action='store_true',
        help='Delete short entries (requires confirmation)'
    )
    parser.add_argument(
        '--yes', '-y',
        action='store_true',
        help='Skip confirmation prompt when deleting'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=200,
        help='Number of entries to fetch (default: 200)'
    )
    args = parser.parse_args()

    # Load configuration
    config = ClockifyConfig()

    if not config.is_configured():
        missing = config.get_missing_config()
        print("Error: Missing required configuration:")
        for item in missing:
            print(f"  - {item}")
        return

    # Initialize API client
    try:
        api = ClockifyAPI(config.token, config.workspace_id)
    except ClockifyAPIError as e:
        print(f"Error initializing API: {e}")
        return

    # Get short entries
    short_entries = get_short_entries(api, args.limit)

    # Either delete or display
    if args.delete:
        delete_short_entries(api, short_entries, skip_confirm=args.yes)
    else:
        display_entries(short_entries)


if __name__ == "__main__":
    main()
