"""Background ML pipeline runner."""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import METRICS_JSON_PATH


class PipelineState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class PipelineStatus:
    state: PipelineState = PipelineState.IDLE
    current_step: str = ""
    progress: float = 0.0
    message: str = ""
    started_at: float | None = None
    finished_at: float | None = None
    error: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "current_step": self.current_step,
            "progress": self.progress,
            "message": self.message,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
            "metrics": self.metrics,
        }


class PipelineWorker:
    STEPS = [
        ("scripts/bootstrap_dataset.py", "Bootstrap dataset", 0.1),
        ("generate_tts.py", "Generate TTS", 0.2),
        ("prepare_dataset.py", "Prepare dataset", 0.35),
        ("extract_features.py", "Extract features", 0.5),
        ("train_model.py", "Train model", 0.75),
        ("convert_to_tflite.py", "Convert to TFLite", 0.95),
    ]

    def __init__(self) -> None:
        self.status = PipelineStatus()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    def start(self, skip_tts: bool = False, skip_bootstrap: bool = False) -> bool:
        with self._lock:
            if self.status.state == PipelineState.RUNNING:
                return False
            self.status = PipelineStatus(
                state=PipelineState.RUNNING,
                started_at=time.time(),
                message="Starting pipeline...",
            )
            self._thread = threading.Thread(
                target=self._run,
                args=(skip_tts, skip_bootstrap),
                daemon=True,
            )
            self._thread.start()
            return True

    def _run(self, skip_tts: bool, skip_bootstrap: bool) -> None:
        try:
            total = len(self.STEPS)
            for idx, (script, label, progress) in enumerate(self.STEPS):
                if skip_bootstrap and script == "scripts/bootstrap_dataset.py":
                    continue
                if skip_tts and script == "generate_tts.py":
                    continue

                self.status.current_step = label
                self.status.progress = progress
                self.status.message = f"Running {label}..."

                result = subprocess.run(
                    [sys.executable, script],
                    cwd=str(ROOT),
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    raise RuntimeError(
                        f"{label} failed:\n{result.stderr[-2000:]}"
                    )

            self.status.progress = 1.0
            self.status.state = PipelineState.COMPLETED
            self.status.message = "Pipeline completed successfully"
            self.status.finished_at = time.time()

            if METRICS_JSON_PATH.exists():
                with open(METRICS_JSON_PATH) as f:
                    self.status.metrics = json.load(f)

        except Exception as exc:
            self.status.state = PipelineState.FAILED
            self.status.error = str(exc)
            self.status.message = f"Pipeline failed: {exc}"
            self.status.finished_at = time.time()

    def get_status(self) -> dict[str, Any]:
        with self._lock:
            return self.status.to_dict()
