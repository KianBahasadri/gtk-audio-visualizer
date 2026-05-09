#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
root=".."

title="Gemini Left Mask Probe"
monitor="${GEMINI_MASK_MONITOR:-1920x1080+0+0}"
window="${GEMINI_MASK_WINDOW:-400,450,1120,180}"
source_mask="${GEMINI_MASK_SOURCE:-$root/masks/left.png}"
mask="$root/.cache/wallpaper-probe/gemini-left-mask-crop.png"
preview="$root/.cache/wallpaper-probe/gemini-left-mask-crop-preview.png"

cleanup() {
  if [ -n "${pid:-}" ]; then
    kill "$pid" 2>/dev/null || true
  fi
}
trap cleanup INT TERM EXIT

python3 "$root/scripts/prepare_monitor_mask.py" \
  --input "$source_mask" \
  --monitor "$monitor" \
  --window "$window" \
  --out "$mask" \
  --wallpaper-crop "$root/.cache/wallpaper-probe/wallpaper-crop-2.png" \
  --debug-preview "$preview"

GDK_BACKEND=x11 ./mask_visualizer.py \
  --title "$title" \
  --windows "$window" \
  --mask "$mask" \
  --debug-mask-overlay &
pid="$!"

IFS="," read -r window_x window_y width height <<< "$window"
if ! python3 move_x11_window.py \
  --title "$title" \
  --x "$window_x" \
  --y "$window_y" \
  --width "$width" \
  --height "$height"; then
  echo "Could not position $title" >&2
fi

wait
