import os
import time
import numpy as np
import librosa
import pyaudio
from tensorflow.keras.models import load_model

# === Configuration ===
SAMPLE_RATE = 16000
CHUNK_DURATION = 1.0 
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_DURATION)
DETECTION_THRESHOLD = 0.5  # הורדתי ל-0.5 כדי שיהיה קל יותר לזהות בהתחלה
COOLDOWN_SECONDS = 2.0
MODEL_PATH = "models/wake_word_model.h5"

def process_audio_chunk(audio_bytes):
    # 1. המרה למערך נומרי
    audio_int16 = np.frombuffer(audio_bytes, dtype=np.int16)
    audio_float = audio_int16.astype(np.float32)
    
    # 2. נרמול עוצמה (Peak Normalization) - קריטי למיקרופון!
    max_val = np.max(np.abs(audio_float))
    if max_val > 0:
        audio_float = audio_float / max_val
    else:
        audio_float = audio_float / 32768.0 # fallback
        
    # 3. חילוץ MFCC
    mfccs = librosa.feature.mfcc(y=audio_float, sr=SAMPLE_RATE, n_mfcc=40)
    mfccs = mfccs.T # הופך ל- (frames, 40)
    
    # 4. התאמת גודל ל-32 פריימים (בדיוק מה שהמודל מצפה)
    target_frames = 32
    if mfccs.shape[0] < target_frames:
        pad_width = [(0, target_frames - mfccs.shape[0]), (0, 0)]
        mfccs = np.pad(mfccs, pad_width, mode='constant')
    else:
        mfccs = mfccs[:target_frames, :]
        
    # 5. הוספת ממד Batch ו-Channel: (1, 32, 40, 1)
    return mfccs.reshape(1, target_frames, 40, 1)

def detect_wake_word():
    print("\n" + "="*50)
    print("🚀 HELLO NEVO - LIVE DETECTION READY")
    print("="*50)
    
    if not os.path.exists(MODEL_PATH):
        print(f"❌ Error: Model not found at {MODEL_PATH}")
        return

    model = load_model(MODEL_PATH)
    p = pyaudio.PyAudio()
    
    try:
        stream = p.open(format=pyaudio.paInt16,
                        channels=1,
                        rate=SAMPLE_RATE,
                        input=True,
                        frames_per_buffer=CHUNK_SIZE)
        
        print("\nListening... (Try saying 'Hey Nevo')")
        print("Press Ctrl+C to stop.\n")
        
        last_detection_time = 0
        
        while True:
            # קריאת האודיו
            audio_bytes = stream.read(CHUNK_SIZE, exception_on_overflow=False)
            
            # בדיקת Cooldown
            if time.time() - last_detection_time < COOLDOWN_SECONDS:
                continue
                
            # עיבוד
            input_data = process_audio_chunk(audio_bytes)
            
            # חיזוי
            prediction = model.predict(input_data, verbose=0)
            confidence = float(prediction[0][0])
            
            # הדפסת Confidence בזמן אמת (לצורך דיבאג)
            if confidence > 0.01:
                print(f"\rConfidence: {confidence:.4f} ", end="", flush=True)
            
            # זיהוי!
            if confidence >= DETECTION_THRESHOLD:
                print(f"\n\n🚨 [WAKE WORD DETECTED!] Confidence: {confidence:.2%}")
                print("------------------------------------------\n")
                last_detection_time = time.time()
                
    except KeyboardInterrupt:
        print("\n\nStopping gracefully...")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()

if __name__ == "__main__":
    detect_wake_word()
