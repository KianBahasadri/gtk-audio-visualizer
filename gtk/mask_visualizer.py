#!/usr/bin/env python3
import argparse
import math
import re
import signal
import sys

import cairo
import gi

import visualizer

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk


def split_optional_paths(value):
    if not value:
        return []
    return [item.strip() or None for item in value.split(";")]


def get_indexed_path(paths, index):
    if not paths:
        return None
    if index < len(paths):
        return paths[index]
    if len(paths) == 1:
        return paths[0]
    return None


def load_png(path):
    try:
        return cairo.ImageSurface.create_from_png(path)
    except Exception as error:
        print(f"mask_visualizer: could not load {path}: {error}", file=sys.stderr)
        return None


def make_test_mask(width, height, shape):
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    cr = cairo.Context(surface)
    cr.set_operator(cairo.OPERATOR_SOURCE)
    cr.set_source_rgba(0.0, 0.0, 0.0, 0.0)
    cr.paint()
    cr.set_operator(cairo.OPERATOR_OVER)
    cr.set_source_rgba(1.0, 1.0, 1.0, 1.0)

    if shape == "circle":
        radius = min(width, height) * 0.36
        cr.arc(width / 2, height / 2, radius, 0, math.tau)
        cr.fill()
    elif shape == "columns":
        column_width = width / 7
        for index in range(1, 7, 2):
            cr.rectangle(index * column_width, 0, column_width, height)
            cr.fill()
    else:
        rect_width = width * 0.34
        rect_height = height * 0.72
        visualizer.rounded_rectangle(
            cr,
            (width - rect_width) / 2,
            (height - rect_height) / 2,
            rect_width,
            rect_height,
            18,
        )
        cr.fill()

    surface.flush()
    return surface


class MaskedVisualizerWindow(visualizer.VisualizerWindow):
    def __init__(self, app, levels, options):
        self.mask_path = options.mask
        self.mask_surface = load_png(options.mask) if options.mask else None
        self.overlay_path = options.overlay_image
        self.overlay_surface = (
            load_png(options.overlay_image) if options.overlay_image else None
        )
        self.overlay_opacity = options.overlay_opacity
        self.test_mask_shape = options.test_mask
        self.test_mask_surface = None
        self.test_mask_size = None
        self.debug_mask_overlay = options.debug_mask_overlay
        self.render_surface = None
        self.render_context = None
        self.render_size = None
        self.mask_pattern = None
        self.mask_pattern_key = None
        self.overlay_pattern = None
        self.overlay_pattern_key = None
        self.use_frame_clock = options.use_frame_clock
        self.frame_tick_id = None
        self.last_frame_time_us = 0
        self.frame_accumulator_ms = 0.0
        super().__init__(app, levels, options)
        if self.use_frame_clock:
            if self.tick_id:
                visualizer.GLib.source_remove(self.tick_id)
                self.tick_id = None
            self.frame_tick_id = self.area.add_tick_callback(self.frame_clock_tick)

    def frame_clock_tick(self, _widget, frame_clock):
        frame_time_us = frame_clock.get_frame_time()
        if self.last_frame_time_us:
            elapsed_ms = (frame_time_us - self.last_frame_time_us) / 1000.0
        else:
            elapsed_ms = visualizer.UPDATE_MS
        self.last_frame_time_us = frame_time_us
        self.frame_accumulator_ms += elapsed_ms

        while self.frame_accumulator_ms >= visualizer.UPDATE_MS:
            self.update_display_bands()
            self.frame_accumulator_ms -= visualizer.UPDATE_MS

        self.area.queue_draw()
        return True

    def update_display_bands(self):
        target, _using_audio = self.levels.snapshot()
        for index, value in enumerate(target):
            current = self.display_bands[index]
            speed = 0.62 if value > current else 0.22
            self.display_bands[index] = current + (value - current) * speed

    def draw(self, area, cr, width, height):
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0.0, 0.0, 0.0, 0.0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)

        visualizer_surface, visualizer_cr = self.get_render_target(width, height)
        clear_surface(visualizer_cr)

        using_audio = self.levels.snapshot()[1]
        segments = self.segments or [(0, 0, width, height)]
        for x, y, segment_width, segment_height in segments:
            self.draw_visualizer(
                visualizer_cr, x, y, segment_width, segment_height, using_audio
            )

        mask_surface = self.mask_surface
        if not mask_surface and self.test_mask_shape:
            mask_size = (width, height)
            if not self.test_mask_surface or self.test_mask_size != mask_size:
                self.test_mask_surface = make_test_mask(
                    width, height, self.test_mask_shape
                )
                self.test_mask_size = mask_size
            mask_surface = self.test_mask_surface

        if mask_surface:
            erase_with_alpha_mask(
                visualizer_surface,
                visualizer_cr,
                self.get_mask_pattern(mask_surface, width, height),
            )

        cr.set_source_surface(visualizer_surface, 0, 0)
        cr.paint()

        if self.overlay_surface:
            draw_image_overlay(
                cr,
                self.get_overlay_pattern(self.overlay_surface, width, height),
                self.overlay_opacity,
            )

        if mask_surface and self.debug_mask_overlay:
            draw_mask_overlay(cr, mask_surface, width, height)

    def get_render_target(self, width, height):
        size = (width, height)
        if self.render_size != size:
            self.render_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
            self.render_context = cairo.Context(self.render_surface)
            self.render_size = size
        return self.render_surface, self.render_context

    def get_mask_pattern(self, mask_surface, width, height):
        key = (id(mask_surface), width, height)
        if self.mask_pattern_key != key:
            self.mask_pattern = make_scaled_surface_pattern(mask_surface, width, height)
            self.mask_pattern_key = key
        return self.mask_pattern

    def get_overlay_pattern(self, image_surface, width, height):
        key = (id(image_surface), width, height)
        if self.overlay_pattern_key != key:
            self.overlay_pattern = make_scaled_surface_pattern(image_surface, width, height)
            self.overlay_pattern_key = key
        return self.overlay_pattern


def clear_surface(cr):
    cr.set_operator(cairo.OPERATOR_SOURCE)
    cr.set_source_rgba(0.0, 0.0, 0.0, 0.0)
    cr.paint()
    cr.set_operator(cairo.OPERATOR_OVER)


def erase_with_alpha_mask(target_surface, cr, mask_pattern):
    cr.set_operator(cairo.OPERATOR_DEST_OUT)
    cr.set_source(mask_pattern)
    cr.paint()
    cr.set_operator(cairo.OPERATOR_OVER)
    target_surface.flush()


def draw_mask_overlay(cr, mask_surface, width, height):
    cr.save()
    cr.set_operator(cairo.OPERATOR_OVER)
    cr.set_source_rgba(1.0, 0.1, 0.2, 0.28)
    mask_width = max(1, mask_surface.get_width())
    mask_height = max(1, mask_surface.get_height())
    cr.scale(width / mask_width, height / mask_height)
    cr.mask_surface(mask_surface, 0, 0)
    cr.restore()


def draw_image_overlay(cr, image_pattern, opacity):
    cr.save()
    cr.set_operator(cairo.OPERATOR_OVER)
    cr.set_source(image_pattern)
    cr.paint_with_alpha(opacity)
    cr.restore()


def make_scaled_surface_pattern(surface, width, height):
    surface_width = max(1, surface.get_width())
    surface_height = max(1, surface.get_height())
    pattern = cairo.SurfacePattern(surface)
    pattern.set_filter(cairo.FILTER_BILINEAR)
    pattern.set_extend(cairo.EXTEND_NONE)
    pattern.set_matrix(cairo.Matrix(xx=surface_width / width, yy=surface_height / height))
    return pattern


class MaskedVisualizerApp(Gtk.Application):
    def __init__(self, options):
        app_suffix = re.sub(r"[^A-Za-z0-9]", "", options.title) or "Default"
        super().__init__(
            application_id=f"dev.local.ForegroundMaskVisualizer.{app_suffix}"
        )
        self.options = options
        self.levels = visualizer.AudioLevels()
        self.windows = []

    def do_activate(self):
        visualizer.install_css()
        self.levels.start()
        window_specs = visualizer.parse_segments(self.options.windows)
        if not window_specs:
            window_specs = [(0, 0, self.options.width, self.options.height)]

        mask_paths = split_optional_paths(self.options.masks)
        overlay_paths = split_optional_paths(self.options.overlay_images)
        for index, (_x, _y, width, height) in enumerate(window_specs):
            window_options = argparse.Namespace(
                title=self.options.title
                if len(window_specs) == 1
                else f"{self.options.title} {index}",
                width=width,
                height=height,
                segments="",
                mask=get_indexed_path(mask_paths, index) or self.options.mask,
                overlay_image=get_indexed_path(overlay_paths, index)
                or self.options.overlay_image,
                overlay_opacity=self.options.overlay_opacity,
                test_mask=self.options.test_mask,
                debug_mask_overlay=self.options.debug_mask_overlay,
                use_frame_clock=self.options.use_frame_clock,
            )
            window = MaskedVisualizerWindow(self, self.levels, window_options)
            self.windows.append(window)
            window.present()

    def do_shutdown(self):
        self.levels.stop()
        Gtk.Application.do_shutdown(self)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", default="Foreground Mask Visualizer Test")
    parser.add_argument("--width", type=int, default=visualizer.WINDOW_WIDTH)
    parser.add_argument("--height", type=int, default=visualizer.WINDOW_HEIGHT)
    parser.add_argument("--segments", default="")
    parser.add_argument("--windows", default="")
    parser.add_argument("--mask", default="")
    parser.add_argument("--masks", default="")
    parser.add_argument("--overlay-image", default="")
    parser.add_argument("--overlay-images", default="")
    parser.add_argument("--overlay-opacity", type=float, default=0.45)
    parser.add_argument("--use-frame-clock", action="store_true")
    parser.add_argument(
        "--test-mask",
        choices=("circle", "rectangle", "columns"),
        default="",
        help="Use a generated alpha mask instead of loading a PNG.",
    )
    parser.add_argument("--debug-mask-overlay", action="store_true")
    options = parser.parse_args()

    app = MaskedVisualizerApp(options)
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    return app.run([])


if __name__ == "__main__":
    raise SystemExit(main())
