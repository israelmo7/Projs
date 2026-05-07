#!/usr/bin/env python3
"""
Stage 3: Pro Renderer 4.0 (The M4 Mashup Engine)
================================================
The final execution layer. Features robust FFmpeg audio routing,
dynamic amix normalization bypass, and silent-video crash protection.
"""

import json
import os
import sys
import subprocess
from typing import Optional, List, Dict
from moviepy import ImageClip, VideoFileClip, CompositeVideoClip, VideoClip
from moviepy.video.fx.CrossFadeIn import CrossFadeIn

OUTPUT_RESOLUTION = (1920, 1080)
FRAME_RATE = 24
TEMP_VIDEO_FILENAME = "temp_video_only.mp4"
FINAL_OUTPUT_FILENAME = "final_video.mp4"
INPUT_EDL_FILE = "edit_decision_list.json"

def has_audio_stream(file_path: str) -> bool:
    """מונע קריסה של FFmpeg על ידי בדיקה מראש האם לסרטון יש ערוץ שמע"""
    cmd = [
        "ffprobe", "-v", "error", 
        "-select_streams", "a", 
        "-show_entries", "stream=codec_type", 
        "-of", "csv=p=0", file_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        return "audio" in result.stdout.lower()
    except Exception:
        return False

def process_media_clip(decision: dict) -> Optional[VideoClip]:
    path = decision.get("file_path")
    media_type = decision.get("media_type")
    duration = decision.get("duration", 2.0)
    effect = decision.get("effect", "static")
    
    if not os.path.exists(path):
        print(f"  [-] Missing file: {path}")
        return None

    if media_type == "video":
        try:
            # בווידאו אנחנו מביאים רק את התמונה ל-MoviePy
            clip = VideoFileClip(path, audio=False) 
            safe_duration = min(duration, clip.duration)
            clip = clip.subclipped(0, safe_duration).with_duration(duration)
        except Exception as e: 
            print(f"  [-] Error loading video {path}: {e}")
            return None
    else:
        try:
            clip = ImageClip(path).with_duration(duration)
        except Exception:
            return None

    clip = clip.resized(height=OUTPUT_RESOLUTION[1])
    
    if media_type == "image":
        zoom_factor = 0.04
        if effect == "zoom_in": 
            clip = clip.resized(lambda t: 1.0 + zoom_factor * (t / duration))
        elif effect == "zoom_out": 
            clip = clip.resized(lambda t: (1.0 + zoom_factor) - zoom_factor * (t / duration))
            
    return clip.with_position(('center', 'center'))

def build_ffmpeg_filter_complex(music_tracks: List[Dict], valid_mashup_intervals: List[Dict]) -> str:
    """בונה את שרשרת האודיו. מותאם למניעת הנמכה אוטומטית של amix."""
    filter_parts = []
    num_music = len(music_tracks)
    
    # 1. שרשור מוזיקת הרקע
    if num_music > 1:
        inputs_str = "".join(f"[{i+1}:a]" for i in range(num_music))
        filter_parts.append(f"{inputs_str}concat=n={num_music}:v=0:a=1[bg_raw]")
    elif num_music == 1:
        filter_parts.append("[1:a]anull[bg_raw]")
    else:
        # במקרה נדיר שאין מוזיקת רקע כלל
        filter_parts.append("anullsrc=r=44100:cl=stereo[bg_raw]")

    # 2. החלת ווליום דינמי על מוזיקת הרקע (Ducking)
    bg_vol_chain = "[bg_raw]"
    for idx, interval in enumerate(valid_mashup_intervals):
        start = max(0, interval["start"] - interval.get("lead_in", 0))
        end = interval["end"]
        vol = interval.get("bg_vol", 0.4)
        fade = interval.get("fade_dur", 0.5)
        
        node = f"[bg_v{idx}]"
        v_filter = (
            f"volume=enable='between(t,{start-fade},{end+fade})':"
            f"volume='if(between(t,{start},{end}),{vol},if(less(t,{start}),1.0-(1.0-{vol})*(t-({start-fade}))/{fade},{vol}+(1.0-{vol})*(t-{end})/{fade}))':eval=frame"
        )
        bg_vol_chain += f"{v_filter}{node};{node}"
    
    filter_parts.append(bg_vol_chain.rsplit(";", 1)[0] + "[bg_final]")

    # 3. הכנת האודיו של הסרטונים (J-Cut ו-Fade)
    video_audio_nodes = []
    for idx, interval in enumerate(valid_mashup_intervals):
        input_idx = num_music + 1 + idx
        
        start_with_jcut = max(0, interval["start"] - interval.get("lead_in", 0.0))
        delay_ms = int(start_with_jcut * 1000)
        fade_dur = interval.get("fade_dur", 0.5)
        
        v_aud_filter = f"[{input_idx}:a]adelay={delay_ms}|{delay_ms},afade=t=in:st={start_with_jcut}:d={fade_dur}[v_aud_f_{idx}]"
        filter_parts.append(v_aud_filter)
        video_audio_nodes.append(f"[v_aud_f_{idx}]")

    # 4. המיקס הסופי - normalize=0 מונע מ-FFmpeg להרוס לנו את לוגיקת הווליום
    all_nodes = "[bg_final]" + "".join(video_audio_nodes)
    num_inputs = 1 + len(video_audio_nodes)
    
    # שימוש ב-normalize=0 הקריטי ליציבות המאשאפ
    filter_parts.append(f"{all_nodes}amix=inputs={num_inputs}:duration=first:dropout_transition=2:normalize=0[a_out]")

    return ";".join(filter_parts)

def render_mashup():
    if not os.path.exists(INPUT_EDL_FILE):
        sys.exit(f"[-] Error: Missing {INPUT_EDL_FILE}. Run Stage 2 first.")
        
    with open(INPUT_EDL_FILE, 'r') as f:
        edl = json.load(f)
    
    decisions = edl.get("edit_decisions", [])
    raw_intervals = edl.get("mashup_intervals", [])
    music = edl.get("music_tracks", [])
    total_dur = edl.get("total_duration", 0.0)

    # סינון אינטרוולים: משאירים רק סרטונים שבאמת יש בהם סאונד
    print("[*] Verifying audio streams for video clips...")
    valid_intervals = []
    for inter in raw_intervals:
        path = inter.get("path")
        if path and has_audio_stream(path):
            valid_intervals.append(inter)
        else:
            print(f"  [-] Skipping audio processing for silent video: {os.path.basename(path)}")

    # --- שלב 1: רינדור הווידאו (MoviePy) ---
    print(f"\n[*] Rendering Visual Layer. Total Timeline: {total_dur}s")
    video_clips = []
    for idx, d in enumerate(decisions):
        clip = process_media_clip(d)
        if not clip: continue
        
        clip = clip.with_start(d["start_time"])
        if d.get("transition_type") == "crossfade" and d.get("transition_duration", 0) > 0:
            clip = clip.with_effects([CrossFadeIn(d["transition_duration"])])
            
        video_clips.append(clip)

    if not video_clips:
        sys.exit("[-] No valid media found to render.")

    final_video = CompositeVideoClip(video_clips, size=OUTPUT_RESOLUTION).with_duration(total_dur)
    
    # שימוש מקסימלי במשאבים (ה-M4 יטחן את זה בקלות)
    threads = os.cpu_count() or 4
    final_video.write_videofile(
        TEMP_VIDEO_FILENAME, 
        fps=FRAME_RATE, 
        codec="libx264", 
        audio=False, 
        preset="ultrafast",
        threads=threads
    )
    
    # ניקוי זיכרון אגרסיבי
    final_video.close()
    for c in video_clips:
        try: c.close()
        except: pass

    # --- שלב 2: המאשאפ האקוסטי (FFmpeg) ---
    print(f"\n[*] Mastering Audio Mashup Layout...")
    
    input_files = ["-i", TEMP_VIDEO_FILENAME]
    for track in music:
        input_files.extend(["-i", track["file_path"]])
        
    for inter in valid_intervals:
        input_files.extend(["-i", inter["path"]])

    filter_complex = build_ffmpeg_filter_complex(music, valid_intervals)

    cmd = [
        "ffmpeg", "-y",
        *input_files,
        "-filter_complex", filter_complex,
        "-map", "0:v", "-map", "[a_out]",
        "-c:v", "copy",             # מעתיק את הווידאו כמו שהוא (0 זמן רינדור נוסף)
        "-c:a", "aac", "-b:a", "256k", # קידוד אודיו באיכות גבוהה (256k במקום 192k)
        "-t", str(total_dur),
        FINAL_OUTPUT_FILENAME
    ]

    print("[*] Running Final FFmpeg Mixdown...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print(f"\n[+] BOOM! Mashup Complete. Masterpiece saved as: {FINAL_OUTPUT_FILENAME}")
        if os.path.exists(TEMP_VIDEO_FILENAME):
            os.remove(TEMP_VIDEO_FILENAME)
    else:
        print(f"\n[-] FFmpeg Error Details:\n{result.stderr}")

if __name__ == "__main__":
    render_mashup()