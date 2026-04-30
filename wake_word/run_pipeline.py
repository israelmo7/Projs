import subprocess
import os

def run_step(script_name):
    print(f"\n--- Starting: {script_name} ---")
    result = subprocess.run(["python", script_name], capture_output=False)
    if result.returncode != 0:
        print(f"❌ Error in {script_name}. Stopping pipeline.")
        exit(1)
    print(f"✅ Finished: {script_name}")

def main():
    # רשימת הסקריפטים לפי הסדר
    pipeline = [
        "generate_tts.py",      # מייצר קולות
        "prepare_dataset.py",   # מארגן את התיקיות
        "extract_features.py",  # הופך למספרים
        "train_model.py",       # מאמן את המודל
        "convert_to_tflite.py"  # (הסקריפט שנכתוב עכשיו להמרה ל-ESP)
    ]
    
    for script in pipeline:
        if os.path.exists(script):
            run_step(script)
        else:
            print(f"⚠️ Warning: {script} not found, skipping...")

    print("\n" + "="*30)
    print("🏆 FULL PIPELINE COMPLETE!")
    print("="*30)

if __name__ == "__main__":
    main()
