#include "safety.h"

#include <stdlib.h>
#include "esp_log.h"
#include "esp_system.h"
#include "esp_task_wdt.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "stator/include/levitation.h"
#include "stator/include/safety.h"

static const char *TAG = "SAFETY";

// סף סטייה קריטי מנקודת הכיול. אם הסטייה גדולה מהסף הזה, זה אומר שהדיסק כבר לא שם.
#define DROP_THRESHOLD_ADC 800 

static void safety_monitor_task(void *arg)
{
    ESP_LOGI(TAG, "Safety monitor task started on Core 1.");

    // רושמים את המשימה הזו אצל כלב השמירה (כדי שיוודא שהיא לא נתקעת)
    esp_task_wdt_add(NULL);

    while (1) {
        // "מאכילים" את כלב השמירה כדי שלא יאתחל את המכשיר
        esp_task_wdt_reset();

        // בודקים חריגות רק אם המערכת באוויר ומכוילת
        if (lev_state.is_calibrated) {
            for (int i = 0; i < 3; i++) {
                int current_val = lev_state.current_adc[i];
                int baseline = lev_state.hall_offsets[i];
                
                int deviation = abs(current_val - baseline);

                if (deviation > DROP_THRESHOLD_ADC) {
                    ESP_LOGE(TAG, "CRITICAL FAULT: Drop detected on axis %d! Deviation: %d", i, deviation);
                    ESP_LOGE(TAG, "Hardware protection triggered. Restarting system to cut power to coils!");
                    
                    // פעולת מניעה אגרסיבית: אתחול חומרתי חותך מיד את אותות ה-PWM 
                    // ומשאיר את הפינים במצב צף (Safe State) כדי שהזרם לסלילים ייעצר ב-0 מילישניות.
                    esp_restart();
                }
            }
        }

        // המשימה הולכת לישון ל-10 מילישניות (לא צורכת כוח עיבוד)
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}

esp_err_t safety_init(void)
{
    ESP_LOGI(TAG, "Initializing Hardware Safety Module...");

    // 1. הגדרת Task Watchdog Timer (קריסה אחרי 2 שניות ללא תגובה)
    esp_task_wdt_config_t wdt_config = {
        .timeout_ms = 2000,
        .idle_core_mask = (1 << portNUM_PROCESSORS) - 1, // ניטור של שתי הליבות
        .trigger_panic = true, // גורם ל-Kernel Panic והדפסת שגיאות למסך
    };
    
    // ב-ESP-IDF v5 ייתכן שה-WDT מופעל כבר ב-Boot. ננסה לאתחל, ואם כשל, פשוט נמשיך.
    esp_task_wdt_init(&wdt_config);

    // 2. הפעלת משימת הניטור על ליבה 1 (כדי לא להפריע לליבה 0 שמריצה את ה-10kHz החומרתי)
    xTaskCreatePinnedToCore(
        safety_monitor_task, 
        "safety_task", 
        4096, 
        NULL, 
        10,  // עדיפות גבוהה (High Priority)
        NULL, 
        1    // הצמדה ל-Core 1
    );

    return ESP_OK;
}