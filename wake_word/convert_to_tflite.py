#!/usr/bin/env python3
"""Convert Keras model to TFLite and generate C header for ESP32."""

import json
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
import tensorflow as tf

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from config import (
    METRICS_JSON_PATH,
    MODEL_HEADER_PATH,
    MODEL_H5_PATH,
    MODEL_TFLITE_PATH,
    PREPARED_FEATURES_DIR,
)

X_train = np.load(PREPARED_FEATURES_DIR / "data_train.npy").astype(np.float32)


def representative_data_gen():
    for i in range(min(200, len(X_train))):
        yield [X_train[i : i + 1].astype(np.float32)]


def convert_model(model: tf.keras.Model) -> tuple[bytes, str]:
    """Export SavedModel first (required for TF 2.16+), then convert."""
    with tempfile.TemporaryDirectory() as tmpdir:
        export_dir = str(Path(tmpdir) / "saved_model")
        model.export(export_dir)

        strategies = [
            ("int8", lambda c: _apply_int8(c)),
            ("dynamic", lambda c: _apply_dynamic(c)),
            ("float32", lambda c: None),
        ]

        last_error = None
        for name, configure in strategies:
            try:
                converter = tf.lite.TFLiteConverter.from_saved_model(export_dir)
                configure(converter)
                print(f"Trying {name} conversion...")
                tflite_model = converter.convert()
                print(f"Success with {name} strategy")
                return tflite_model, name
            except Exception as exc:
                print(f"{name} conversion failed: {exc}")
                last_error = exc

    raise RuntimeError(f"All conversion strategies failed: {last_error}")


def _apply_int8(converter: tf.lite.TFLiteConverter) -> None:
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.representative_dataset = representative_data_gen
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    converter.inference_input_type = tf.int8
    converter.inference_output_type = tf.int8


def _apply_dynamic(converter: tf.lite.TFLiteConverter) -> None:
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.representative_dataset = representative_data_gen


def write_header(tflite_model: bytes, path: Path) -> None:
    hex_array = [f"0x{b:02X}" for b in tflite_model]
    header = f"""#ifndef MODEL_DATA_H
#define MODEL_DATA_H

const unsigned char model_data[] = {{
{', '.join(hex_array)}
}};

const unsigned int model_data_len = {len(tflite_model)};

#endif
"""
    path.write_text(header)


if not MODEL_H5_PATH.exists():
    raise FileNotFoundError(f"Missing model: {MODEL_H5_PATH}")

print(f"Loading model: {MODEL_H5_PATH}")
model = tf.keras.models.load_model(str(MODEL_H5_PATH))

tflite_model, strategy = convert_model(model)

MODEL_TFLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
MODEL_TFLITE_PATH.write_bytes(tflite_model)
print(f"Saved TFLite: {MODEL_TFLITE_PATH} ({len(tflite_model) / 1024:.2f} KB, {strategy})")

write_header(tflite_model, MODEL_HEADER_PATH)
print(f"Generated {MODEL_HEADER_PATH}")

if METRICS_JSON_PATH.exists():
    with open(METRICS_JSON_PATH) as f:
        metrics = json.load(f)
else:
    metrics = {}

metrics["tflite_size_kb"] = round(len(tflite_model) / 1024, 2)
metrics["tflite_strategy"] = strategy
metrics["model_header_bytes"] = len(tflite_model)

with open(METRICS_JSON_PATH, "w") as f:
    json.dump(metrics, f, indent=2)

print("Conversion complete!")
