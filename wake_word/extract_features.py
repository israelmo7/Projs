#!/usr/bin/env python3
"""
Extract MFCC features from audio dataset for Wake Word Spotting model training.
Converts raw audio files in dataset/train/positive and dataset/train/negative
into formatted NumPy files for ML training.
"""

import os
import numpy as np
import librosa
from sklearn.model_selection import train_test_split


# Configuration
DATA_DIR = "dataset/train"
POSITIVE_DIR = os.path.join(DATA_DIR, "positive")
NEGATIVE_DIR = os.path.join(DATA_DIR, "negative")
MFCC_N_COEFFS = 40
SAMPLE_RATE = 16000
DURATION_SEC = 1.0
TEST_SPLIT = 0.2
OUTPUT_DIR = "prepared_features"


def load_and_pad_audio(filepath, duration=DURATION_SEC, sr=SAMPLE_RATE):
    """Load audio file and trim/pad to exact duration."""
    audio, _ = librosa.load(filepath, sr=sr)
    target_samples = int(duration * sr)
    
    if len(audio) > target_samples:
        audio = audio[:target_samples]
    else:
        audio = np.pad(audio, (0, target_samples - len(audio)), mode='constant')
    
    return audio


def extract_mfccs(audio, sr=SAMPLE_RATE, n_mfcc=MFCC_N_COEFFS):
    """Extract MFCC features from audio."""
    mfccs = librosa.feature.mfcc(y=audio, sr=sr, n_mfcc=n_mfcc)
    return mfccs.T  # Shape: (n_mfcc, n_time_frames)


def pad_mfcc_matrices(X_list):
    """Pad or truncate all MFCC matrices to same shape."""
    if not X_list:
        return np.array([])
    
    # Find max number of time frames
    max_frames = max(mfcc.shape[1] for mfcc in X_list)
    
    padded_features = []
    for mfcc in X_list:
        if mfcc.shape[1] < max_frames:
            # Pad with zeros
            pad_width = [(0, 0), (0, max_frames - mfcc.shape[1])]
            padded = np.pad(mfcc, pad_width, mode='constant')
        else:
            # Truncate if necessary
            padded = mfcc[:MFCC_N_COEFFS, :max_frames]
        padded_features.append(padded)
    
    return np.array(padded_features)


def load_and_label_data():
    """Load all audio files and extract features with labels."""
    X_positive = []
    y_positive = []
    X_negative = []
    y_negative = []
    
    # Check if directories exist
    positive_exists = os.path.exists(POSITIVE_DIR)
    negative_exists = os.path.exists(NEGATIVE_DIR)
    
    if not positive_exists and not negative_exists:
        print(f"Warning: Neither {POSITIVE_DIR} nor {NEGATIVE_DIR} found.")
        return None, None
    
    # Load positive samples
    if positive_exists:
        positive_files = [os.path.join(POSITIVE_DIR, f) 
                         for f in os.listdir(POSITIVE_DIR) 
                         if f.endswith('.wav')]
        if positive_files:
            print(f"Processing {len(positive_files)} positive samples...")
            for idx, filepath in enumerate(positive_files, 1):
                try:
                    audio = load_and_pad_audio(filepath)
                    mfccs = extract_mfccs(audio)
                    X_positive.append(mfccs)
                    y_positive.append(1)
                    if idx % 100 == 0:
                        print(f"  Processed {idx}/{len(positive_files)} positive files")
                except Exception as e:
                    print(f"  Error processing {filepath}: {e}")
                    continue
    
    # Load negative samples
    if negative_exists:
        negative_files = [os.path.join(NEGATIVE_DIR, f) 
                         for f in os.listdir(NEGATIVE_DIR) 
                         if f.endswith('.wav')]
        if negative_files:
            print(f"Processing {len(negative_files)} negative samples...")
            for idx, filepath in enumerate(negative_files, 1):
                try:
                    audio = load_and_pad_audio(filepath)
                    mfccs = extract_mfccs(audio)
                    X_negative.append(mfccs)
                    y_negative.append(0)
                    if idx % 100 == 0:
                        print(f"  Processed {idx}/{len(negative_files)} negative files")
                except Exception as e:
                    print(f"  Error processing {filepath}: {e}")
                    continue
    
    # Pad all feature matrices to same shape
    if X_positive:
        X_positive = pad_mfcc_matrices(X_positive)
        print(f"Positive features shape: {X_positive.shape}")
    
    if X_negative:
        X_negative = pad_mfcc_matrices(X_negative)
        print(f"Negative features shape: {X_negative.shape}")
    
    return X_positive, y_positive, X_negative, y_negative


def split_and_save(X, y, save_name, save_dir):
    """Split data into train/val and save to NumPy files."""
    if len(X) == 0 or len(y) == 0:
        print(f"Skipping {save_name}: no data to split")
        return
    
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=TEST_SPLIT, random_state=42, shuffle=True
    )
    
    np.save(os.path.join(save_dir, f"{save_name}_train.npy"), X_train)
    np.save(os.path.join(save_dir, f"{save_name}_val.npy"), X_val)
    np.save(os.path.join(save_dir, f"y_{save_name}_train.npy"), y_train)
    np.save(os.path.join(save_dir, f"y_{save_name}_val.npy"), y_val)
    
    print(f"Saved {save_name} data:")
    print(f"  X_train: {X_train.shape}")
    print(f"  X_val: {X_val.shape}")
    print(f"  y_train: {y_train.shape}")
    print(f"  y_val: {y_val.shape}")


def main():
    """Main function to extract features and save to NumPy files."""
    print("=" * 70)
    print("Extract MFCC Features for Wake Word Model Training")
    print("=" * 70)
    
    # Load and process all data
    print(f"\nLoading data from:")
    print(f"  Positive: {POSITIVE_DIR}")
    print(f"  Negative: {NEGATIVE_DIR}")
    
    X_pos, y_pos, X_neg, y_neg = load_and_label_data()
    
    if X_pos is None:
        print("\nNo data found. Exiting.")
        return
    
    # Combine positive and negative data
    X = np.vstack([X_pos, X_neg])
    y = np.concatenate([y_pos, y_neg])
    
    print(f"\nTotal samples loaded: {len(X)}")
    
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Save training and validation sets
    split_and_save(X, y, "data", OUTPUT_DIR)
    
    # Save summary
    print(f"\n" + "=" * 70)
    print("Feature Extraction Complete!")
    print("=" * 70)
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Saved files:")
    print(f"  {OUTPUT_DIR}/X_train.npy")
    print(f"  {OUTPUT_DIR}/X_val.npy")
    print(f"  {OUTPUT_DIR}/y_train.npy")
    print(f"  {OUTPUT_DIR}/y_val.npy")
    print(f"\nFeature shape: {X.shape[0]} samples x {X.shape[1]} MFCCs x {X.shape[2]} time frames")
    print("=" * 70)


if __name__ == "__main__":
    main()
