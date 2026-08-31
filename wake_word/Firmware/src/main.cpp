#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <driver/i2s.h>
#include <EloquentTinyML.h>

#include "../../models/model_data.h"
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

// באפר ליניארי פשוט שמחזיק את ה-16000 דגימות האחרונות
int16_t* audioWindow; 

// --- הגדרות TensorFlow Lite Micro ---
#define ARENA_SIZE (40 * 1024) 
uint8_t tensorArena[ARENA_SIZE];
#define MODEL_INPUT_SIZE 128
Eloquent::TinyML::TfLite<MODEL_INPUT_SIZE, 2, ARENA_SIZE> ml;

enum SystemState { LOCAL_LISTENING, STREAMING_COMMAND };
SystemState currentState = LOCAL_LISTENING;

unsigned long streamStartTime = 0;
uint32_t packetSeq = 0;

// =========================================================================
// 🌟 התיקון: מערכים ענקיים הועברו לזיכרון הגלובלי כדי למנוע Stack Overflow
// =========================================================================
int16_t newSamples[READ_CHUNK_SIZE / 4]; // באפר זמני לקריאה מהמיקרופון (512 דגימות)
float inputFeatures[MODEL_INPUT_SIZE];   // מערך הפיצ'רים שיוזן למודל (5KB)
uint8_t udpPacket[1032];                 // חבילת הרשת לשידור (1KB)
float outputFeatures[2] = {0.0f, 0.0f};  // תוצאות החיזוי

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

void extractFeaturesOnESP(int16_t* audioSrc, float* featuresOut) {
    int windows = 64;
    int step = SIGNAL_LENGTH / windows; // 250
    
    for (int i = 0; i < windows; i++) {
        long energySum = 0;
        int zcrCount = 0;
        int startIndex = i * step;
        
        for (int j = 0; j < step; j++) {
            int16_t val = audioSrc[startIndex + j];
            energySum += abs(val);
            
            // חישוב ZCR
            if (j > 0) {
                int16_t prev = audioSrc[startIndex + j - 1];
                if ((val >= 0 && prev < 0) || (val < 0 && prev >= 0)) {
                    zcrCount++;
                }
            }
        }
        
        float avgEnergy = (float)energySum / step;
        // הכנסת הערכים ברצף: פעם אנרגיה, פעם ZCR
        featuresOut[i * 2] = avgEnergy / 32768.0f; 
        featuresOut[i * 2 + 1] = (float)zcrCount / step; 
    }
}

void setup() {
    Serial.begin(115200);
    delay(3000);
    Serial.println("\n🤖 Nevo Autonomous Ear Booting...");

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
        
        for (int i = 0; i < numSamples; i++) {
            newSamples[i] = (int16_t)(rawSamples[i] >> 14);
        }

        if (currentState == LOCAL_LISTENING) {
            memmove(audioWindow, audioWindow + numSamples, (SIGNAL_LENGTH - numSamples) * sizeof(int16_t));
            memcpy(audioWindow + (SIGNAL_LENGTH - numSamples), newSamples, numSamples * sizeof(int16_t));

            int16_t maxSample = 0;
            for (int i = 0; i < numSamples; i++) {
                if (abs(newSamples[i]) > maxSample) maxSample = abs(newSamples[i]);
            }

            extractFeaturesOnESP(audioWindow, inputFeatures); 
            ml.predict(inputFeatures, outputFeatures);            
            
            #define PRINT_THROTTLE_MS 500
            static unsigned long lastPrintTime = 0;
            if (millis() - lastPrintTime > PRINT_THROTTLE_MS) {
                lastPrintTime = millis();
                Serial.printf("[Mic Vol: %5d] | Background: %.2f | WakeWord: %.2f\n", 
                              maxSample, outputFeatures[0], outputFeatures[1]);
                Serial.printf("{\"wake\":%.2f,\"bg\":%.2f,\"state\":\"listening\",\"vol\":%d}\n",
                              outputFeatures[1], outputFeatures[0], maxSample);
            }

            if (outputFeatures[1] > 0.80f) { 
                Serial.printf("\n🔥 [🔥] WAKE WORD DETECTED! Confidence: %.2f\n", outputFeatures[1]);
                Serial.printf("{\"wake\":%.2f,\"bg\":%.2f,\"state\":\"streaming\"}\n",
                              outputFeatures[1], outputFeatures[0]);
                connectToWiFi(); 
                
                udp.beginPacket(hostIP, port);
                uint32_t header[2] = {packetSeq++, millis()};
                udp.write((uint8_t*)header, 8);
                udp.write((uint8_t*)audioWindow, SIGNAL_LENGTH * sizeof(int16_t));
                udp.endPacket();
                
                currentState = STREAMING_COMMAND;
                streamStartTime = millis();
            }

        } else if (currentState == STREAMING_COMMAND) {
            uint32_t timestamp = millis();
            memcpy(&udpPacket[0], &packetSeq, 4);       
            memcpy(&udpPacket[4], &timestamp, 4);       
            memcpy(&udpPacket[8], newSamples, numSamples * 2); 

            udp.beginPacket(hostIP, port);
            udp.write(udpPacket, (numSamples * 2) + 8);
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