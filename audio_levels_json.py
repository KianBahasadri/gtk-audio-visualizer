#!/usr/bin/env python3
import json
import signal
import sys
import time

import visualizer


def main():
    levels = visualizer.AudioLevels()
    running = True

    def stop(_signum, _frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    levels.start()
    try:
        while running:
            bands, using_audio = levels.snapshot()
            print(
                json.dumps(
                    {
                        "using_audio": using_audio,
                        "bands": [round(value, 4) for value in bands],
                    },
                    separators=(",", ":"),
                ),
                flush=True,
            )
            time.sleep(visualizer.UPDATE_MS / 1000.0)
    finally:
        levels.stop()


if __name__ == "__main__":
    main()
