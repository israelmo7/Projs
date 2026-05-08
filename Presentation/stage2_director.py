#!/usr/bin/env python3
"""
Stage 2: Smart AI Director Pro 3.2 (LLM Mashup, Captions & Intros)
==================================================================
The Director Agent: Utilizes Llama 3 to make artistic decisions (J-Cuts, Spotlights),
tags highlights for manual captions, and scaffolds Intro/Outro blocks.
"""

import json
import os
import sys
import random
import re
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List, Dict, Any, Tuple
from moviepy import AudioFileClip

INPUT_FILE = "video_plan.json"
OUTPUT_FILE = "edit_decision_list.json"
MUSIC_DIR = "assets/music"
OLLAMA_API_URL = "http://localhost:11434/api/generate"
DIRECTOR_MODEL = "llama3"

# Artistic Constants
MAX_WORKERS = 4

def scan_music_pool() -> List[Dict[str, Any]]:
    """סורק את תיקיית המוזיקה וממיין את השירים לפי התו הראשון בשם הקובץ (1-9)"""
    tracks = []
    if not os.path.exists(MUSIC_DIR): 
        return tracks
        
    supported_ext = {".mp3", ".wav", ".aac", ".m4a"}
    
    files = [f for f in os.listdir(MUSIC_DIR) if os.path.splitext(f)[1].lower() in supported_ext]
    files.sort(key=lambda x: x[0]) 
    
    for f in files:
        path = os.path.join(MUSIC_DIR, f)
        try:
            audio = AudioFileClip(path)
            tracks.append({"file_path": path, "duration": round(audio.duration, 2)})
            audio.close()
        except Exception as e: 
            print(f"  [-] Failed to load music track {f}: {e}")
            
    return tracks

def build_artistic_sequence(media_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """מארגן את המדיה לסדר קולנועי עם עדיפות לפיזור נכון"""
    videos = [m for m in media_list if m.get("media_type") == "video"]
    images = [m for m in media_list if m.get("media_type") == "image"]
    
    videos.sort(key=lambda x: x.get("datetime", ""))
    images.sort(key=lambda x: x.get("datetime", ""))
    
    sequence = []
    while videos or images:
        if videos:
            sequence.append(videos.pop(0))
        for _ in range(random.randint(3, 5)):
            if images: sequence.append(images.pop(0))
            
    return sequence

def ask_llama_director(media: Dict[str, Any]) -> Dict[str, Any]:
    """מתייעץ עם Llama 3 לגבי אסטרטגיית המעבר, ומסמן נקודות לטקסט רק בשיאים"""
    audio_prof = media.get("audio_profile", {})
    energy = audio_prof.get("energy_score", 0)
    bpm = audio_prof.get("bpm", 0)
    desc = media.get("raw_description", "Unknown action")
    
    prompt = f"""
    You are a professional video editor. Analyze this clip metadata:
    Visuals: "{desc}"
    Acoustic Energy: {energy}/10 (High energy means loud singing/karaoke/action)
    BPM: {bpm}

    DECISION RULE FOR CAPTIONS:
    - If the energy is ABOVE 0.8 or the visual action is a clear highlight, set "caption": "" (an empty string).
    - Otherwise, do NOT include the "caption" key at all.
    - NEVER write actual words. Only provide the empty string as a placeholder if it's a highlight.
    
    Return ONLY a valid JSON object with these keys:
    "bg_music_vol": float (0.0 for full spotlight/karaoke, 0.4 for mashup mix, 0.8 for background),
    "lead_in": float (seconds to start clip audio BEFORE video appears, e.g. 0.0 to 1.2),
    "fade_dur": float (crossfade duration in seconds, e.g. 0.5 to 1.5),
    "caption": "" (ONLY INCLUDE THIS KEY IF IT'S A HIGHLIGHT)
    """
    
    payload = {
        "model": DIRECTOR_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json"
    }
    
    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=20)
        if response.status_code == 200:
            raw_text = response.json().get("response", "")
            json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
    except Exception as e:
        pass

    if energy > 0.7:
        return {"bg_music_vol": 0.0, "lead_in": 0.8, "fade_dur": 1.2, "caption": ""}
    elif energy > 0.3:
        return {"bg_music_vol": 0.4, "lead_in": 0.4, "fade_dur": 0.8}
    else:
        return {"bg_music_vol": 0.2, "lead_in": 0.0, "fade_dur": 0.5}
        
def process_director_decisions(videos: List[Dict]) -> Dict[str, Dict]:
    """מריץ את החלטות הבימוי במקביל"""
    print(f"[*] Consulting AI Director (Llama 3) for {len(videos)} video clips...")
    decisions = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_path = {executor.submit(ask_llama_director, v): v["path"] for v in videos}
        for count, future in enumerate(as_completed(future_to_path), 1):
            path = future_to_path[future]
            try:
                decisions[path] = future.result()
                if "caption" in decisions[path]:
                    print(f"  [+] Clip {count}/{len(videos)}: Highlight detected! Added empty caption slot.")
            except Exception:
                decisions[path] = {"bg_music_vol": 0.4, "lead_in": 0.0, "fade_dur": 0.8}
    return decisions

def find_sync_duration(sequenced_media: List[Dict], total_music_time: float, intro_out_dur: float) -> float:
    """מוצא את משך הזמן לתמונות, תוך קיזוז הזמן של הפתיח והסיום"""
    def simulate(base_dur):
        curr = intro_out_dur 
        for m in sequenced_media:
            if m.get("media_type") == "video":
                curr += m.get("duration", 0)
            else:
                curr += base_dur
        return curr

    low, high = 1.0, 10.0
    for _ in range(30):
        mid = (low + high) / 2
        if simulate(mid) < total_music_time: low = mid
        else: high = mid
    return low

def generate_mashup_edl(sequenced: List[Dict], music_tracks: List[Dict], chosen_base: float, ai_decisions: Dict) -> Dict:
    final_decisions = []
    video_intervals = [] 
    timeline = 0.0
    
    # 1. הזרקת בלוק פתיח (Intro)
    intro_dur = 4.0
    final_decisions.append({
        "media_type": "intro",
        "source": "black", # אפשר לשנות ב-JSON ל-#hex או נתיב לקובץ
        "duration": intro_dur,
        "start_time": round(timeline, 3),
        "caption": "טקסט פתיח"
    })
    timeline += intro_dur
    
    # 2. שאר המדיה (תמונות וסרטונים)
    for media in sequenced:
        m_type = media.get("media_type", "image")
        
        if m_type == "video":
            profile = ai_decisions.get(media["path"], {"bg_music_vol": 0.4, "lead_in": 0.0, "fade_dur": 0.8})
            duration = media.get("duration", 0)
            
            video_intervals.append({
                "path": media["path"],
                "start": round(timeline, 3),
                "end": round(timeline + duration, 3),
                "bg_vol": float(profile.get("bg_music_vol", 0.4)),
                "fade_dur": float(profile.get("fade_dur", 0.8)),
                "lead_in": float(profile.get("lead_in", 0.0))
            })
            
            final_decisions.append({
                "file_path": media["path"],
                "media_type": "video",
                "start_time": round(timeline, 3),
                "duration": round(duration, 3),
                "transition_profile": profile
            })
            timeline += duration
        else:
            duration = chosen_base * random.uniform(0.95, 1.05)
            final_decisions.append({
                "file_path": media["path"],
                "media_type": "image",
                "start_time": round(timeline, 3),
                "duration": round(duration, 3),
                "effect": random.choice(["zoom_in", "zoom_out", "static"])
            })
            timeline += duration
            
    # 3. הזרקת בלוק סיום (Outro)
    outro_dur = 4.0
    final_decisions.append({
        "media_type": "outro",
        "source": "black",
        "duration": outro_dur,
        "start_time": round(timeline, 3),
        "caption": "טקסט סיום"
    })
    timeline += outro_dur
            
    return {
        "total_duration": round(timeline, 3),
        "music_tracks": music_tracks,
        "mashup_intervals": video_intervals,
        "edit_decisions": final_decisions
    }

def main():
    print("=" * 60)
    print("Stage 2: AI Director Pro (LLM Mashup & Intros Engine)")
    print("=" * 60)
    
    if not os.path.exists(INPUT_FILE):
        sys.exit(f"[-] Error: Missing {INPUT_FILE}. Run Stage 1 first.")
        
    with open(INPUT_FILE, "r") as f:
        data = json.load(f)
    
    media_items = data.get("photos", [])
    music_tracks = scan_music_pool()
    
    if not music_tracks: 
        sys.exit("[-] Error: No music tracks found in the assets/music directory.")
        
    print(f"[*] Found {len(music_tracks)} music tracks. Sorted chronologically.")
    total_music = sum(t["duration"] for t in music_tracks)
    
    sequenced_media = build_artistic_sequence(media_items)
    
    videos_only = [m for m in sequenced_media if m.get("media_type") == "video"]
    ai_decisions = process_director_decisions(videos_only)
    
    # חישוב הסנכרון עם קיזוז 8 שניות של פתיח וסיום
    perfect_base = find_sync_duration(sequenced_media, total_music, intro_out_dur=8.0)
    print(f"\n[*] Suggested image duration for 100% audio sync: {perfect_base:.3f}s")
    
    user_val = input(f"[?] Press Enter to use {perfect_base:.3f}s, or input a custom range (e.g. 2-3): ").strip()
    
    if '-' in user_val:
        min_b, max_b = map(float, user_val.split('-'))
        chosen_base = max(min_b, min(max_b, perfect_base))
    elif user_val:
        chosen_base = float(user_val)
    else:
        chosen_base = perfect_base

    edl = generate_mashup_edl(sequenced_media, music_tracks, chosen_base, ai_decisions)
    
    with open(OUTPUT_FILE, "w") as f:
        json.dump(edl, f, indent=2, ensure_ascii=False)
    
    print(f"\n[+] Master Plan Ready! Saved to {OUTPUT_FILE}")
    print(f"    Timeline Duration: {edl['total_duration']}s")
    print(f"    Music Duration:    {total_music}s")

if __name__ == "__main__":
    main()