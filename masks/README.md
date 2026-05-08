# Manual Foreground Masks

Put generated foreground mask images in this directory. Image files in this
folder are ignored by git.

Expected names for the current three-monitor layout:

- `left.png` for monitor `1920x1080+0+0`
- `center.png` for monitor `1920x1080+1920+0`
- `right.png` for monitor `1920x1080+3840+0`

Masks may be either:

- full-monitor masks, such as `1920x1080`
- visualizer-crop masks, such as `1120x180`

White/opaque pixels hide the visualizer. Black/transparent pixels let it show.

