#ifndef STATOR_AUDIO_H
#define STATOR_AUDIO_H

#include <stdint.h>
#include <stddef.h>
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

// גודל מקסימלי של חבילת Opus בודדת (Payload)
#define AUDIO_MAX_PACKET_SIZE 256

/**
 * @brief מבנה נתונים לחבילת שמע נכנסת
 */
typedef struct {
    uint8_t data[AUDIO_MAX_PACKET_SIZE];
    size_t length;
} audio_packet_t;

/**
 * @brief אתחול מודול השמע
 * מפעיל את ממשק ה-I2S (תקן שמע דיגיטלי) ומכין את תור הנתונים.
 * @return ESP_OK במקרה של הצלחה.
 */
esp_err_t audio_init(void);

/**
 * @brief הפעלת משימת הפענוח (מוצמדת ל-Core 1)
 * @return ESP_OK במקרה של הצלחה.
 */
esp_err_t audio_start(void);

/**
 * @brief דחיפת חבילת Opus חדשה לתור הפענוח
 * (יקרא על ידי מודול התקשורת שיקלוט את הנתונים מהרוטור)
 * @param data מצביע לנתוני ה-Opus
 * @param len אורך הנתונים
 * @return ESP_OK אם החבילה נכנסה לתור, ESP_FAIL אם התור מלא.
 */
esp_err_t audio_enqueue_packet(const uint8_t *data, size_t len);

#ifdef __cplusplus
}
#endif

#endif // STATOR_AUDIO_H