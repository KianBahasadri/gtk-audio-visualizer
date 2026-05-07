#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

height="${VISUALIZER_HEIGHT:-220}"
declare -a pids=()

cleanup() {
  for pid in "${pids[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
}
trap cleanup INT TERM EXIT

index=0
while read -r line; do
  geometry="$(printf '%s\n' "$line" | grep -oE '[0-9]+/[0-9]+x[0-9]+/[0-9]+[-+][0-9]+[-+][0-9]+' | head -n 1)"
  [ -n "$geometry" ] || continue

  size="${geometry%%+*}"
  offsets="${geometry#*+}"
  width="${size%%/*}"
  monitor_height_part="${size#*x}"
  monitor_height="${monitor_height_part%%/*}"
  x="${offsets%%+*}"
  y="${offsets#*+}"
  window_y="$((y + monitor_height - height))"
  title="Visualizer Monitor $index"

  GDK_BACKEND=x11 python3 visualizer.py --title "$title" --width "$width" --height "$height" &
  pids+=("$!")
  python3 move_x11_window.py --title "$title" --x "$x" --y "$window_y" --width "$width" --height "$height"
  index="$((index + 1))"
done < <(xrandr --listmonitors | sed '1d')

if [ "${#pids[@]}" -eq 0 ]; then
  echo "No monitors found from xrandr" >&2
  exit 1
fi

wait
