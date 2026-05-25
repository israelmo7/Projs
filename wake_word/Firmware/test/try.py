import socket
import struct
import numpy as np
import sounddevice as sd
import threading
import time
import os

# ביטול אזהרות GPU של TensorFlow
os.environ['TF_FORCE_GPU_ALLOW_GROWTH'] = 'true'
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
import tensorflow as tf
import librosa

# ==========================================
# הגדרות מערכת
# ==========================================
UDP_IP = "0.0.0.0"
UDP_PORT = 5000
SAMPLE_RATE = 16000
WINDOW_SECONDS = 1.0  # אורך החלון (שנייה אחת של אודיו)
BUFFER_SIZE = int(SAMPLE_RATE * WINDOW_SECONDS)

# נתיב למודל שאימנת
MODEL_PATH = "../models/wake_word_model.h5" 
THRESHOLD = 0.85 # רף הביטחון של המודל כדי לצעוק "זיהיתי!"

# משתנים משותפים בין ה-Threads
audio_buffer = np.zeros(BUFFER_SIZE, dtype=np.float32)
buffer_lock = threading.Lock()
is_running = True

# ==========================================
# פונקציית חילוץ פיצ'רים (חובה להתאים ל-extract_features.py שלך!)
# ==========================================
def extract_live_features(audio_window):
    """
    חילוץ פיצ'רים בזמן אמת, מותאם 1:1 לקוד האימון של נבו.
    """
    # 1. חילוץ הפיצ'רים עם אותם פרמטרים בדיוק כמו בקוד האימון שלך
    mfccs = librosa.feature.mfcc(y=audio_window, sr=16000, n_mfcc=40)
    
    # 2. הטרנספוזיציה (Transpose) שעשית בקוד המקורי שלך: mfccs.T
    mfccs = mfccs.T 
    
    # 3. הוספת מימדים כדי שיתאים למבנה ה-CNN של Keras (Batch, Height, Width, Channels)
    mfccs_reshaped = np.expand_dims(mfccs, axis=0)       # הוספת Batch=1
    mfccs_reshaped = np.expand_dims(mfccs_reshaped, axis=-1) # הוספת Channels=1
    
    return mfccs_reshaped
# ==========================================
# Thread 2: מוח הבינה המלאכותית
# ==========================================
# הגדרת המצבים של המערכת
enum_states = {"LISTENING": 0, "PROCESSING_COMMAND": 1}
current_state = enum_states["LISTENING"]

def ai_processor_thread():
    global audio_buffer, current_state
    
    print("[AI] Loading Model...")
    try:
        model = tf.keras.models.load_model(MODEL_PATH)
        print("[AI] Model Loaded Successfully! System is Live.")
    except Exception as e:
        print(f"[AI] ❌ Failed to load model: {e}")
        return

    while is_running:
        time.sleep(0.1) # בדיקה מהירה יותר (10 פעמים בשנייה) בשביל תגובתיות שיא
        
        if current_state != enum_states["LISTENING"]:
            continue

        with buffer_lock:
            window_copy = audio_buffer.copy()
            
        if np.max(np.abs(window_copy)) < 0.01:
            continue

        try:
            features = extract_live_features(window_copy)
            prediction = model.predict(features, verbose=0)[0][0]
            
            if prediction > THRESHOLD:
                print("\n" + "=" * 50)
                print(f"🤖 🔔 WAKE WORD DETECTED! ({prediction:.2f}) -> Switching State")
                print("=" * 50)
                
                # 1. שינוי מצב - עוצרים את ההאזנה ל-Wake Word
                current_state = enum_states["PROCESSING_COMMAND"]
                
                # 2. איפוס ה-Cache מיד! 
                # ממלאים את הבאפר באפסים כדי שה"נבו" הנוכחי לא יישאר בזיכרון ויקפיץ שוב
                with buffer_lock:
                    audio_buffer.fill(0)
                
                # 3. ביצוע המשימה / הפעלת הפקודה
                execute_wake_word_action()
                
        except Exception as e:
            print(f"[AI Error] {e}")

def execute_wake_word_action():
    global current_state
    print("⚡ [Action] Executing trigger command... (e.g., Recording full command / LED On)")
    
    # כאן יבוא הקוד של מה שקורה אחרי שקראת לו
    # למשל: פתיחת חיבור להקלטת פקודה של 5 שניות, שליחת פקודת API, הדלקת נורה וכו'.
    time.sleep(3) # סימולציה של זמן עבודה/תגובה
    
    # 4. חזרה להאזנה מחדש
    print("⏸️ [Action] Finished. Going back to LISTENING mode...")
    current_state = enum_states["LISTENING"]
# ==========================================
# Thread 1: ניהול רשת ושמע (התראד הראשי)
# ==========================================
def main():
    global audio_buffer, is_running
    
    # פתיחת אפיק אודיו ישיר
    stream = sd.RawOutputStream(samplerate=SAMPLE_RATE, channels=1, dtype='int16')
    stream.start()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))

    print(f"[*] Hub Listening on port {UDP_PORT}.")
    
    # הפעלת תראד ה-AI ברקע
    ai_thread = threading.Thread(target=ai_processor_thread)
    ai_thread.start()

    try:
        while True:
            data, addr = sock.recvfrom(2048)
            
            if len(data) > 8:
                payload = data[8:]
                
                # 1. השמעה בלייב ברמקולים
                stream.write(payload)
                
                # 2. המרה ממספרים שלמים לשברים עשרוניים (-1.0 עד 1.0) עבור ה-AI
                samples_int16 = np.frombuffer(payload, dtype=np.int16)
                samples_float32 = samples_int16.astype(np.float32) / 32768.0
                
                # 3. גלגול החלון שמאלה והכנסת הדאטה החדש לצד ימין
                with buffer_lock:
                    audio_buffer = np.roll(audio_buffer, -len(samples_float32))
                    audio_buffer[-len(samples_float32):] = samples_float32

    except KeyboardInterrupt:
        print("\n[*] Stopping Network and AI...")
        is_running = False
        stream.stop()
        stream.close()
        ai_thread.join()
        print("[*] System Shutdown Complete.")

if __name__ == "__main__":
    main()