#!/usr/bin/env python3
import argparse
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps


def run_rembg(input_path, output_path):
    try:
        import rembg
    except Exception as error:
        print(f"generate_crop_mask: rembg is not available: {error}", file=sys.stderr)
        return False

    with Image.open(input_path) as image:
        result = rembg.remove(image.convert("RGBA"))
        result.save(output_path)
    return True


def run_rembg_cli(input_path, output_path):
    command = ["rembg", "i", str(input_path), str(output_path)]
    try:
        subprocess.check_call(command)
        return True
    except Exception as error:
        print(f"generate_crop_mask: rembg CLI failed: {error}", file=sys.stderr)
        return False


def make_space_threshold_mask(image, threshold, blur, dilate, erode):
    rgb = image.convert("RGB")
    pixels = rgb.load()
    mask = Image.new("L", rgb.size, 0)
    mask_pixels = mask.load()

    width, height = rgb.size
    for y in range(height):
        for x in range(width):
            red, green, blue = pixels[x, y]
            brightness = max(red, green, blue)
            color_spread = max(red, green, blue) - min(red, green, blue)
            saturation_hint = color_spread > 16 and brightness > 28

            if brightness > threshold or saturation_hint:
                mask_pixels[x, y] = 255

    mask = clean_mask(mask, blur, dilate, erode)
    return mask


def clean_mask(mask, blur, dilate, erode):
    for _ in range(max(0, dilate)):
        mask = mask.filter(ImageFilter.MaxFilter(3))
    for _ in range(max(0, erode)):
        mask = mask.filter(ImageFilter.MinFilter(3))
    if blur > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(blur))
    return mask


def alpha_to_mask(image, blur, dilate, erode):
    if image.mode != "RGBA":
        image = image.convert("RGBA")
    alpha = image.getchannel("A")
    return clean_mask(alpha, blur, dilate, erode)


def save_debug_preview(source, mask, output_path):
    source = source.convert("RGBA")
    overlay = Image.new("RGBA", source.size, (0, 255, 255, 0))
    overlay.putalpha(mask.point(lambda value: int(value * 0.55)))
    preview = Image.alpha_composite(source, overlay)
    preview.save(output_path)


def save_alpha_mask(mask, output_path):
    alpha_mask = Image.new("RGBA", mask.size, (255, 255, 255, 0))
    alpha_mask.putalpha(mask)
    alpha_mask.save(output_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--method",
        choices=("threshold", "rembg", "rembg-cli", "alpha"),
        default="threshold",
    )
    parser.add_argument("--threshold", type=int, default=34)
    parser.add_argument("--blur", type=float, default=1.2)
    parser.add_argument("--dilate", type=int, default=2)
    parser.add_argument("--erode", type=int, default=0)
    parser.add_argument("--debug-preview", default="")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        print(f"generate_crop_mask: input does not exist: {input_path}", file=sys.stderr)
        return 1

    source = Image.open(input_path)

    if args.method == "rembg":
        extracted_path = output_path.with_name(output_path.stem + "-foreground.png")
        if not run_rembg(input_path, extracted_path):
            return 1
        with Image.open(extracted_path) as extracted:
            mask = alpha_to_mask(extracted, args.blur, args.dilate, args.erode)
    elif args.method == "rembg-cli":
        extracted_path = output_path.with_name(output_path.stem + "-foreground.png")
        if not run_rembg_cli(input_path, extracted_path):
            return 1
        with Image.open(extracted_path) as extracted:
            mask = alpha_to_mask(extracted, args.blur, args.dilate, args.erode)
    elif args.method == "alpha":
        mask = alpha_to_mask(source, args.blur, args.dilate, args.erode)
    else:
        mask = make_space_threshold_mask(
            source,
            clamp(args.threshold, 0, 255),
            args.blur,
            args.dilate,
            args.erode,
        )

    save_alpha_mask(mask, output_path)
    print(f"mask: {output_path}")

    if args.debug_preview:
        preview_path = Path(args.debug_preview)
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        save_debug_preview(source, mask, preview_path)
        print(f"debug_preview: {preview_path}")

    return 0


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


if __name__ == "__main__":
    raise SystemExit(main())
