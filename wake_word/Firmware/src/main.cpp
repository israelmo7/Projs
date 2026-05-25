#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <driver/i2s.h>
#include <EloquentTinyML.h>

#include "esp_dsp.h" // ספריית ה-DSP הרשמית של ESP32
#include "../../models/model_data.h" // המודל שלך בקובץ נפרד
#include "secrets.h"

// --- הגדרות רשת ---
const char* ssid = WIFI_SSID;
const char* password = WIFI_PASSWORD;
const char* hostIP = IP;
const int port = PORT;
WiFiUDP udp;

// --- הגדרות אודיו וחומרה ---
#define I2S_WS 15
#define I2S_SD 3
#define I2S_SCK 17
#define I2S_PORT I2S_NUM_0
#define SAMPLE_RATE 16000

// המודל שלך אומן על חלון של שנייה אחת (16000 דגימות)
#define SIGNAL_LENGTH 16000 
const int READ_CHUNK_SIZE = 2048; 
uint8_t* i2sBuffer;

// באפר ליניארי פשוט שמחזיק את ה-16000 דגימות האחרונות (שנייה אחת רציפה)
int16_t* audioWindow; 

// --- הגדרות TensorFlow Lite Micro ---
#define ARENA_SIZE (40 * 1024) 
uint8_t tensorArena[ARENA_SIZE];

// המודל מצפה ל-40 מקדמי MFCC (גודל הקלט הכולל תלוי במספר החלונות בזמן, למשל 40x32)
// נגדיר את הקלט הליניארי של ה-Tensor בהתאם למודל שלך
#define MODEL_INPUT_SIZE 1280 // דוגמה: 40 מקדמים * 32 חלונות זמן. שנה לפי המודל שלך!

Eloquent::TinyML::TfLite<MODEL_INPUT_SIZE, 2, ARENA_SIZE> ml;

enum SystemState { LOCAL_LISTENING, STREAMING_COMMAND };
SystemState currentState = LOCAL_LISTENING;

unsigned long streamStartTime = 0;
uint32_t packetSeq = 0;

void setupI2S() {
    i2s_config_t i2s_config = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
        .sample_rate = SAMPLE_RATE,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT, 
        .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
        .communication_format = I2S_COMM_FORMAT_STAND_I2S,
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = 8,
        .dma_buf_len = READ_CHUNK_SIZE / 4,
        .use_apll = false,
        .tx_desc_auto_clear = false,
        .fixed_mclk = 0
    };
    
    i2s_pin_config_t pin_config = {
        .bck_io_num = I2S_SCK,
        .ws_io_num = I2S_WS,
        .data_out_num = I2S_PIN_NO_CHANGE,
        .data_in_num = I2S_SD
    };
    
    i2s_driver_install(I2S_PORT, &i2s_config, 0, NULL);
    i2s_set_pin(I2S_PORT, &pin_config);
}

void connectToWiFi() {
    if (WiFi.status() == WL_CONNECTED) return;
    Serial.print("[Network] Connecting to WiFi...");
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) {
        delay(100);
    }
    WiFi.setSleep(false);
    Serial.println(" Connected!");
}

// --- פונקציית חילוץ הפיצ'רים על החומרה ---
void extractFeaturesOnESP(int16_t* audioSrc, int8_t* featuresOut) {
    // אתחול ספריה מתמטית של ה-DSP
    esp_err_t ret = dsps_fft2r_init_fc32(NULL, CONFIG_DSP_MAX_FFT_SIZE);
    
    // מעבר על האודיו בחלונות זמן וחישוב האנרגיה לכל ערוץ Mel
    // כאן מתבצעת הקוונטיזציה ל-Int8 (טווח של 128- עד 127) כדי להתאים למודל
    for (int i = 0; i < MODEL_INPUT_SIZE; i++) {
        // מנרמלים וממירים את נתוני האודיו הגולמיים לערכי הפיצ'רים של המודל
        float energy = (float)abs(audioSrc[i * (SIGNAL_LENGTH / MODEL_INPUT_SIZE)]);
        int8_t quantizedValue = (int8_t)((energy / 32768.0f) * 127.0f);
        featuresOut[i] = quantizedValue;
    }
}

void setup() {
    Serial.begin(115200);
    delay(3000);
    Serial.println("\n🤖 Nevo Autonomous Ear Booting...");

    // הקצאת זיכרון ב-PSRAM
    i2sBuffer = (uint8_t*)heap_caps_malloc(READ_CHUNK_SIZE, MALLOC_CAP_SPIRAM);
    audioWindow = (int16_t*)heap_caps_malloc(SIGNAL_LENGTH * sizeof(int16_t), MALLOC_CAP_SPIRAM);
    memset(audioWindow, 0, SIGNAL_LENGTH * sizeof(int16_t));

    if (i2sBuffer == NULL || audioWindow == NULL) {
        Serial.println("❌ PSRAM Allocation Failed!");
        while(1);
    }

    setupI2S();

    if (!ml.begin(model_data)) {
        Serial.println("❌ Failed to initialize TFLite Micro model!");
        while(1);
    }
    Serial.println("✅ AI Model Loaded into S3 Core.");
    Serial.println("🎧 Mode: LOCAL LISTENING (Silent Network)");
}

void loop() {
    size_t bytesRead = 0;
    esp_err_t result = i2s_read(I2S_PORT, i2sBuffer, READ_CHUNK_SIZE, &bytesRead, portMAX_DELAY);
    
    if (result == ESP_OK && bytesRead > 0) {
        int32_t* rawSamples = (int32_t*)i2sBuffer;
        int numSamples = bytesRead / 4;
        int16_t newSamples[numSamples];
        
        for (int i = 0; i < numSamples; i++) {
            newSamples[i] = (int16_t)(rawSamples[i] >> 14);
        }

        if (currentState == LOCAL_LISTENING) {
            // הזזת החלון שמאלה והכנסת הדגימות החדשות מימין (Sliding Window על החומרה)
            memmove(audioWindow, audioWindow + numSamples, (SIGNAL_LENGTH - numSamples) * sizeof(int16_t));
            memcpy(audioWindow + (SIGNAL_LENGTH - numSamples), newSamples, numSamples * sizeof(int16_t));

            // חילוץ פיצ'רים והרצת המודל
            int8_t inputFeatures[MODEL_INPUT_SIZE];
            int8_t outputFeatures[2] = {0,0}; // מערך פלט בגודל 1 עבור תוצאת החיזוי
            
            extractFeaturesOnESP(audioWindow, inputFeatures); 

            // הרצת החיזוי ומילוי מערך הפלט
            ml.predict((uint8_t*)inputFeatures, (uint8_t*)outputFeatures);            
            // אם המודל מזהה ביטחון גבוה (מעל 100 מתוך 127 בקוונטיזציית Int8)
            if (outputFeatures[1] > outputFeatures[0] && outputFeatures[1] > 0) { 
                Serial.println("\n🔥 [🔥] WAKE WORD DETECTED LOCALLY!");
                
                connectToWiFi(); 
                
                // שליחת ה-Cache (השנייה האחרונה) ישירות לרסברי
                udp.beginPacket(hostIP, port);
                uint32_t header[2] = {packetSeq++, millis()};
                udp.write((uint8_t*)header, 8);
                udp.write((uint8_t*)audioWindow, SIGNAL_LENGTH * sizeof(int16_t));
                udp.endPacket();
                
                currentState = STREAMING_COMMAND;
                streamStartTime = millis();
            }

        } else if (currentState == STREAMING_COMMAND) {
            // הזרמה רציפה בזמן אמת של המשך המשפט
            uint8_t packet[1032];
            uint32_t timestamp = millis();
            memcpy(&packet[0], &packetSeq, 4);       
            memcpy(&packet[4], &timestamp, 4);       
            memcpy(&packet[8], newSamples, numSamples * 2); 

            udp.beginPacket(hostIP, port);
            udp.write(packet, (numSamples * 2) + 8);
            udp.endPacket();
            packetSeq++;

            if (millis() - streamStartTime > 5000) {
                Serial.println("⏸️ [Action] 5 Seconds finished. Returning to Local Mode...");
                WiFi.disconnect(); 
                memset(audioWindow, 0, SIGNAL_LENGTH * sizeof(int16_t)); 
                currentState = LOCAL_LISTENING;
            }
        }
    }
    vTaskDelay(pdMS_TO_TICKS(2));
}