#ifndef STATOR_SAFETY_H
#define STATOR_SAFETY_H

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief אתחול מודול הבטיחות.
 * מגדיר את כלב השמירה (TWDT) ומפעיל משימת בקרה שרצה ברקע (על ליבה 1) 
 * ומנטרת את יציבות הריחוף כדי למנוע שריפת סלילים.
 * * @return ESP_OK במקרה של הצלחה.
 */
esp_err_t safety_init(void);

#ifdef __cplusplus
}
#endif

#endif // STATOR_SAFETY_H