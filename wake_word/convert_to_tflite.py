#!/usr/bin/env python3

import os
import numpy as np
import tensorflow as tf

# =========================================================
# PATHS
# =========================================================

MODEL_PATH = "models/wake_word_model.h5"

X_TRAIN_PATH = "prepared_features/data_train.npy"

OUTPUT_TFLITE = "models/wake_word_model.tflite"

OUTPUT_HEADER = "models/model_data.h"

# =========================================================
# LOAD CALIBRATION DATA
# =========================================================

if os.path.exists(X_TRAIN_PATH):

    X_train = np.load(X_TRAIN_PATH).astype(np.float32)

    print(f"✅ Calibration data loaded: {X_train.shape}")

else:

    raise FileNotFoundError(
        f"Missing calibration data: {X_TRAIN_PATH}"
    )

# =========================================================
# REPRESENTATIVE DATASET
# =========================================================

def representative_data_gen():

    for i in range(min(200, len(X_train))):

        sample = X_train[i:i+1].astype(np.float32)

        yield [sample]

# =========================================================
# LOAD MODEL
# =========================================================

if not os.path.exists(MODEL_PATH):

    raise FileNotFoundError(
        f"Missing model: {MODEL_PATH}"
    )

print(f"📦 Loading model: {MODEL_PATH}")

model = tf.keras.models.load_model(MODEL_PATH)

# =========================================================
# CONVERTER
# =========================================================

converter = tf.lite.TFLiteConverter.from_keras_model(model)

# ---------------------------------------------------------
# OPTIMIZATION
# ---------------------------------------------------------

converter.optimizations = [
    tf.lite.Optimize.DEFAULT
]

# ---------------------------------------------------------
# FULL INT8 QUANTIZATION
# ---------------------------------------------------------

converter.representative_dataset = representative_data_gen

converter.target_spec.supported_ops = [
    tf.lite.OpsSet.TFLITE_BUILTINS_INT8
]

converter.inference_input_type = tf.int8
converter.inference_output_type = tf.int8

# =========================================================
# CONVERT
# =========================================================

print("\n🚀 Converting to TFLite INT8...")

tflite_model = converter.convert()

print("✅ Conversion complete!")

# =========================================================
# SAVE TFLITE
# =========================================================

os.makedirs("models", exist_ok=True)

with open(OUTPUT_TFLITE, "wb") as f:
    f.write(tflite_model)

print(f"💾 Saved TFLite model:")
print(OUTPUT_TFLITE)

# =========================================================
# VERIFY MODEL
# =========================================================

print("\n🔍 Verifying TFLite model...")

interpreter = tf.lite.Interpreter(model_content=tflite_model)

interpreter.allocate_tensors()

input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()

print("\n📥 INPUT DETAILS")
print(input_details)

print("\n📤 OUTPUT DETAILS")
print(output_details)

# =========================================================
# TEST INFERENCE
# =========================================================

sample = X_train[0:1]

input_scale, input_zero_point = input_details[0]['quantization']

sample_quantized = (
    sample / input_scale + input_zero_point
).astype(np.int8)

interpreter.set_tensor(
    input_details[0]['index'],
    sample_quantized
)

interpreter.invoke()

output = interpreter.get_tensor(
    output_details[0]['index']
)

print("\n🧠 Raw quantized output:")
print(output)

# =========================================================
# EXPORT C HEADER
# =========================================================

print("\n📦 Generating C header...")

hex_array = []

for b in tflite_model:
    hex_array.append(f"0x{b:02X}")

header = f"""
#ifndef MODEL_DATA_H
#define MODEL_DATA_H

const unsigned char model_data[] = {{
{', '.join(hex_array)}
}};

const unsigned int model_data_len = {len(tflite_model)};

#endif
"""

with open(OUTPUT_HEADER, "w") as f:
    f.write(header)

print("✅ model_data.h generated!")

print("\n" + "=" * 60)
print("🎉 SUCCESS")
print("=" * 60)

print(f"Model size: {len(tflite_model)/1024:.2f} KB")