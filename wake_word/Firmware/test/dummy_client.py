import socket
import struct
import wave
import sounddevice as sd

# הגדרות רשת ואודיו
UDP_IP = "0.0.0.0"
UDP_PORT = 5000
SAMPLE_RATE = 16000
CHANNELS = 1
OUTPUT_FILE = "live_record_test.wav"

print("=" * 50)
print("🚀 Nevo Proxy Hub: Live Audio Stream (Demo)")
print("=" * 50)

# פתיחת אפיק ישיר לרמקולים בפורמט שה-ESP שולח (int16)
try:
    stream = sd.RawOutputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype='int16')
    stream.start()
except Exception as e:
    print(f"❌ Error opening sound device: {e}")
    exit(1)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))

print(f"[*] Listening on UDP port {UDP_PORT}...")
print("[*] Speak into the ESP32! (Press Ctrl+C to stop and save)")

audio_data = []
total_packets = 0

try:
    while True:
        data, addr = sock.recvfrom(2048)
        
        if len(data) > 8:
            total_packets += 1
            # חילוץ ההדר
            seq, timestamp = struct.unpack('<II', data[:8])
            payload = data[8:]
            
            # 1. דחיפת האודיו ישירות לרמקולים של המחשב בזמן אמת!
            stream.write(payload)
            
            # 2. שמירת הנתונים כדי שניצור קובץ בסוף ההקלטה
            audio_data.append(payload)

            if total_packets % 20 == 0:
                print(f"[LIVE] Seq: {seq} | Timestamp: {timestamp}ms | Playing...", end='\r')

except KeyboardInterrupt:
    print("\n\n[*] Stopping stream...")
    stream.stop()
    stream.close()
    
    # שמירת הקובץ
    if audio_data:
        print("[*] Saving recorded audio...")
        with wave.open(OUTPUT_FILE, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2) # 16-bit
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(b''.join(audio_data))
        print(f"✅ Audio saved to: {OUTPUT_FILE}")