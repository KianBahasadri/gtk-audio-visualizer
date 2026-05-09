#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
root=".."

opacity="${VISUALIZER_WALLPAPER_OVERLAY_OPACITY:-0.45}"
mode="${VISUALIZER_WALLPAPER_OVERLAY_MODE:-edges}"
title="Wallpaper Alignment Probe"

cleanup() {
  if [ -n "${pid:-}" ]; then
    kill "$pid" 2>/dev/null || true
  fi
}
trap cleanup INT TERM EXIT

probe_output="$(python3 "$root/scripts/wallpaper_probe.py" --out-dir "$root/.cache/wallpaper-probe")"
printf '%s\n' "$probe_output"

windows="$(printf '%s\n' "$probe_output" | awk -F': ' '/^visualizer_windows_arg:/ {print $2}')"
if [ "$mode" = "crop" ]; then
  overlays="$(printf '%s\n' "$probe_output" | awk -F': ' '/^overlay_arg:/ {print $2}')"
else
  overlays="$(printf '%s\n' "$probe_output" | awk -F': ' '/^edge_overlay_arg:/ {print $2}')"
  opacity="${VISUALIZER_WALLPAPER_OVERLAY_OPACITY:-0.9}"
fi

if [ -z "$windows" ] || [ -z "$overlays" ]; then
  echo "Could not read probe windows or overlays" >&2
  exit 1
fi

GDK_BACKEND=x11 ./mask_visualizer.py \
  --title "$title" \
  --windows "$windows" \
  --overlay-images "$overlays" \
  --overlay-opacity "$opacity" &
pid="$!"

IFS=";" read -r -a window_array <<< "$windows"
for index in "${!window_array[@]}"; do
  IFS="," read -r window_x window_y width height <<< "${window_array[$index]}"
  window_title="$title"
  if [ "${#window_array[@]}" -gt 1 ]; then
    window_title="$title $index"
  fi
  if ! python3 move_x11_window.py \
    --title "$window_title" \
    --x "$window_x" \
    --y "$window_y" \
    --width "$width" \
    --height "$height"; then
    echo "Could not position $window_title" >&2
  fi
done

wait
