#!/usr/bin/env python3
"""
Convert trained Keras model to TensorFlow Lite Micro format with Int8 quantization.
Generates a C header file for direct inclusion in ESP32-S3 firmware.
"""

import os
import numpy as np
import tensorflow as tf
from tensorflow import keras


# === Configuration ===
MODEL_PATH = "models/wake_word_model.h5"
TFLITE_PATH = "models/wake_word_model.tflite"
HEADER_PATH = "models/model_data.h"
TRAIN_DATA_PATH = "prepared_features/data_train.npy"
REPRESENTATIVE_BATCH_SIZE = 100


def load_model():
    """Load the trained Keras model."""
    print("=" * 60)
    print("Loading Model...")
    print("=" * 60)
    model = keras.models.load_model(MODEL_PATH)
    print(f"Model loaded successfully from: {MODEL_PATH}")
    return model


def get_representative_dataset():
    """Load a representative dataset for quantization calibration."""
    print("\n" + "=" * 60)
    print("Preparing Representative Dataset for Quantization...")
    print("=" * 60)
    
    # Load training data
    X_train = np.load(TRAIN_DATA_PATH)
    print(f"Loaded training data shape: {X_train.shape}")
    
    # Add channel dimension if not present
    if X_train.ndim == 3:
        X_train = X_train[..., np.newaxis]
        print(f"Data reshaped to: {X_train.shape}")
    
    # Take first N samples as representative dataset
    n_samples = min(REPRESENTATIVE_BATCH_SIZE, len(X_train))
    representative_batch = X_train[:n_samples]
    
    print(f"Using {n_samples} samples for quantization calibration")
    print(f"Representative dataset shape: {representative_batch.shape}")
    
    return representative_batch


def convert_to_tflite_with_quantization(model, rep_dataset):
    print("\n" + "=" * 60)
    print("Converting to TensorFlow Lite with Int8 Quantization...")
    print("=" * 60)
    
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    
    # פונקציית גנרטור שמחזירה דגימה אחת בכל פעם
    def representative_data_gen():
        for i in range(len(rep_dataset)):
            # מוסיף ממד Batch של 1 ומבטיח סוג נתונים Float32
            yield [rep_dataset[i:i+1].astype(np.float32)]
            
    converter.representative_dataset = representative_data_gen
    
    # הגדרות מחמירות כדי להבטיח שהמודל יהיה Int8 מלא (מתאים ל-S3)
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    converter.inference_input_type = tf.int8
    converter.inference_output_type = tf.int8
    
    print("Converting model (this might take a minute)...")
    tflite_model = converter.convert()
    print("Conversion successful!")
    return tflite_model



def save_tflite_model(tflite_model):
    """Save the TFLite model to file."""
    print("\n" + "=" * 60)
    print("Saving TFLite Model...")
    print("=" * 60)
    
    os.makedirs(os.path.dirname(TFLITE_PATH), exist_ok=True)
    with open(TFLITE_PATH, 'wb') as f:
        f.write(tflite_model)
    
    print(f"TFLite model saved to: {TFLITE_PATH}")
    return TFLITE_PATH


def generate_c_header(tflite_model, header_path):
    """Generate C header file with model data as const unsigned char array."""
    print("\n" + "=" * 60)
    print("Generating C Header File...")
    print("=" * 60)
    
    # Get model bytes
    model_bytes = tflite_model
    
    # Get the size of the model in bytes
    model_size = len(model_bytes)
    print(f"Model data size: {model_size} bytes ({model_size / 1024:.2f} KB)")
    
    # Create header file content
    header_content = '''#ifndef MODEL_DATA_H
#define MODEL_DATA_H

/**
 * @file model_data.h
 * @brief TensorFlow Lite model data for ESP32-S3 wake word recognition.
 * 
 * This file contains a const unsigned char array with the complete
 * quantized TFLite model. Use this in your ESP-IDF or Arduino project
 * to load the model directly into flash memory.
 * 
 * Example usage:
 *   #include "model_data.h"
 *   
 *   tflite::FlatBufferModel* model = tflite::FlatBufferModel::Build(
 *       model_data, sizeof(model_data), tflite::FlatBufferModelOptions());
 */

// Model data as hex array
const unsigned char model_data[] = {

''';
    
    # Convert bytes to hex string
    hex_strings = ['0x{:02X}'.format(b) for b in model_bytes]
    header_content += ',\n'.join(hex_strings)
    header_content += '''
};

// Model size in bytes (compile-time constant)
const int model_size = sizeof(model_data);

// Function to get model pointer (can be passed directly to TFLite)
inline const unsigned char* get_model_data() {
    return model_data;
}

inline int get_model_size() {
    return model_size;
}

#endif // MODEL_DATA_H
'''
    
    # Write header file
    os.makedirs(os.path.dirname(header_path), exist_ok=True)
    with open(header_path, 'w') as f:
        f.write(header_content)
    
    print(f"C header file generated: {header_path}")
    return header_path


def print_statistics(original_size_bytes, tflite_size_bytes, header_size_bytes):
    """Print file size statistics and compression ratio."""
    print("\n" + "=" * 60)
    print("File Size Statistics")
    print("=" * 60)
    
    # Original H5 size
    original_size_bytes = original_size_bytes if original_size_bytes else 0
    original_size_kb = original_size_bytes / 1024
    original_size_mb = original_size_bytes / (1024 * 1024)
    
    # TFLite size
    tflite_size_kb = tflite_size_bytes / 1024
    tflite_size_mb = tflite_size_bytes / (1024 * 1024)
    
    # Header file size
    header_size_kb = header_size_bytes / 1024 if header_size_bytes else 0
    
    print(f"\nOriginal .h5 model size:    {original_size_kb:>10.2f} KB")
    print(f"Quantized .tflite size:     {tflite_size_kb:>10.2f} KB")
    print(f"C header file size:         {header_size_kb:>10.2f} KB")
    
    # Compression ratio
    if original_size_bytes > 0:
        compression_ratio = original_size_bytes / tflite_size_bytes
        ratio_percent = (compression_ratio - 1) * 100
        print(f"\nCompression ratio:          {compression_ratio:.3f}x")
        print(f"Size reduction:             {ratio_percent:.1f}%")
    else:
        print("\nCould not calculate compression ratio (original size unknown)")
    
    print("\n" + "=" * 60)
    print("Conversion Complete!")
    print("=" * 60)
    print(f"\nOutput files:")
    print(f"  TFLite model:   {TFLITE_PATH}")
    print(f"  C header:       {HEADER_PATH}")
    print("\n" + "=" * 60)


def main():
    """Main function to run the conversion pipeline."""
    print("\n" + "=" * 60)
    print("TensorFlow Lite Micro Model Conversion")
    print("ESP32-S3 Wake Word Recognition Model")
    print("=" * 60)
    
    # Verify input files exist
    if not os.path.exists(MODEL_PATH):
        print(f"\n❌ Error: Model not found at {MODEL_PATH}")
        return False
    
    if not os.path.exists(TRAIN_DATA_PATH):
        print(f"\n❌ Error: Training data not found at {TRAIN_DATA_PATH}")
        print("Please run extract_features.py and train_model.py first.")
        return False
    
    # Step 1: Load model
    model = load_model()
    
    # Step 2: Get representative dataset
    rep_dataset = get_representative_dataset()
    
    # Step 3: Convert to TFLite with quantization
    tflite_model = convert_to_tflite_with_quantization(model, rep_dataset)
    
    # Step 4: Save TFLite model
    tflite_path = save_tflite_model(tflite_model)
    
    # Step 5: Get original model size
    original_size = os.path.getsize(MODEL_PATH)
    
    # Step 6: Generate C header
    header_path = generate_c_header(tflite_model, HEADER_PATH)
    
    # Step 7: Print statistics
    tflite_size = os.path.getsize(tflite_path)
    header_size = os.path.getsize(header_path)
    print_statistics(original_size, tflite_size, header_size)
    
    return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
