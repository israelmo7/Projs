# Wake Word Detection Project - "Nevo"

A complete pipeline for training and deploying a wake word recognition model ("Hey Nevo") using TensorFlow/Keras with TensorFlow Lite Micro support for ESP32-S3 deployment.

The system consists of two main components:
- **Python ML Pipeline**: Train and convert models for embedded deployment
- **Firmware**: ESP32-S3 firmware for audio capture and inference

---

## 📁 Project Structure

```
wake_word/
├── dataset/                    # Audio datasets
│   ├── clean/                  # Clean audio samples for negative training
│   ├── noise/                  # Background noise samples for augmentation
│   ├── positive_raw/           # Raw "Hey Nevo" audio files
│   └── train/                  # Training data (positive/negative splits)
├── models/                     # Trained model artifacts
│   ├── wake_word_model.h5      # Trained Keras model (saved before conversion)
│   └── wake_word_model.tflite  # Quantized TFLite model for deployment
├── Firmware/                   # ESP32-S3 Firmware
│   ├── src/                   # Firmware source code
│   │   └── main.cpp          # Main firmware logic
│   ├── include/               # Header files
│   ├── lib/                   # Dependencies
│   ├── platformio.ini        # PlatformIO configuration
│   └── test/                  # Testing utilities
├── *.py                       # Python scripts
│   ├── main.py                # Full ML pipeline runner
│   ├── generate_tts.py        # Generate synthetic wake word audio
│   ├── prepare_dataset.py     # Prepare and augment dataset
│   ├── extract_features.py    # Extract Energy and ZCR features
│   ├── train_model.py         # Train CNN model
│   ├── convert_to_tflite.py   # Convert to TensorFlow Lite Micro
│   ├── run_pipeline.py        # Execute full ML pipeline
│   ├── live_inference.py      # Real-time microphone detection
│   ├── test_model_live.py     # Test model with live input
│   └── neve_brain.py          # Serial handler for ESP32 communication
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

---

## 📄 Files and Their Purposes

### Python ML Pipeline Scripts

| File | Purpose |
|------|-------|
| **`generate_tts.py`** | Generates synthetic "Hey Nevo" audio samples using Azure TTS with various voices, rates, and pitches. Creates diverse training data. |
| **`prepare_dataset.py`** | Prepares the dataset by loading raw audio, applying data augmentation (noise injection), and organizing files into train directories. |
| **`extract_features.py`** | Extracts Energy and Zero-Crossing Rate (ZCR) features from audio files. Pads/trims audio to uniform duration (1 second / 16000 samples) and computes features over 64 windows. Saves as NumPy arrays. |
| **`train_model.py`** | Builds and trains a Conv1D model using TensorFlow/Keras. Accepts pre-extracted Energy+ZCR features and train/val splits. Outputs a trained `.h5` model. |
| **`convert_to_tflite.py`** | Converts the trained Keras model to TensorFlow Lite format with Int8 quantization. Outputs `.tflite` model for embedded deployment. |
| **`run_pipeline.py`** | Executes the full ML pipeline in order: `generate_tts` → `prepare_dataset` → `extract_features` → `train_model` → `convert_to_tflite`. |
| **`live_inference.py`** | Real-time wake word detection from microphone input. Processes audio chunks, extracts Energy+ZCR features, and runs inference on the trained model. Prints confidence scores. |
| **`test_model_live.py`** | Alternative real-time inference script for testing the model with live audio input. |
| **`neve_brain.py`** | Serial communication handler for ESP32-S3. Receives audio data via UART, buffers audio after wake detection, and forwards to AI processor for processing. |
| **`main.py`** | Master pipeline script that runs all ML steps in sequence. Call `python main.py` to run the complete pipeline. |

### Firmware Files

| File | Purpose |
|------|-------|
| **`Firmware/src/main.cpp`** | Main firmware source for ESP32-S3. Handles I2S audio capture, TF Lite Micro inference, WiFi streaming, and network communication. |
| **`Firmware/platformio.ini`** | PlatformIO configuration for ESP32-S3 DevKit. Defines board, libraries (EloquentTinyML), and build flags. |
| **`Firmware/secrets.h`** | Configuration file for WiFi credentials and other secrets. Copy from `secrets_example.h` and edit. |

---

## 🎯 How to Train a Wake Word Detection Model

### Prerequisites

```bash
# Python 3.8+ and dependencies
pip install -r requirements.txt
```

### Option 1: Run Full Pipeline (Recommended for Training from Scratch)

```bash
cd wake_word

# Run the complete pipeline
python main.py
```

The pipeline will:
1. Generate synthetic wake word audio samples using Azure TTS
2. Prepare and augment the dataset
3. Extract Energy and ZCR features from all audio files
4. Train a CNN model on the extracted features
5. Convert the model to TensorFlow Lite with Int8 quantization
6. Generate quantized TFLite model for ESP32 deployment

### Option 2: Step-by-Step (Manual Control)

```bash
# Step 1: Generate synthetic audio samples
python generate_tts.py

# Step 2: Prepare and augment the dataset
python prepare_dataset.py

# Step 3: Extract Energy and ZCR features
python extract_features.py

# Step 4: Train the model
python train_model.py

# Step 5: Convert to TFLite for embedded deployment
python convert_to_tflite.py
```

---

## 🎯 How to Deploy on ESP32-S3

### 1. Build Firmware

```bash
cd Firmware

# Build using PlatformIO CLI
pio run

# Or build and upload directly
pio run -t upload
```

### 2. Upload to Device

```bash
# Upload to ESP32-S3 DevKit
pio run -t upload

# Specify custom port if needed
pio run -t upload -p /dev/ttyUSB0
```

### 3. Configuration

Before uploading, copy and edit the secrets file:

```bash
cd Firmware
cp secrets_example.h secrets.h
# Edit secrets.h with your WiFi credentials
```

### 4. Monitor Serial Output

```bash
# Open serial monitor (115200 baud)
pio device monitor

# Or use PlatformIO CLI
pio device monitor
```

Expected startup output:
```
🤖 Nevo Autonomous Ear Booting...
✅ AI Model Loaded into S3 Core.
🎧 Mode: LOCAL LISTENING (Silent Network)
```

---

## 🧠 Model Architecture

The model is a lightweight Conv1D designed for Energy + Zero-Crossing Rate (ZCR) feature inputs.

```
Input: (64, 2, 1)  # Windows, Features (Energy+ZCR), Channels

Conv1D(32) → Conv1D(32) → MaxPool →  
Conv1D(64) → Conv1D(64) → MaxPool →  
Conv1D(128) → Conv1D(128) → MaxPool →  
Flatten → Dense(64) → ReLU → Dense(1) [sigmoid]

Total inputs: 64 windows × 2 features (Energy, ZCR) = 128 features

Output: Probability of wake word (0.0 to 1.0)
```

---

## 🚀 Usage Examples

### Real-time Detection (with Microphone)

```bash
python live_inference.py
```

The program will:
- Listen via microphone at 16kHz sample rate
- Process 1-second audio chunks (16000 samples)
- Display confidence scores in real-time
- Detect wake word when confidence > 0.8
- Apply 2-second cooldown after detection

### Serial Handler (for ESP32-S3)

```bash
python neve_brain.py
```

This script handles serial communication to receive audio data from the ESP32's ADC and forwards to the AI processor for processing.

### Test Firmware Directly

```bash
# Open PlatformIO Serial Monitor
cd Firmware
pio device monitor
```

The ESP32 will listen locally and print:
```
[Mic Vol: XXXX] | Background: 0.00 | WakeWord: 0.00
🔥 [🔥] WAKE WORD DETECTED! Confidence: 0.85
```

---

## 📊 Dataset Configuration

The dataset includes:
- **Positive samples**: Augmented "Hey Nevo" recordings (noise-injected)
- **Negative samples**: Random audio segments from clean/noise directories
- **Sample rate**: 16kHz
- **Duration per sample**: 1 second
- **Feature extraction**: 64 windows, 2 features per window (Energy, ZCR)

---

## 📦 Model Artifacts

After training, the following files are generated in the `models/` directory:

- `wake_word_model.h5` - Trained Keras model (saved before conversion)
- `wake_word_model.tflite` - Quantized TensorFlow Lite model for embedded deployment

The TFLite model is automatically included in the firmware build via the `EloquentTinyML` library.

---

## 🔧 Requirements

### Python Environment

```
Python >= 3.8
tensorflow >= 2.10
numpy >= 1.21
librosa
scikit-learn
soundfile
edge-tts
pyaudio
```

Install with:

```bash
pip install -r requirements.txt
```

### Firmware Dependencies

- PlatformIO with ESP32 package
- EloquentTinyML (EloquentTinyML@^0.0.3)

---

## 🌐 Network Mode

When the wake word is detected (confidence > 0.8):
1. ESP32 connects to WiFi
2. Sends buffered 1-second audio chunk via UDP
3. Listens for commands from AI processor
4. After 5 seconds, returns to local listening mode

---

## 📝 License

MIT License

---

## 💡 Tips

1. **First run**: Always run the full pipeline to train the model from scratch
2. **Audio quality**: Ensure microphone is connected and working before running `live_inference.py`
3. **Threshold tuning**: Modify detection threshold in firmware (`#define` near line 175 in `main.cpp`) to adjust sensitivity
4. **Model size**: The quantized model is ~250KB, suitable for embedded deployment
5. **WiFi credentials**: Edit `Firmware/secrets.h` before uploading to your device
6. **PSRAM required**: ESP32-S3 must have PSRAM enabled (automatic in platformio.ini)
7. **Serial monitor**: Use 115200 baud rate when monitoring firmware output

---

## 🐛 Troubleshooting

### Firmware won't upload
- Check USB connection and board recognition
- Ensure PlatformIO ESP32 package is installed: `pio update`

### Model inference errors
- Verify `wake_word_model.tflite` is in the models/ directory
- Check that `models/` folder exists in project root
- Ensure model was converted with `convert_to_tflite.py`

### No audio input
- Check I2S pin configuration in `Firmware/src/main.cpp`
- Verify microphone/jack connection

### WiFi connection fails
- Verify credentials in `secrets.h`
- Check router SSID/password
- Ensure WiFi signal is strong enough
