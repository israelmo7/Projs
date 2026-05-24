import subprocess
import os
import time

SCRIPT_SEQUENCE = [
    "generate_tts.py",
    "prepare_dataset.py",
    "extract_features.py",
    "train_model.py",
    "convert_to_tflite.py",
]


def run_step(script_name):
    print(f"\n--- Starting: {script_name} ---")
    result = subprocess.run(["python3", script_name], capture_output=False)
    if result.returncode != 0:
        print(f"❌ Error in {script_name}. Stopping pipeline.")
        exit(1)
    print(f"✅ Finished: {script_name}")
    time.sleep(1)

def main():
    for script in SCRIPT_SEQUENCE:
        if os.path.exists(script):
            run_step(script)
        else:
            print(f"⚠️ Warning: {script} not found, skipping...")

    print("\n" + "=" * 30)
    print("🏆 FULL PIPELINE COMPLETE!")
    print("=" * 30)


if __name__ == "__main__":
    main()
