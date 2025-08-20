#!/bin/bash

start_pomodoro() {
  # Start a work session (Pomodoro)
  gdbus call --session \
    --dest org.gnome.Pomodoro \
    --object-path /org/gnome/Pomodoro \
    --method org.gnome.Pomodoro.Start
}

stop_pomodoro() {
  # Stop the current session
  gdbus call --session \
    --dest org.gnome.Pomodoro \
    --object-path /org/gnome/Pomodoro \
    --method org.gnome.Pomodoro.Stop
}

pause_pomodoro() {
  # Pause the current session
  gdbus call --session \
    --dest org.gnome.Pomodoro \
    --object-path /org/gnome/Pomodoro \
    --method org.gnome.Pomodoro.Pause
}

resume_pomodoro() {
  # Resume the current session
  gdbus call --session \
    --dest org.gnome.Pomodoro \
    --object-path /org/gnome/Pomodoro \
    --method org.gnome.Pomodoro.Resume
}

skip_pomodoro() {
  # Skip to next session (e.g., from work to break)
  gdbus call --session \
    --dest org.gnome.Pomodoro \
    --object-path /org/gnome/Pomodoro \
    --method org.gnome.Pomodoro.Skip
}

short_break() {
  # Switch immediately to a short break
  gdbus call --session \
    --dest org.gnome.Pomodoro \
    --object-path /org/gnome/Pomodoro \
    --method org.gnome.Pomodoro.SetState 'short-break' 0.0
}

set_work_duration() {
  # Set work (pomodoro) length to 20 minutes
  gdbus call --session \
    --dest org.gnome.Pomodoro \
    --object-path /org/gnome/Pomodoro \
    --method org.gnome.Pomodoro.SetStateDuration 'pomodoro' 1200.0
}

get_all_properties() {
  # All properties
  gdbus call --session \
    --dest org.gnome.Pomodoro \
    --object-path /org/gnome/Pomodoro \
    --method org.freedesktop.DBus.Properties.GetAll org.gnome.Pomodoro
}

get_current_state() {
  # Single property (current state)
  gdbus call --session \
    --dest org.gnome.Pomodoro \
    --object-path /org/gnome/Pomodoro \
    --method org.freedesktop.DBus.Properties.Get \
    org.gnome.Pomodoro State
}
