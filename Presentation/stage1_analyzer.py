#!/usr/bin/env python3
"""
Stage 1: Sensory Media Analyzer Pro 3.0 (Multithreaded + BPM Detection)
=======================================================================
Highly optimized analyzer leveraging ThreadPoolExecutor for M4 architecture.
Extracts visual narrative via Llava and complex acoustic signatures (Peaks, Onset, BPM) via Librosa.
"""

import os
import io
import sys
import json
import base64
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Tuple, List, Dict, Any

import PIL.Image
import PIL.ExifTags
import face_recognition
import requests
import numpy as np
import cv2
import librosa

# Configuration
REFERENCE_STAR_PATH = "assets/star.jpg"
PHOTOS_DIR = "photos"
OUTPUT_JSON = "video_plan.json"
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llava"

VALID_CATEGORIES = ["Portrait", "Friends/Group", "Funny", "Childhood", "Action/Event"]
SUPPORTED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
SUPPORTED_VIDEO_EXT = {".mp4", ".mov", ".avi"}

MAX_WORKERS = 4 # ניצול יעיל של הליבות מול Ollama

# --- Audio Analysis Engine ---

def analyze_audio_for_mashup(video_path: str) -> Dict[str, Any]:
    """מנתח את ה-DNA האקוסטי כולל מציאת BPM (טמפו) לתזמון אומנותי"""
    try:
        y, sr = librosa.load(video_path, sr=None)
        if len(y) == 0:
            return {"energy_score": 0, "peaks": [], "onset_sec": 0, "bpm": 0}

        # עוצמה ונקודות כניסה
        rms = librosa.feature.rms(y=y)[0]
        times = librosa.frames_to_time(range(len(rms)), sr=sr)
        
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        onsets = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr, units='time')
        first_onset = float(onsets[0]) if len(onsets) > 0 else 0.0

        # שיאי אנרגיה
        peak_indices = np.argsort(rms)[-3:]
        peaks = sorted([round(float(times[i]), 2) for i in peak_indices])

        # זיהוי קצב (BPM) לטובת סנכרון עם מוזיקת הרקע!
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        bpm = float(tempo[0]) if isinstance(tempo, (list, np.ndarray)) else float(tempo)

        energy_score = float(np.mean(rms)) * 10 

        return {
            "energy_score": round(min(energy_score, 1.0), 2),
            "peaks": peaks, 
            "onset_sec": round(first_onset, 2),
            "bpm": round(bpm, 1),
            "is_dynamic": bool(np.std(rms) > 0.05)
        }
    except Exception as e:
        print(f"    [!] Audio analysis failed for {os.path.basename(video_path)}: {e}")
        return {"energy_score": 0, "peaks": [], "onset_sec": 0, "bpm": 0}

# --- Visual & System Functions ---

def get_media_datetime(file_path: str, pil_img: Optional[PIL.Image.Image] = None) -> str:
    """שואב תאריך יצירה מקורי מה-EXIF או נופל לתאריך קובץ"""
    try:
        if pil_img:
            exif = pil_img.getexif()
            if exif:
                # 36867 is DateTimeOriginal, 306 is DateTime
                dt_str = exif.get(36867) or exif.get(306)
                if dt_str:
                    # המרה מפורמט EXIF ל-ISO
                    dt_obj = datetime.strptime(str(dt_str), "%Y:%m:%d %H:%M:%S")
                    return dt_obj.isoformat()
    except Exception:
        pass
    
    # Fallback למערכת הקבצים
    try:
        timestamp = os.path.getmtime(file_path)
        return datetime.fromtimestamp(timestamp).isoformat()
    except Exception:
        return datetime.now().isoformat()

def pil_image_to_base64(img: PIL.Image.Image) -> str:
    if img.mode != 'RGB': img = img.convert('RGB')
    img.thumbnail((512, 512), PIL.Image.LANCZOS)
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=70)
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

def extract_strategic_frames(video_path: str) -> Tuple[List[PIL.Image.Image], float]:
    """מחלץ 5 פריימים משמעותיים לאיזון בין מהירות ודיוק נרטיבי"""
    frames = []
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened(): return frames, 0.0
    
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    duration = total_frames / fps if fps > 0 else 0.0
    
    # דגימה ב: 0%, 25%, 50%, 75%, 90%
    indices = [int(total_frames * p) for p in [0.0, 0.25, 0.5, 0.75, 0.9]]
    
    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, min(idx, total_frames - 1))
        ret, frame = cap.read()
        if ret:
            frames.append(PIL.Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
            
    cap.release()
    return frames, duration

def check_star_in_pil_image(pil_img: PIL.Image.Image, star_encodings: List[Any]) -> Tuple[bool, int]:
    try:
        image_array = np.array(pil_img.convert('RGB'))
        photo_encodings = face_recognition.face_encodings(image_array)
        for star_encoding in star_encodings:
            for photo_encoding in photo_encodings:
                if face_recognition.compare_faces([star_encoding], photo_encoding, tolerance=0.6)[0]:
                    return True, len(photo_encodings)
        return False, len(photo_encodings)
    except Exception: 
        return False, 0

def classify_with_ollama(base64_image: str, retries: int = 2) -> Tuple[str, str]:
    """תקשורת חסינה מול Ollama עם מנגנון Retry"""
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": "What is happening? Describe action/vibe. End with: [Portrait], [Friends/Group], [Funny], [Childhood], or [Action/Event].",
        "images": [base64_image],
        "stream": False
    }
    
    for attempt in range(retries):
        try:
            response = requests.post(OLLAMA_API_URL, json=payload, timeout=45)
            if response.status_code == 200:
                raw_output = response.json().get("response", "").strip()
                category = "General"
                for valid_cat in VALID_CATEGORIES:
                    if f"[{valid_cat}]" in raw_output:
                        category = valid_cat
                        break
                clean_desc = raw_output.split('[')[0].strip().replace('\n', ' ')
                return category, clean_desc
        except Exception as e:
            time.sleep(2) # המתנה לפני ניסיון נוסף
            
    return "NeedsReview", "Failed to analyze image."

def process_single_media(file_path: str, star_encodings: List[Any]) -> Dict[str, Any]:
    """הפונקציה המרכזית לעיבוד קובץ בודד (מתוכננת לרוץ בת'רד נפרד)"""
    filename = os.path.basename(file_path)
    ext = os.path.splitext(filename)[1].lower()
    print(f"[*] Analyzing: {filename}...")
    
    media_data = {
        "filename": filename,
        "path": file_path,
        "media_type": "image",
        "duration": 0.0,
        "datetime": None,
        "category": "General",
        "audio_profile": None
    }

    if ext in SUPPORTED_VIDEO_EXT:
        media_data["media_type"] = "video"
        media_data["datetime"] = get_media_datetime(file_path)
        
        frames, duration = extract_strategic_frames(file_path)
        media_data["duration"] = duration
        
        if frames:
            mid_frame = frames[len(frames)//2]
            media_data["star_present"], media_data["face_count"] = check_star_in_pil_image(mid_frame, star_encodings)
            
            descs = []
            for i, f in enumerate(frames):
                _, desc = classify_with_ollama(pil_image_to_base64(f))
                if desc and desc != "Failed to analyze image.":
                    descs.append(desc)
            
            # בניית תיאור וידאו רציף ומאוחד
            media_data["raw_description"] = " | ".join(descs) if descs else "No clear description."
            media_data["category"] = "Action/Event"
            
        media_data["audio_profile"] = analyze_audio_for_mashup(file_path)
        
    else:
        try:
            pil_img = PIL.Image.open(file_path)
            media_data["datetime"] = get_media_datetime(file_path, pil_img)
            media_data["star_present"], media_data["face_count"] = check_star_in_pil_image(pil_img, star_encodings)
            cat, desc = classify_with_ollama(pil_image_to_base64(pil_img))
            media_data["category"] = cat
            media_data["raw_description"] = desc
        except Exception as e:
            print(f"  [-] Failed image {filename}: {e}")
            media_data["category"] = "NeedsReview"
            
    return media_data

def main():
    print("=" * 60)
    print("Stage 1: Sensory Media Analyzer Pro (Multithreaded)")
    print("=" * 60)
    
    if not os.path.exists(PHOTOS_DIR): sys.exit("ERROR: 'photos/' directory missing.")
    if not os.path.exists(REFERENCE_STAR_PATH): sys.exit(f"ERROR: Reference star {REFERENCE_STAR_PATH} missing.")
    
    try:
        star_img = face_recognition.load_image_file(REFERENCE_STAR_PATH)
        star_encodings = face_recognition.face_encodings(star_img)
        if not star_encodings: sys.exit("ERROR: No face found in reference image.")
    except Exception as e:
        sys.exit(f"ERROR loading reference star: {e}")
    
    all_extensions = SUPPORTED_IMAGE_EXT.union(SUPPORTED_VIDEO_EXT)
    files = [os.path.join(PHOTOS_DIR, f) for f in os.listdir(PHOTOS_DIR) if os.path.splitext(f)[1].lower() in all_extensions]
    
    print(f"Found {len(files)} media files. Firing up {MAX_WORKERS} parallel workers...\n")
    
    results = []
    # הרצה מקבילית לפלט חזק ומהיר
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_single_media, f, star_encodings): f for f in files}
        for count, future in enumerate(as_completed(futures), 1):
            try:
                data = future.result()
                results.append(data)
                print(f"  [+] Finished {count}/{len(files)}: {data['filename']}")
            except Exception as e:
                print(f"  [-] Critical failure on a worker thread: {e}")
                
    # סידור כרונולוגי לפני השמירה
    results.sort(key=lambda x: x.get("datetime", ""))
    
    with open(OUTPUT_JSON, "w") as f:
        json.dump({"photos": results}, f, indent=2)
        
    print(f"\nStage 1 Complete! Extremely rich metadata saved to {OUTPUT_JSON}.")

if __name__ == "__main__":
    main()