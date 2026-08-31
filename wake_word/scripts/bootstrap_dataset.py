#!/usr/bin/env python3
"""Generate synthetic clean/noise WAV files for dataset bootstrap."""

import sys
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import CLEAN_DIR, NOISE_DIR, SAMPLE_RATE

DURATION_SEC = 3


def write_wav(path: Path, audio: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), audio.astype(np.float32), SAMPLE_RATE)


def generate_clean_samples() -> None:
    """Speech-like tones and silence segments as negative 'clean' sources."""
    n = int(DURATION_SEC * SAMPLE_RATE)
    t = np.linspace(0, DURATION_SEC, n, endpoint=False)

    samples = {
        "tone_440hz.wav": 0.3 * np.sin(2 * np.pi * 440 * t),
        "tone_880hz.wav": 0.2 * np.sin(2 * np.pi * 880 * t),
        "chirp.wav": 0.25 * np.sin(2 * np.pi * (200 + 800 * t / DURATION_SEC) * t),
        "silence.wav": np.zeros(n, dtype=np.float32),
        "hum_60hz.wav": 0.15 * np.sin(2 * np.pi * 60 * t),
    }

    for name, audio in samples.items():
        write_wav(CLEAN_DIR / name, audio)
        print(f"  Created {CLEAN_DIR / name}")


def generate_noise_samples() -> None:
    """Background noise sources for augmentation."""
    n = int(DURATION_SEC * SAMPLE_RATE)
    rng = np.random.default_rng(42)

    samples = {
        "white_noise.wav": rng.normal(0, 0.05, n),
        "pink_noise.wav": _pink_noise(n, rng),
        "brown_noise.wav": np.cumsum(rng.normal(0, 0.002, n)),
    }

    for name, audio in samples.items():
        audio = np.clip(audio, -1.0, 1.0)
        write_wav(NOISE_DIR / name, audio)
        print(f"  Created {NOISE_DIR / name}")


def _pink_noise(n: int, rng: np.random.Generator) -> np.ndarray:
    white = rng.normal(0, 1, n)
    fft = np.fft.rfft(white)
    freqs = np.arange(len(fft)) + 1
    fft /= np.sqrt(freqs)
    return np.fft.irfft(fft, n=n) * 0.05


def main() -> None:
    print("Bootstrapping dataset with synthetic clean/noise WAV files...")
    generate_clean_samples()
    generate_noise_samples()
    print("Done.")


if __name__ == "__main__":
    main()
