import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import GObject from 'gi://GObject';
import St from 'gi://St';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const BAR_COUNT = 72;
const VISUALIZER_WIDTH = 1120;
const VISUALIZER_HEIGHT = 180;
const UPDATE_MS = 33;
const HELPER_PATH = '/home/kian/live-wallpaper/gtk-audio-visualizer/audio_levels_json.py';
const LOG_PREFIX = 'audio-visualizer-wallpaper';
const MASK_NAMES = ['left', 'center', 'right'];

function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
}

const VisualizerCanvas = GObject.registerClass(
class VisualizerCanvas extends St.DrawingArea {
    _init(monitor, index, maskData) {
        super._init({
            reactive: false,
            x_expand: false,
            y_expand: false,
        });

        this._monitor = monitor;
        this._index = index;
        this._phase = index * 0.71;
        this._bands = new Array(BAR_COUNT).fill(0);
        this._target = new Array(BAR_COUNT).fill(0);
        this._externalBands = null;
        this._lastExternalUpdateMs = 0;
        this._timeoutId = 0;
        this._maskData = maskData;

        const width = Math.min(VISUALIZER_WIDTH, monitor.width);
        const height = Math.min(VISUALIZER_HEIGHT, monitor.height);
        const x = monitor.x + Math.floor((monitor.width - width) / 2);
        const y = monitor.y + Math.floor((monitor.height - height) / 2);

        this.set_position(x, y);
        this.set_size(width, height);
        this.set_opacity(255);
    }

    start() {
        if (this._timeoutId)
            return;

        this._timeoutId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, UPDATE_MS, () => {
            this._updateBands();
            this.queue_repaint();
            return GLib.SOURCE_CONTINUE;
        });
    }

    stop() {
        if (this._timeoutId) {
            GLib.source_remove(this._timeoutId);
            this._timeoutId = 0;
        }
    }

    _updateBands() {
        const nowMs = GLib.get_monotonic_time() / 1000;
        if (this._externalBands && nowMs - this._lastExternalUpdateMs < 700) {
            for (let index = 0; index < BAR_COUNT; index++) {
                const value = this._externalBands[index] ?? 0;
                const current = this._bands[index];
                const speed = value > current ? 0.62 : 0.22;
                this._bands[index] = current + (value - current) * speed;
            }
            return;
        }

        this._phase += 0.095;
        for (let index = 0; index < BAR_COUNT; index++) {
            const wave = Math.sin(this._phase + index * 0.28) * 0.5 + 0.5;
            const pulse = Math.sin(this._phase * 0.37 + index * 0.08) * 0.5 + 0.5;
            const value = clamp(wave * 0.65 + pulse * 0.25, 0.0, 1.0);
            const current = this._bands[index];
            const speed = value > current ? 0.62 : 0.22;
            this._target[index] = value;
            this._bands[index] = current + (value - current) * speed;
        }
    }

    setAudioBands(bands) {
        if (!Array.isArray(bands) || bands.length < BAR_COUNT)
            return;
        this._externalBands = bands.slice(0, BAR_COUNT).map(value => clamp(Number(value) || 0, 0, 1));
        this._lastExternalUpdateMs = GLib.get_monotonic_time() / 1000;
    }

    vfunc_repaint() {
        const cr = this.get_context();
        const [width, height] = this.get_surface_size();
        if (!width || !height) {
            cr.$dispose();
            return;
        }

        cr.setOperator(0);
        cr.paint();
        cr.setOperator(2);

        const padX = 24;
        const padTop = 18;
        const padBottom = 20;
        const gap = 4;
        const usableWidth = Math.max(1, width - padX * 2);
        const barWidth = Math.max(2, (usableWidth - gap * (BAR_COUNT - 1)) / BAR_COUNT);
        const baseline = height - padBottom;
        const maxHeight = Math.max(10, height - padTop - padBottom);

        for (let index = 0; index < BAR_COUNT; index++) {
            const value = this._bands[index];
            const x = padX + index * (barWidth + gap);
            const barHeight = Math.max(3, value * maxHeight);
            const y = baseline - barHeight;
            const mix = index / Math.max(1, BAR_COUNT - 1);
            const red = 0.0 + mix * 0.55;
            const green = 0.9 - mix * 0.35;
            const blue = 1.0 - mix * 0.04;
            const alpha = 0.52 + value * 0.42;
            const clipped = this._applyMaskClip(cr, index, y - 2, baseline + 2);

            roundedRectangle(cr, x - 1, y - 2, barWidth + 2, barHeight + 4, Math.min(6, barWidth / 2 + 1));
            cr.setSourceRGBA(red, green, blue, alpha * 0.22);
            cr.fill();

            roundedRectangle(cr, x, y, barWidth, barHeight, Math.min(5, barWidth / 2));
            cr.setSourceRGBA(red, green, blue, alpha);
            cr.fill();

            if (value > 0.58) {
                cr.rectangle(x, y, barWidth, Math.min(8, barHeight));
                cr.setSourceRGBA(0.97, 0.98, 0.99, (value - 0.58) * 0.34);
                cr.fill();
            }

            if (clipped)
                cr.restore();
        }

        cr.$dispose();
    }

    _applyMaskClip(cr, index, clipTop, clipBottom) {
        if (!this._maskData?.bars?.[index])
            return false;

        cr.save();
        for (const column of this._maskData.bars[index]) {
            for (const [start, end] of column.runs) {
                const runStart = Math.max(start, clipTop);
                const runEnd = Math.min(end, clipBottom);
                if (runEnd > runStart)
                    cr.rectangle(column.x, runStart, 1, runEnd - runStart);
            }
        }
        cr.clip();
        return true;
    }
});

function roundedRectangle(cr, x, y, width, height, radius) {
    radius = Math.min(radius, width / 2, height / 2);
    cr.newPath();
    cr.arc(x + width - radius, y + radius, radius, -Math.PI / 2, 0);
    cr.arc(x + width - radius, y + height - radius, radius, 0, Math.PI / 2);
    cr.arc(x + radius, y + height - radius, radius, Math.PI / 2, Math.PI);
    cr.arc(x + radius, y + radius, radius, Math.PI, Math.PI * 1.5);
    cr.closePath();
}

export default class AudioVisualizerWallpaperExtension extends Extension {
    enable() {
        this._actors = [];
        this._signals = [];
        this._audioProcess = null;
        this._audioStream = null;
        this._audioCancellable = null;
        this._maskData = this._loadMasks();
        this._rebuild();
        this._startAudioHelper();

        this._signals.push(Main.layoutManager.connect('monitors-changed', () => {
            this._clearActors();
            this._rebuild();
        }));
    }

    disable() {
        for (const signalId of this._signals ?? [])
            Main.layoutManager.disconnect(signalId);
        this._signals = [];
        this._stopAudioHelper();
        this._clearActors();
    }

    _rebuild() {
        const monitors = Main.layoutManager.monitors;
        for (let index = 0; index < monitors.length; index++) {
            const monitor = monitors[index];
            const actor = new VisualizerCanvas(
                monitor,
                index,
                this._maskData[this._maskNameForMonitor(monitor)]
            );
            this._addActorToBackground(actor);
            actor.start();
            this._actors.push(actor);
        }
    }

    _maskNameForMonitor(monitor) {
        if (monitor.x < 1920)
            return 'left';
        if (monitor.x < 3840)
            return 'center';
        return 'right';
    }

    _loadMasks() {
        const masks = {};
        for (const name of MASK_NAMES) {
            const path = GLib.build_filenamev([this.path, 'masks', `${name}.json`]);
            try {
                const [ok, contents] = GLib.file_get_contents(path);
                if (!ok)
                    continue;
                masks[name] = JSON.parse(new TextDecoder().decode(contents));
                console.log(`${LOG_PREFIX}: loaded mask ${path}`);
            } catch (error) {
                console.warn(`${LOG_PREFIX}: could not load mask ${path}: ${error}`);
            }
        }
        return masks;
    }

    _addActorToBackground(actor) {
        const backgroundGroup = Main.layoutManager._backgroundGroup;
        if (backgroundGroup) {
            backgroundGroup.add_child(actor);
            backgroundGroup.set_child_above_sibling(actor, null);
            return;
        }

        console.warn(`${LOG_PREFIX}: Main.layoutManager._backgroundGroup unavailable; falling back to windowGroup`);
        global.windowGroup.insert_child_at_index(actor, 0);
    }

    _clearActors() {
        for (const actor of this._actors ?? []) {
            actor.stop();
            actor.destroy();
        }
        this._actors = [];
    }

    _startAudioHelper() {
        try {
            console.log(`${LOG_PREFIX}: starting audio helper ${HELPER_PATH}`);
            this._audioCancellable = new Gio.Cancellable();
            this._audioProcess = Gio.Subprocess.new(
                ['python3', HELPER_PATH],
                Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE
            );
            this._audioStream = new Gio.DataInputStream({
                base_stream: this._audioProcess.get_stdout_pipe(),
            });
            this._readAudioError();
            this._readAudioLine();
        } catch (error) {
            console.error(`${LOG_PREFIX}: could not start audio helper: ${error}`);
            this._stopAudioHelper();
        }
    }

    _readAudioLine() {
        if (!this._audioStream)
            return;

        this._audioStream.read_line_async(
            GLib.PRIORITY_DEFAULT,
            this._audioCancellable,
            (stream, result) => {
                try {
                    const [line] = stream.read_line_finish_utf8(result);
                    if (line === null) {
                        this._stopAudioHelper();
                        return;
                    }

                    const message = JSON.parse(line);
                    if (message.bands)
                        this._setAudioBands(message.bands);

                    this._readAudioLine();
                } catch (error) {
                    if (!this._audioCancellable?.is_cancelled())
                        console.error(`${LOG_PREFIX}: audio read failed: ${error}`);
                    this._stopAudioHelper();
                }
            }
        );
    }

    _readAudioError() {
        const stderrPipe = this._audioProcess?.get_stderr_pipe();
        if (!stderrPipe)
            return;

        this._audioErrorStream = new Gio.DataInputStream({
            base_stream: stderrPipe,
        });
        this._readAudioErrorLine();
    }

    _readAudioErrorLine() {
        if (!this._audioErrorStream)
            return;

        this._audioErrorStream.read_line_async(
            GLib.PRIORITY_DEFAULT,
            this._audioCancellable,
            (stream, result) => {
                try {
                    const [line] = stream.read_line_finish_utf8(result);
                    if (line === null)
                        return;
                    if (line)
                        console.error(`${LOG_PREFIX}: helper stderr: ${line}`);
                    this._readAudioErrorLine();
                } catch (error) {
                    if (!this._audioCancellable?.is_cancelled())
                        console.error(`${LOG_PREFIX}: stderr read failed: ${error}`);
                }
            }
        );
    }

    _setAudioBands(bands) {
        for (const actor of this._actors ?? [])
            actor.setAudioBands(bands);
    }

    _stopAudioHelper() {
        if (this._audioCancellable) {
            this._audioCancellable.cancel();
            this._audioCancellable = null;
        }
        this._audioStream = null;
        this._audioErrorStream = null;
        if (this._audioProcess) {
            this._audioProcess.force_exit();
            this._audioProcess = null;
        }
    }
}
