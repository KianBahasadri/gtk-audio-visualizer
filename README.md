# Desktop Audio Visualizer

GTK4 audio visualizer for the live desktop setup. It uses cyan/violet Conky-style
signal colors while keeping the window background fully transparent.

Run it with:

```bash
python3 visualizer.py
```

Or launch a centered X11-backed desktop window:

```bash
./run-visualizer-all-monitors.sh
```

The launcher defaults to one window because multiple transparent X11 windows can make
GNOME/Mutter unstable. To force one visualizer per monitor:

```bash
VISUALIZER_MAX_WINDOWS=all ./run-visualizer-all-monitors.sh
```

It captures the default PulseAudio/PipeWire monitor with `parec`. If capture fails, it displays a test animation instead. The launcher centers each visualizer on its monitor at the same `1120px` width as the Codex Conky panel, clamping to narrower monitors. The window draws with transparency and updates at roughly 30 FPS.

On GNOME Wayland this is still a normal app window. GNOME does not let regular apps become true click-through wallpaper clients, but this gives us a controllable base for visual design and audio behavior.
