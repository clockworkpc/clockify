#!/bin/bash

# Save TASK_NAME variable from zenity --entry

TASK_NAME=$(zenity --entry --title="Clockify Task Name" --text="Enter the new task name:")

clockify --task-name "$TASK_NAME"
