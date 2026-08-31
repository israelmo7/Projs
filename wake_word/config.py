"""Shared configuration for the Nevo wake word pipeline."""

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent

# Audio settings (must match firmware)
SAMPLE_RATE = 16000
SIGNAL_LENGTH = 16000  # 1 second
WINDOWS = 64
STEP = SIGNAL_LENGTH // WINDOWS
MODEL_INPUT_SIZE = WINDOWS * 2  # 128

# Detection
WAKE_THRESHOLD = 0.80
COOLDOWN_SECONDS = 2.0
COMMAND_DURATION_SECONDS = 5

# Dataset paths
DATASET_DIR = ROOT_DIR / "dataset"
POSITIVE_RAW_DIR = DATASET_DIR / "positive_raw"
CLEAN_DIR = DATASET_DIR / "clean"
NOISE_DIR = DATASET_DIR / "noise"
TRAIN_POSITIVE_DIR = DATASET_DIR / "train" / "positive"
TRAIN_NEGATIVE_DIR = DATASET_DIR / "train" / "negative"

# Model paths
MODELS_DIR = ROOT_DIR / "models"
PREPARED_FEATURES_DIR = ROOT_DIR / "prepared_features"
MODEL_H5_PATH = MODELS_DIR / "wake_word_model.h5"
MODEL_TFLITE_PATH = MODELS_DIR / "wake_word_model.tflite"
MODEL_HEADER_PATH = MODELS_DIR / "model_data.h"
METRICS_JSON_PATH = MODELS_DIR / "metrics.json"

# TTS
WAKE_PHRASE = "היי נבו"
TTS_VOICES = ["he-IL-AvriNeural", "he-IL-HilaNeural"]
TTS_RATES = ["-20%", "+0%", "+20%"]
TTS_PITCHES = ["-20Hz", "+0Hz", "+20Hz"]

# UDP protocol (ESP32)
UDP_PORT = 5555
UDP_PACKET_AUDIO_SIZE = 1024

# Backend
BACKEND_HOST = "0.0.0.0"
BACKEND_PORT = 8000
