#!/usr/bin/env python3
"""
Train a CNN for Wake Word Spotting - גרסה יציבה מותאמת ל-ESP32 (TinyML)
כולל תיקון סיווג ל-2 מחלקות (Softmax) והסרת תלויות בעייתיות בהמרה
"""

import os

# ====================== הגדרות לפני TensorFlow ======================
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['TF_FORCE_GPU_ALLOW_GROWTH'] = 'true'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['GRPC_VERBOSITY'] = 'ERROR'
os.environ['PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION'] = 'python'

# אילוץ ריצה על CPU אם יש שגיאות Metal ב-M4
# os.environ["CUDA_VISIBLE_DEVICES"] = "-1"   

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
print("\nBuilding Model (TinyML Optimized Architecture)...")

model = tf.keras.Sequential([
    tf.keras.layers.Input(shape=(X_train.shape[1], X_train.shape[2], 1)),
    
    # בלוק 1
    tf.keras.layers.Conv2D(16, (3, 3), activation='relu', padding='same'),
    tf.keras.layers.Conv2D(16, (3, 3), strides=(2, 2), activation='relu', padding='same'),
    
    # בלוק 2
    tf.keras.layers.Conv2D(32, (3, 3), activation='relu', padding='same'),
    tf.keras.layers.Conv2D(32, (3, 3), strides=(2, 2), activation='relu', padding='same'),
    
    # בלוק 3
    tf.keras.layers.Conv2D(64, (3, 3), activation='relu', padding='same'),
    tf.keras.layers.Conv2D(64, (3, 3), strides=(2, 2), activation='relu', padding='same'),
    
    tf.keras.layers.Flatten(),
    tf.keras.layers.Dense(128, activation='relu'),
    tf.keras.layers.Dropout(0.5),
    
    # 🌟 התיקון הקריטי: 2 פלטים (אינדקס 0 = רקע, אינדקס 1 = מילת התעוררות)
    tf.keras.layers.Dense(2, activation='softmax')
])

model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
    loss='sparse_categorical_crossentropy',
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
print(f"\n✅ Model saved successfully to {MODEL_DIR}/{MODEL_NAME}")