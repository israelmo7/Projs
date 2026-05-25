#!/usr/bin/env python3
"""
Extract ESP32-Compatible Features from Audio Dataset
Improved + Stable Version

Changes:
- Fixed int16 overflow issue
- Added stable ZCR thresholding
- Added optional feature normalization
- Added debug statistics
- Cleaner and safer processing

Output:
NumPy arrays ready for TinyML training
"""

import os
import numpy as np
import librosa
from sklearn.model_selection import train_test_split

# =========================================================
# PATHS
# =========================================================

DATASET_PATH = "dataset"
OUTPUT_DIR = "prepared_features"

# =========================================================
# AUDIO SETTINGS
# =========================================================

SAMPLE_RATE = 16000
SIGNAL_LENGTH = 16000          # 1 second
WINDOWS = 64
STEP = SIGNAL_LENGTH // WINDOWS

# =========================================================
# FEATURE SETTINGS
# =========================================================

USE_FEATURE_NORMALIZATION = False  # Set to True if you want to normalize features across the dataset

# Noise threshold for ZCR stability
# Helps ignore tiny ADC/mic noise
ZCR_THRESHOLD = 500

# =========================================================
# FEATURE EXTRACTION
# =========================================================

def extract_esp32_compatible_features(audio_data_int16):
    """
    Extract lightweight ESP32-compatible features.

    Features:
    - Energy envelope
    - Zero Crossing Rate (ZCR)

    Output shape:
    (64, 2)

    IMPORTANT:
    This logic should match the ESP32 firmware exactly.
    """

    # -----------------------------------------------------
    # Ensure exact 1-second length
    # -----------------------------------------------------

    if len(audio_data_int16) < SIGNAL_LENGTH:
        audio_data_int16 = np.pad(
            audio_data_int16,
            (0, SIGNAL_LENGTH - len(audio_data_int16)),
            mode='constant'
        )
    else:
        audio_data_int16 = audio_data_int16[:SIGNAL_LENGTH]

    # -----------------------------------------------------
    # Create feature matrix
    # -----------------------------------------------------

    features = np.zeros((WINDOWS, 2), dtype=np.float32)

    # -----------------------------------------------------
    # Process windows
    # -----------------------------------------------------

    for i in range(WINDOWS):

        start = i * STEP
        end = start + STEP

        window = audio_data_int16[start:end]

        if len(window) == 0:
            continue

        # =================================================
        # FIXED OVERFLOW BUG
        # =================================================

        # Convert to int32 BEFORE abs()
        # Prevents int16 overflow on -32768
        window_int32 = window.astype(np.int32)

        # =================================================
        # FEATURE 1: ENERGY
        # =================================================

        avg_energy = np.mean(np.abs(window_int32))

        # Normalize to ~0..1
        features[i, 0] = avg_energy / 32768.0

        # =================================================
        # FEATURE 2: STABLE ZCR
        # =================================================

        crossings = 0

        prev = window_int32[0]

        for j in range(1, len(window_int32)):

            curr = window_int32[j]

            # Ignore tiny noise around zero
            if abs(curr) < ZCR_THRESHOLD:
                continue

            if abs(prev) < ZCR_THRESHOLD:
                prev = curr
                continue

            # Detect zero crossing
            if (
                (curr >= 0 and prev < 0) or
                (curr < 0 and prev >= 0)
            ):
                crossings += 1

            prev = curr

        features[i, 1] = crossings / STEP

    # =====================================================
    # OPTIONAL NORMALIZATION
    # =====================================================

    if USE_FEATURE_NORMALIZATION:

        mean = np.mean(features)
        std = np.std(features)

        features = (features - mean) / (std + 1e-6)

    return features.astype(np.float32)

# =========================================================
# DATA LOADING
# =========================================================

def load_data():

    X = []
    y = []

    labels_map = {
        "background": 0,
        "positive_raw": 1
    }

    print("\n" + "=" * 60)
    print("🚀 Starting Feature Extraction")
    print("Mode: ESP32-Compatible Lightweight DSP")
    print("=" * 60)

    total_processed = 0
    total_failed = 0

    for folder_name, label in labels_map.items():

        folder_path = os.path.join(DATASET_PATH, folder_name)

        if not os.path.exists(folder_path):
            print(f"⚠️ Missing folder: {folder_path}")
            continue

        files = [
            f for f in os.listdir(folder_path)
            if f.endswith(".wav")
        ]

        print(f"\n📁 Processing '{folder_name}'")
        print(f"Files found: {len(files)}")

        for file_name in files:

            file_path = os.path.join(folder_path, file_name)

            try:

                # -------------------------------------------------
                # Load audio
                # -------------------------------------------------

                audio_float, _ = librosa.load(
                    file_path,
                    sr=SAMPLE_RATE,
                    mono=True
                )

                # -------------------------------------------------
                # Convert to int16
                # -------------------------------------------------

                audio_int16 = np.int16(audio_float * 32767)

                # -------------------------------------------------
                # Extract features
                # -------------------------------------------------

                features = extract_esp32_compatible_features(audio_int16)

                X.append(features)
                y.append(label)

                total_processed += 1

            except Exception as e:

                total_failed += 1
                print(f"❌ Error processing {file_name}")
                print(e)

    print("\n" + "=" * 60)
    print("📊 Extraction Summary")
    print("=" * 60)
    print(f"Processed: {total_processed}")
    print(f"Failed:    {total_failed}")

    return np.array(X, dtype=np.float32), np.array(y)

# =========================================================
# MAIN
# =========================================================

def main():

    X, y = load_data()

    if len(X) == 0:
        print("\n❌ No data processed!")
        return

    print("\n" + "=" * 60)
    print("📊 Dataset Statistics")
    print("=" * 60)

    print(f"Samples:        {len(X)}")
    print(f"Feature shape:  {X.shape}")
    print(f"Feature min:    {X.min():.4f}")
    print(f"Feature max:    {X.max():.4f}")
    print(f"Feature mean:   {X.mean():.4f}")
    print(f"Feature std:    {X.std():.4f}")

    # =====================================================
    # TRAIN / VALIDATION SPLIT
    # =====================================================

    X_train, X_val, y_train, y_val = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y
    )

    # =====================================================
    # SAVE OUTPUT
    # =====================================================

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    np.save(os.path.join(OUTPUT_DIR, "data_train.npy"), X_train)
    np.save(os.path.join(OUTPUT_DIR, "data_val.npy"), X_val)

    np.save(os.path.join(OUTPUT_DIR, "y_data_train.npy"), y_train)
    np.save(os.path.join(OUTPUT_DIR, "y_data_val.npy"), y_val)

    print("\n" + "=" * 60)
    print("💾 Saved Feature Files")
    print("=" * 60)

    print(f"Train: {X_train.shape}")
    print(f"Val:   {X_val.shape}")

    print(f"\n📂 Output directory:")
    print(f"{OUTPUT_DIR}")

    print("\n✅ Feature extraction completed successfully!")

# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":
    main()