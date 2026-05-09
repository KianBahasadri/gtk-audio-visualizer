# Desktop Audio Visualizer

GNOME Shell audio visualizer for the live desktop setup.

The current main implementation is a GNOME Shell extension. It draws the
visualizer inside Shell, behind normal windows, and reads audio levels from a
small Python helper. Foreground masks can hide the bars so the visualizer appears
behind wallpaper objects.

## GNOME Extension

Install or refresh the local extension:

```bash
./install-gnome-extension.sh
```

Enable it:

```bash
./enable-gnome-extension.sh
```

GNOME Shell may require a logout/login after extension code changes.

## Masks

Put manual full-monitor masks here:

```text
masks/left.png
masks/center.png
masks/right.png
```

Mask PNGs are gitignored. White/opaque pixels hide the visualizer; black pixels
let it show.

Rebuild the extension mask JSON after changing mask PNGs:

```bash
python3 scripts/prepare_monitor_mask.py --input masks/left.png --monitor 1920x1080+0+0 --window 400,450,1120,180 --out .cache/manual-masks/left-prepared.png
python3 scripts/prepare_monitor_mask.py --input masks/center.png --monitor 1920x1080+1920+0 --window 2320,450,1120,180 --out .cache/manual-masks/center-prepared.png
python3 scripts/prepare_monitor_mask.py --input masks/right.png --monitor 1920x1080+3840+0 --window 4240,450,1120,180 --out .cache/manual-masks/right-prepared.png
./scripts/build_extension_masks.py
./install-gnome-extension.sh
```

## Layout

- `gnome-extension/`: Shell extension source and generated mask JSON.
- `scripts/`: shared helpers for audio, wallpaper geometry, and mask prep.
- `masks/`: ignored user-provided mask PNGs plus documentation.
- `gtk/`: older GTK/X11 implementation and experiments, kept as fallback.
- `docs/`: planning notes.

## GTK Fallback

The previous GTK implementation still exists:

```bash
cd gtk
./run-visualizer-all-monitors.sh
```

