#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <driver/i2s.h>
#include "secrets.h"

// --- הגדרות רשת ---
const char* ssid = WIFI_SSID;
const char* password = WIFI_PASSWORD;
const char* hostIP = IP;
const int port = PORT;

WiFiUDP udp;

// --- הגדרות חומרה (INMP441 Mono) ---
#define I2S_WS 15
#define I2S_SD 3
#define I2S_SCK 17
#define I2S_PORT I2S_NUM_0
#define SAMPLE_RATE 16000

uint8_t* audioBuffer;
// הוגדל ל-2048 כדי למנוע את שגיאה 12 (נותן לראוטר זמן לנשום)
const int READ_CHUNK_SIZE = 2048; 
uint32_t packetSeq = 0; 

void setupI2S() {
    i2s_config_t i2s_config = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
        .sample_rate = SAMPLE_RATE,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT, 
        .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,  // מונו!
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

void setup() {
    Serial.begin(115200);
    delay(3000); 
    
    Serial.println("\n🚀 Nevo Ears: Live Streaming Mode Booting...");

    audioBuffer = (uint8_t*)heap_caps_malloc(READ_CHUNK_SIZE, MALLOC_CAP_SPIRAM);
    if (audioBuffer == NULL) {
        Serial.println("❌ Failed to allocate PSRAM.");
        while (1);
    }

    setupI2S();
    Serial.println("🎤 Mono Microphone Ready.");

    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println("\n✅ Connected to WiFi!");
    WiFi.setSleep(false); 
}

void loop() {
    size_t bytesRead = 0;
    esp_err_t result = i2s_read(I2S_PORT, audioBuffer, READ_CHUNK_SIZE, &bytesRead, portMAX_DELAY);
    
    if (result == ESP_OK && bytesRead > 0) {
        int32_t* rawSamples = (int32_t*)audioBuffer;
        
        // המרה ל-16 ביט
        int numSamples = bytesRead / 4;
        int16_t samples16[numSamples];
        for (int i = 0; i < numSamples; i++) {
            samples16[i] = (int16_t)(rawSamples[i] >> 14); 
        }

        // אריזת חבילה (8 בייטים הדר + דאטה מנורמל)
        size_t payloadSize = numSamples * 2;
        uint8_t packet[1032]; 
        uint32_t timestamp = millis();
        
        memcpy(&packet[0], &packetSeq, 4);       
        memcpy(&packet[4], &timestamp, 4);       
        memcpy(&packet[8], samples16, payloadSize); 

        // שידור
        udp.beginPacket(hostIP, port);
        udp.write(packet, payloadSize + 8);
        udp.endPacket();
        
        packetSeq++;
    }
    // הוגדל ל-5 כדי למנוע קריסות ברשת
    vTaskDelay(pdMS_TO_TICKS(5)); 
}