# Wayland Visualizer Test

Small GTK4 prototype for testing a custom Linux audio visualizer window.

Run it with:

```bash
python3 visualizer.py
```

It captures the default PulseAudio/PipeWire monitor with `parec`. If capture fails, it displays a test animation instead. The window draws with transparency and updates at roughly 60 FPS when the compositor allows it.

On GNOME Wayland this is still a normal app window. GNOME does not let regular apps become true click-through wallpaper clients, but this gives us a controllable base for visual design and audio behavior.
