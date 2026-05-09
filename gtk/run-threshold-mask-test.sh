#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
root=".."

title="Foreground Mask Probe"
method="${VISUALIZER_MASK_METHOD:-threshold}"
threshold="${VISUALIZER_MASK_THRESHOLD:-34}"
debug="${VISUALIZER_MASK_DEBUG:-1}"

cleanup() {
  if [ -n "${pid:-}" ]; then
    kill "$pid" 2>/dev/null || true
  fi
}
trap cleanup INT TERM EXIT

probe_output="$(python3 "$root/scripts/wallpaper_probe.py" --out-dir "$root/.cache/wallpaper-probe")"
printf '%s\n' "$probe_output"

windows="$(printf '%s\n' "$probe_output" | awk -F': ' '/^visualizer_windows_arg:/ {print $2}')"
crops="$(printf '%s\n' "$probe_output" | awk -F': ' '/^overlay_arg:/ {print $2}')"

if [ -z "$windows" ] || [ -z "$crops" ]; then
  echo "Could not read probe windows or crops" >&2
  exit 1
fi

IFS=";" read -r -a crop_array <<< "$crops"
mask_paths=()
for index in "${!crop_array[@]}"; do
  crop="${crop_array[$index]}"
  mask="$root/.cache/wallpaper-probe/foreground-mask-${index}.png"
  preview="$root/.cache/wallpaper-probe/foreground-mask-${index}-preview.png"
  if [ "$method" = "rembg" ]; then
    uv run --with 'rembg[cpu]' python3 generate_crop_mask.py \
      --method "$method" \
      --threshold "$threshold" \
      --input "$crop" \
      --out "$mask" \
      --debug-preview "$preview"
  else
    python3 generate_crop_mask.py \
      --method "$method" \
      --threshold "$threshold" \
      --input "$crop" \
      --out "$mask" \
      --debug-preview "$preview"
  fi
  mask_paths+=("$mask")
done

masks="$(
  IFS=";"
  printf '%s' "${mask_paths[*]}"
)"

args=(
  --title "$title"
  --windows "$windows"
  --masks "$masks"
)

if [ "$debug" = "1" ]; then
  args+=(--debug-mask-overlay)
fi

GDK_BACKEND=x11 ./mask_visualizer.py "${args[@]}" &
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
