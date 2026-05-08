#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

uuid="audio-visualizer-wallpaper@local"
target="${XDG_DATA_HOME:-$HOME/.local/share}/gnome-shell/extensions/$uuid"

mkdir -p "$(dirname "$target")"
rm -rf "$target"
cp -a "$PWD/gnome-extension" "$target"

echo "Installed $uuid at $target"
echo "Enable with: gnome-extensions enable $uuid"
