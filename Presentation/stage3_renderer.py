#!/usr/bin/env python3
"""
Stage 3: Video Renderer (Clean & Subtle Version)
==============================================
מייצר וידאו נקי עם אפקטים עדינים מאוד השומרים על איכות התמונה.
מותאם ל-MoviePy 2.0+ ולמעבדי Apple Silicon M-Series.
"""

import json
import os
from typing import Optional, List
from moviepy import ImageClip, AudioFileClip, CompositeVideoClip, VideoClip, AudioClip

# הגדרות רזולוציה ואיכות
OUTPUT_RESOLUTION = (1920, 1080)
FRAME_RATE = 24
OUTPUT_FILENAME = "final_video.mp4"
INPUT_EDL_FILE = "edit_decision_list.json"
BACKGROUND_MUSIC_PATH = "assets/background_music.mp3"

def get_effect_clip(file_path: str, duration: float, effect: str) -> VideoClip:
    """
    יצירת קליפ עם אפקטים עדינים מאוד שלא מעוותים את התמונה.
    """
    # טעינת התמונה
    clip = ImageClip(file_path).with_duration(duration)
    
    # שינוי גודל חכם: מתאים את הגובה ל-1080 ושומר על פרופורציות
    clip = clip.resized(height=OUTPUT_RESOLUTION[1])
    
    # הגדרת עוצמת הזום - 3% בלבד (עדין מאוד וכמעט בלתי מורגש, נותן תחושת עומק)
    zoom_factor = 0.03 

    if effect == "zoom_in":
        # גדל מ-100% ל-103%
        return (clip.resized(lambda t: 1.0 + zoom_factor * (t / duration))
                .with_position(('center', 'center')))
        
    elif effect == "zoom_out":
        # קטן מ-103% ל-100%
        return (clip.resized(lambda t: (1.0 + zoom_factor) - zoom_factor * (t / duration))
                .with_position(('center', 'center')))
        
    elif "pan" in effect:
        # Panning עדין מאוד על ידי הזזה של פיקסלים בודדים
        return clip.with_position(('center', 'center')) # כרגע סטטי כדי למנוע רעידות
            
    # ברירת מחדל: תמונה סטטית ממורכזת
    return clip.with_position(('center', 'center'))

def render_video():
    """פונקציית הרינדור המרכזית"""
    
    if not os.path.exists(INPUT_EDL_FILE):
        print(f"Error: {INPUT_EDL_FILE} not found!")
        return

    with open(INPUT_EDL_FILE, 'r') as f:
        edl = json.load(f)
    
    total_duration = edl.get("total_duration", 0)
    edit_decisions = edl.get("edit_decisions", [])
    
    print(f"Starting render: {total_duration}s, {len(edit_decisions)} clips.")
    
    clips = []
    for decision in edit_decisions:
        path = decision.get("file_path")
        if not os.path.exists(path):
            print(f"Skipping missing file: {path}")
            continue
            
        duration = decision.get("duration", 2.0)
        start_time = decision.get("start_time", 0.0)
        effect = decision.get("effect", "static")
        
        print(f"  Adding: {path} [{effect}]")
        
        # יצירת הקליפ והצמדה לזמן ההתחלה
        c = get_effect_clip(path, duration, effect).with_start(start_time)
        clips.append(c)

    if not clips:
        print("No clips to render!")
        return

    # חיבור כל השכבות לווידאו אחד עם רקע שחור
    final_video = CompositeVideoClip(clips, size=OUTPUT_RESOLUTION).with_duration(total_duration)

    # טיפול באודיו (אם קיים)
    if os.path.exists(BACKGROUND_MUSIC_PATH):
        print("Adding background music...")
        audio = AudioFileClip(BACKGROUND_MUSIC_PATH).subclip(0, total_duration).fadeout(2.0)
        final_video = final_video.with_audio(audio)

    # כתיבת הקובץ - אופטימיזציה למעבדי M4
    print(f"\nWriting final file: {OUTPUT_FILENAME}")
    final_video.write_videofile(
        OUTPUT_FILENAME,
        fps=FRAME_RATE,
        codec="libx264",
        audio_codec="aac",
        threads=4, # ניצול ריבוי ליבות
        preset="slower" # איכות גבוהה יותר על חשבון עוד כמה שניות רינדור
    )
    
    final_video.close()

if __name__ == "__main__":
    render_video()