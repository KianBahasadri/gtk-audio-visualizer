#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

title="${VISUALIZER_MASK_TITLE:-Manual Mask Visualizer}"
mask_dir="${VISUALIZER_MASK_DIR:-masks}"
threshold="${VISUALIZER_MASK_THRESHOLD:-128}"
blur="${VISUALIZER_MASK_BLUR:-1.0}"
debug="${VISUALIZER_MASK_DEBUG:-0}"

cleanup() {
  if [ -n "${pid:-}" ]; then
    kill "$pid" 2>/dev/null || true
  fi
}
trap cleanup INT TERM EXIT

probe_output="$(python3 wallpaper_probe.py)"
printf '%s\n' "$probe_output"

windows="$(printf '%s\n' "$probe_output" | awk -F': ' '/^visualizer_windows_arg:/ {print $2}')"
crops="$(printf '%s\n' "$probe_output" | awk -F': ' '/^overlay_arg:/ {print $2}')"

if [ -z "$windows" ]; then
  echo "Could not read visualizer windows from wallpaper probe" >&2
  exit 1
fi

IFS=";" read -r -a window_array <<< "$windows"
IFS=";" read -r -a crop_array <<< "$crops"

mask_paths=()
for index in "${!window_array[@]}"; do
  IFS="," read -r window_x window_y width height <<< "${window_array[$index]}"

  if [ "$window_x" -lt 1920 ]; then
    name="left"
    monitor="1920x1080+0+0"
  elif [ "$window_x" -lt 3840 ]; then
    name="center"
    monitor="1920x1080+1920+0"
  else
    name="right"
    monitor="1920x1080+3840+0"
  fi

  source_mask="$mask_dir/$name.png"
  if [ ! -f "$source_mask" ]; then
    echo "Missing manual mask: $source_mask" >&2
    echo "Expected masks: masks/left.png, masks/center.png, masks/right.png" >&2
    exit 1
  fi

  prepared_mask=".cache/manual-masks/$name-prepared.png"
  preview=".cache/manual-masks/$name-preview.png"
  args=(
    --input "$source_mask"
    --monitor "$monitor"
    --window "${window_array[$index]}"
    --threshold "$threshold"
    --blur "$blur"
    --out "$prepared_mask"
  )
  if [ "${crop_array[$index]:-}" != "" ]; then
    args+=(--wallpaper-crop "${crop_array[$index]}" --debug-preview "$preview")
  fi

  python3 prepare_monitor_mask.py "${args[@]}"
  mask_paths+=("$prepared_mask")
done

masks="$(
  IFS=";"
  printf '%s' "${mask_paths[*]}"
)"

visualizer_args=(
  --title "$title"
  --windows "$windows"
  --masks "$masks"
)

if [ "$debug" = "1" ]; then
  visualizer_args+=(--debug-mask-overlay)
fi

GDK_BACKEND=x11 ./mask_visualizer.py "${visualizer_args[@]}" &
pid="$!"

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
