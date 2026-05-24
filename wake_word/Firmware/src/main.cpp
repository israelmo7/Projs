#include <Arduino.h>
#include <driver/i2s.h>

// --- הגדרות חומרה (INMP441 Mono) ---
#define I2S_WS 15
#define I2S_SD 3
#define I2S_SCK 17
#define I2S_PORT I2S_NUM_0
#define SAMPLE_RATE 16000

void setupI2S() {
    i2s_config_t i2s_config = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
        .sample_rate = SAMPLE_RATE,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT, // המיקרופון שולח 32 ביט
        .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,  // מיקרופון בודד (פין L/R במיקרופון מחובר ל-GND)
        .communication_format = I2S_COMM_FORMAT_STAND_I2S,
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = 8,
        .dma_buf_len = 64, // באפר קטן כי אנחנו רק קוראים דגימות בודדות לטרמינל
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
    delay(3000); // מחכים קצת כדי שהטרמינל יספיק להיפתח בלי לתקוע את ה-ESP
    
    Serial.println("\n🚀 Nevo Ears: Mono Mic Test Mode Booting...");

    // הפעלת המיקרופון
    setupI2S();
    Serial.println("🎤 Single I2S Microphone Ready!");
    Serial.println("👉 Please open the Serial Plotter to see the audio waves.");
}

void loop() {
    size_t bytesRead = 0;
    int32_t sample = 0; // משתנה בודד לקריאת הדגימה (4 בייטים)
    
    // קריאת אודיו גולמי
    esp_err_t result = i2s_read(I2S_PORT, &sample, sizeof(sample), &bytesRead, portMAX_DELAY);
    
    // אם קראנו בהצלחה את הנתון
    if (result == ESP_OK && bytesRead == sizeof(sample)) {
        
        // הסטת ביטים ימינה לחילוץ הסאונד מהרעש הדיגיטלי של פרוטוקול I2S
        int32_t audioValue = sample >> 14; 

        // הדפסה רגילה בשורה חדשה - ה-Serial Plotter יזהה את זה ויצייר גרף של קו אחד
        Serial.println(audioValue);
    }
}