# Audio Visualizer Wallpaper GNOME Extension

GNOME Shell version of the visualizer. It draws animated bars as Shell actors,
behind regular windows, and reads audio bands from `scripts/audio_levels_json.py`
in this repo. Since that script lives outside the installed extension
directory, `install-gnome-extension.sh` writes a `config.json` next to the
installed `extension.js` with the repo's absolute path (`repoRoot`); the
extension reads that file at runtime instead of hardcoding a path.
Mask JSON files under `gnome-extension/masks/` are generated from ignored manual
mask PNGs in the repo-level `masks/` directory.

Install for local testing:

```bash
./install-gnome-extension.sh
gnome-extensions enable audio-visualizer-wallpaper@local
```

On Wayland, log out and back in if GNOME does not pick up the extension after
installing it. On X11, `Alt+F2`, `r`, Enter can reload Shell.
