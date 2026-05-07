# Desktop Audio Visualizer

GTK4 audio visualizer for the live desktop setup. It uses cyan/violet Conky-style
signal colors while keeping the window background fully transparent.

Run it with:

```bash
python3 visualizer.py
```

Or launch one shared GTK process that draws an underlay window on each monitor:

```bash
./run-visualizer-all-monitors.sh
```

It captures the default PulseAudio/PipeWire monitor with `parec`. If capture fails, it displays a test animation instead. The launcher starts one GTK process and one audio capture, then creates one transparent underlay window per monitor because GNOME/Xwayland may clip a single giant window to one output. Each monitor gets a centered `1120px` visualizer, clamped to narrower monitors. The windows draw with transparency and update at roughly 30 FPS.

On GNOME Wayland this is still a normal app window. GNOME does not let regular apps become true click-through wallpaper clients, but this gives us a controllable base for visual design and audio behavior.
