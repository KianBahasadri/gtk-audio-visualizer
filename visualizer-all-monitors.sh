#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

height="${VISUALIZER_HEIGHT:-180}"
visualizer_width="${VISUALIZER_WIDTH:-1120}"
max_windows="${VISUALIZER_MAX_WINDOWS:-1}"
declare -a pids=()

cleanup() {
  for pid in "${pids[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
}
trap cleanup INT TERM EXIT

index=0
while read -r line; do
  if [[ ! "$line" =~ ([0-9]+)\/[0-9]+x([0-9]+)\/[0-9]+([-+][0-9]+)([-+][0-9]+) ]]; then
    continue
  fi

  monitor_width="${BASH_REMATCH[1]}"
  monitor_height="${BASH_REMATCH[2]}"
  x="${BASH_REMATCH[3]}"
  y="${BASH_REMATCH[4]}"
  width="$visualizer_width"
  if [ "$width" -gt "$monitor_width" ]; then
    width="$monitor_width"
  fi
  window_x="$((x + (monitor_width - width) / 2))"
  window_y="$((y + (monitor_height - height) / 2))"
  title="Visualizer Monitor $index"

  GDK_BACKEND=x11 python3 visualizer.py --title "$title" --width "$width" --height "$height" &
  pids+=("$!")
  if ! python3 move_x11_window.py --title "$title" --x "$window_x" --y "$window_y" --width "$width" --height "$height"; then
    echo "Could not position $title" >&2
  fi
  index="$((index + 1))"
  if [ "$max_windows" != "all" ] && [ "$index" -ge "$max_windows" ]; then
    break
  fi
done < <(xrandr --listmonitors | sed '1d')

if [ "${#pids[@]}" -eq 0 ]; then
  echo "No monitors found from xrandr" >&2
  exit 1
fi

wait
