# Wake Word "Nevo" — Full-Stack Portfolio

Custom Hebrew wake word detection (**"היי נבו"**) with a complete ML pipeline, ESP32-S3 edge deployment, and a React dashboard for live demo.

## Architecture

```
TTS → Augment → Energy+ZCR Features → Conv1D → INT8 TFLite → ESP32 / Browser → Whisper
```

| Layer | Tech |
|-------|------|
| ML Pipeline | Python, TensorFlow 2.16, edge-tts, librosa |
| Inference | Shared `features.py` + `inference/engine.py` |
| Backend | FastAPI, WebSocket, UDP :5555, faster-whisper |
| Frontend | React 18, Vite, TypeScript, Tailwind, Recharts |
| Firmware | ESP32-S3, PlatformIO, TFLite Micro |

## Quick Start

### 1. Install dependencies

```bash
cd wake_word
pip install -r requirements.txt
# macOS Apple Silicon (optional):
# pip install -r requirements-macos.txt
```

### 2. Train the model (first time)

```bash
python3 main.py --skip-tts        # uses existing positive_raw audio
python3 main.py                   # full pipeline including TTS
python3 main.py --skip-tts --skip-bootstrap  # fastest re-run
```

### 3. Start the dashboard

```bash
./dev.sh
# Backend:  http://localhost:8000/api/health
# Frontend: http://localhost:5173
```

Or manually:

```bash
# Terminal 1
PYTHONPATH=.:. uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2
cd frontend && npm install && npm run dev
```

### 4. Live CLI test (no browser)

```bash
python3 test_model_live.py
```

## Demo Modes

### Browser Mode (no hardware)
1. Open http://localhost:5173
2. Click **Start Listening** and grant mic permission
3. Say **"היי נבו"** — confidence bar spikes
4. Whisper transcript appears in the Transcript panel

### ESP32 Mode (hardware hero)
1. Copy and edit firmware secrets:
   ```bash
   cd Firmware && cp secrets_example.h secrets.h
   ```
2. Flash firmware:
   ```bash
   pio run -t upload
   ```
3. Set `IP` in `secrets.h` to your backend host IP
4. Dashboard Device panel shows UDP packets and transcript on wake

## Project Structure

```
wake_word/
├── config.py              # Shared constants
├── features.py            # Canonical Energy+ZCR (matches firmware)
├── protocol.py            # UDP packet format
├── inference/engine.py    # Keras + TFLite inference
├── backend/               # FastAPI app
├── frontend/              # React dashboard
├── scripts/bootstrap_dataset.py
├── dataset/               # clean, noise, positive_raw, train/
├── models/                # .h5, .tflite, model_data.h, metrics.json
├── Firmware/              # ESP32-S3 PlatformIO project
├── tests/test_feature_parity.py
└── main.py                # ML pipeline orchestrator
```

## Model Architecture

```
Input: (64, 2)   # 64 windows × Energy + ZCR

Conv1D(8)  → MaxPool
Conv1D(16) → MaxPool
Conv1D(24) → AvgPool(16) → Flatten
Dense(16) → Dropout(0.2) → Dense(2, softmax)

Output: [background, wake_word]
```

INT8 TFLite model is ~12 KB. Firmware TFLite arena: 40 KB.

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/health` | Model + device status |
| `GET /api/model/metrics` | Training accuracy, loss history |
| `POST /api/pipeline/run` | Trigger background retrain |
| `GET /api/pipeline/status` | Pipeline progress |
| `WS /ws/inference` | Browser mic → live inference |
| `WS /ws/events` | Dashboard event stream |
| `UDP :5555` | ESP32 audio packets |

## Hardware BOM

- ESP32-S3 DevKit (PSRAM required)
- I2S MEMS microphone
- Pins: WS=15, SD=3, SCK=17

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NEVO_WHISPER_MODEL` | `tiny` | faster-whisper model size |
| `NEVO_LLM_ENABLED` | `false` | Enable Ollama LLM reply |
| `NEVO_LLM_URL` | `http://localhost:11434/api/generate` | Ollama endpoint |

## 5-Minute Employee Demo Script

1. Show dashboard architecture banner
2. Browser: say "היי נבו" → confidence spike → Whisper transcript
3. Training Lab: show 96%+ val accuracy and INT8 model size
4. ESP32 on desk: wake → UDP stream → dashboard updates
5. Mention: runs offline on MCU, Hebrew wake word, full custom pipeline

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Pipeline fails on empty dataset | Run `python3 scripts/bootstrap_dataset.py` |
| No mic in browser | Use HTTPS or localhost; check browser permissions |
| ESP32 no UDP | Verify `secrets.h` IP matches backend host |
| TFLite conversion fails | Uses SavedModel export (TF 2.16+); check `convert_to_tflite.py` logs |
| Whisper slow | Uses `tiny` model by default; first run downloads weights |

## License

MIT
