#!/usr/bin/env python3
"""
Migration script to convert bash clockifyrc to Python JSON format.
"""
import os
import json
import shlex
from pathlib import Path


def parse_bash_config(config_file: Path) -> dict:
    """Parse bash-style configuration file."""
    config = {}
    
    if not config_file.exists():
        print(f"Config file not found: {config_file}")
        return config
    
    with open(config_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            if '=' in line:
                key, value = line.split('=', 1)
                # Remove quotes if present
                value = shlex.split(value)[0] if value else ""
                
                # Map bash variable names to Python config keys
                key_mapping = {
                    'CLOCKIFY_TOKEN': 'token',
                    'CLOCKIFY_WORKSPACE_ID': 'workspace_id', 
                    'CLOCKIFY_PROJECT_ID': 'project_id',
                    'CLOCKIFY_TASK_NAME': 'task_name'
                }
                
                python_key = key_mapping.get(key, key.lower())
                config[python_key] = value
    
    return config


def migrate_config():
    """Migrate bash config to Python JSON format."""
    # Paths
    old_config_file = Path.home() / ".config" / "clockify" / "clockifyrc"
    new_config_dir = Path.home() / ".config" / "clockify"
    new_config_file = new_config_dir / "config.json"
    backup_file = new_config_dir / "clockifyrc.backup"
    
    print("Migrating Clockify configuration from bash to Python format...")
    print(f"Source: {old_config_file}")
    print(f"Target: {new_config_file}")
    
    # Check if old config exists
    if not old_config_file.exists():
        print("No existing bash configuration found.")
        return
    
    # Parse the bash config
    config = parse_bash_config(old_config_file)
    
    if not config:
        print("No configuration data found to migrate.")
        return
    
    print("\nFound configuration:")
    for key, value in config.items():
        # Don't print the full token for security
        if key == 'token' and value:
            print(f"  {key}: {value[:8]}...")
        else:
            print(f"  {key}: {value}")
    
    # Create new config directory if it doesn't exist
    new_config_dir.mkdir(parents=True, exist_ok=True)
    
    # Check if new config already exists
    if new_config_file.exists():
        response = input(f"\nPython config already exists at {new_config_file}. Overwrite? (y/N): ")
        if response.lower() != 'y':
            print("Migration cancelled.")
            return
    
    # Write new JSON config
    with open(new_config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"\nConfiguration migrated successfully to: {new_config_file}")
    
    # Create backup of old config
    if backup_file.exists():
        print(f"Backup already exists: {backup_file}")
    else:
        try:
            import shutil
            shutil.copy2(old_config_file, backup_file)
            print(f"Backup created: {backup_file}")
        except Exception as e:
            print(f"Warning: Could not create backup: {e}")
    
    print("\nMigration complete! You can now use the Python version:")
    print("  ./app.py info")


if __name__ == "__main__":
    migrate_config()