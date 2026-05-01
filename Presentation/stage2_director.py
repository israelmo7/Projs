#!/usr/bin/env python3
"""
Stage 2: AI Director - Video Edit Decision List Generator
"""

import json
import random
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

# Constants
STAR_PRESENCE_BONUS = 100
SOLO_FACE_BONUS = 10
GROUP_FACE_BONUS = 15
CROWD_PENALTY = 20
CHILDHOOD_KEYWORD_BONUS = 22
FUNNY_KEYWORD_BONUS = 25

# Duration presets (in seconds)
DURATION_PORTRAIT_CHILDHOOD = 3.0
DURATION_FUNNY_ACTION = 0.8
DURATION_DEFAULT = 2.0

# Visual effects pool
EFFECTS = ["zoom_in", "zoom_out", "pan_left", "pan_right"]

# Keyword mappings
CHILDHOOD_KEYWORDS = ["baby", "kid", "child", "young"]
FUNNY_KEYWORDS = ["laugh", "funny", "joke", "hilarious", "amused"]
ACTION_KEYWORDS = ["run", "walk", "move", "dance", "action"]
PORTRAIT_KEYWORDS = ["portrait", "pose", "looking at camera", "smile"]

# Input/output paths
INPUT_FILE = "video_plan.json"
OUTPUT_FILE = "edit_decision_list.json"


def extract_datetime_from_path(path: str) -> Optional[datetime]:
    """Try to extract datetime from file path/filename if EXIF date is missing."""
    patterns = [
        r'(\d{4})/(\d{2})/(\d{2})',
        r'(\d{2})-(\d{2})-(\d{4})',
        r'(\d{4})-(\d{2})-(\d{2})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, path)
        if match:
            try:
                year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
                return datetime(year, month, day)
            except ValueError:
                continue
    return None


def extract_datetime_from_filename(filename: str) -> Optional[datetime]:
    """Try to extract datetime from filename."""
    base_name = Path(filename).stem
    base_name = re.sub(r'^\d+', '', base_name)
    
    patterns = [
        r'(\d{4})-?(\d{1,2})-?(\d{1,2})',
        r'(\d{1,2})/?(\d{1,2})/?(\d{4})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, base_name)
        if match:
            try:
                parts = [int(p) for p in match.groups()]
                for perm in [(0,1,2), (2,0,1), (1,2,0)]:
                    try:
                        year, month, day = parts[perm[0]], parts[perm[1]], parts[perm[2]]
                        return datetime(year, month, day)
                    except ValueError:
                        continue
            except ValueError:
                continue
    return None


def get_file_datetime(photo: Dict[str, Any]) -> datetime:
    """Get datetime for a photo, falling back to filename/metadata if needed."""
    if photo.get("datetime"):
        # Handle string dates if they come as strings
        if isinstance(photo["datetime"], str):
            try:
                return datetime.fromisoformat(photo["datetime"].replace('Z', '+00:00'))
            except ValueError:
                pass
        return photo["datetime"]
    
    dt = extract_datetime_from_filename(photo.get("filename", ""))
    if dt: return dt
    
    dt = extract_datetime_from_path(photo.get("path", ""))
    if dt: return dt
    
    return datetime.now()


def extract_keywords(description: str, keywords: List[str]) -> bool:
    if not description: return False
    description_lower = description.lower()
    for keyword in keywords:
        pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
        if re.search(pattern, description_lower):
            return True
    return False


def extract_action_from_description(description: str) -> bool:
    if not description: return False
    action_phrases = ["in motion", "moving", "walking", "running", "action"]
    for phrase in action_phrases:
        if phrase in description.lower():
            return True
    return False


def calculate_score(photo: Dict[str, Any]) -> int:
    score = 0
    if photo.get("star_present", False):
        score += STAR_PRESENCE_BONUS
    
    face_count = photo.get("face_count", 0)
    if face_count == 1:
        score += SOLO_FACE_BONUS
    elif 2 <= face_count <= 5:
        score += GROUP_FACE_BONUS
    elif not photo.get("star_present", False) and face_count > 5:
        score -= CROWD_PENALTY
    
    raw_desc = photo.get("raw_description", "")
    if photo.get("category") == "General":
        if extract_keywords(raw_desc, CHILDHOOD_KEYWORDS):
            score += CHILDHOOD_KEYWORD_BONUS
        if extract_keywords(raw_desc, FUNNY_KEYWORDS):
            score += FUNNY_KEYWORD_BONUS
    return score


def categorize_photo(photo: Dict[str, Any], score: int) -> str:
    raw_desc = photo.get("raw_description", "").lower()
    if extract_keywords(raw_desc, FUNNY_KEYWORDS): return "Funny"
    if extract_action_from_description(raw_desc) or extract_keywords(raw_desc, ACTION_KEYWORDS): return "Action"
    if extract_keywords(raw_desc, CHILDHOOD_KEYWORDS): return "Childhood"
    
    if photo.get("star_present", False) and photo.get("category") == "General":
        if any(w in raw_desc for w in ["looking at camera", "smile", "portrait"]):
            return "Portrait"
            
    return "Friends/Group" if photo.get("face_count", 0) > 1 else "Portrait"


def assign_duration(category: str) -> float:
    if category in ["Funny", "Action"]: return DURATION_FUNNY_ACTION
    if category in ["Portrait", "Childhood"]: return DURATION_PORTRAIT_CHILDHOOD
    return DURATION_DEFAULT


def generate_edit_notes(photo: Dict[str, Any], category: str, score: int, start_time: float) -> str:
    notes = []
    if score >= 100:
        notes.append("STAR FEATURE: Confirmed star presence" if photo.get("star_present") else "Star detected")
    
    notes.append(f"Category: {category}")
    description = photo.get("raw_description", "")[:100]
    return " | ".join(notes) + f" - {description}..."


def segment_photos_by_category(photos: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    segments = {cat: [] for cat in ["Childhood", "Portrait", "Friends/Group", "Action", "Funny", "Other"]}
    for photo in photos:
        score = calculate_score(photo)
        category = categorize_photo(photo, score)
        photo["_score"] = score
        photo["_category"] = category
        segments.get(category, segments["Other"]).append(photo)
    return segments


def sequence_narrative(segments: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    edit_decisions = []
    
    # Start
    start_candidates = segments["Childhood"] + segments["Portrait"]
    if start_candidates:
        start_photo = max(start_candidates, key=lambda x: x.get("_score", 0))
        edit_decisions.append(start_photo)
        for cat in ["Childhood", "Portrait"]:
            if start_photo in segments[cat]: segments[cat].remove(start_photo)
    
    # Middle
    middle = sorted(segments["Friends/Group"] + segments["Action"], 
                    key=lambda x: get_file_datetime(x))
    edit_decisions.extend(middle)
    
    # Climax
    edit_decisions.extend(sorted(segments["Funny"], key=lambda x: get_file_datetime(x)))
    
    # End
    if segments["Portrait"]:
        end_photo = max(segments["Portrait"], key=lambda x: x.get("_score", 0))
        if end_photo not in edit_decisions:
            edit_decisions.append(end_photo)
            
    return edit_decisions


def generate_edit_decision_list(photos: List[Dict[str, Any]]) -> Dict[str, Any]:
    segments = segment_photos_by_category(photos)
    edit_decisions = sequence_narrative(segments)
    
    final_list = []
    current_time = 0.0
    
    for photo in edit_decisions:
        duration = assign_duration(photo["_category"])
        final_list.append({
            "file_path": photo["path"],
            "start_time": round(current_time, 2),
            "duration": duration,
            "category": photo["_category"],
            "effect": random.choice(EFFECTS),
            "edit_notes": generate_edit_notes(photo, photo["_category"], photo["_score"], current_time)
        })
        current_time += duration
        
    return {
        "total_duration": round(current_time, 2),
        "photo_count": len(final_list),
        "edit_decisions": final_list
    }

def main():
    try:
        with open(INPUT_FILE, "r") as f:
            data = json.load(f)
        
        result = generate_edit_decision_list(data.get("photos", []))
        
        with open(OUTPUT_FILE, "w") as f:
            json.dump(result, f, indent=2)
            
        print(f"Success! Created {OUTPUT_FILE} with {result['photo_count']} steps.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()