import asyncio
import serial_asyncio
import logging
import collections

# --- הגדרות ---
SERIAL_PORT = '/dev/ttyUSB0'
BAUD_RATE = 921600
WAKE_SIGNAL = b"WAKE"
CMD_DURATION = 5  # כמה שניות להקליט לאחר הזיהוי
SAMPLE_RATE = 16000
BYTES_PER_SECOND = SAMPLE_RATE * 2 # 16-bit = 2 bytes

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("NevoBrain")

class NevoProtocol(asyncio.Protocol):
    def __init__(self, audio_queue):
        self.audio_queue = audio_queue
        self.transport = None
        self._buffer = b"" # באפר זמני לזיהוי סיגנלים
        self.is_processing = False

    def connection_made(self, transport):
        self.transport = transport
        logger.info(f"✅ Serial Connected: {SERIAL_PORT}")

    def data_received(self, data):
        # 1. ניהול זיהוי סיגנל (טיפול בפרגמנטציה)
        self._buffer += data
        if not self.is_processing:
            if WAKE_SIGNAL in self._buffer:
                logger.info("🚨 WAKE detected! Starting capture...")
                self.is_processing = True
                self._buffer = b"" # ניקוי הבאפר להתחלת האודיו
                # מודיע למעבד להתחיל איסוף
                asyncio.create_task(self.start_command_window())
        
        # 2. הזרמת האודיו לתור בזמן אמת
        if self.is_processing:
            self.audio_queue.put_nowait(data)
            
        # מונע מהבאפר לגדול אינסופית אם אין זיהוי
        if len(self._buffer) > 100:
            self._buffer = self._buffer[-10:]

    async def start_command_window(self):
        """מנהל את חלון הזמן של הפקודה"""
        await asyncio.sleep(CMD_DURATION)
        logger.info("⏹️ Command window closed. Sending to AI...")
        self.is_processing = False
        self.audio_queue.put_nowait(None) # אות סוף הקלטה (Sentinel Value)

async def ai_processor_task(audio_queue):
    """ה'מוח' שמחכה לסוף ההקלטה ומעבד אותה"""
    full_audio = b""
    
    while True:
        chunk = await audio_queue.get()
        
        if chunk is None: # הגענו לסוף הפקודה
            # כאן יקרה הקסם:
            # 1. אימות Handshake (האם ב-2 השניות הראשונות באמת יש 'היי נבו'?)
            # 2. תמלול Whisper
            # 3. תשובה של Phi-3
            logger.info(f"🎤 Processing {len(full_audio)} bytes of command audio...")
            
            # TODO: process_with_ai(full_audio)
            
            full_audio = b"" # איפוס לפעם הבאה
            continue
            
        full_audio += chunk

async def main():
    audio_queue = asyncio.Queue()
    loop = asyncio.get_event_loop()
    
    try:
        # פתיחת הקשר הטורי
        coro = serial_asyncio.create_serial_connection(
            loop, lambda: NevoProtocol(audio_queue), SERIAL_PORT, baudrate=BAUD_RATE
        )
        await asyncio.gather(coro, ai_processor_task(audio_queue))
    except Exception as e:
        logger.error(f"❌ Connection Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
