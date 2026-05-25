import sounddevice as sd
import numpy as np
import tensorflow as tf
import os
import sys

# הגדרות שזהות ל-ESP32
SAMPLE_RATE = 16000
SIGNAL_LENGTH = 16000
MODEL_INPUT_SIZE = 1280
STEP = SIGNAL_LENGTH // MODEL_INPUT_SIZE

MODEL_PATH = "models/wake_word_model.h5"

if not os.path.exists(MODEL_PATH):
    print(f"❌ Error: Model file '{MODEL_PATH}' not found!")
    sys.exit(1)

print("📦 Loading model...")
model = tf.keras.models.load_model(MODEL_PATH)
print("✅ Model loaded successfully!")

# באפר ששומר שנייה אחת של אודיו אחורה (כמו ה-audioWindow ב-ESP)
audio_buffer = np.zeros(SIGNAL_LENGTH, dtype=np.int16)

def extract_features(audio_window):
    """בדיוק אותה פונקציה מה-ESP32 ומסקריפט החילוץ"""
    features = np.zeros(MODEL_INPUT_SIZE, dtype=np.float32)
    
    for i in range(MODEL_INPUT_SIZE):
        idx = i * STEP
        window = audio_window[idx : idx + STEP]
        if len(window) > 0:
            avg_energy = np.mean(np.abs(window))
            features[i] = (avg_energy / 32768.0) * 127.0
            
    return features.reshape(1, 32, 40, 1)

def audio_callback(indata, frames, time, status):
    global audio_buffer
    if status:
        print(status)
        
    # המרה ל-int16 כדי לדמות את חומרת ה-ESP
    audio_int16 = (indata[:, 0] * 32767).astype(np.int16)
    
    # הזזת הבאפר שמאלה והוספת הדגימות החדשות לימין (בדיוק כמו ב-loop של C++)
    audio_buffer = np.roll(audio_buffer, -frames)
    audio_buffer[-frames:] = audio_int16
    
    # חילוץ הפיצ'רים המלוכלכים של ה-ESP
    features = extract_features(audio_buffer)
    
    # הרצת המודל
    prediction = model.predict(features, verbose=0)[0]
    background_score = prediction[0]
    wake_word_score = prediction[1]
    
    # בדיקת עוצמה להדפסה
    max_vol = np.max(np.abs(audio_int16))
    
    # נדפיס רק כשיש רעש, כדי לא להציף את המסך
    if max_vol > 500:
        print(f"[Vol: {max_vol:5d}] | Background: {background_score:.2f} | WakeWord: {wake_word_score:.2f}")
        
        if wake_word_score > 0.80:
             print("\n" + "="*50)
             print(f"🔥 [🔥] WAKE WORD DETECTED IN LIVE TEST! Confidence: {wake_word_score:.2f}")
             print("="*50 + "\n")

print("\n🎧 Starting Live Microphone Test (ESP32 Simulation Mode)...")
print("Speak into your computer's microphone (Say 'Nevo'). Press Ctrl+C to stop.\n")

# פתיחת צינור אודיו חי בחלונות של בערך חצי שנייה (כדי לא לאמץ את המעבד יותר מדי בפייתון)
try:
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, callback=audio_callback, blocksize=4000):
        while True:
            pass
except KeyboardInterrupt:
    print("\n⏹️ Test stopped.")