#!/usr/bin/env python3
"""Generate synthetic wake word audio using edge-tts."""

import asyncio
import sys
from pathlib import Path

import librosa
import soundfile as sf

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from config import POSITIVE_RAW_DIR, TTS_PITCHES, TTS_RATES, TTS_VOICES, WAKE_PHRASE


def get_file_name(voice: str, rate: str, pitch: str) -> str:
    voice_name = "avri" if "Avri" in voice else "hila"
    rate_clean = rate.replace("%", "").replace("+", "plus").replace("-", "minus")
    pitch_clean = pitch.replace("Hz", "").replace("+", "plus").replace("-", "minus")
    return f"{voice_name}_rate_{rate_clean}_pitch_{pitch_clean}.wav"


async def generate_tts(voice: str, rate: str, pitch: str) -> Path:
    import edge_tts

    print(f"Generating: voice={voice}, rate={rate}, pitch={pitch}")

    communicate = edge_tts.Communicate(WAKE_PHRASE, voice, rate=rate, pitch=pitch)
    tmp_mp3 = POSITIVE_RAW_DIR / "_tmp.mp3"
    POSITIVE_RAW_DIR.mkdir(parents=True, exist_ok=True)
    await communicate.save(str(tmp_mp3))

    audio, sr = librosa.load(str(tmp_mp3), sr=16000, mono=True)
    tmp_mp3.unlink(missing_ok=True)

    filepath = POSITIVE_RAW_DIR / get_file_name(voice, rate, pitch)
    sf.write(str(filepath), audio, 16000)
    print(f"Saved: {filepath}")
    return filepath


async def main() -> None:
    total = len(TTS_VOICES) * len(TTS_RATES) * len(TTS_PITCHES)
    print(f"Target text: {WAKE_PHRASE}")
    print(f"Generating {total} WAV files to {POSITIVE_RAW_DIR}...\n")

    for voice in TTS_VOICES:
        for rate in TTS_RATES:
            for pitch in TTS_PITCHES:
                await generate_tts(voice, rate, pitch)

    print("\nAll audio files generated successfully!")


if __name__ == "__main__":
    asyncio.run(main())
