#include "audio.h"

#include <string.h>
#include "esp_log.h"
#include "esp_err.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"

// API החדש של ESP-IDF v5 עבור I2S
#include "driver/i2s_std.h"

// ספריות הפרויקט
#include "stator/include/config.h"
#include "stator/include/audio.h"

// הערה: נדרשת התקנת ספריית libopus (למשל דרך idf_component.yml)
// #include "opus.h" 

static const char *TAG = "AUDIO";

// הגדרות I2S ו-Opus
#define AUDIO_SAMPLE_RATE 48000
#define AUDIO_CHANNELS 2 // סטריאו
#define MAX_FRAME_SIZE 2880 // מקסימום דגימות פר פריים של Opus (48kHz)

// הגדרות פינים ל-I2S (אם לא הוגדרו ב-config.h)
#ifndef AUDIO_I2S_BCLK_PIN
#define AUDIO_I2S_BCLK_PIN 17
#define AUDIO_I2S_LRCK_PIN 18 // נקרא גם WS
#define AUDIO_I2S_DOUT_PIN 19
#endif

static i2s_chan_handle_t s_tx_chan = NULL;
static QueueHandle_t s_audio_queue = NULL;
static TaskHandle_t s_audio_task_handle = NULL;

// מצביע למפענח (כרגע ב-void עד שנוסיף את ספריית Opus לקימפול)
//static void *s_opus_decoder = NULL; 

/**
 * @brief משימת ה-FreeRTOS שרצה על ליבה 1 (Core 1) וטוחנת את האודיו
 */
static void audio_decoder_task(void *arg)
{
    ESP_LOGI(TAG, "Audio decoder task started on Core 1.");
    
    audio_packet_t packet;
    int16_t pcm_buffer[MAX_FRAME_SIZE * AUDIO_CHANNELS]; // חוצץ לשמע מפענח (Raw PCM)

    // TODO: יצירת אובייקט ה-Opus Decoder האמיתי ברגע שהספרייה תשולב
    // int err;
    // s_opus_decoder = opus_decoder_create(AUDIO_SAMPLE_RATE, AUDIO_CHANNELS, &err);

    while (1) {
        // 1. המתנה לחבילה מהתור (חוסם את המשימה כדי לא לבזבז CPU כשאין שמע)
        if (xQueueReceive(s_audio_queue, &packet, portMAX_DELAY) == pdTRUE) {
            
            // 2. פענוח החבילה מ-Opus ל-PCM
            /* * כאן תיכנס פקודת הפענוח האמיתית:
             * int decoded_samples = opus_decode((OpusDecoder*)s_opus_decoder, packet.data, packet.length, pcm_buffer, MAX_FRAME_SIZE, 0);
             */
             
            // נדמה פענוח מוצלח (לצורך בניית התשתית)
            int decoded_samples = 960; // חבילה טיפוסית של 20ms ב-48kHz
            size_t bytes_to_write = decoded_samples * AUDIO_CHANNELS * sizeof(int16_t);
            size_t bytes_written = 0;

            // 3. הזרקת ה-PCM ישירות ל-I2S DMA ששולח למגברים
            if (s_tx_chan != NULL) {
                esp_err_t ret = i2s_channel_write(s_tx_chan, pcm_buffer, bytes_to_write, &bytes_written, portMAX_DELAY);
                if (ret != ESP_OK) {
                    ESP_LOGW(TAG, "I2S write timeout or error.");
                }
            }
        }
    }
}

esp_err_t audio_init(void)
{
    ESP_LOGI(TAG, "Initializing I2S Audio Subsystem...");

    // 1. יצירת ערוץ ה-I2S (Transmit)
    i2s_chan_config_t chan_cfg = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0, I2S_ROLE_MASTER);
    ESP_ERROR_CHECK(i2s_new_channel(&chan_cfg, &s_tx_chan, NULL));

    // 2. הגדרת התקן (Standard Mode) - 48kHz, 16-bit, Stereo
    i2s_std_config_t std_cfg = {
        .clk_cfg  = I2S_STD_CLK_DEFAULT_CONFIG(AUDIO_SAMPLE_RATE),
        .slot_cfg = I2S_STD_MSB_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_16BIT, I2S_SLOT_MODE_STEREO),
        .gpio_cfg = {
            .mclk = I2S_GPIO_UNUSED,    // ה-MAX98357A לא צריך MCLK
            .bclk = AUDIO_I2S_BCLK_PIN, // Bit Clock
            .ws   = AUDIO_I2S_LRCK_PIN, // Word Select (L/R)
            .dout = AUDIO_I2S_DOUT_PIN, // Data Out
            .din  = I2S_GPIO_UNUSED,
            .invert_flags = {
                .mclk_inv = false,
                .bclk_inv = false,
                .ws_inv   = false,
            },
        },
    };
    ESP_ERROR_CHECK(i2s_channel_init_std_mode(s_tx_chan, &std_cfg));

    // 3. הפעלת ה-I2S והכנת חוצצי ה-DMA חומרתית
    ESP_ERROR_CHECK(i2s_channel_enable(s_tx_chan));

    // 4. יצירת התור הפנימי שלנו לחבילות שמע (עד 20 חבילות בהמתנה = כמעט חצי שנייה של באפר)
    s_audio_queue = xQueueCreate(20, sizeof(audio_packet_t));
    if (s_audio_queue == NULL) {
        ESP_LOGE(TAG, "Failed to create audio queue!");
        return ESP_FAIL;
    }

    ESP_LOGI(TAG, "Audio subsystem initialized successfully.");
    return ESP_OK;
}

esp_err_t audio_start(void)
{
    if (s_audio_task_handle != NULL) {
        return ESP_OK; // כבר רץ
    }

    // הפעלת משימת הפענוח והצמדתה לליבה 1 !
    // עדיפות 5 (גבוהה, אבל לא מפריעה לפסיקות הריחוף של ליבה 0)
    BaseType_t ret = xTaskCreatePinnedToCore(
        audio_decoder_task,
        "audio_task",
        8192, // דורש הרבה מחסנית (Stack) בגלל פענוח ה-Opus
        NULL,
        5,
        &s_audio_task_handle,
        1     // Core 1
    );

    if (ret != pdPASS) {
        ESP_LOGE(TAG, "Failed to create audio task");
        return ESP_FAIL;
    }

    return ESP_OK;
}

esp_err_t audio_enqueue_packet(const uint8_t *data, size_t len)
{
    if (s_audio_queue == NULL || data == NULL || len == 0 || len > AUDIO_MAX_PACKET_SIZE) {
        return ESP_ERR_INVALID_ARG;
    }

    audio_packet_t packet;
    packet.length = len;
    memcpy(packet.data, data, len);

    // ניסיון לדחוף את החבילה לתור עם המתנה של עד 5 מילישניות
    if (xQueueSend(s_audio_queue, &packet, pdMS_TO_TICKS(5)) != pdTRUE) {
        ESP_LOGW(TAG, "Audio queue full! Packet dropped.");
        return ESP_FAIL;
    }

    return ESP_OK;
}