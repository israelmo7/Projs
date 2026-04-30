# Wake Word Detection Project

A complete pipeline for training and deploying a wake word recognition model (e.g., "Hey Nevo") using TensorFlow/Keras with TensorFlow Lite Micro support for ESP32-S3 deployment.

---

## 📁 Project Structure

```
wake_word/
├── dataset/                    # Audio datasets
│   ├── clean/                  # Clean audio samples for negative training
│   ├── noise/                  # Background noise samples for augmentation
│   ├── positive_raw/           # Raw "Hey Nevo" audio files
│   ├── train/                  # Training data (positive/negative splits)
│   └── test/                   # Test dataset
├── models/                     # Trained models
│   ├── wake_word_model.h5      # Keras model (PyTorch/TensorFlow)
│   ├── wake_word_model.tflite  # TensorFlow Lite quantized model
│   ├── model_data.h            # C header for direct inclusion in firmware
│   └── requirements.txt        # Model deployment dependencies
├── prepared_features/          # Preprocessed MFCC features
│   ├── data_train.npy          # Training MFCC features
│   ├── data_val.npy            # Validation MFCC features
│   └── y_data_train.npy         # Training labels (1=positive, 0=negative)
├── raw_audio/                  # Generated TTS audio files
└── *.py                        # Python scripts
```

---

## 📄 Files and Their Purposes

| File | Purpose |
|------|---------|
| **`generate_tts.py`** | Generates synthetic "Hey Nevo" audio samples using Azure TTS with various voices, rates, and pitches. Creates diverse training data. |
| **`prepare_dataset.py`** | Prepares the dataset by: 1) Loading raw audio, 2) Applying data augmentation (pitch shift, time stretch, noise injection), 3) Generating negative samples, 4) Organizing files into train directories. |
| **`extract_features.py`** | Extracts MFCC (Mel-frequency Cepstral Coefficients) features from audio files. Pads/trims audio to uniform duration and splits into train/validation sets. Saves as NumPy arrays. |
| **`train_model.py`** | Builds and trains a CNN model using TensorFlow/Keras. Accepts pretrained MFCC features and train/val splits. Outputs a trained `.h5` model. |
| **`convert_to_tflite.py`** | Converts the trained Keras model to TensorFlow Lite format with Int8 quantization. Generates a C header file (`model_data.h`) for direct inclusion in ESP32 firmware. |
| **`run_pipeline.py`** | Executes the full ML pipeline in order: `generate_tts` → `prepare_dataset` → `extract_features` → `train_model` → `convert_to_tflite`. |
| **`live_inference.py`** | Real-time wake word detection from microphone input. Processes audio chunks, extracts MFCC features, and runs inference on the trained model. Prints confidence scores. |
| **`nevo_brain.py`** | Serial communication handler for ESP32-S3. Receives audio data via UART, buffers audio after wake detection, and forwards to AI processor for processing. |
| **`requirements.txt`** | Dependencies for the model deployment. Use `pip install -r requirements.txt` to install. |

---

## 🎯 How to Create a Wake Word Detection Model

### Option 1: Run Full Pipeline (Recommended for Training from Scratch)

This runs all steps in order to train a model from scratch:

```bash
cd wake_word

# 1. Install dependencies
pip install -r models/requirements.txt

# 2. Run the full pipeline
python run_pipeline.py
```

The pipeline will:
1. Generate synthetic wake word audio samples using Azure TTS
2. Prepare and augment the dataset
3. Extract MFCC features from all audio files
4. Train a CNN model on the extracted features
5. Convert the model to TensorFlow Lite with Int8 quantization
6. Generate C header file for ESP32 deployment

### Option 2: Step-by-Step (Manual Control)

For more control, run each step individually:

```bash
# Step 1: Generate synthetic audio samples
python generate_tts.py

# Step 2: Prepare and augment the dataset
python prepare_dataset.py

# Step 3: Extract MFCC features
python extract_features.py

# Step 4: Train the model
python train_model.py

# Step 5: Convert to TFLite for embedded deployment
python convert_to_tflite.py
```

### Option 3: Test Pretrained Model

If you have a pretrained model in `models/wake_word_model.h5`, you can skip training steps and go straight to testing:

```bash
# Test with microphone input
python live_inference.py
```

---

## 🧠 Model Architecture

The model is a lightweight CNN designed for MFCC feature inputs:

```
Input: (1, 32, 40, 1)  # Batch, Time Frames, MFCCs, Channels

Conv2D(16) → Conv2D(16) → MaxPool →  
Conv2D(32) → Conv2D(32) → MaxPool →  
Conv2D(64) → Conv2D(64) → MaxPool →  
Flatten → Dense(128) → Dropout(0.5) → Dense(1) [sigmoid]

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
- Process 1-second audio chunks
- Display confidence scores in real-time
- Detect wake word when confidence > 50%
- Apply 2-second cooldown after detection

### Serial Handler (for ESP32-S3)

```bash
python neve_brain.py
```

This script handles serial communication to receive audio data from the ESP32's ADC and forwards to the AI processor for processing.

---

## 📊 Dataset Configuration

The dataset includes:
- **Positive samples**: Augmented "Hey Nevo" recordings (pitch-shifted, time-stretched, noise-injected)
- **Negative samples**: Random audio segments from clean/noise directories
- **Sample rate**: 16kHz
- **Duration per sample**: 1 second
- **MFCC features**: 40 coefficients

---

## 📦 Deployment

The trained model is converted to TensorFlow Lite Micro format and packaged as:
- `wake_word_model.tflite` - The quantized model binary
- `model_data.h` - C header file with the model data as a const array

These files can be directly included in ESP-IDF or Arduino projects for embedded deployment on ESP32-S3.

---

## 🔧 Requirements

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
pip install -r models/requirements.txt
```

---

## 📝 License

MIT License

---

## 💡 Tips

1. **First run**: Always run the full pipeline to train the model from scratch
2. **Audio quality**: Ensure microphone is connected and working before running `live_inference.py`
3. **Threshold tuning**: Modify `DETECTION_THRESHOLD` in `live_inference.py` to adjust sensitivity
4. **Model size**: The quantized model is ~100KB, suitable for embedded deployment
