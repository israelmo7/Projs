#!/usr/bin/env python3
"""
Train a CNN for Wake Word Spotting.
Loads prepared MFCC features and trains a lightweight sequential CNN model.
"""

import os
import numpy as np
from tensorflow.keras import Sequential, layers


# === Configuration ===
DATA_DIR = "prepared_features"  # תוקן הנתיב
MODEL_DIR = "models"            # תוקן הנתיב
MODEL_NAME = "wake_word_model.h5"
BATCH_SIZE = 32
EPOCHS = 25


# === 1. Load Data ===
print("=" * 60)
print("Loading Data from prepared_features directory...")
print("=" * 60)

X_train = np.load(os.path.join(DATA_DIR, "data_train.npy"))
X_val = np.load(os.path.join(DATA_DIR, "data_val.npy"))
y_train = np.load(os.path.join(DATA_DIR, "y_data_train.npy"))
y_val = np.load(os.path.join(DATA_DIR, "y_data_val.npy"))

print(f"\nTraining data shape: {X_train.shape}")  
print(f"Validation data shape: {X_val.shape}")
print(f"Training labels shape: {y_train.shape}")
print(f"Validation labels shape: {y_val.shape}")


# === 2. Reshape Data ===
print("\n" + "=" * 60)
print("Reshaping data to include channel dimension...")
print("=" * 60)

X_train = X_train[..., np.newaxis]  
X_val = X_val[..., np.newaxis]

print(f"Training data reshaped: {X_train.shape}")  
print(f"Validation data reshaped: {X_val.shape}")


# === 3. Build CNN Model ===
print("\n" + "=" * 60)
print("Building CNN Model...")
print("=" * 60)

model = Sequential([
    layers.Conv2D(16, (3, 3), activation='relu', padding='same',
                  input_shape=(X_train.shape[1], X_train.shape[2], 1)),
    layers.Conv2D(16, (3, 3), activation='relu', padding='same'),
    layers.MaxPooling2D((2, 2)),
    
    layers.Conv2D(32, (3, 3), activation='relu', padding='same'),
    layers.Conv2D(32, (3, 3), activation='relu', padding='same'),
    layers.MaxPooling2D((2, 2)),
    
    layers.Conv2D(64, (3, 3), activation='relu', padding='same'),
    layers.Conv2D(64, (3, 3), activation='relu', padding='same'),
    layers.MaxPooling2D((2, 2)),
    
    layers.Flatten(),
    
    layers.Dense(128, activation='relu'),
    layers.Dropout(0.5),
    
    layers.Dense(1, activation='sigmoid')
])

print(f"\nModel summary:")
model.summary()


# === 4. Compile Model ===
print("\n" + "=" * 60)
print("Compiling Model...")
print("=" * 60)

model.compile(
    optimizer='adam',
    loss='binary_crossentropy',
    metrics=['accuracy']
)


# === 5. Train Model ===
print("\n" + "=" * 60)
print("Training Model...")
print("=" * 60)

history = model.fit(
    X_train, y_train,  # תוקן: הורדו הסוגריים העגולים המיותרים
    validation_data=(X_val, y_val),
    epochs=EPOCHS,
    batch_size=BATCH_SIZE,
    verbose=1
)


# === 6. Evaluate on Validation Set ===
print("\n" + "=" * 60)
print("Evaluating Model on Validation Set...")
print("=" * 60)

val_loss, val_accuracy = model.evaluate(X_val, y_val, verbose=0)
print(f"\nValidation Accuracy: {val_accuracy:.4f}")
print(f"Validation Loss: {val_loss:.4f}")


# === 7. Save Model ===
print("\n" + "=" * 60)
print("Saving Model...")
print("=" * 60)

os.makedirs(MODEL_DIR, exist_ok=True)
model_path = os.path.join(MODEL_DIR, MODEL_NAME)
model.save(model_path)
print(f"Model saved to: {model_path}")


# === 8. Print Training History ===
print("\n" + "=" * 60)
print("Training History Summary...")
print("=" * 60)
print(f"\n{'Epoch':<8} {'Train Acc':<12} {'Val Acc':<10} {'Train Loss':<12} {'Val Loss':<10}")
print("-" * 70)

# תוקנה לולאת ההדפסה שקרסה
for epoch in range(EPOCHS):
    train_acc = history.history['accuracy'][epoch]
    val_acc = history.history['val_accuracy'][epoch]
    train_loss = history.history['loss'][epoch]
    val_loss = history.history['val_loss'][epoch]
    print(f"{epoch+1:<8} {train_acc:<12.4f} {val_acc:<10.4f} {train_loss:<12.4f} {val_loss:<10.4f}")


print("\n" + "=" * 60)
print("Training Complete!")
print("=" * 60)
