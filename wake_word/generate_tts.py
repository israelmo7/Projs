import asyncio
import edge_tts
import os

# Target text in Hebrew
TARGET_TEXT = "היי נבו"

# Voice options
VOICES = ["he-IL-AvriNeural", "he-IL-HilaNeural"]

# Rate options
RATES = ["-20%", "+0%", "+20%"]

# Pitch options - MUST include the Hz suffix for Azure SSML validation
PITCHES = ["-20Hz", "+0Hz", "+20Hz"]

# Output directory
OUTPUT_DIR = "wake_word/raw_audio"

def get_file_name(voice, rate, pitch):
    """Generate descriptive filename from parameters."""
    voice_name = "asaf" if "Asaf" in voice else "hila"
    # Clean up the strings to make safe file names
    rate_clean = rate.replace("%", "").replace("+", "plus").replace("-", "minus")
    pitch_clean = pitch.replace("Hz", "").replace("+", "plus").replace("-", "minus")
    return f"{voice_name}_rate_{rate_clean}_pitch_{pitch_clean}.mp3"

async def generate_tts(voice, rate, pitch):
    """Generate audio for a specific combination of voice, rate, and pitch."""
    print(f"Generating: voice={voice}, rate={rate}, pitch={pitch}")
    
    # Create the TTS configuration - pass rate and pitch correctly
    communicate = edge_tts.Communicate(
        TARGET_TEXT, 
        voice,
        rate=rate,
        pitch=pitch
    )
    
    # Generate the audio
    filename = get_file_name(voice, rate, pitch)
    filepath = os.path.join(OUTPUT_DIR, filename)
    
    # save takes the file path
    await communicate.save(filepath)
    
    print(f"Saved: {filepath}")
    return filepath

async def main():
    """Main function to generate all combinations."""
    # Ensure output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    total_files = len(VOICES) * len(RATES) * len(PITCHES)
    print(f"Target text: {TARGET_TEXT}")
    print(f"Generating {total_files} audio files...\n")
    
    # Iterate through all combinations
    for voice in VOICES:
        for rate in RATES:
            for pitch in PITCHES:
                await generate_tts(voice, rate, pitch)
    
    print("\nAll audio files generated successfully!")
    print(f"Files saved to: {OUTPUT_DIR}")

if __name__ == "__main__":
    asyncio.run(main())
