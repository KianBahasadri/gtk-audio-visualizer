#!/usr/bin/env bash
set -euo pipefail

uuid="audio-visualizer-wallpaper@local"

if ! gnome-extensions info "$uuid" >/dev/null; then
  echo "GNOME Shell does not see $uuid yet."
  echo "On Wayland, log out and back in, then run this again."
  echo "On X11, press Alt+F2, type r, press Enter, then run this again."
  exit 1
fi

gnome-extensions enable "$uuid"
gnome-extensions info "$uuid"
