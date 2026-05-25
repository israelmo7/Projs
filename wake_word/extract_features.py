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
    משולב ZCR + Energy (אנרגיה ותדר) למניעת עיוורון הרשת.
    מקבל מערך אודיו ליניארי של שנייה אחת (16000 דגימות ב-int16).
    """
    SIGNAL_LENGTH = 16000
    WINDOWS = 64
    STEP = SIGNAL_LENGTH // WINDOWS # 250 דגימות לכל חלון של 15.6 מילי-שנייה
    
    # ודא שהקובץ הוא בדיוק באורך של שנייה אחת
    if len(audio_data_int16) < SIGNAL_LENGTH:
        audio_data_int16 = np.pad(audio_data_int16, (0, SIGNAL_LENGTH - len(audio_data_int16)), 'constant')
    else:
        audio_data_int16 = audio_data_int16[:SIGNAL_LENGTH]
        
    # מטריצה דו-מימדית: 64 חלונות זמן, 2 פיצ'רים בכל חלון
    features = np.zeros((WINDOWS, 2), dtype=np.float32)
    
    for i in range(WINDOWS):
        start = i * STEP
        window = audio_data_int16[start : start + STEP]
        
        if len(window) > 0:
            # 🌟 פיצ'ר 1: אנרגיה ממוצעת בחלון (עוצמת הקול)
            avg_energy = np.mean(np.abs(window))
            features[i, 0] = avg_energy / 32768.0
            
            # 🌟 פיצ'ר 2: ZCR (Zero Crossing Rate - תדר הגל)
            crossings = 0
            for j in range(1, len(window)):
                if (window[j] >= 0 and window[j-1] < 0) or (window[j] < 0 and window[j-1] >= 0):
                    crossings += 1
            features[i, 1] = crossings / STEP
            
    # מחזיר מטריצה נקייה בגודל (64, 2) ללא צורך ב-Reshape דו-מימדי ישן
    return features
    
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