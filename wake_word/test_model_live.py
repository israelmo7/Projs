#!/usr/bin/env python3
"""Live wake word detection using shared inference engine."""

import sys
import time
from pathlib import Path

import numpy as np
import sounddevice as sd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from config import COOLDOWN_SECONDS, SAMPLE_RATE, SIGNAL_LENGTH, WAKE_THRESHOLD
from inference.engine import InferenceEngine


def main() -> None:
    engine = InferenceEngine()
    print(f"Model loaded ({engine.backend_name}). Input: 1 second @ {SAMPLE_RATE} Hz")
    print(f"Say 'היי נבו' — threshold {WAKE_THRESHOLD}. Ctrl+C to stop.\n")

    last_wake = 0.0

    try:
        while True:
            recording = sd.rec(
                SIGNAL_LENGTH, samplerate=SAMPLE_RATE, channels=1, dtype=np.int16
            )
            sd.wait()
            audio = recording.flatten()

            result = engine.predict_int16(audio)
            now = time.time()

            print(
                f"Background: {result.background:.3f} | "
                f"Wake: {result.wake_word:.3f}",
                end="",
            )

            if result.is_wake and (now - last_wake) > COOLDOWN_SECONDS:
                print(" -> WAKE DETECTED!")
                last_wake = now
            else:
                print()

            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
