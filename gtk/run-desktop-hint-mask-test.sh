#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

VISUALIZER_MASK_TITLE="${VISUALIZER_MASK_TITLE:-Desktop Hint Mask Visualizer}" \
VISUALIZER_X11_WINDOW_TYPE="${VISUALIZER_X11_WINDOW_TYPE:-desktop}" \
VISUALIZER_X11_STICKY="${VISUALIZER_X11_STICKY:-1}" \
./run-manual-mask-visualizer.sh
