#ifndef STATOR_ROTATION_H
#define STATOR_ROTATION_H

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief אתחול מודול הסיבוב (DRV8313).
 * מגדיר את טיימר ה-MCPWM, הקומפרטורים והפינים עבור 3 הפאזות.
 * * @return ESP_OK במקרה של הצלחה, או קוד שגיאה.
 */
esp_err_t rotation_init(void);

/**
 * @brief הפעלת משימת ה-FreeRTOS של מנוע ה-SPWM (מוצמדת ל-Core 0).
 * * @return ESP_OK במקרה של הצלחה.
 */
esp_err_t rotation_start(void);

/**
 * @brief עדכון מהירות הסיבוב של הדיסק.
 * * @param delay_ms זמן ההשהיה במילי-שניות (ערך נמוך יותר = סיבוב מהיר יותר).
 */
void rotation_set_speed(int delay_ms);

#ifdef __cplusplus
}
#endif

#endif // STATOR_ROTATION_H