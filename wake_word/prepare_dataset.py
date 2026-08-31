#!/usr/bin/env python3
"""
Wake Word Dataset Preparation Script
Prepares and augments audio dataset for Wake Word Spotting model training.
"""

import os
import random
import sys
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from config import (
    CLEAN_DIR as CLEAN_PATH,
    NOISE_DIR as NOISE_PATH,
    POSITIVE_RAW_DIR,
    SAMPLE_RATE,
    TRAIN_NEGATIVE_DIR,
    TRAIN_POSITIVE_DIR,
)

SOURCE_DIR = str(POSITIVE_RAW_DIR)
NOISE_DIR = str(NOISE_PATH)
CLEAN_DIR = str(CLEAN_PATH)
OUTPUT_POSITIVE = str(TRAIN_POSITIVE_DIR)
OUTPUT_NEGATIVE = str(TRAIN_NEGATIVE_DIR)
TARGET_SAMPLE_RATE = SAMPLE_RATE
NUM_AUGMENTATIONS_PER_FILE = 30
NUM_NEGATIVE_SAMPLES = 300
NOISE_INJECTION_PROBABILITY = 0.8
SNR_MIN_DB = 5
SNR_MAX_DB = 20

def load_and_resample_audio(filepath, sample_rate=TARGET_SAMPLE_RATE):
    """Load audio and resample to target sample rate."""
    audio, sr = sf.read(filepath)
    # Convert to mono if stereo
    if len(audio.shape) > 1:
        audio = audio.mean(axis=1)
    # Resample to target sample rate
    if sr != sample_rate:
        audio = librosa.resample(audio, orig_sr=sr, target_sr=sample_rate)
    return audio, sample_rate

def generate_noise_segment(target_duration, noise_files):
    """Extract a noise segment with matching duration from noise files."""
    if not noise_files:
        return None
        
    # Shuffle noise files for randomness
    shuffled_noise = random.sample(noise_files, min(10, len(noise_files)))
    
    for noise_file in shuffled_noise:
        noise_audio, _ = load_and_resample_audio(noise_file)
        noise_duration = len(noise_audio) / TARGET_SAMPLE_RATE
        
        if noise_duration >= target_duration:
            # Extract segment matching target duration
            sample_count = int(target_duration * TARGET_SAMPLE_RATE)
            noise_segment = noise_audio[:sample_count]
            return noise_segment
        
        # If noise file is shorter, loop it and truncate
        if noise_duration < target_duration:
            num_loops = int(np.ceil(target_duration / noise_duration))
            noise_segment = np.tile(noise_audio, num_loops)
            sample_count = int(target_duration * TARGET_SAMPLE_RATE)
            noise_segment = noise_segment[:sample_count]
            return noise_segment
    
    return None

def apply_pitch_shift(audio, n_steps):
    """Apply pitch shift to audio. n_steps is in semitones."""
    try:
        audio_shifted = librosa.effects.pitch_shift(y=audio, sr=TARGET_SAMPLE_RATE, n_steps=n_steps)
        return audio_shifted
    except Exception as e:
        print(f"Warning: Pitch shift failed: {e}")
        return audio

def apply_time_stretch(audio, rate_factor):
    """Apply time stretch to audio."""
    try:
        # Time stretch (e.g., 0.95 for slower, 1.05 for faster)
        audio_stretched = librosa.effects.time_stretch(y=audio, rate=rate_factor)
        return audio_stretched
    except Exception as e:
        print(f"Warning: Time stretch failed: {e}")
        return audio

def calculate_and_mix_with_noise(audio, noise_segment, snr_db):
    """Mix audio with noise at specified SNR in dB."""
    if audio is None or noise_segment is None:
        return audio
    
    audio_power = np.sum(audio ** 2)
    if audio_power == 0:
        return audio
        
    # Calculate noise power needed for target SNR
    snr_linear = 10 ** (snr_db / 10)
    noise_power = audio_power / snr_linear
    noise_level = np.sqrt(noise_power / len(noise_segment))
    
    # Normalize noise segment
    noise_max = np.max(np.abs(noise_segment))
    if noise_max == 0:
        return audio
        
    noise_normalized = noise_segment / noise_max
    noise_scaled = noise_normalized * noise_level
    
    # Mix audio and noise
    mixed_audio = audio + noise_scaled
    return mixed_audio

def generate_positive_augmentation(original_audio, augmentation_id, noise_files):
    """Generate a single augmented version of the audio."""
    augmented_audio = original_audio.copy()
    
    # Randomly decide if we add noise injection (80% chance)
    add_noise = random.random() < NOISE_INJECTION_PROBABILITY
    
    if add_noise and noise_files:
        # Generate random SNR between min and max
        snr = random.uniform(SNR_MIN_DB, SNR_MAX_DB)
        
        # Get target duration
        target_duration = len(augmented_audio) / TARGET_SAMPLE_RATE
        
        # Generate noise segment matching target duration
        noise_segment = generate_noise_segment(target_duration, noise_files)
        
        if noise_segment is not None:
            # Pitch shift the noise slightly before mixing (in semitones)
            noise_pitch_shift = random.uniform(-2.0, 2.0)
            noise_segment = apply_pitch_shift(noise_segment, n_steps=noise_pitch_shift)
            
            # Mix with random SNR
            augmented_audio = calculate_and_mix_with_noise(augmented_audio, noise_segment, snr)
    
    # Apply pitch shift to the wake word (random up or down in semitones)
    pitch_shift = random.uniform(-2.0, 2.0)
    augmented_audio = apply_pitch_shift(augmented_audio, n_steps=pitch_shift)
    
    # Occasionally apply time stretch (10% chance)
    if random.random() < 0.1:
        rate_factor = random.uniform(0.90, 1.10)
        augmented_audio = apply_time_stretch(augmented_audio, rate_factor=rate_factor)
    
    return augmented_audio

def generate_negative_samples(num_samples):
    """Generate random negative samples from clean and noise directories."""
    negative_samples = []

    clean_files = [os.path.join(CLEAN_DIR, f) for f in os.listdir(CLEAN_DIR) if f.endswith('.wav')] if os.path.exists(CLEAN_DIR) else []
    noise_files = [os.path.join(NOISE_DIR, f) for f in os.listdir(NOISE_DIR) if f.endswith('.wav')] if os.path.exists(NOISE_DIR) else []

    files = clean_files + noise_files
    if not files:
        print("Warning: No files found in clean or noise directories to generate negative samples.")
        return negative_samples

    for i in range(num_samples):
        filepath = random.choice(files)
        audio, sr = load_and_resample_audio(filepath)

        # Random crop/pad to 1 second for variety when looping same files
        if len(audio) > TARGET_SAMPLE_RATE:
            start = random.randint(0, len(audio) - TARGET_SAMPLE_RATE)
            audio = audio[start : start + TARGET_SAMPLE_RATE]
        elif len(audio) < TARGET_SAMPLE_RATE:
            audio = np.pad(audio, (0, TARGET_SAMPLE_RATE - len(audio)), mode='constant')

        output_path = os.path.join(OUTPUT_NEGATIVE, f"negative_{i+1:04d}.wav")
        sf.write(output_path, audio, TARGET_SAMPLE_RATE)
        negative_samples.append(output_path)

        if (i + 1) % 100 == 0:
            print(f"Generated {i + 1}/{num_samples} negative samples...")

    return negative_samples

def main():
    """Main function to prepare the dataset."""
    print("=" * 60)
    print("Wake Word Dataset Preparation Script")
    print("=" * 60)
    
    # Create required directories
    os.makedirs(OUTPUT_POSITIVE, exist_ok=True)
    os.makedirs(OUTPUT_NEGATIVE, exist_ok=True)
    
    # Check if source directory exists
    if not os.path.exists(SOURCE_DIR):
        print(f"Error: Source directory {SOURCE_DIR} not found.")
        return

    # Load all positive raw files
    positive_files = [os.path.join(SOURCE_DIR, f) for f in os.listdir(SOURCE_DIR) if f.endswith('.wav') or f.endswith('.mp3')]
    print(f"\nFound {len(positive_files)} positive raw files in {SOURCE_DIR}")
    
    # Load all noise files
    if os.path.exists(NOISE_DIR):
        noise_files = [os.path.join(NOISE_DIR, f) for f in os.listdir(NOISE_DIR) if f.endswith('.wav')]
        print(f"Found {len(noise_files)} noise files in {NOISE_DIR}")
    else:
        noise_files = []
        print(f"Warning: Noise directory {NOISE_DIR} not found.")
    
    # Generate positive augmentations
    print(f"\nGenerating {NUM_AUGMENTATIONS_PER_FILE} augmentations per file...")
    for positive_file in positive_files:
        try:
            audio, sr = load_and_resample_audio(positive_file)
            audio_length = len(audio)
            print(f"\nProcessing: {os.path.basename(positive_file)} (duration: {audio_length/TARGET_SAMPLE_RATE:.2f}s)")
            
            for aug_id in range(1, NUM_AUGMENTATIONS_PER_FILE + 1):
                augmented_audio = generate_positive_augmentation(audio, aug_id, noise_files)
                
                # Save with sequential naming
                base_name = os.path.splitext(os.path.basename(positive_file))[0]
                output_path = os.path.join(OUTPUT_POSITIVE, f"{base_name}_aug_{aug_id:02d}.wav")
                sf.write(output_path, augmented_audio, TARGET_SAMPLE_RATE)
                
            print(f"  Generated {NUM_AUGMENTATIONS_PER_FILE} augmentations for {os.path.basename(positive_file)}")
            
        except Exception as e:
            print(f"Error processing {positive_file}: {e}")
            continue
    
    # Generate negative samples
    print(f"\nGenerating {NUM_NEGATIVE_SAMPLES} negative samples...")
    negative_samples = generate_negative_samples(NUM_NEGATIVE_SAMPLES)
    print(f"\nGenerated {len(negative_samples)} negative samples in {OUTPUT_NEGATIVE}")
    
    # Summary
    positive_count = len(os.listdir(OUTPUT_POSITIVE))
    negative_count = len(os.listdir(OUTPUT_NEGATIVE))
    
    print("\n" + "=" * 60)
    print("Dataset Preparation Complete!")
    print("=" * 60)
    print(f"Positive samples: {positive_count}")
    print(f"Negative samples: {negative_count}")
    print(f"Sample rate: {TARGET_SAMPLE_RATE} Hz")
    print("=" * 60)

if __name__ == "__main__":
    main()
1