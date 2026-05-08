#!/usr/bin/env python3
import json
from pathlib import Path

from PIL import Image

import visualizer


MASK_DIR = Path(".cache/manual-masks")
OUT_DIR = Path("gnome-extension/masks")
NAMES = ("left", "center", "right")


def alpha_at(mask_pixels, x, y):
    value = mask_pixels[x, y]
    if isinstance(value, tuple):
        return value[3] if len(value) >= 4 else max(value[:3])
    return value


def build_bar_runs(image):
    mask = image.convert("RGBA")
    pixels = mask.load()
    width, height = mask.size

    pad_x = 24
    gap = 4
    usable_width = max(1, width - pad_x * 2)
    bar_width = max(2, (usable_width - gap * (visualizer.BAR_COUNT - 1)) / visualizer.BAR_COUNT)

    bars = []
    for index in range(visualizer.BAR_COUNT):
        x0 = int(round(pad_x + index * (bar_width + gap)))
        x1 = int(round(x0 + bar_width))
        x0 = max(0, min(width - 1, x0))
        x1 = max(x0 + 1, min(width, x1))

        columns = []
        for x in range(x0, x1):
            visible = []
            in_run = False
            run_start = 0
            for y in range(height):
                foreground = alpha_at(pixels, x, y) >= 96
                if not foreground and not in_run:
                    run_start = y
                    in_run = True
                elif foreground and in_run:
                    visible.append([run_start, y])
                    in_run = False
            if in_run:
                visible.append([run_start, height])
            columns.append({"x": x, "runs": visible})
        bars.append(columns)

    return {
        "width": width,
        "height": height,
        "bar_count": visualizer.BAR_COUNT,
        "bars": bars,
    }


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    built = []

    for name in NAMES:
        path = MASK_DIR / f"{name}-prepared.png"
        if not path.exists():
            print(f"missing: {path}")
            continue

        data = build_bar_runs(Image.open(path))
        out_path = OUT_DIR / f"{name}.json"
        out_path.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
        built.append(str(out_path))
        print(f"wrote: {out_path}")

    if not built:
        raise SystemExit("no prepared masks found; run ./run-manual-mask-visualizer.sh once or prepare masks first")


if __name__ == "__main__":
    main()
