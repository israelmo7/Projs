import sounddevice as sd
import numpy as np
import tensorflow as tf
import os
import sys
import time

# ====================== Settings ======================
SAMPLE_RATE = 16000
DURATION = 3  # seconds
SIGNAL_LENGTH = SAMPLE_RATE * DURATION

MODEL_PATH = "models/wake_word_model.h5"

if not os.path.exists(MODEL_PATH):
    print(f"❌ Error: Model file '{MODEL_PATH}' not found!")
    sys.exit(1)

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

print("📦 Loading model...")
model = tf.keras.models.load_model(MODEL_PATH)
print(f"✅ Model loaded successfully! Input shape: {model.input_shape}")

# ====================== Feature Extraction ======================
WINDOWS = 64
STEP = SIGNAL_LENGTH // WINDOWS

def extract_features(audio):
    features = np.zeros((WINDOWS, 2), dtype=np.float32)
    
    for i in range(WINDOWS):
        start = i * STEP
        window = audio[start : start + STEP]
        
        if len(window) > 0:
            # Energy
            avg_energy = np.mean(np.abs(window))
            features[i, 0] = avg_energy / 32768.0
            
            # Zero Crossing Rate
            crossings = np.sum((window[1:] * window[:-1]) < 0)
            features[i, 1] = crossings / STEP
    
    return features.reshape(1, WINDOWS, 2)


# ====================== Main Continuous Loop ======================
print("\n🎙️ Starting continuous recording & playback loop...")
print("Each cycle: Record 3s → Analyze → Play back")
print("Press Ctrl+C to stop.\n")

try:
    while True:
        # --- Recording ---
        print(f"🎤 Recording {DURATION} seconds... Speak now!")
        audio_recording = sd.rec(int(SAMPLE_RATE * DURATION), 
                               samplerate=SAMPLE_RATE, 
                               channels=1, 
                               dtype=np.int16)
        sd.wait()

        audio = audio_recording.flatten()

        # --- Analysis ---
        print("🔍 Analyzing with model...")
        features = extract_features(audio)
        prediction = model.predict(features, verbose=0)[0]

        background_score = prediction[0]
        wake_word_score = prediction[1]

        print("="*65)
        print(f"📊 RESULTS (Last {DURATION} seconds)")
        print(f"   Background Score : {background_score:.4f}")
        print(f"   Wake Word Score  : {wake_word_score:.4f}")
        print("="*65)

        if wake_word_score > 0.80:
            print("🔥🔥 WAKE WORD DETECTED! 🔥🔥")
        elif wake_word_score > 0.60:
            print("⚠️  Possible wake word detected")
        else:
            print("❌ No wake word detected")

        # --- Playback ---
        print(f"▶️ Playing back the recording...")
        sd.play(audio, SAMPLE_RATE)
        sd.wait()

        print("-" * 65)
        print("Starting next cycle...\n")
        # Small pause between cycles (optional)
        time.sleep(0.3)

except KeyboardInterrupt:
    print("\n\n⏹️ Program stopped by user.")
except Exception as e:
    print(f"\n❌ Error occurred: {e}")