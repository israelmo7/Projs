#!/usr/bin/env python3
"""
Train a CNN for Wake Word Spotting - גרסה יציבה ל-Apple Silicon
"""

import os

# ====================== הגדרות לפני TensorFlow ======================
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['TF_FORCE_GPU_ALLOW_GROWTH'] = 'true'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['GRPC_VERBOSITY'] = 'ERROR'
os.environ['PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION'] = 'python'

# ניסיון להפעיל Metal (GPU של Apple) - הסר אם רוצה CPU בלבד
# os.environ["CUDA_VISIBLE_DEVICES"] = "-1"   # ← הסר את ה# אם רוצה CPU בלבד

import numpy as np
import tensorflow as tf

print("TensorFlow version:", tf.__version__)
print("Devices:", tf.config.list_physical_devices())

tf.keras.backend.clear_session()

# === Configuration ===
DATA_DIR = "prepared_features"
MODEL_DIR = "models"
MODEL_NAME = "wake_word_model.h5"

BATCH_SIZE = 32
EPOCHS = 30

# === Load Data ===
print("\n" + "="*70)
print("Loading data...")
print("="*70)

X_train = np.load(os.path.join(DATA_DIR, "data_train.npy"))
X_val   = np.load(os.path.join(DATA_DIR, "data_val.npy"))
y_train = np.load(os.path.join(DATA_DIR, "y_data_train.npy"))
y_val   = np.load(os.path.join(DATA_DIR, "y_data_val.npy"))

print(f"Train: {X_train.shape} | Val: {X_val.shape}")

# Reshape
X_train = X_train[..., np.newaxis]
X_val   = X_val[..., np.newaxis]

# === Build Model ===
print("\nBuilding Model...")

model = tf.keras.Sequential([
    tf.keras.layers.Input(shape=(X_train.shape[1], X_train.shape[2], 1)),
    
    tf.keras.layers.Conv2D(16, (3, 3), activation='relu', padding='same'),
    tf.keras.layers.Conv2D(16, (3, 3), activation='relu', padding='same'),
    tf.keras.layers.MaxPooling2D((2, 2)),
    tf.keras.layers.BatchNormalization(),
    
    tf.keras.layers.Conv2D(32, (3, 3), activation='relu', padding='same'),
    tf.keras.layers.Conv2D(32, (3, 3), activation='relu', padding='same'),
    tf.keras.layers.MaxPooling2D((2, 2)),
    tf.keras.layers.BatchNormalization(),
    
    tf.keras.layers.Conv2D(64, (3, 3), activation='relu', padding='same'),
    tf.keras.layers.Conv2D(64, (3, 3), activation='relu', padding='same'),
    tf.keras.layers.MaxPooling2D((2, 2)),
    tf.keras.layers.BatchNormalization(),
    
    tf.keras.layers.Flatten(),
    tf.keras.layers.Dense(128, activation='relu'),
    tf.keras.layers.Dropout(0.5),
    tf.keras.layers.Dense(1, activation='sigmoid')
])

model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
    loss='binary_crossentropy',
    metrics=['accuracy']
)

model.summary()

# === Train ===
print("\nStarting Training...\n")

history = model.fit(
    X_train, y_train,
    validation_data=(X_val, y_val),
    epochs=EPOCHS,
    batch_size=BATCH_SIZE,
    verbose=1
)

# === Save ===
os.makedirs(MODEL_DIR, exist_ok=True)
model.save(os.path.join(MODEL_DIR, MODEL_NAME))
print(f"\nModel saved to {MODEL_DIR}/{MODEL_NAME}")