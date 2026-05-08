#!/usr/bin/env python3
"""
Stage 3: Pro Renderer 4.7 (Intros, Outros, RTL Fix & Mashup Engine)
===================================================================
The final execution layer. Features contents-intelligent text overlays,
Intro/Outro block parsing (color vs media), robust FFmpeg audio routing, 
dynamic amix bypass, float-to-int crash protection, and RTL Hebrew fixing.
Requirements: brew install imagemagick
"""

import json
import os
import sys
import subprocess
from typing import Optional, List, Dict
from moviepy import ImageClip, VideoFileClip, CompositeVideoClip, VideoClip, TextClip, ColorClip
from moviepy.video.fx.CrossFadeIn import CrossFadeIn

# --- Configuration ---
OUTPUT_RESOLUTION = (1920, 1080)
FRAME_RATE = 24
TEMP_VIDEO_FILENAME = "temp_video_only.mp4"
FINAL_OUTPUT_FILENAME = "final_video.mp4"
INPUT_EDL_FILE = "edit_decision_list.json"

# --- Text Styling ---
FONT_NAME = '/System/Library/Fonts/Supplemental/Arial Bold.ttf' # נתיב בטוח למק
if not os.path.exists(FONT_NAME):
    FONT_NAME = '/Library/Fonts/Arial Bold.ttf'

FONT_SIZE = 60
TEXT_COLOR = 'white'
TEXT_BG_COLOR = 'black'
TEXT_OPACITY = 0.6

def hex_to_rgb(hex_color: str) -> tuple:
    """ממיר צבעי Hex ל-RGB עבור רקעים של פתיח וסיום"""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 6:
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    return (0, 0, 0) # Fallback to black

def fix_rtl(text: str) -> str:
    """מבצע Reverse לטקסט עברי כדי שיוצג נכון ב-ImageMagick, תוך שמירה על סדר השורות"""
    if not text:
        return text
    lines = text.split('\n')
    reversed_lines = [line[::-1] for line in lines]
    return '\n'.join(reversed_lines)

def has_audio_stream(file_path: str) -> bool:
    """מונע קריסה של FFmpeg על ידי בדיקה מראש האם לסרטון יש ערוץ שמע"""
    if not file_path or not os.path.exists(file_path): 
        return False
        
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

def create_text_overlay(text: str, clip_duration: float, is_title: bool = False) -> Optional[VideoClip]:
    """מייצר כתובית מעוצבת. תומך בכתוביות תחתיות (דיפולט) וכותרות ענק ממורכזות (לפתיח/סיום)"""
    if not text or text.strip() == "": return None
    try:
        # הפעלת התיקון לעברית
        text_rtl = fix_rtl(text)
        
        # עיגול של הנתונים למספרים שלמים
        max_width = int(OUTPUT_RESOLUTION[0] * (0.9 if is_title else 0.8))
        f_size = 120 if is_title else FONT_SIZE
        
        # יצירת שכבת הטקסט עם הטקסט ההפוך לעברית
        txt = TextClip(
            text=text_rtl,
            font_size=f_size,
            color=TEXT_COLOR,
            font=FONT_NAME if os.path.exists(FONT_NAME) else 'Arial',
            method='caption',
            size=(max_width, None),
            horizontal_align='center'
        )
        
        if is_title:
            # כותרת פתיח/סיום: אין רקע שחור, ממורכז לגמרי במסך
            return txt.with_position("center").with_duration(clip_duration)
        else:
            # כתובית תחתית: עם רקע שחור חצי שקוף
            bg = ColorClip(
                size=(int(txt.w + 40), int(txt.h + 20)),
                color=(0, 0, 0)
            ).with_opacity(TEXT_OPACITY)
            
            overlay = CompositeVideoClip([
                bg.with_position("center"),
                txt.with_position("center")
            ], size=bg.size).with_duration(clip_duration)
            
            pos_y = int(OUTPUT_RESOLUTION[1] * 0.85)
            return overlay.with_position(('center', pos_y))
            
    except Exception as e:
        print(f"  [!] Text Overlay Error: {e}")
        return None

def process_media_clip(decision: dict) -> Optional[VideoClip]:
    m_type = decision.get("media_type")
    dur = decision.get("duration", 2.0)
    
    # --- 1. לוגיקה ייעודית לפתיח / סיום ---
    if m_type in ["intro", "outro"]:
        source = decision.get("source", "black")
        caption = decision.get("caption", "")
        
        # בניית הרקע (תמונה/וידאו או צבע אחיד)
        if os.path.exists(source):
            if source.lower().endswith(('.mp4', '.mov')):
                base_clip = VideoFileClip(source, audio=False).subclipped(0, dur).with_duration(dur).resized(height=OUTPUT_RESOLUTION[1]).with_position(('center', 'center'))
            else:
                base_clip = ImageClip(source).with_duration(dur).resized(height=OUTPUT_RESOLUTION[1]).with_position(('center', 'center'))
        else:
            # זה צבע (או משהו שלא קיים במערכת)
            bg_color = (0,0,0)
            if source.startswith("#"): bg_color = hex_to_rgb(source)
            elif source.lower() == "white": bg_color = (255,255,255)
            base_clip = ColorClip(size=OUTPUT_RESOLUTION, color=bg_color).with_duration(dur)
            
        # הוספת טקסט כותרת
        if caption:
            txt_overlay = create_text_overlay(caption, dur, is_title=True)
            if txt_overlay: return CompositeVideoClip([base_clip, txt_overlay], size=OUTPUT_RESOLUTION)
        return base_clip
        
    # --- 2. לוגיקה רגילה לתמונות וסרטונים ---
    path = decision.get("file_path")
    effect = decision.get("effect", "static")
    profile = decision.get("transition_profile", {})
    caption = profile.get("caption", "")
    
    if not path or not os.path.exists(path):
        print(f"  [-] Missing file: {path}")
        return None

    try:
        if m_type == "video":
            clip = VideoFileClip(path, audio=False) 
            safe_duration = min(dur, clip.duration)
            clip = clip.subclipped(0, safe_duration).with_duration(dur)
        else:
            clip = ImageClip(path).with_duration(dur)

        clip = clip.resized(height=OUTPUT_RESOLUTION[1])
        
        if m_type == "image":
            zoom_factor = 0.04
            if effect == "zoom_in": 
                clip = clip.resized(lambda t: 1.0 + zoom_factor * (t / dur))
            elif effect == "zoom_out": 
                clip = clip.resized(lambda t: (1.0 + zoom_factor) - zoom_factor * (t / dur))
                
        base_clip = clip.with_position(('center', 'center'))
        
        # כתובית תחתית רגילה
        if caption and caption.strip() != "":
            overlay = create_text_overlay(caption, dur, is_title=False)
            if overlay:
                return CompositeVideoClip([base_clip, overlay], size=OUTPUT_RESOLUTION)
                
        return base_clip
        
    except Exception as e: 
        print(f"  [-] Error loading media {path}: {e}")
        return None

def build_ffmpeg_filter_complex(music_tracks: List[Dict], valid_mashup_intervals: List[Dict]) -> str:
    """בונה שרשרת אודיו ליניארית וחסינה לחלוטין לשגיאות Syntax"""
    filter_parts = []
    num_music = len(music_tracks)
    
    # 1. שרשור מוזיקת הרקע לאפיק אחד אחיד [bg_raw]
    if num_music > 1:
        inputs_str = "".join(f"[{i+1}:a]" for i in range(num_music))
        filter_parts.append(f"{inputs_str}concat=n={num_music}:v=0:a=1[bg_raw]")
    elif num_music == 1:
        filter_parts.append("[1:a]anull[bg_raw]")
    else:
        filter_parts.append("anullsrc=r=44100:cl=stereo[bg_raw]")

    # 2. החלת פילטר הווליום (Ducking) במבנה ליניארי
    current_label = "[bg_raw]"
    for idx, interval in enumerate(valid_mashup_intervals):
        start = max(0.001, interval["start"])
        lead_in = interval.get("lead_in", 0.0)
        fade_start = max(0.001, start - lead_in)
        end = interval["end"]
        vol = interval.get("bg_vol", 0.4)
        fade = max(0.1, interval.get("fade_dur", 0.5))
        
        f_in_start = max(0.0, fade_start - fade)
        next_label = f"[bg_v{idx}]"
        
        v_expr = (
            f"if(between(t,{fade_start},{end}),{vol},"
            f"if(lt(t,{fade_start}),1.0-(1.0-{vol})*(t-{f_in_start})/{fade},"
            f"{vol}+(1.0-{vol})*(t-{end})/{fade}))"
        )
        enable_expr = f"between(t,{f_in_start},{end+fade})"
        
        filter_str = f"{current_label}volume=volume='{v_expr}':enable='{enable_expr}':eval=frame{next_label}"
        filter_parts.append(filter_str)
        current_label = next_label
    
    filter_parts.append(f"{current_label}anull[bg_master]")

    # 3. הכנת האודיו של הסרטונים (J-Cut ו-Fade-In)
    video_audio_nodes = []
    for idx, interval in enumerate(valid_mashup_intervals):
        input_idx = num_music + 1 + idx
        start_audio = max(0.0, interval["start"] - interval.get("lead_in", 0.0))
        delay_ms = int(start_audio * 1000)
        fade_dur = max(0.1, interval.get("fade_dur", 0.5))
        
        node = f"[v_aud_f_{idx}]"
        filter_parts.append(f"[{input_idx}:a]adelay={delay_ms}|{delay_ms},afade=t=in:st={start_audio}:d={fade_dur}{node}")
        video_audio_nodes.append(node)

    # 4. מיקס סופי
    if video_audio_nodes:
        all_nodes = "[bg_master]" + "".join(video_audio_nodes)
        num_inputs = 1 + len(video_audio_nodes)
        filter_parts.append(f"{all_nodes}amix=inputs={num_inputs}:duration=first:dropout_transition=2:normalize=0[a_out]")
    else:
        filter_parts.append("[bg_master]anull[a_out]")

    return ";".join(filter_parts)

def render_mashup():
    print("=" * 60)
    print("Stage 3: Pro Renderer 4.7 - Intros, Outros & Mashup Engine")
    print("=" * 60)
    
    if not os.path.exists(INPUT_EDL_FILE):
        sys.exit(f"[-] Error: Missing {INPUT_EDL_FILE}. Run Stage 2 first.")
        
    with open(INPUT_EDL_FILE, 'r') as f:
        edl = json.load(f)
    
    decisions = edl.get("edit_decisions", [])
    raw_intervals = edl.get("mashup_intervals", [])
    music = edl.get("music_tracks", [])
    total_dur = edl.get("total_duration", 0.0)

    print("[*] Verifying audio streams for video clips...")
    valid_intervals = []
    for inter in raw_intervals:
        path = inter.get("path")
        if path and has_audio_stream(path):
            valid_intervals.append(inter)
        else:
            print(f"  [-] Skipping audio processing for silent/missing video: {os.path.basename(path) if path else 'Unknown'}")

    # --- שלב 1: רינדור הווידאו ---
    print(f"\n[*] Rendering Visual Layer. Total Timeline: {total_dur}s")
    clips = []
    for d in decisions:
        c = process_media_clip(d)
        if c:
            c = c.with_start(d["start_time"])
            if d.get("transition_type") == "crossfade" and d.get("transition_duration", 0) > 0:
                c = c.with_effects([CrossFadeIn(d["transition_duration"])])
            clips.append(c)

    if not clips:
        sys.exit("[-] No valid media found to render.")

    final_v = CompositeVideoClip(clips, size=OUTPUT_RESOLUTION).with_duration(total_dur)
    
    threads = os.cpu_count() or 4
    final_v.write_videofile(
        TEMP_VIDEO_FILENAME, 
        fps=FRAME_RATE, 
        codec="libx264", 
        audio=False, 
        preset="ultrafast", 
        threads=threads
    )
    final_v.close()
    
    for c in clips:
        try: c.close()
        except: pass

    # --- שלב 2: המאשאפ האקוסטי ---
    print(f"\n[*] Mastering Audio Mashup Layout...")
    input_args = ["-i", TEMP_VIDEO_FILENAME]
    
    for t in music: 
        input_args.extend(["-i", t["file_path"]])
        
    for inter in valid_intervals: 
        input_args.extend(["-i", inter["path"]])

    filter_complex = build_ffmpeg_filter_complex(music, valid_intervals)

    cmd = [
        "ffmpeg", "-y", *input_args,
        "-filter_complex", filter_complex,
        "-map", "0:v", "-map", "[a_out]",
        "-c:v", "copy", 
        "-c:a", "aac", "-b:a", "256k", 
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