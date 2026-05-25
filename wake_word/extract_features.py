#!/usr/bin/env python3
"""
Extract ESP32-Compatible Features from Audio Dataset
Outputs NumPy arrays ready for training the CNN model. (.npy files)

"""

import os
import numpy as np
import librosa
from sklearn.model_selection import train_test_split

# === הגדרות נתיבים ===
# ודא שיש לך תיקיית 'dataset' ובתוכה שתי תיקיות: 'positive_raw' ו-'background'
DATASET_PATH = "dataset" 
OUTPUT_DIR = "prepared_features"

SAMPLE_RATE = 16000

def extract_esp32_compatible_features(audio_data_int16):
    """
    מחלץ פיצ'רים בפייתון בדיוק באותה צורה שה-ESP32 מחשב אותם בחומרה.
    מקבל מערך אודיו ליניארי של שנייה אחת (16000 דגימות ב-int16).
    """
    SIGNAL_LENGTH = 16000
    MODEL_INPUT_SIZE = 1280
    
    # ודא שהקובץ הוא בדיוק באורך של שנייה אחת
    if len(audio_data_int16) < SIGNAL_LENGTH:
        audio_data_int16 = np.pad(audio_data_int16, (0, SIGNAL_LENGTH - len(audio_data_int16)), 'constant')
    else:
        audio_data_int16 = audio_data_int16[:SIGNAL_LENGTH]
        
    # שינוי ל-float32 כדי להתאים במדויק לקלט החדש של ה-ESP32
    features = np.zeros(MODEL_INPUT_SIZE, dtype=np.float32)
    step = SIGNAL_LENGTH // MODEL_INPUT_SIZE # שווה ל-12
    
    # חישוב ממוצע אנרגיה על כל החלון כדי לייצר "מעטפת קול" חסינה ל-Aliasing
    for i in range(MODEL_INPUT_SIZE):
        idx = i * step
        # לקיחת חלון של 12 דגימות
        window = audio_data_int16[idx : idx + step]
        if len(window) > 0:
            # ממוצע אמת במקום דגימה בודדת
            avg_energy = np.mean(np.abs(window))
            # נרמול לטווח 0.0 עד 127.0 ושמירה כ-float
            features[i] = (avg_energy / 32768.0) * 127.0
            
    # החזרת המטריצה במימדים שהמודל הדו-מימדי מצפה להם
    return features.reshape(32, 40)

def load_data():
    X = []
    y = []
    
    # מיפוי התיקיות לתוויות (0 לרקע, 1 למילת התעוררות)
    labels_map = {
        "background": 0,
        "positive_raw": 1
    }
    
    print("\n" + "="*50)
    print("🚀 Starting Feature Extraction (ESP32 Mode - Envelope Averaging)...")
    print("="*50)
    
    for folder_name, label in labels_map.items():
        folder_path = os.path.join(DATASET_PATH, folder_name)
        if not os.path.exists(folder_path):
            print(f"⚠️ Warning: Folder '{folder_path}' not found. Skipping...")
            continue
            
        files = [f for f in os.listdir(folder_path) if f.endswith('.wav')]
        print(f"📁 Processing {len(files)} files in '{folder_name}'...")
        
        for file_name in files:
            file_path = os.path.join(folder_path, file_name)
            
            try:
                # 1. טעינת האודיו (librosa מחזיר float32 בין -1 ל-1)
                audio_float, _ = librosa.load(file_path, sr=SAMPLE_RATE)
                
                # 2. המרה קריטית ל-int16 כדי להתאים למתמטיקה של ה-ESP32
                audio_int16 = np.int16(audio_float * 32767)
                
                # 3. חילוץ הפיצ'רים המותאמים לחומרה עם ממוצע המעטפת
                features = extract_esp32_compatible_features(audio_int16)
                
                X.append(features)
                y.append(label)
                
            except Exception as e:
                print(f"❌ Error processing {file_name}: {e}")
                
    return np.array(X), np.array(y)

def main():
    X, y = load_data()
    
    if len(X) == 0:
        print("\n❌ No data processed! Please check your 'dataset' folder structure.")
        return
        
    print(f"\n✅ Total samples extracted: {len(X)}")
    print(f"📊 Features shape: {X.shape}")
    
    # פיצול לסט אימון וסט ולידציה (80% / 20%)
    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # שמירת הקבצים בתיקייה המוכנה לאימון
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    np.save(os.path.join(OUTPUT_DIR, "data_train.npy"), X_train)
    np.save(os.path.join(OUTPUT_DIR, "data_val.npy"), X_val)
    np.save(os.path.join(OUTPUT_DIR, "y_data_train.npy"), y_train)
    np.save(os.path.join(OUTPUT_DIR, "y_data_val.npy"), y_val)
    
    print("\n" + "="*50)
    print(f"💾 Success! Files saved to '{OUTPUT_DIR}' directory.")
    print("Train split:", X_train.shape)
    print("Val split:", X_val.shape)
    print("="*50)

if __name__ == "__main__":
    main()