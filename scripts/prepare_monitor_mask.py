#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

from PIL import Image, ImageFilter

from wallpaper_probe import format_geometry, parse_geometry


def parse_window(value):
    parts = value.split(",")
    if len(parts) != 4:
        raise ValueError(f"invalid window: {value}")
    x, y, width, height = [int(part) for part in parts]
    return {"x": x, "y": y, "width": width, "height": height}


def crop_monitor_mask(image, monitor, window, threshold, blur, invert):
    if image.size == (window["width"], window["height"]):
        gray = image.convert("L")
        mask = gray.point(lambda value: 255 if value >= threshold else 0)
        if invert:
            mask = Image.eval(mask, lambda value: 255 - value)
        if blur > 0:
            mask = mask.filter(ImageFilter.GaussianBlur(blur))
        return mask

    local_window = {
        "x": window["x"] - monitor["x"],
        "y": window["y"] - monitor["y"],
        "width": window["width"],
        "height": window["height"],
    }

    if local_window["x"] < 0 or local_window["y"] < 0:
        raise ValueError("window starts outside monitor")
    if local_window["x"] + local_window["width"] > monitor["width"]:
        raise ValueError("window extends past monitor width")
    if local_window["y"] + local_window["height"] > monitor["height"]:
        raise ValueError("window extends past monitor height")

    gray = image.convert("L")
    scaled = gray.resize((monitor["width"], monitor["height"]), Image.Resampling.BICUBIC)
    crop_box = (
        local_window["x"],
        local_window["y"],
        local_window["x"] + local_window["width"],
        local_window["y"] + local_window["height"],
    )
    mask = scaled.crop(crop_box)
    mask = mask.point(lambda value: 255 if value >= threshold else 0)
    if invert:
        mask = Image.eval(mask, lambda value: 255 - value)
    if blur > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(blur))
    return mask


def save_alpha_mask(mask, output_path):
    alpha_mask = Image.new("RGBA", mask.size, (255, 255, 255, 0))
    alpha_mask.putalpha(mask)
    alpha_mask.save(output_path)


def save_debug_preview(source_crop, mask, output_path):
    source = source_crop.convert("RGBA")
    overlay = Image.new("RGBA", source.size, (0, 255, 255, 0))
    overlay.putalpha(mask.point(lambda value: int(value * 0.55)))
    Image.alpha_composite(source, overlay).save(output_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--monitor", required=True, help="Geometry like 1920x1080+0+0.")
    parser.add_argument("--window", required=True, help="Absolute window x,y,width,height.")
    parser.add_argument("--threshold", type=int, default=128)
    parser.add_argument("--blur", type=float, default=1.0)
    parser.add_argument("--invert", action="store_true")
    parser.add_argument("--wallpaper-crop", default="")
    parser.add_argument("--debug-preview", default="")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        print(f"prepare_monitor_mask: input does not exist: {input_path}", file=sys.stderr)
        return 1

    monitor = parse_geometry(args.monitor)
    window = parse_window(args.window)
    image = Image.open(input_path)
    mask = crop_monitor_mask(image, monitor, window, args.threshold, args.blur, args.invert)
    save_alpha_mask(mask, output_path)

    print(f"input: {input_path}")
    print(f"input_size: {image.width}x{image.height}")
    print(f"monitor: {format_geometry(monitor)}")
    print(f"window: {window['x']},{window['y']},{window['width']},{window['height']}")
    print(f"mask: {output_path}")

    if args.wallpaper_crop and args.debug_preview:
        wallpaper_crop = Image.open(args.wallpaper_crop)
        preview_path = Path(args.debug_preview)
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        save_debug_preview(wallpaper_crop, mask, preview_path)
        print(f"debug_preview: {preview_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
