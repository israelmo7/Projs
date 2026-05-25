#!/usr/bin/env python3
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
import numpy as np
import tensorflow as tf

DATA_DIR = "prepared_features"
MODEL_DIR = "models"
MODEL_NAME = "wake_word_model.h5"

X_train = np.load(os.path.join(DATA_DIR, "data_train.npy"))
X_val   = np.load(os.path.join(DATA_DIR, "data_val.npy"))
y_train = np.load(os.path.join(DATA_DIR, "y_data_train.npy"))
y_val   = np.load(os.path.join(DATA_DIR, "y_data_val.npy"))

print(f"Training on shape: {X_train.shape}")

model = tf.keras.Sequential([
    tf.keras.layers.Input(shape=(64, 2)), # 64 חלונות זמן, 2 פיצ'רים בכל חלון
    
    tf.keras.layers.Conv1D(16, kernel_size=3, activation='relu', padding='same'),
    tf.keras.layers.MaxPooling1D(pool_size=2),
    
    tf.keras.layers.Conv1D(32, kernel_size=3, activation='relu', padding='same'),
    tf.keras.layers.MaxPooling1D(pool_size=2),
    
    tf.keras.layers.Flatten(),
    tf.keras.layers.Dense(64, activation='relu'),
    tf.keras.layers.Dropout(0.5),
    tf.keras.layers.Dense(2, activation='softmax')
])

model.compile(optimizer='adam', loss='sparse_categorical_crossentropy', metrics=['accuracy'])
model.summary()

model.fit(X_train, y_train, validation_data=(X_val, y_val), epochs=30, batch_size=32)

os.makedirs(MODEL_DIR, exist_ok=True)
model.save(os.path.join(MODEL_DIR, MODEL_NAME))
print(f"✅ Model saved to {MODEL_DIR}/{MODEL_NAME}")