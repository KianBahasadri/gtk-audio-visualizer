#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

height="${VISUALIZER_HEIGHT:-180}"
visualizer_width="${VISUALIZER_WIDTH:-1120}"

cleanup() {
  if [ -n "${pid:-}" ]; then
    kill "$pid" 2>/dev/null || true
  fi
}
trap cleanup INT TERM EXIT

index=0
windows=""

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
  segment_x="$((x + (monitor_width - width) / 2))"
  segment_y="$((y + (monitor_height - height) / 2))"

  segment="${segment_x},${segment_y},${width},${height}"
  if [ -n "$windows" ]; then
    windows="${windows};${segment}"
  else
    windows="$segment"
  fi

  index="$((index + 1))"
done < <(xrandr --listmonitors | sed '1d')

if [ "$index" -eq 0 ]; then
  echo "No monitors found from xrandr" >&2
  exit 1
fi

title="Visualizer Desktop Underlay"
GDK_BACKEND=x11 python3 visualizer.py --title "$title" --windows "$windows" &
pid="$!"
IFS=";" read -r -a window_array <<< "$windows"
for index in "${!window_array[@]}"; do
  IFS="," read -r window_x window_y width height <<< "${window_array[$index]}"
  window_title="$title"
  if [ "${#window_array[@]}" -gt 1 ]; then
    window_title="$title $index"
  fi
  if ! python3 move_x11_window.py --title "$window_title" --x "$window_x" --y "$window_y" --width "$width" --height "$height"; then
    echo "Could not position $window_title" >&2
  fi
done

wait
