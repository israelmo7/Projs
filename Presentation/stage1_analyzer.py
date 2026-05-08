#!/usr/bin/env python3
"""
Stage 1: Sensory Media Analyzer Pro 3.1 (Incremental + Force Flag)
==================================================================
Highly optimized analyzer leveraging ThreadPoolExecutor for M4 architecture.
Extracts visual narrative via Llava and complex acoustic signatures (Peaks, Onset, BPM) via Librosa.
Features incremental saving (skips existing) and a --force flag.
"""

import os
import io
import sys
import json
import base64
import time
import argparse
import gc
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Tuple, List, Dict, Any
import subprocess
import uuid

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

MAX_WORKERS = 2 # ניצול יעיל של הליבות מול Ollama

# --- Audio Analysis Engine ---
def analyze_audio_for_mashup(video_path: str) -> Dict[str, Any]:
    """מנתח את ה-DNA האקוסטי בגרסה חסינה המונעת התנגשויות ת'רדים ו-Segmentation Faults"""
    unique_id = uuid.uuid4().hex[:8]
    temp_wav = f"temp_audio_{unique_id}.wav"
    
    try:
        # 1. חילוץ האודיו החוצה בצורה בטוחה
        cmd = [
            "ffmpeg", "-y", "-i", video_path, 
            "-vn", "-acodec", "pcm_s16le", "-ar", "22050", "-ac", "1", 
            temp_wav
        ]
        subprocess.run(cmd, capture_output=True, check=False)
        
        if not os.path.exists(temp_wav):
            return {"energy_score": 0, "peaks": [], "onset_sec": 0, "bpm": 0, "is_dynamic": False}

        # 2. טעינה מקובץ WAV
        y, sr = librosa.load(temp_wav, sr=None)
        if len(y) == 0:
            return {"energy_score": 0, "peaks": [], "onset_sec": 0, "bpm": 0, "is_dynamic": False}

        rms = librosa.feature.rms(y=y)[0]
        times = librosa.frames_to_time(range(len(rms)), sr=sr)
        
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        onsets = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr, units='time')
        first_onset = float(onsets[0]) if len(onsets) > 0 else 0.0

        peak_indices = np.argsort(rms)[-3:]
        peaks = sorted([round(float(times[i]), 2) for i in peak_indices])

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
        return {"energy_score": 0, "peaks": [], "onset_sec": 0, "bpm": 0, "is_dynamic": False}
    finally:
        if os.path.exists(temp_wav):
            try: os.remove(temp_wav)
            except: pass

# --- Visual & System Functions ---

def get_media_datetime(file_path: str, pil_img: Optional[PIL.Image.Image] = None) -> str:
    try:
        if pil_img:
            exif = pil_img.getexif()
            if exif:
                dt_str = exif.get(36867) or exif.get(306)
                if dt_str:
                    dt_obj = datetime.strptime(str(dt_str), "%Y:%m:%d %H:%M:%S")
                    return dt_obj.isoformat()
    except Exception: pass
    
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
    frames = []
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened(): return frames, 0.0
    
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    duration = total_frames / fps if fps > 0 else 0.0
    
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
            time.sleep(2) 
            
    return "NeedsReview", "Failed to analyze image."

def process_single_media(file_path: str, star_encodings: List[Any]) -> Dict[str, Any]:
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
            
    # ניקוי זיכרון אגרסיבי למניעת קריסות (Segmentation Faults)
    gc.collect()
    return media_data

def main():
    # הגדרת אופציות דרך שורת הפקודה
    parser = argparse.ArgumentParser(description="Sensory Media Analyzer Pro")
    parser.add_argument("--force", action="store_true", help="Force re-analysis of all files, ignoring existing data.")
    args = parser.parse_args()

    print("=" * 60)
    print("Stage 1: Sensory Media Analyzer Pro (Incremental Mode)")
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
    all_files = [os.path.join(PHOTOS_DIR, f) for f in os.listdir(PHOTOS_DIR) if os.path.splitext(f)[1].lower() in all_extensions]
    
    # חילוץ מידע קיים אם קיים ולא הופעל דגל ה-force
    existing_data = {}
    if not args.force and os.path.exists(OUTPUT_JSON):
        try:
            with open(OUTPUT_JSON, "r") as f:
                old_data = json.load(f)
                for item in old_data.get("photos", []):
                    # נשמור רק פריטים שכבר עברו ניתוח ויש להם תיאור
                    if item.get("raw_description") and item.get("raw_description") != "Failed to analyze image.":
                        existing_data[item["filename"]] = item
            print(f"[*] Found {len(existing_data)} previously analyzed items in {OUTPUT_JSON}.")
        except Exception as e:
            print(f"[*] Warning: Could not read existing {OUTPUT_JSON}: {e}")

    results = []
    files_to_process = []

    # סינון קבצים שכבר נותחו
    for f in all_files:
        filename = os.path.basename(f)
        if filename in existing_data:
            print(f"  [>] Skipping {filename} (Already analyzed)")
            results.append(existing_data[filename])
        else:
            files_to_process.append(f)

    if files_to_process:
        print(f"\n[*] Firing up {MAX_WORKERS} parallel workers for {len(files_to_process)} NEW media files...\n")
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(process_single_media, f, star_encodings): f for f in files_to_process}
            for count, future in enumerate(as_completed(futures), 1):
                try:
                    data = future.result()
                    results.append(data)
                    print(f"  [+] Finished {count}/{len(files_to_process)}: {data['filename']}")
                except Exception as e:
                    print(f"  [-] Critical failure on a worker thread: {e}")
    else:
        print("\n[*] All files are already analyzed! (Use --force to run anyway)")

    # סידור כרונולוגי לפני השמירה מחדש
    results.sort(key=lambda x: x.get("datetime", ""))
    
    with open(OUTPUT_JSON, "w") as f:
        json.dump({"photos": results}, f, indent=2)
        
    print(f"\nStage 1 Complete! Extremely rich metadata saved to {OUTPUT_JSON}.")

if __name__ == "__main__":
    main()