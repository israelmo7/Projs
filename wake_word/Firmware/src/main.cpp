#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <driver/i2s.h>
#include "secrets.h"

// 2. קריאת המשתנה באמצעות הפונקציה הסטנדרטית של C++

// --- הגדרות רשת ---
const char* ssid = (const char*)WIFI_SSID;
const char* password = (const char*)WIFI_PASSWORD;
const char* hostIP = (const char*)IP;
const int port = (int)PORT;

WiFiUDP udp;

// --- הגדרות חומרה (INMP441 Stereo) ---
#define I2S_WS 15
#define I2S_SD 3
#define I2S_SCK 17
#define I2S_PORT I2S_NUM_0
#define SAMPLE_RATE 16000

uint8_t* audioBuffer;
const int READ_CHUNK_SIZE = 1024; // קריאה במנות קטנות כדי לשמור על זמן אמת
uint32_t packetSeq = 0; 

void setupI2S() {
    i2s_config_t i2s_config = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
        .sample_rate = SAMPLE_RATE,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT, // המיקרופון שולח 32 ביט
        .channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT, // תמיכה בשני מיקרופונים (סטריאו)
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
    delay(3000); // מחכים קצת כדי שהטרמינל יספיק להיפתח בלי לתקוע את ה-S3
    
    Serial.println("\n🚀 Nevo Ears: Booting Up...");

    // 1. הקצאת זיכרון ב-PSRAM
    audioBuffer = (uint8_t*)heap_caps_malloc(READ_CHUNK_SIZE, MALLOC_CAP_SPIRAM);
    if (audioBuffer == NULL) {
        Serial.println("❌ Critical Error: Failed to allocate PSRAM.");
        while (1);
    }

    // 2. הפעלת מיקרופונים
    setupI2S();
    Serial.println("🎤 I2S Microphones Ready.");

    // 3. חיבור לרשת
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println("\n✅ Connected to WiFi!");
    
    // קריטי למניעת שגיאה 12 (ENOMEM) בשידור UDP מהיר
    WiFi.setSleep(false); 
    
    Serial.println("🎧 Listening and Streaming...");
}

void loop() {
    size_t bytesRead = 0;
    
    // קריאת אודיו גולמי לתוך ה-PSRAM
    esp_err_t result = i2s_read(I2S_PORT, audioBuffer, READ_CHUNK_SIZE, &bytesRead, portMAX_DELAY);
    
    if (result == ESP_OK && bytesRead > 0) {
        int32_t* rawSamples = (int32_t*)audioBuffer;
        
        // --- חיווי חיים ובדיקת חומרה (כל שנייה) ---
        static unsigned long lastPrint = 0;
        if (millis() - lastPrint > 1000) {
            Serial.printf("Raw Mic Value: %d | Free PSRAM: %u bytes\n", rawSamples[0], ESP.getFreePsram());
            lastPrint = millis();
        }

        // --- המרה מ-32 ביט ל-16 ביט (Downsampling) ---
        int numSamples = bytesRead / 4;
        int16_t samples16[numSamples];
        for (int i = 0; i < numSamples; i++) {
            // הסטת ביטים ימינה כדי לחלץ את הסאונד מהרעש הדיגיטלי
            samples16[i] = (int16_t)(rawSamples[i] >> 14); 
        }

        // --- אריזת הנתונים בפרוטוקול המותאם שלנו ---
        size_t payloadSize = numSamples * 2;
        uint8_t packet[1032]; // 8 בייטים של הדר + 1024 בייטים מקסימום דאטה
        uint32_t timestamp = millis();
        
        memcpy(&packet[0], &packetSeq, 4);       // מזהה חבילה רציף
        memcpy(&packet[4], &timestamp, 4);       // חותמת זמן
        memcpy(&packet[8], samples16, payloadSize); // הסאונד עצמו

        // --- שידור לרשת ---
        udp.beginPacket(hostIP, port);
        udp.write(packet, payloadSize + 8);
        udp.endPacket();
        
        packetSeq++;
    }
    
    // השהייה מינימלית לשמירה על יציבות הראוטר הביתי
    vTaskDelay(pdMS_TO_TICKS(2)); 
}