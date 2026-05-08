# Audio Visualizer Wallpaper GNOME Extension

Experimental GNOME Shell version of the visualizer. This first pass draws fake
animated bars as Shell actors, behind regular windows, to test whether Shell
rendering avoids the GTK/Xwayland background-window frame-rate issue.

Install for local testing:

```bash
./install-gnome-extension.sh
gnome-extensions enable audio-visualizer-wallpaper@local
```

On Wayland, log out and back in if GNOME does not pick up the extension after
installing it. On X11, `Alt+F2`, `r`, Enter can reload Shell.

