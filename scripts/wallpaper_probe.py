#!/usr/bin/env python3
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

from PIL import Image, ImageFilter


DEFAULT_VISUALIZER_WIDTH = 1120
DEFAULT_VISUALIZER_HEIGHT = 180


def run_text(command):
    try:
        return subprocess.check_output(command, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def unwrap_gsettings_string(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == "'" and value[-1] == "'":
        return value[1:-1]
    return value


def uri_to_path(value):
    value = unwrap_gsettings_string(value)
    if value.startswith("file://"):
        parsed = urlparse(value)
        return unquote(parsed.path)
    return value


def detect_wallpaper_path():
    color_scheme = unwrap_gsettings_string(
        run_text(["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"])
    )
    dark_uri = run_text(["gsettings", "get", "org.gnome.desktop.background", "picture-uri-dark"])
    light_uri = run_text(["gsettings", "get", "org.gnome.desktop.background", "picture-uri"])

    if "dark" in color_scheme and dark_uri:
        path = uri_to_path(dark_uri)
        if path and os.path.exists(path):
            return path

    path = uri_to_path(light_uri)
    if path and os.path.exists(path):
        return path

    path = uri_to_path(dark_uri)
    if path and os.path.exists(path):
        return path

    return ""


def detect_picture_options():
    value = run_text(["gsettings", "get", "org.gnome.desktop.background", "picture-options"])
    return unwrap_gsettings_string(value) or "zoom"


def parse_geometry(value):
    match = re.fullmatch(r"(\d+)x(\d+)([-+]\d+)([-+]\d+)", value.strip())
    if not match:
        raise ValueError(f"invalid geometry: {value}")
    width, height, x, y = match.groups()
    return {
        "x": int(x),
        "y": int(y),
        "width": int(width),
        "height": int(height),
    }


def format_geometry(rect):
    x_sign = "+" if rect["x"] >= 0 else ""
    y_sign = "+" if rect["y"] >= 0 else ""
    return f'{rect["width"]}x{rect["height"]}{x_sign}{rect["x"]}{y_sign}{rect["y"]}'


def detect_monitors():
    output = run_text(["xrandr", "--listmonitors"])
    monitors = []
    for line in output.splitlines()[1:]:
        match = re.search(r"([0-9]+)/[0-9]+x([0-9]+)/[0-9]+([-+][0-9]+)([-+][0-9]+)", line)
        if not match:
            continue
        width, height, x, y = match.groups()
        monitors.append(
            {
                "x": int(x),
                "y": int(y),
                "width": int(width),
                "height": int(height),
            }
        )
    return monitors


def desktop_bounds(monitors):
    min_x = min(monitor["x"] for monitor in monitors)
    min_y = min(monitor["y"] for monitor in monitors)
    max_x = max(monitor["x"] + monitor["width"] for monitor in monitors)
    max_y = max(monitor["y"] + monitor["height"] for monitor in monitors)
    return {
        "x": min_x,
        "y": min_y,
        "width": max_x - min_x,
        "height": max_y - min_y,
    }


def default_visualizer_window(monitor, visualizer_width, visualizer_height):
    width = min(visualizer_width, monitor["width"])
    height = min(visualizer_height, monitor["height"])
    return {
        "x": monitor["x"] + (monitor["width"] - width) // 2,
        "y": monitor["y"] + (monitor["height"] - height) // 2,
        "width": width,
        "height": height,
    }


def image_rect_for_mode(image_size, target, mode):
    image_width, image_height = image_size
    target_width = target["width"]
    target_height = target["height"]

    if mode == "stretched":
        return {
            "x": target["x"],
            "y": target["y"],
            "width": target_width,
            "height": target_height,
            "scale_x": target_width / image_width,
            "scale_y": target_height / image_height,
        }

    if mode == "scaled":
        scale = min(target_width / image_width, target_height / image_height)
    elif mode in ("centered", "wallpaper"):
        scale = 1.0
    else:
        scale = max(target_width / image_width, target_height / image_height)

    rendered_width = image_width * scale
    rendered_height = image_height * scale
    return {
        "x": target["x"] + (target_width - rendered_width) / 2,
        "y": target["y"] + (target_height - rendered_height) / 2,
        "width": rendered_width,
        "height": rendered_height,
        "scale_x": scale,
        "scale_y": scale,
    }


def crop_wallpaper(image, window, target, mode):
    image_rect = image_rect_for_mode(image.size, target, mode)

    if mode == "wallpaper":
        return crop_wallpaper_tiled(image, window, image_rect), image_rect

    source_x = (window["x"] - image_rect["x"]) / image_rect["scale_x"]
    source_y = (window["y"] - image_rect["y"]) / image_rect["scale_y"]
    source_width = window["width"] / image_rect["scale_x"]
    source_height = window["height"] / image_rect["scale_y"]

    crop = Image.new("RGB", (window["width"], window["height"]), (0, 0, 0))
    region = image.transform(
        (window["width"], window["height"]),
        Image.Transform.EXTENT,
        (source_x, source_y, source_x + source_width, source_y + source_height),
        resample=Image.Resampling.BICUBIC,
    )
    crop.paste(region, (0, 0))
    return crop, image_rect


def crop_wallpaper_tiled(image, window, image_rect):
    crop = Image.new("RGB", (window["width"], window["height"]), (0, 0, 0))
    image_width, image_height = image.size
    start_x = int((window["x"] - image_rect["x"]) % image_width) - image_width
    start_y = int((window["y"] - image_rect["y"]) % image_height) - image_height
    for x in range(start_x, window["width"] + image_width, image_width):
        for y in range(start_y, window["height"] + image_height, image_height):
            crop.paste(image, (x, y))
    return crop, image_rect


def make_edge_overlay(image):
    edges = image.convert("L").filter(ImageFilter.FIND_EDGES)
    alpha = edges.point(lambda value: 220 if value > 32 else 0)
    overlay = Image.new("RGBA", image.size, (0, 255, 255, 0))
    overlay.putalpha(alpha)
    return overlay


def write_probe_outputs(args, wallpaper_path, options, monitors):
    output_dir = Path(args.out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    image = Image.open(wallpaper_path).convert("RGB")
    bounds = desktop_bounds(monitors)
    windows = [default_visualizer_window(m, args.visualizer_width, args.visualizer_height) for m in monitors]

    print(f"wallpaper: {wallpaper_path}")
    print(f"wallpaper_size: {image.width}x{image.height}")
    print(f"picture_options: {options}")
    print(f"desktop_bounds: {format_geometry(bounds)}")

    overlay_paths = []
    edge_paths = []
    for index, (monitor, window) in enumerate(zip(monitors, windows)):
        target = bounds if options == "spanned" else monitor
        crop, image_rect = crop_wallpaper(image, window, target, options)
        crop_path = output_dir / f"wallpaper-crop-{index}.png"
        crop.save(crop_path)
        overlay_paths.append(str(crop_path))

        edge_path = output_dir / f"wallpaper-edges-{index}.png"
        make_edge_overlay(crop).save(edge_path)
        edge_paths.append(str(edge_path))

        print(f"monitor_{index}: {format_geometry(monitor)}")
        print(f"window_{index}: {window['x']},{window['y']},{window['width']},{window['height']}")
        print(
            "image_rect_{index}: {width:.2f}x{height:.2f}{x:+.2f}{y:+.2f}".format(
                index=index,
                width=image_rect["width"],
                height=image_rect["height"],
                x=image_rect["x"],
                y=image_rect["y"],
            )
        )
        print(f"crop_{index}: {crop_path}")
        print(f"edges_{index}: {edge_path}")

    print("visualizer_windows_arg: " + ";".join(
        f'{w["x"]},{w["y"]},{w["width"]},{w["height"]}' for w in windows
    ))
    print("overlay_arg: " + ";".join(overlay_paths))
    print("edge_overlay_arg: " + ";".join(edge_paths))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wallpaper", default="", help="Override GNOME wallpaper path.")
    parser.add_argument("--picture-options", default="", help="Override GNOME picture-options.")
    parser.add_argument(
        "--monitor",
        action="append",
        default=[],
        help="Monitor geometry like 1920x1080+0+0. Can be passed more than once.",
    )
    parser.add_argument("--out-dir", default=".cache/wallpaper-probe")
    parser.add_argument("--visualizer-width", type=int, default=DEFAULT_VISUALIZER_WIDTH)
    parser.add_argument("--visualizer-height", type=int, default=DEFAULT_VISUALIZER_HEIGHT)
    args = parser.parse_args()

    wallpaper_path = args.wallpaper or detect_wallpaper_path()
    if not wallpaper_path:
        print("wallpaper_probe: could not detect a wallpaper path", file=sys.stderr)
        return 1
    if not os.path.exists(wallpaper_path):
        print(f"wallpaper_probe: wallpaper does not exist: {wallpaper_path}", file=sys.stderr)
        return 1

    options = args.picture_options or detect_picture_options()
    monitors = [parse_geometry(value) for value in args.monitor] if args.monitor else detect_monitors()
    if not monitors:
        print(
            "wallpaper_probe: could not detect monitors; pass --monitor 1920x1080+0+0",
            file=sys.stderr,
        )
        return 1

    write_probe_outputs(args, wallpaper_path, options, monitors)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
