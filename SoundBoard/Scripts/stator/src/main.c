#include <stdio.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "nvs_flash.h"

// ספריות המודולים של הפרויקט
#include "stator/include/config.h"
#include "stator/include/levitation.h"
#include "stator/include/rotation.h"
#include "stator/include/safety.h"
#include "stator/include/audio.h"

static const char *TAG = "MAIN_BOOT";

void app_main(void)
{
    ESP_LOGI(TAG, "========================================");
    ESP_LOGI(TAG, "   SoundBoard Stator Boot Sequence      ");
    ESP_LOGI(TAG, "========================================");

    // 1. אתחול NVS (זיכרון קבוע לא נדיף) - נדרש עבור תתי-מערכות פנימיות רבות ב-ESP-IDF
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    // 2. אתחול הגדרות החומרה (הקמת צינורות ה-ADC, ה-MCPWM וכלבי השמירה)
    ESP_LOGI(TAG, "[1/4] Initializing Hardware Subsystems...");
    ESP_ERROR_CHECK(levitation_hardware_init());
    ESP_ERROR_CHECK(rotation_init());
    ESP_ERROR_CHECK(safety_init());
    ESP_ERROR_CHECK(audio_init());

    // 3. תהליך כיול עצמי של חיישני ה-Hall (חוסם את המשך העלייה עד לקבלת ערכי בסיס יציבים)
    ESP_LOGI(TAG, "[2/4] Calibrating Hall Sensors...");
    if (!levitation_calibrate_halls()) {
        ESP_LOGE(TAG, "FATAL: Hall sensor calibration failed! Output out of safe bounds.");
        ESP_LOGE(TAG, "Halting boot process permanently to protect hardware.");
        
        // מלכודת בטיחות אינסופית - מונעת מהמערכת להפעיל סלילים עם ערכי כיול שגויים
        while (1) {
            vTaskDelay(pdMS_TO_TICKS(1000));
        }
    }
    ESP_LOGI(TAG, "Calibration successful. Sensor baselines locked.");

    // 4. הפעלת חוגי הבקרה והמשימות האסינכרוניות
    ESP_LOGI(TAG, "[3/4] Igniting Control Loops...");
    
    // הפעלת פסיקת ה-Hardware Timer של הריחוף (קצב של 10kHz באופן עצמאי בחומרה)
    ESP_ERROR_CHECK(levitation_start_loop()); 
    
    // הזנקת משימת ה-SPWM לסיבוב הדיסק (מנוהלת בתוך המודול ומוצמדת ל-Core 0)
    ESP_ERROR_CHECK(rotation_start());

    // הזנקת משימת פענוח השמע על Core 1
    ESP_ERROR_CHECK(audio_start());

    ESP_LOGI(TAG, "[4/4] === SYSTEM ACTIVE AND FLOATING ===");

    // 5. הלולאה הראשית של app_main משוחררת לחלוטין מניהול זמן-אמת קשיח
    // ננצל אותה להזרמת נתוני טלמטריה איטיים לטרמינל לצורך ניטור וכיול עתידי
    while (1) {
        // הדפסת הסטייה הנוכחית של ה-ADC מנקודת האפס המכוילת (אחת לשנייה)
        ESP_LOGI("TELEMETRY", "X_Dev: %d | Y_Dev: %d | Z_Dev: %d", 
                 lev_state.current_adc[0] - lev_state.hall_offsets[0],
                 lev_state.current_adc[1] - lev_state.hall_offsets[1],
                 lev_state.current_adc[2] - lev_state.hall_offsets[2]);

        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}