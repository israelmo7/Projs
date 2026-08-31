"""Tests for feature extraction parity with ESP32 firmware."""

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import SIGNAL_LENGTH, STEP, WINDOWS
from features import extract_features_int16


def firmware_extract_reference(audio_int16: np.ndarray) -> np.ndarray:
    """Reference implementation mirroring Firmware/src/main.cpp."""
    audio = np.asarray(audio_int16, dtype=np.int16)
    if len(audio) < SIGNAL_LENGTH:
        audio = np.pad(audio, (0, SIGNAL_LENGTH - len(audio)), mode="constant")
    else:
        audio = audio[:SIGNAL_LENGTH]

    features = np.zeros(WINDOWS * 2, dtype=np.float32)
    for i in range(WINDOWS):
        start_index = i * STEP
        energy_sum = 0
        zcr_count = 0
        for j in range(STEP):
            val = int(audio[start_index + j])
            energy_sum += abs(val)
            if j > 0:
                prev = int(audio[start_index + j - 1])
                if (val >= 0 and prev < 0) or (val < 0 and prev >= 0):
                    zcr_count += 1
        avg_energy = float(energy_sum) / STEP
        features[i * 2] = avg_energy / 32768.0
        features[i * 2 + 1] = float(zcr_count) / STEP
    return features


@pytest.mark.parametrize("seed", [0, 1, 42, 99])
def test_feature_parity_random(seed: int) -> None:
    rng = np.random.default_rng(seed)
    audio = rng.integers(-30000, 30000, size=SIGNAL_LENGTH, dtype=np.int16)
    python_features = extract_features_int16(audio)
    reference = firmware_extract_reference(audio)
    np.testing.assert_allclose(python_features, reference, rtol=1e-6, atol=1e-6)


def test_feature_parity_silence() -> None:
    audio = np.zeros(SIGNAL_LENGTH, dtype=np.int16)
    np.testing.assert_array_equal(
        extract_features_int16(audio), firmware_extract_reference(audio)
    )


def test_feature_parity_short_audio_padded() -> None:
    audio = np.array([1000, -1000, 500, -500], dtype=np.int16)
    np.testing.assert_array_equal(
        extract_features_int16(audio), firmware_extract_reference(audio)
    )
