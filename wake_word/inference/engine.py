"""Shared inference engine for Keras and TFLite models."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np

from config import MODEL_H5_PATH, MODEL_TFLITE_PATH, WAKE_THRESHOLD
from features import extract_features_int16, extract_features_matrix


@dataclass
class InferenceResult:
    background: float
    wake_word: float
    is_wake: bool

    @classmethod
    def from_scores(cls, scores: np.ndarray, threshold: float = WAKE_THRESHOLD) -> InferenceResult:
        bg, wake = float(scores[0]), float(scores[1])
        return cls(background=bg, wake_word=wake, is_wake=wake >= threshold)


class InferenceEngine:
    def __init__(
        self,
        model_path: Path | None = None,
        backend: Literal["auto", "keras", "tflite"] = "auto",
    ):
        self.model_path = model_path
        self.backend = backend
        self._keras_model = None
        self._tflite_interpreter = None
        self._input_details = None
        self._output_details = None
        self._load()

    def _resolve_backend(self) -> str:
        if self.backend != "auto":
            return self.backend
        if MODEL_TFLITE_PATH.exists():
            return "tflite"
        if MODEL_H5_PATH.exists():
            return "keras"
        raise FileNotFoundError("No model found (.tflite or .h5)")

    def _load(self) -> None:
        backend = self._resolve_backend()
        if backend == "tflite":
            import tensorflow as tf

            path = self.model_path or MODEL_TFLITE_PATH
            self._tflite_interpreter = tf.lite.Interpreter(model_path=str(path))
            self._tflite_interpreter.allocate_tensors()
            self._input_details = self._tflite_interpreter.get_input_details()
            self._output_details = self._tflite_interpreter.get_output_details()
            self._backend_name = "tflite"
        else:
            import os

            os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
            import tensorflow as tf

            path = self.model_path or MODEL_H5_PATH
            self._keras_model = tf.keras.models.load_model(str(path))
            self._backend_name = "keras"

    @property
    def loaded(self) -> bool:
        return self._keras_model is not None or self._tflite_interpreter is not None

    @property
    def backend_name(self) -> str:
        return self._backend_name

    def predict_int16(self, audio_int16: np.ndarray) -> InferenceResult:
        features_matrix = extract_features_matrix(audio_int16)
        return self.predict_features(features_matrix)

    def predict_features(self, features: np.ndarray) -> InferenceResult:
        if features.ndim == 1:
            features = features.reshape(1, 64, 2)
        elif features.ndim == 2:
            features = features.reshape(1, *features.shape)

        if self._keras_model is not None:
            scores = self._keras_model.predict(features, verbose=0)[0]
            return InferenceResult.from_scores(scores)

        sample = features.astype(np.float32)
        input_scale, input_zero_point = self._input_details[0]["quantization"]
        sample_q = (sample / input_scale + input_zero_point).astype(np.int8)

        self._tflite_interpreter.set_tensor(self._input_details[0]["index"], sample_q)
        self._tflite_interpreter.invoke()
        output_q = self._tflite_interpreter.get_tensor(self._output_details[0]["index"])

        output_scale, output_zero_point = self._output_details[0]["quantization"]
        scores = (output_q.astype(np.float32) - output_zero_point) * output_scale
        return InferenceResult.from_scores(scores[0])

    def predict_flat(self, flat_features: np.ndarray) -> InferenceResult:
        matrix = flat_features.reshape(64, 2)
        return self.predict_features(matrix)
