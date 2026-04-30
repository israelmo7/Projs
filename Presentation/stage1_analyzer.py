#!/usr/bin/env python3
"""
Stage 1: Image Analyzer
======================
Analyzes photos in the photos/ directory and outputs video_plan.json

Features:
- Extracts EXIF datetime using Pillow
- Uses face_recognition to detect the reference "star" in each photo
- Uses Ollama LLaVA to classify images into categories
- Saves aggregated data to video_plan.json
"""

import os
import sys
import json
import base64
import PIL.Image
from datetime import datetime
import face_recognition
import requests

# Configuration
REFERENCE_STAR_PATH = "assets/star.jpg"
PHOTOS_DIR = "photos"
OUTPUT_JSON = "video_plan.json"
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llava"

# Classification categories
VALID_CATEGORIES = ["Portrait", "Friends/Group", "Funny", "Childhood", "Action/Event"]


def image_to_base64(image_path: str) -> str:
    """Convert image to base64 string for API upload."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def extract_exif_datetime(image_path: str) -> str | None:
    """Extract datetime from EXIF metadata using Pillow."""
    try:
        with PIL.Image.open(image_path) as img:
            exif_data = img.getexif()
            if exif_data:
                # Try different EXIF tags for datetime
                dt_raw = exif_data.get(36867)  # DateTimeOriginal
                if dt_raw:
                    return dt_raw
                dt_raw = exif_data.get(42419)  # DateTime
                if dt_raw:
                    return dt_raw
    except Exception:
        pass
    return None


def check_star_in_photo(image_path: str, star_path: str) -> tuple[bool, int]:
    """
    Check if reference star appears in the photo.
    Returns: (found_star, face_count_in_photo)
    """
    try:
        # Load reference image
        if not os.path.exists(star_path):
            print(f"ERROR: Reference star not found at '{star_path}'. Please place your reference photo there.")
            return False, 0
        
        star_image = face_recognition.load_image_file(star_path)
        star_encodings = face_recognition.face_encodings(star_image)
        
        if not star_encodings:
            print(f"ERROR: No face found in reference star at '{star_path}'. Hard aborting.")
            sys.exit(1)
        
        # Load photo and find faces
        photo_image = face_recognition.load_image_file(image_path)
        photo_encodings = face_recognition.face_encodings(photo_image)
        
        if not photo_encodings:
            return False, 0
        
        # Compare encodings
        for star_encoding in star_encodings:
            for photo_encoding in photo_encodings:
                if face_recognition.compare_faces([star_encoding], photo_encoding, tolerance=0.6)[0]:
                    return True, len(photo_encodings)
        
        return False, len(photo_encodings)
        
    except Exception as e:
        print(f"WARNING: Face recognition failed for '{image_path}': {e}")
        return False, 0


def classify_with_ollama(image_path: str) -> tuple[str | None, str | None]:
    """
    Send image to Ollama LLaVA for classification.
    Returns: (category, raw_description)
    """
    try:
        image_base64 = image_to_base64(image_path)
        
        # System prompt with strict formatting instructions
        system_prompt = """You are an image classifier. Analyze the provided image and return ONLY the category name
or a strict JSON with category and description.

Valid categories:
- Portrait
- Friends/Group  
- Funny
- Childhood
- Action/Event

Return format:
{
  "category": "<one valid category>",
  "raw_description": "<brief description>"
}

Be strict. Only return valid categories.
"""
        
        user_prompt = "Classify this image."
        
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": user_prompt,
            "system": system_prompt,
            "images": [image_base64],
            "stream": False
        }
        
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=60)
        
        if response.status_code != 200:
            print(f"ERROR: Ollama API returned {response.status_code}: {response.text}")
            return None, None
        
        result = response.json()
        raw_output = result.get("response", "")
        
        # Try to parse as JSON first
        try:
            parsed = json.loads(raw_output)
            category = parsed.get("category")
            raw_description = parsed.get("raw_description", "")
            
            if not category:
                print(f"WARNING: Ollama returned invalid JSON. Raw output: {raw_output}")
                return None, raw_output
            
            # Validate category
            if category not in VALID_CATEGORIES:
                print(f"WARNING: Ollama returned unknown category '{category}'. Using fallback.")
                category = None
            
            return category, raw_output
            
        except json.JSONDecodeError:
            # Fallback: try to extract category from plain text
            lines = raw_output.strip().split("\n")
            for line in lines:
                line = line.strip()
                if line.startswith("category:") or line.startswith("Category:"):
                    category = line.split(":", 1)[1].strip()
                    if category and category in VALID_CATEGORIES:
                        return category, raw_output
                elif line in VALID_CATEGORIES:
                    category = line
                    return category, raw_output
            
            # Return raw description if no category found
            return None, raw_output
            
    except Exception as e:
        print(f"ERROR: Failed to call Ollama for '{image_path}': {e}")
        return None, None


def process_photo(image_path: str, photo_index: int, total_photos: int) -> dict:
    """Process a single photo and return its metadata."""
    filename = os.path.basename(image_path)
    print(f"[{photo_index + 1}/{total_photos}] Processing: {filename}")
    
    # Extract EXIF datetime
    dt = extract_exif_datetime(image_path)
    
    # Check for star
    star_found, face_count = check_star_in_photo(image_path, REFERENCE_STAR_PATH)
    
    # Classify with Ollama
    category, raw_description = classify_with_ollama(image_path)
    
    # Fallback category if Ollama failed
    if not category:
        print(f"  -> Ollama unavailable. Marking as 'NeedsReview'.")
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
        photo = process_photo(image_path, idx, len(image_files))
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
