#!/usr/bin/env python3

import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

import numpy as np
import tensorflow as tf

# =========================================================
# PATHS
# =========================================================

DATA_DIR = "prepared_features"
MODEL_DIR = "models"

MODEL_NAME = "wake_word_model.h5"

# =========================================================
# LOAD DATA
# =========================================================

X_train = np.load(os.path.join(DATA_DIR, "data_train.npy"))
X_val   = np.load(os.path.join(DATA_DIR, "data_val.npy"))

y_train = np.load(os.path.join(DATA_DIR, "y_data_train.npy"))
y_val   = np.load(os.path.join(DATA_DIR, "y_data_val.npy"))

print("=" * 60)
print("📊 Dataset Loaded")
print("=" * 60)

print(f"Train shape: {X_train.shape}")
print(f"Val shape:   {X_val.shape}")

# =========================================================
# MODEL
# =========================================================

model = tf.keras.Sequential([

    tf.keras.layers.Input(shape=(64, 2)),

    # -----------------------------------------------------
    # BLOCK 1
    # -----------------------------------------------------

    tf.keras.layers.Conv1D(
        filters=8,
        kernel_size=3,
        padding='same',
        activation='relu'
    ),

    tf.keras.layers.MaxPooling1D(pool_size=2),

    # -----------------------------------------------------
    # BLOCK 2
    # -----------------------------------------------------

    tf.keras.layers.Conv1D(
        filters=16,
        kernel_size=3,
        padding='same',
        activation='relu'
    ),

    tf.keras.layers.MaxPooling1D(pool_size=2),

    # -----------------------------------------------------
    # BLOCK 3
    # -----------------------------------------------------

    tf.keras.layers.Conv1D(
        filters=24,
        kernel_size=3,
        padding='same',
        activation='relu'
    ),

    # -----------------------------------------------------
    # GLOBAL POOLING
    # -----------------------------------------------------

    tf.keras.layers.GlobalAveragePooling1D(),

    # -----------------------------------------------------
    # SMALL DENSE HEAD
    # -----------------------------------------------------

    tf.keras.layers.Dense(
        16,
        activation='relu'
    ),

    tf.keras.layers.Dropout(0.2),

    # -----------------------------------------------------
    # OUTPUT
    # -----------------------------------------------------

    tf.keras.layers.Dense(
        2,
        activation='softmax'
    )
])

# =========================================================
# COMPILE
# =========================================================

model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
    loss='sparse_categorical_crossentropy',
    metrics=['accuracy']
)

# =========================================================
# SUMMARY
# =========================================================

print("\n" + "=" * 60)
print("🧠 MODEL SUMMARY")
print("=" * 60)

model.summary()

# =========================================================
# CALLBACKS
# =========================================================

callbacks = [

    tf.keras.callbacks.EarlyStopping(
        monitor='val_loss',
        patience=5,
        restore_best_weights=True
    ),

    tf.keras.callbacks.ReduceLROnPlateau(
        monitor='val_loss',
        factor=0.5,
        patience=2,
        verbose=1
    )
]

# =========================================================
# TRAIN
# =========================================================

print("\n" + "=" * 60)
print("🚀 TRAINING")
print("=" * 60)

history = model.fit(

    X_train,
    y_train,

    validation_data=(X_val, y_val),

    epochs=30,
    batch_size=32,

    callbacks=callbacks,

    verbose=1
)

# =========================================================
# EVALUATE
# =========================================================

print("\n" + "=" * 60)
print("📈 EVALUATION")
print("=" * 60)

loss, accuracy = model.evaluate(X_val, y_val, verbose=0)

print(f"Validation Loss:     {loss:.4f}")
print(f"Validation Accuracy: {accuracy:.4f}")

# =========================================================
# SAVE MODEL
# =========================================================

os.makedirs(MODEL_DIR, exist_ok=True)

save_path = os.path.join(MODEL_DIR, MODEL_NAME)

model.save(save_path)

print("\n" + "=" * 60)
print("💾 MODEL SAVED")
print("=" * 60)

print(f"Saved to:")
print(save_path)