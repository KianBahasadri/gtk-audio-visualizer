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
WINDOW_WIDTH = 900
WINDOW_HEIGHT = 220
UPDATE_MS = 16
SAMPLE_RATE = 44100


class AudioLevels:
    def __init__(self):
        self.lock = threading.Lock()
        self.bands = [0.0] * BAR_COUNT
        self.running = True
        self.proc = None
        self.using_audio = False

    def start(self):
        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()

    def stop(self):
        self.running = False
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()

    def snapshot(self):
        with self.lock:
            return list(self.bands), self.using_audio

    def _set_bands(self, values, using_audio):
        with self.lock:
            self.using_audio = using_audio
            self.bands = values

    def _run(self):
        source = self._default_monitor_source()
        if source:
            try:
                self._read_parec(source)
                return
            except Exception:
                pass

        self._fake_levels()

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

        frame_count = 256
        byte_count = frame_count * 2
        previous = [0.0] * BAR_COUNT

        while self.running:
            data = self.proc.stdout.read(byte_count) if self.proc.stdout else b""
            if len(data) < byte_count:
                break

            samples = struct.unpack(f"<{frame_count}h", data)
            values = []
            chunk = max(1, frame_count // BAR_COUNT)

            for index in range(BAR_COUNT):
                start = index * chunk
                segment = samples[start : start + chunk]
                if not segment:
                    values.append(0.0)
                    continue
                rms = math.sqrt(sum(sample * sample for sample in segment) / len(segment))
                boosted = min(1.0, (rms / 18000.0) ** 0.65)
                values.append(max(boosted, previous[index] * 0.78))

            previous = values
            self._set_bands(values, True)

    def _fake_levels(self):
        phase = 0.0
        while self.running:
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
        self.add_css_class("visualizer-window")

        self.display_bands = [0.0] * BAR_COUNT
        self.levels = levels

        self.area = Gtk.DrawingArea()
        self.area.add_css_class("visualizer-canvas")
        self.area.set_draw_func(self.draw)
        self.area.add_tick_callback(self.tick)
        self.set_child(self.area)

    def tick(self, widget, frame_clock):
        target, _using_audio = self.levels.snapshot()
        for index, value in enumerate(target):
            current = self.display_bands[index]
            speed = 0.62 if value > current else 0.22
            self.display_bands[index] = current + (value - current) * speed

        self.area.queue_draw()
        return GLib.SOURCE_CONTINUE

    def draw(self, area, cr, width, height):
        self.levels.snapshot()

        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0.0, 0.0, 0.0, 0.0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)

        gap = 4
        bar_width = max(2, (width - gap * (BAR_COUNT + 1)) / BAR_COUNT)
        baseline = height - 22
        max_height = height - 50

        for index, value in enumerate(self.display_bands):
            x = gap + index * (bar_width + gap)
            bar_height = max(3, value * max_height)
            y = baseline - bar_height
            hue = index / max(1, BAR_COUNT - 1)
            red = 0.12 + hue * 0.35
            green = 0.82 - hue * 0.25
            blue = 1.0
            cr.set_source_rgba(red, green, blue, 1.0)
            rounded_rectangle(cr, x, y, bar_width, bar_height, min(5, bar_width / 2))
            cr.fill()


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
