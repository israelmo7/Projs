#!/usr/bin/env python3
"""Master pipeline runner for the Nevo wake word ML pipeline."""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from config import METRICS_JSON_PATH

SCRIPT_SEQUENCE = [
    ("scripts/bootstrap_dataset.py", "Bootstrap clean/noise dataset"),
    ("generate_tts.py", "Generate TTS wake word samples"),
    ("prepare_dataset.py", "Prepare augmented training dataset"),
    ("extract_features.py", "Extract Energy+ZCR features"),
    ("train_model.py", "Train Conv1D model"),
    ("convert_to_tflite.py", "Convert to INT8 TFLite"),
]


def run_step(script_name: str) -> None:
    print(f"\n--- Starting: {script_name} ---")
    result = subprocess.run(
        [sys.executable, script_name],
        cwd=str(ROOT),
        capture_output=False,
    )
    if result.returncode != 0:
        print(f"Error in {script_name}. Stopping pipeline.")
        sys.exit(1)
    print(f"Finished: {script_name}")
    time.sleep(0.5)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Nevo wake word ML pipeline")
    parser.add_argument(
        "--skip-tts",
        action="store_true",
        help="Skip TTS generation (use existing positive_raw files)",
    )
    parser.add_argument(
        "--skip-bootstrap",
        action="store_true",
        help="Skip dataset bootstrap (use existing clean/noise files)",
    )
    args = parser.parse_args()

    for script, description in SCRIPT_SEQUENCE:
        if args.skip_bootstrap and script == "scripts/bootstrap_dataset.py":
            print(f"Skipping bootstrap (--skip-bootstrap)")
            continue
        if args.skip_tts and script == "generate_tts.py":
            print(f"Skipping TTS (--skip-tts)")
            continue

        script_path = ROOT / script
        if not script_path.exists():
            print(f"Warning: {script} not found, skipping...")
            continue

        print(f"\n[{description}]")
        run_step(script)

    print("\n" + "=" * 40)
    print("FULL PIPELINE COMPLETE!")
    print("=" * 40)

    if METRICS_JSON_PATH.exists():
        with open(METRICS_JSON_PATH) as f:
            metrics = json.load(f)
        print(f"Validation accuracy: {metrics.get('val_accuracy', 'N/A')}")
        print(f"Model size: {metrics.get('tflite_size_kb', 'N/A')} KB")


if __name__ == "__main__":
    main()
