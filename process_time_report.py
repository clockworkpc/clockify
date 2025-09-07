#!/usr/bin/env python3
"""
Process Clockify time report CSV and create formal tasks with time entries.
"""
import csv
import sys
from datetime import datetime
from typing import Dict, Set
from collections import defaultdict

from modules.config import ClockifyConfig
from modules.api_client import ClockifyAPI, ClockifyAPIError


class TimeReportProcessor:
    """Processes Clockify CSV time reports and creates formal tasks."""
    
    def __init__(self, config: ClockifyConfig):
        self.config = config
        self.api = ClockifyAPI(config.token, config.workspace_id)
        
        # Cache for efficiency
        self.projects_cache = {}
        self.tasks_cache = {}
        self.created_tasks = {}  # Track newly created tasks
        
        # Statistics
        self.stats = {
            'processed_entries': 0,
            'created_tasks': 0,
            'created_time_entries': 0,
            'skipped_entries': 0,
            'errors': 0
        }
    
    def load_projects_cache(self):
        """Load and cache all projects."""
        print("Loading projects...")
        try:
            projects = self.api.get_projects()
            for project in projects:
                self.projects_cache[project["name"]] = project
            print(f"Loaded {len(projects)} projects")
        except ClockifyAPIError as e:
            print(f"Error loading projects: {e}")
            sys.exit(1)
    
    def get_or_create_task(self, project_name: str, task_name: str) -> str:
        """Get existing task or create new one. Returns task ID."""
        if project_name not in self.projects_cache:
            print(f"Warning: Project '{project_name}' not found, skipping")
            return None
        
        project = self.projects_cache[project_name]
        project_id = project["id"]
        
        # Check cache first
        cache_key = f"{project_id}:{task_name}"
        if cache_key in self.tasks_cache:
            return self.tasks_cache[cache_key]
        
        # Check if task exists
        existing_task = self.api.find_task_by_name(project_id, task_name)
        if existing_task:
            task_id = existing_task["id"]
            self.tasks_cache[cache_key] = task_id
            return task_id
        
        # Create new task
        try:
            print(f"Creating task '{task_name}' in project '{project_name}'...")
            new_task = self.api.create_task(project_id, task_name)
            task_id = new_task["id"]
            
            self.tasks_cache[cache_key] = task_id
            self.created_tasks[cache_key] = task_name
            self.stats['created_tasks'] += 1
            
            return task_id
            
        except ClockifyAPIError as e:
            print(f"Error creating task '{task_name}': {e}")
            self.stats['errors'] += 1
            return None
    
    def parse_datetime(self, date_str: str, time_str: str) -> str:
        """Parse date and time strings into ISO format."""
        try:
            # Parse date (MM/DD/YYYY) and time (HH:MM:SS)
            dt_str = f"{date_str} {time_str}"
            dt = datetime.strptime(dt_str, "%m/%d/%Y %H:%M:%S")
            return dt.isoformat() + "Z"
        except ValueError as e:
            print(f"Error parsing datetime '{date_str} {time_str}': {e}")
            return None
    
    def process_csv_entry(self, row: Dict[str, str]) -> bool:
        """Process a single CSV row. Returns True if successful."""
        project_name = row.get("Project", "").strip()
        task_name = row.get("Description", "").strip()  # Description is the task name
        start_date = row.get("Start Date", "").strip()
        start_time = row.get("Start Time", "").strip()
        end_date = row.get("End Date", "").strip()
        end_time = row.get("End Time", "").strip()
        duration_decimal = row.get("Duration (decimal)", "").strip()
        
        # Skip if essential data is missing
        if not all([project_name, task_name, start_date, start_time, end_date, end_time]):
            print(f"Skipping entry with missing data: {row}")
            self.stats['skipped_entries'] += 1
            return False
        
        # Skip if duration is 0
        try:
            if float(duration_decimal) <= 0:
                print(f"Skipping entry with zero duration: {task_name}")
                self.stats['skipped_entries'] += 1
                return False
        except (ValueError, TypeError):
            print(f"Invalid duration value: {duration_decimal}")
            self.stats['skipped_entries'] += 1
            return False
        
        # Get or create task
        task_id = self.get_or_create_task(project_name, task_name)
        if not task_id:
            self.stats['errors'] += 1
            return False
        
        # Parse start and end times
        start_iso = self.parse_datetime(start_date, start_time)
        end_iso = self.parse_datetime(end_date, end_time)
        
        if not start_iso or not end_iso:
            self.stats['errors'] += 1
            return False
        
        # Create time entry
        try:
            project = self.projects_cache[project_name]
            
            print(f"Creating time entry: {task_name} ({duration_decimal}h)")
            
            self.api.create_time_entry(
                project_id=project["id"],
                task_id=task_id,
                description=task_name,
                start_time=start_iso,
                end_time=end_iso
            )
            
            self.stats['created_time_entries'] += 1
            return True
            
        except ClockifyAPIError as e:
            print(f"Error creating time entry for '{task_name}': {e}")
            self.stats['errors'] += 1
            return False
    
    def process_csv_file(self, csv_file_path: str):
        """Process the entire CSV file."""
        print(f"Processing CSV file: {csv_file_path}")
        
        # Load projects cache
        self.load_projects_cache()
        
        try:
            with open(csv_file_path, 'r', encoding='utf-8') as file:
                # Detect if file uses comma or semicolon as delimiter
                sample = file.read(1024)
                file.seek(0)
                
                delimiter = ',' if sample.count(',') > sample.count(';') else ';'
                
                reader = csv.DictReader(file, delimiter=delimiter)
                
                print(f"Found columns: {reader.fieldnames}")
                print()
                
                for row_num, row in enumerate(reader, start=2):  # Start at 2 since row 1 is headers
                    self.stats['processed_entries'] += 1
                    
                    print(f"Processing row {row_num}: {row.get('Description', 'Unknown')} - {row.get('Project', 'Unknown')}")
                    
                    success = self.process_csv_entry(row)
                    if not success:
                        print(f"Failed to process row {row_num}")
                    
                    print()  # Empty line for readability
        
        except FileNotFoundError:
            print(f"Error: CSV file not found: {csv_file_path}")
            sys.exit(1)
        except Exception as e:
            print(f"Error reading CSV file: {e}")
            sys.exit(1)
    
    def print_summary(self):
        """Print processing summary."""
        print("=" * 50)
        print("PROCESSING SUMMARY")
        print("=" * 50)
        print(f"Total entries processed: {self.stats['processed_entries']}")
        print(f"Tasks created: {self.stats['created_tasks']}")
        print(f"Time entries created: {self.stats['created_time_entries']}")
        print(f"Entries skipped: {self.stats['skipped_entries']}")
        print(f"Errors encountered: {self.stats['errors']}")
        print()
        
        if self.created_tasks:
            print("NEWLY CREATED TASKS:")
            print("-" * 30)
            for cache_key, task_name in self.created_tasks.items():
                project_id, _ = cache_key.split(":", 1)
                # Find project name
                project_name = "Unknown"
                for name, project in self.projects_cache.items():
                    if project["id"] == project_id:
                        project_name = name
                        break
                print(f"  - {task_name} (in {project_name})")


def main():
    """Main function."""
    if len(sys.argv) != 2:
        print("Usage: python process_time_report.py <csv_file_path>")
        print("Example: python process_time_report.py Clockify_Time_Report_Detailed_01_01_2025-12_31_2025.csv")
        sys.exit(1)
    
    csv_file_path = sys.argv[1]
    
    # Load configuration
    config = ClockifyConfig()
    
    # Check required configuration
    missing = config.get_missing_config()
    if missing:
        print("Error: Missing required configuration:")
        for item in missing:
            print(f"  - {item}")
        print("\nRun 'clockify info' to configure your API token and workspace.")
        sys.exit(1)
    
    # Process the CSV file
    processor = TimeReportProcessor(config)
    processor.process_csv_file(csv_file_path)
    processor.print_summary()


if __name__ == "__main__":
    main()