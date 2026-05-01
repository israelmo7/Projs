#!/usr/bin/env python3
"""
Stage 1: Image Analyzer
======================
Analyzes photos in the photos/ directory and outputs video_plan.json
"""

import os
import io
import sys
import json
import base64
import PIL.Image
from datetime import datetime
import face_recognition
import requests
from typing import Optional, Tuple, List, Dict, Any

# Configuration
REFERENCE_STAR_PATH = "assets/star.jpg"
PHOTOS_DIR = "photos"
OUTPUT_JSON = "video_plan.json"
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llava"

# Classification categories
VALID_CATEGORIES = ["Portrait", "Friends/Group", "Funny", "Childhood", "Action/Event"]


def image_to_base64(image_path: str) -> str:
    """Resize image and convert to compressed base64 JPEG."""
    with PIL.Image.open(image_path) as img:
        # המרה ל-RGB (למנוע בעיות עם PNG שקופים)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # הקטנה ל-640 פיקסלים (מספיק בהחלט לסיווג)
        max_size = 640
        img.thumbnail((max_size, max_size), PIL.Image.LANCZOS)
            
        # שמירה כ-JPEG דחוס לתוך הזיכרון
        buffered = io.BytesIO()
        img.save(buffered, format="JPEG", quality=70) # 70% איכות זה די והותר
        return base64.b64encode(buffered.getvalue()).decode("utf-8")


def extract_exif_datetime(image_path: str) -> Optional[str]:
    """Extract datetime from EXIF metadata using Pillow."""
    try:
        with PIL.Image.open(image_path) as img:
            exif_data = img.getexif()
            if exif_data:
                # Try different EXIF tags for datetime
                dt_raw = exif_data.get(36867)  # DateTimeOriginal
                if dt_raw:
                    return str(dt_raw)
                dt_raw = exif_data.get(42419)  # DateTime
                if dt_raw:
                    return str(dt_raw)
    except Exception:
        pass
    return None


def check_star_in_photo(image_path: str, star_encodings: List[Any]) -> Tuple[bool, int]:
    """
    Check if reference star appears in the photo using pre-loaded encodings.
    Returns: (found_star, face_count_in_photo)
    """
    try:
        # Load photo and find faces
        photo_image = face_recognition.load_image_file(image_path)
        photo_encodings = face_recognition.face_encodings(photo_image)
        
        if not photo_encodings:
            return False, 0
        
        # Compare encodings
        for star_encoding in star_encodings:
            for photo_encoding in photo_encodings:
                # [0] is required because compare_faces returns a list of booleans
                if face_recognition.compare_faces([star_encoding], photo_encoding, tolerance=0.6)[0]:
                    return True, len(photo_encodings)
        
        return False, len(photo_encodings)
        
    except Exception as e:
        print(f"WARNING: Face recognition failed for '{image_path}': {e}")
        return False, 0


def classify_with_ollama(image_path: str) -> Tuple[Optional[str], Optional[str]]:
    try:
        image_base64 = image_to_base64(image_path)
        
        # פרומפט חדש שמתמקד בתיאור אנושי וסביבתי
        system_prompt = """You are an expert image describer. Your task is to provide a natural, 
concise description of the photo in one sentence.

Focus Priority:
1. The people: Number of people, their actions (smiling, looking away, hugging), and their expressions.
2. The environment: Where they are and what is around them (on a bench, in a room, outdoors).

Example: "A smiling man and a woman beside him sitting on a bench in a sunny park."

After the description, include one of these labels in brackets at the end: [Portrait], [Friends/Group], [Funny], [Childhood], [Action/Event]."""

        payload = {
            "model": OLLAMA_MODEL,
            "prompt": "Describe the people and the environment in this photo.",
            "system": system_prompt,
            "images": [image_base64],
            "stream": False
        }
        
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=60)
        result = response.json()
        raw_output = result.get("response", "").strip()
        
        print(f"  [DEBUG] Ollama description: '{raw_output}'")

        # חילוץ הקטגוריה מתוך הסוגריים (למשל [Portrait])
        category = "General"
        for valid_cat in VALID_CATEGORIES:
            if f"[{valid_cat}]" in raw_output:
                category = valid_cat
                break
        
        # ניקוי התיאור מהתגית בסוף כדי שיישאר רק הטקסט
        clean_description = raw_output.split('[')[0].strip()
        
        return category, clean_description
            
    except Exception as e:
        print(f"  [DEBUG] Exception: {e}")
        return None, None

def process_photo(image_path: str, photo_index: int, total_photos: int, star_encodings: List[Any]) -> Dict[str, Any]:
    """Process a single photo and return its metadata."""
    filename = os.path.basename(image_path)
    print(f"[{photo_index + 1}/{total_photos}] Processing: {filename}")
    
    dt = extract_exif_datetime(image_path)
    
    # Check for star using the pre-loaded encodings
    star_found, face_count = check_star_in_photo(image_path, star_encodings)
    
    # Classify with Ollama
    category, raw_description = classify_with_ollama(image_path)
    
    # Fallback category if Ollama failed
    if not category:
        print(f"  -> Ollama unavailable or unreadable format. Marking as 'NeedsReview'.")
        category = "NeedsReview"
    
    return {
        "filename": filename,
        "path": image_path,
        "datetime": dt,
        "star_present": star_found,
        "face_count": face_count,
        "category": category,
        "raw_description": raw_description
    }


def main():
    """Main entry point."""
    print("=" * 60)
    print("AI Video Director - Stage 1: Image Analyzer")
    print("=" * 60)
    print()
    
    # Validate directories
    if not os.path.exists(PHOTOS_DIR):
        print(f"ERROR: Photos directory not found: '{PHOTOS_DIR}'")
        sys.exit(1)
    
    if not os.path.exists(REFERENCE_STAR_PATH):
        print(f"ERROR: Reference star not found: '{REFERENCE_STAR_PATH}'")
        sys.exit(1)
        
    # Pre-load the star encoding ONCE (Performance fix)
    try:
        print(f"Loading reference star from {REFERENCE_STAR_PATH}...")
        star_image = face_recognition.load_image_file(REFERENCE_STAR_PATH)
        star_encodings = face_recognition.face_encodings(star_image)
        if not star_encodings:
            print(f"ERROR: No face found in reference star at '{REFERENCE_STAR_PATH}'. Hard aborting.")
            sys.exit(1)
        print("Reference star loaded successfully.\n")
    except Exception as e:
        print(f"ERROR: Could not process reference star: {e}")
        sys.exit(1)
    
    # Get all image files
    supported_extensions = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
    image_files = [
        f for f in os.listdir(PHOTOS_DIR)
        if os.path.splitext(f)[1].lower() in supported_extensions
    ]
    
    if not image_files:
        print(f"ERROR: No image files found in '{PHOTOS_DIR}'")
        sys.exit(1)
    
    image_files.sort()  # Process in alphabetical order
    
    print(f"Found {len(image_files)} images to process.\n")
    
    # Process all photos
    photo_data = []
    for idx, filename in enumerate(image_files):
        image_path = os.path.join(PHOTOS_DIR, filename)
        photo = process_photo(image_path, idx, len(image_files), star_encodings)
        photo_data.append(photo)
    
    # Build output structure
    output = {
        "generated_at": datetime.now().isoformat(),
        "total_photos": len(image_files),
        "photos": photo_data
    }
    
    # Save to JSON
    with open(OUTPUT_JSON, "w") as f:
        json.dump(output, f, indent=2)
    
    print()
    print("=" * 60)
    print("Stage 1 Complete!")
    print(f"Output saved to: {OUTPUT_JSON}")
    print("=" * 60)
    
    # Summary statistics
    categories = {}
    for photo in photo_data:
        cat = photo["category"]
        categories[cat] = categories.get(cat, 0) + 1
    
    print("\nCategory Summary:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")


if __name__ == "__main__":
    main()