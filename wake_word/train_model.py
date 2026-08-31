#!/usr/bin/env python3
"""Train the Nevo wake word Conv1D classifier."""

import json
import os
import sys
from pathlib import Path

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

import numpy as np
import tensorflow as tf

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from config import METRICS_JSON_PATH, MODELS_DIR, PREPARED_FEATURES_DIR, MODEL_H5_PATH

X_train = np.load(PREPARED_FEATURES_DIR / "data_train.npy")
X_val = np.load(PREPARED_FEATURES_DIR / "data_val.npy")
y_train = np.load(PREPARED_FEATURES_DIR / "y_data_train.npy")
y_val = np.load(PREPARED_FEATURES_DIR / "y_data_val.npy")

print("=" * 60)
print("Dataset Loaded")
print(f"Train: {X_train.shape}, Val: {X_val.shape}")
print("=" * 60)

model = tf.keras.Sequential(
    [
        tf.keras.layers.Input(shape=(64, 2)),
        tf.keras.layers.Conv1D(8, 3, padding="same", activation="relu"),
        tf.keras.layers.MaxPooling1D(2),
        tf.keras.layers.Conv1D(16, 3, padding="same", activation="relu"),
        tf.keras.layers.MaxPooling1D(2),
        tf.keras.layers.Conv1D(24, 3, padding="same", activation="relu"),
        tf.keras.layers.AveragePooling1D(pool_size=16),
        tf.keras.layers.Flatten(),
        tf.keras.layers.Dense(16, activation="relu"),
        tf.keras.layers.Dropout(0.2),
        tf.keras.layers.Dense(2, activation="softmax"),
    ]
)

model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
    loss="sparse_categorical_crossentropy",
    metrics=["accuracy"],
)

callbacks = [
    tf.keras.callbacks.EarlyStopping(
        monitor="val_loss", patience=5, restore_best_weights=True
    ),
    tf.keras.callbacks.ReduceLROnPlateau(
        monitor="val_loss", factor=0.5, patience=2, verbose=1
    ),
]

history = model.fit(
    X_train,
    y_train,
    validation_data=(X_val, y_val),
    epochs=30,
    batch_size=32,
    callbacks=callbacks,
    verbose=1,
)

loss, accuracy = model.evaluate(X_val, y_val, verbose=0)
print(f"Validation Loss: {loss:.4f}, Accuracy: {accuracy:.4f}")

MODELS_DIR.mkdir(parents=True, exist_ok=True)
model.save(str(MODEL_H5_PATH))
print(f"Model saved to {MODEL_H5_PATH}")

# Confusion matrix
y_pred = np.argmax(model.predict(X_val, verbose=0), axis=1)
confusion = tf.math.confusion_matrix(y_val, y_pred).numpy().tolist()

metrics = {
    "val_loss": float(loss),
    "val_accuracy": float(accuracy),
    "train_samples": int(len(X_train)),
    "val_samples": int(len(X_val)),
    "epochs_run": len(history.history["loss"]),
    "history": {
        "loss": [float(v) for v in history.history["loss"]],
        "val_loss": [float(v) for v in history.history["val_loss"]],
        "accuracy": [float(v) for v in history.history["accuracy"]],
        "val_accuracy": [float(v) for v in history.history["val_accuracy"]],
    },
    "confusion_matrix": confusion,
    "labels": ["background", "wake_word"],
}

with open(METRICS_JSON_PATH, "w") as f:
    json.dump(metrics, f, indent=2)

print(f"Metrics saved to {METRICS_JSON_PATH}")
