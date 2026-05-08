# Foreground Mask Visualizer Plan

## Goal

Make the audio visualizer look like it is playing between the wallpaper
background and the wallpaper foreground subject.

The intended effect is:

1. The desktop wallpaper remains the real background.
2. The visualizer draws as a transparent overlay.
3. Any foreground subject from the wallpaper hides the visualizer.
4. The result looks like the bars are behind the subject but in front of the
   distant background.

## Core Idea

Do not repaint the whole wallpaper in the GTK window if we can avoid it. The
desktop is already showing the wallpaper behind our transparent window.

The best first implementation is:

1. Read the current wallpaper image path.
2. Reconstruct how that wallpaper is scaled and cropped for each monitor.
3. Generate a foreground alpha mask from the wallpaper.
4. Crop that mask to the visualizer window region.
5. While drawing the visualizer, prevent bars from rendering where the mask is
   opaque.

This should produce the illusion without duplicating the wallpaper pixels.

## Candidate Approaches

### Approach A: Clip Visualizer With Foreground Mask

Generate a grayscale or alpha PNG where white means "foreground blocks the
visualizer" and black means "visualizer can draw here."

At render time:

1. Draw the visualizer to an intermediate Cairo surface.
2. Apply the mask so foreground pixels erase the visualizer alpha.
3. Paint the masked visualizer into the transparent GTK window.

Pros:

- Avoids wallpaper color mismatch.
- Keeps the window transparent.
- Runtime cost should be low.
- Works with the current visualizer drawing model.

Cons:

- Requires precise monitor crop and window alignment.
- Needs mask generation before the effect looks correct.
- Edge quality depends on segmentation quality.

This is the preferred first real implementation.

### Approach B: Paste Extracted Foreground Over Visualizer

Generate a transparent PNG containing only the foreground subject, then draw it
over the visualizer.

Pros:

- Easy to reason about visually.
- Useful as a debugging mode.
- Can prove segmentation quality before doing more complex masking.

Cons:

- Can visibly mismatch the real wallpaper due to scaling, color management,
  compression, blur, monitor transforms, or GNOME background rendering.
- Duplicates image pixels the desktop already draws.
- More likely to look wrong at the edges.

This is useful for diagnostics, but probably should not be the default effect.

### Approach C: Manual Mask File

Let the user pass an explicit mask PNG path and skip automatic wallpaper
detection and AI segmentation.

Pros:

- Smallest reliable renderer test.
- Separates compositing bugs from AI/crop bugs.
- Lets us iterate quickly with hand-made masks.

Cons:

- Not automatic.
- Not the final user experience.

This should be the first test harness because it isolates the renderer.

## Likely Components

### Mask Generator

Possible command:

```bash
python3 generate_foreground_mask.py --wallpaper path/to/wallpaper.jpg --monitor 1920x1080+0+0 --window 400,450,1120,180 --out cache/mask-0.png
```

Responsibilities:

- Load wallpaper image.
- Apply the same scaling/cropping mode as the desktop background.
- Run segmentation or use an existing precomputed alpha image.
- Export a mask matching the visualizer window size.

### Renderer Changes

Possible `visualizer.py` flags:

```bash
python3 visualizer.py --mask path/to/mask.png
python3 visualizer.py --windows ... --masks mask-0.png;mask-1.png
python3 visualizer.py --debug-mask-overlay
```

Renderer responsibilities:

- Load a PNG mask as a Cairo image surface.
- Match each mask to the corresponding window.
- Draw the visualizer to an intermediate transparent surface.
- Remove alpha where the foreground mask is opaque.
- Paint the final surface into the GTK drawing area.
- Optionally show the mask as a colored overlay for debugging.

### Wallpaper Detection

GNOME settings to investigate:

```bash
gsettings get org.gnome.desktop.background picture-uri
gsettings get org.gnome.desktop.background picture-uri-dark
gsettings get org.gnome.desktop.background picture-options
```

Expected options may include zoom, centered, scaled, stretched, spanned, or
wallpaper. We should only implement the mode actually used first, then add
others if needed.

### Cache

Generated masks should be cached because segmentation is too expensive to do
every launch if avoidable.

Cache key should include:

- Wallpaper path.
- Wallpaper modified time.
- Monitor geometry.
- Visualizer window geometry.
- Wallpaper scaling mode.
- Segmentation model/tool version if available.

## Segmentation Options

### rembg

Good first candidate because it is easy to run locally and produces transparent
foreground PNGs.

Questions:

- Is it installed?
- Does the model download require network?
- Does it handle the kinds of wallpapers we use?
- Can we get a useful mask without slow startup?

### Segment Anything / SAM Variants

Potentially better quality and more control, but more dependency and workflow
complexity.

Use only if `rembg` quality is not good enough.

### Manual Mask

Always keep this supported as a debug path. It gives us a known-good input when
automatic segmentation is the thing failing.

## Testing Workflow

This feature should be built in layers. Do not combine wallpaper detection,
segmentation, cropping, and rendering in one jump.

### Phase 1: Prove Masked Rendering

Goal: confirm Cairo/GTK can hide the visualizer with a mask.

Steps:

1. Add `--mask` support to `visualizer.py`.
2. Create a simple test mask with a solid circle, rectangle, or silhouette.
3. Run the visualizer with the test mask.
4. Confirm bars disappear behind the masked region.
5. Add `--debug-mask-overlay` so alignment can be inspected visually.

Pass condition:

- The mask hides the visualizer without making the whole GTK window opaque.
- The transparent background still shows the real desktop.
- The visualizer remains smooth at normal update speed.

Failure notes to capture:

- Mask alpha inverted.
- Mask scaled incorrectly.
- Cairo operator clears the entire window.
- Edges look jagged.
- FPS drops.

### Phase 2: Prove Foreground Overlay Debug Mode

Goal: confirm segmentation output roughly matches the wallpaper subject.

Steps:

1. Pick one known wallpaper with a clear foreground subject.
2. Run a background-removal tool and save a transparent foreground PNG.
3. Add or script a debug mode that draws the foreground PNG over the visualizer.
4. Compare the extracted foreground to the real desktop wallpaper.

Pass condition:

- The subject is recognizable.
- Edges are acceptable enough for a moving visualizer.
- The foreground position is close enough that crop math is worth pursuing.

Failure notes to capture:

- Bad segmentation.
- Holes inside the subject.
- Background pieces incorrectly classified as foreground.
- Hair/fine details look distracting.

### Phase 3: Prove Wallpaper Crop Math

Goal: make a source image crop line up with the desktop wallpaper.

Steps:

1. Read the current GNOME wallpaper path and background mode.
2. Read monitor geometry from `xrandr --listmonitors`.
3. Recreate the wallpaper scaling/cropping mode in a standalone script.
4. Export the crop for the visualizer rectangle.
5. Temporarily draw that crop in the visualizer window at partial opacity.
6. Compare it to the desktop wallpaper behind it.

Pass condition:

- Major wallpaper features line up pixel-for-pixel or close enough that the
  mask will appear attached to the real wallpaper subject.

Failure notes to capture:

- Wrong dark/light wallpaper URI.
- Wrong scaling mode.
- Monitor offset not accounted for.
- HiDPI scale factor mismatch.
- X11 window position differs from expected geometry.

### Phase 4: Combine Crop and Segmentation

Goal: generate a visualizer-sized mask from the real current wallpaper.

Steps:

1. Segment the full wallpaper or a relevant monitor crop.
2. Convert the segmentation result to a foreground mask.
3. Crop it to the visualizer rectangle.
4. Run the visualizer with that generated mask.
5. Enable debug overlay to inspect alignment.

Pass condition:

- Foreground regions hide the visualizer in the correct place.
- The effect looks intentional during audio motion.

Failure notes to capture:

- Full-image segmentation changes after crop.
- Cropping before segmentation gives better or worse results.
- Mask needs dilation/erosion/blur.
- Subject edges need feathering.

### Phase 5: Automate Startup

Goal: make the launcher generate or reuse masks automatically.

Steps:

1. Add a mask generation script.
2. Add cache key calculation.
3. Update `run-visualizer-all-monitors.sh` to generate masks per monitor/window.
4. Pass mask paths into `visualizer.py`.
5. Keep an environment variable to disable the feature quickly.

Possible environment variables:

```bash
VISUALIZER_FOREGROUND_MASK=1
VISUALIZER_MASK_DEBUG=1
VISUALIZER_MASK_TOOL=rembg
VISUALIZER_MASK_CACHE=.cache/foreground-masks
```

Pass condition:

- Normal launch still works if mask generation fails.
- Cached masks are reused.
- Startup remains tolerable.
- Debug mode can be enabled without editing code.

## Debug Modes We Should Keep

### Solid Test Mask

Draw a simple generated shape mask. This catches renderer regressions.

### Mask Overlay

Draw the mask as a translucent color over the visualizer window.

### Wallpaper Crop Overlay

Draw the computed wallpaper crop over the real desktop at partial opacity.
This is the fastest way to see crop or scale mismatch.

### Foreground PNG Overlay

Draw the extracted foreground image above the visualizer. This helps inspect
segmentation quality separately from mask compositing.

### Geometry Logging

Print:

- Monitor geometry.
- Visualizer window geometry.
- Wallpaper image size.
- Wallpaper mode.
- Computed crop rectangle.
- Mask path.
- Cache hit or miss.

## Implementation Order

1. Add manual `--mask` support to `visualizer.py`.
2. Add a simple generated test mask script or documented ImageMagick/Python
   one-liner.
3. Add `--debug-mask-overlay`.
4. Add foreground PNG overlay debug support if needed.
5. Build `generate_foreground_mask.py` with manual wallpaper path input.
6. Add GNOME wallpaper detection.
7. Add monitor/window crop math.
8. Add cache.
9. Wire it into `run-visualizer-all-monitors.sh`.

## Open Questions

- Is this system always GNOME, or should the feature support other desktops?
- Which wallpaper scaling mode is actually used right now?
- Are monitors using fractional scaling or mixed DPI?
- Should the mask apply only to the visualizer bars, or also to labels like
  `TEST SIGNAL`?
- Should masks be generated from the full wallpaper first, or from monitor
  crops first?
- Should this feature default on, or remain opt-in until reliable?

## Success Criteria

The feature is successful when:

- The regular transparent visualizer still works without masks.
- A manual mask can hide the visualizer reliably.
- A generated wallpaper foreground mask lines up with the desktop subject.
- Launch failure falls back to the normal visualizer instead of breaking.
- Debug modes make it obvious whether a bug is in rendering, crop math, or
  segmentation.

