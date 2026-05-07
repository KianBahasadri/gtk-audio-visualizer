#!/usr/bin/env python3
import argparse
import math
import random
import signal
import struct
import subprocess
import threading
import time
import re

import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk


BAR_COUNT = 72
WINDOW_WIDTH = 1120
WINDOW_HEIGHT = 180
UPDATE_MS = 33
SAMPLE_RATE = 44100
FRAME_COUNT = 1024
RECONNECT_SECONDS = 2.5


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def set_hex(cr, hex_value, alpha=1.0):
    red = int(hex_value[0:2], 16) / 255.0
    green = int(hex_value[2:4], 16) / 255.0
    blue = int(hex_value[4:6], 16) / 255.0
    cr.set_source_rgba(red, green, blue, alpha)


class AudioLevels:
    def __init__(self):
        self.lock = threading.Lock()
        self.bands = [0.0] * BAR_COUNT
        self.running = True
        self.proc = None
        self.using_audio = False
        self.thread = None

    def start(self):
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)

    def snapshot(self):
        with self.lock:
            return list(self.bands), self.using_audio

    def _set_bands(self, values, using_audio):
        with self.lock:
            self.using_audio = using_audio
            self.bands = values

    def _run(self):
        while self.running:
            source = self._default_monitor_source()
            if not source:
                self._fake_levels(RECONNECT_SECONDS)
                continue

            try:
                self._read_parec(source)
            except Exception:
                self._set_bands([0.0] * BAR_COUNT, False)
                self._fake_levels(RECONNECT_SECONDS)

    def _default_monitor_source(self):
        try:
            default_sink = subprocess.check_output(
                ["pactl", "get-default-sink"], text=True, stderr=subprocess.DEVNULL
            ).strip()
            if default_sink:
                return f"{default_sink}.monitor"
        except Exception:
            return None
        return None

    def _read_parec(self, source):
        self.proc = subprocess.Popen(
            [
                "parec",
                "--device",
                source,
                "--format=s16le",
                f"--rate={SAMPLE_RATE}",
                "--channels=1",
                "--latency-msec=10",
                "--process-time-msec=5",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )

        byte_count = FRAME_COUNT * 2
        previous = [0.0] * BAR_COUNT

        while self.running:
            data = self.proc.stdout.read(byte_count) if self.proc.stdout else b""
            if len(data) < byte_count:
                break

            samples = struct.unpack(f"<{FRAME_COUNT}h", data)
            values = []

            for index in range(BAR_COUNT):
                start = int(index * FRAME_COUNT / BAR_COUNT)
                end = int((index + 1) * FRAME_COUNT / BAR_COUNT)
                segment = samples[start:end]
                if not segment:
                    values.append(0.0)
                    continue
                rms = math.sqrt(sum(sample * sample for sample in segment) / len(segment))
                boosted = clamp((rms / 15500.0) ** 0.7, 0.0, 1.0)
                values.append(max(boosted, previous[index] * 0.82))

            previous = values
            self._set_bands(values, True)

        if self.proc and self.proc.poll() is None:
            self.proc.terminate()

    def _fake_levels(self, duration=None):
        phase = 0.0
        deadline = time.monotonic() + duration if duration else None
        while self.running and (deadline is None or time.monotonic() < deadline):
            phase += 0.09
            values = []
            for index in range(BAR_COUNT):
                wave = math.sin(phase + index * 0.28) * 0.5 + 0.5
                pulse = math.sin(phase * 0.37 + index * 0.08) * 0.5 + 0.5
                values.append(min(1.0, wave * 0.65 + pulse * 0.25 + random.random() * 0.08))
            self._set_bands(values, False)
            time.sleep(UPDATE_MS / 1000.0)


class VisualizerWindow(Gtk.ApplicationWindow):
    def __init__(self, app, levels, options):
        super().__init__(application=app, title=options.title)
        self.set_default_size(options.width, options.height)
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_focusable(False)
        self.set_can_focus(False)
        self.add_css_class("visualizer-window")

        self.display_bands = [0.0] * BAR_COUNT
        self.levels = levels
        self.tick_id = None

        self.area = Gtk.DrawingArea()
        self.area.add_css_class("visualizer-canvas")
        self.area.set_draw_func(self.draw)
        self.set_child(self.area)
        self.tick_id = GLib.timeout_add(UPDATE_MS, self.tick)

    def tick(self):
        target, _using_audio = self.levels.snapshot()
        for index, value in enumerate(target):
            current = self.display_bands[index]
            speed = 0.62 if value > current else 0.22
            self.display_bands[index] = current + (value - current) * speed

        self.area.queue_draw()
        return GLib.SOURCE_CONTINUE

    def draw(self, area, cr, width, height):
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0.0, 0.0, 0.0, 0.0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)

        using_audio = self.levels.snapshot()[1]

        pad_x = 24
        pad_top = 18
        pad_bottom = 20
        gap = 4
        usable_width = max(1, width - pad_x * 2)
        bar_width = max(2, (usable_width - gap * (BAR_COUNT - 1)) / BAR_COUNT)
        baseline = height - pad_bottom
        max_height = max(10, height - pad_top - pad_bottom)

        for index, value in enumerate(self.display_bands):
            x = pad_x + index * (bar_width + gap)
            bar_height = max(3, value * max_height)
            y = baseline - bar_height
            mix = index / max(1, BAR_COUNT - 1)
            red = 0.0 + mix * 0.55
            green = 0.9 - mix * 0.35
            blue = 1.0 - mix * 0.04
            alpha = 0.52 + value * 0.42

            cr.set_source_rgba(red, green, blue, alpha * 0.22)
            rounded_rectangle(cr, x - 1, y - 2, bar_width + 2, bar_height + 4, min(6, bar_width / 2 + 1))
            cr.fill()

            cr.set_source_rgba(red, green, blue, alpha)
            rounded_rectangle(cr, x, y, bar_width, bar_height, min(5, bar_width / 2))
            cr.fill()

            if value > 0.58:
                set_hex(cr, "f8fafc", (value - 0.58) * 0.34)
                cr.rectangle(x, y, bar_width, min(8, bar_height))
                cr.fill()

        if not using_audio:
            cr.select_font_face("JetBrains Mono", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(10)
            set_hex(cr, "facc15", 0.82)
            cr.move_to(pad_x, pad_top + 10)
            cr.show_text("TEST SIGNAL")


def rounded_rectangle(cr, x, y, width, height, radius):
    radius = min(radius, width / 2, height / 2)
    cr.new_sub_path()
    cr.arc(x + width - radius, y + radius, radius, -math.pi / 2, 0)
    cr.arc(x + width - radius, y + height - radius, radius, 0, math.pi / 2)
    cr.arc(x + radius, y + height - radius, radius, math.pi / 2, math.pi)
    cr.arc(x + radius, y + radius, radius, math.pi, 3 * math.pi / 2)
    cr.close_path()

class VisualizerApp(Gtk.Application):
    def __init__(self, options):
        app_suffix = re.sub(r"[^A-Za-z0-9]", "", options.title) or "Default"
        super().__init__(application_id=f"dev.local.WaylandVisualizerTest.{app_suffix}")
        self.options = options
        self.levels = AudioLevels()
        self.window = None

    def do_activate(self):
        install_css()
        self.levels.start()
        self.window = VisualizerWindow(self, self.levels, self.options)
        self.window.present()

    def do_shutdown(self):
        self.levels.stop()
        Gtk.Application.do_shutdown(self)


def install_css():
    display = Gdk.Display.get_default()
    if not display:
        return

    provider = Gtk.CssProvider()
    provider.load_from_data(
        b"""
        window.visualizer-window {
            background: transparent;
        }

        .visualizer-canvas {
            background: transparent;
        }
        """
    )
    Gtk.StyleContext.add_provider_for_display(
        display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", default="Wayland Visualizer Test")
    parser.add_argument("--width", type=int, default=WINDOW_WIDTH)
    parser.add_argument("--height", type=int, default=WINDOW_HEIGHT)
    options = parser.parse_args()

    app = VisualizerApp(options)
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    return app.run([])


if __name__ == "__main__":
    raise SystemExit(main())
