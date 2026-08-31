#!/usr/bin/env python3
"""Extract ESP32-compatible features from prepared training dataset."""

import sys
from pathlib import Path

import librosa
import numpy as np
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from config import (
    PREPARED_FEATURES_DIR,
    SAMPLE_RATE,
    TRAIN_NEGATIVE_DIR,
    TRAIN_POSITIVE_DIR,
)
from features import extract_features_matrix, float32_to_int16

AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg"}


def load_audio_int16(path: Path) -> np.ndarray:
    audio_float, _ = librosa.load(str(path), sr=SAMPLE_RATE, mono=True)
    return float32_to_int16(audio_float)


def load_data() -> tuple[np.ndarray, np.ndarray]:
    X: list[np.ndarray] = []
    y: list[int] = []

    labels_map = {
        TRAIN_NEGATIVE_DIR: 0,
        TRAIN_POSITIVE_DIR: 1,
    }

    print("\n" + "=" * 60)
    print("Starting Feature Extraction")
    print("Mode: ESP32-Compatible Lightweight DSP")
    print("=" * 60)

    total_processed = 0
    total_failed = 0

    for folder_path, label in labels_map.items():
        if not folder_path.exists():
            print(f"Missing folder: {folder_path}")
            continue

        files = sorted(
            f for f in folder_path.iterdir() if f.suffix.lower() in AUDIO_EXTENSIONS
        )
        print(f"\nProcessing '{folder_path.name}' — {len(files)} files")

        for file_path in files:
            try:
                audio_int16 = load_audio_int16(file_path)
                features = extract_features_matrix(audio_int16)
                X.append(features)
                y.append(label)
                total_processed += 1
            except Exception as exc:
                total_failed += 1
                print(f"Error processing {file_path.name}: {exc}")

    print("\n" + "=" * 60)
    print(f"Processed: {total_processed}, Failed: {total_failed}")
    print("=" * 60)

    return np.array(X, dtype=np.float32), np.array(y)


def main() -> None:
    X, y = load_data()

    if len(X) == 0:
        print("\nNo data processed! Run prepare_dataset.py first.")
        sys.exit(1)

    print(f"\nSamples: {len(X)}, Feature shape: {X.shape}")

    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    PREPARED_FEATURES_DIR.mkdir(parents=True, exist_ok=True)
    np.save(PREPARED_FEATURES_DIR / "data_train.npy", X_train)
    np.save(PREPARED_FEATURES_DIR / "data_val.npy", X_val)
    np.save(PREPARED_FEATURES_DIR / "y_data_train.npy", y_train)
    np.save(PREPARED_FEATURES_DIR / "y_data_val.npy", y_val)

    print(f"Train: {X_train.shape}, Val: {X_val.shape}")
    print("Feature extraction completed successfully!")


if __name__ == "__main__":
    main()
