"""
Canonical Energy + ZCR feature extraction.

This logic MUST match Firmware/src/main.cpp extractFeaturesOnESP() exactly.
"""

from __future__ import annotations

import numpy as np

from config import MODEL_INPUT_SIZE, SIGNAL_LENGTH, STEP, WINDOWS


def extract_features_int16(audio_int16: np.ndarray) -> np.ndarray:
    """
    Extract ESP32-compatible features from int16 PCM audio.

    Args:
        audio_int16: 1-D int16 array of length SIGNAL_LENGTH (16000).

    Returns:
        Flat float32 array of shape (MODEL_INPUT_SIZE,) — interleaved [energy, zcr] x 64.
    """
    audio = np.asarray(audio_int16, dtype=np.int16)

    if len(audio) < SIGNAL_LENGTH:
        audio = np.pad(audio, (0, SIGNAL_LENGTH - len(audio)), mode="constant")
    else:
        audio = audio[:SIGNAL_LENGTH]

    features = np.zeros(MODEL_INPUT_SIZE, dtype=np.float32)

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


def extract_features_matrix(audio_int16: np.ndarray) -> np.ndarray:
    """Return (64, 2) matrix instead of flat 128-vector."""
    flat = extract_features_int16(audio_int16)
    return flat.reshape(WINDOWS, 2)


def float32_to_int16(audio_float: np.ndarray) -> np.ndarray:
    """Convert float32 [-1, 1] audio to int16."""
    clipped = np.clip(audio_float, -1.0, 1.0)
    return (clipped * 32767).astype(np.int16)
