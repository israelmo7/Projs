#include <stdio.h>
#include <string.h>
#include <math.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "driver/gpio.h"
#include "esp_adc/adc_oneshot.h"
#include "driver/ledc.h"

#include "stator/include/config.h"
#include "stator/include/diagnostic.h"

static const char *TAG = "DIAGNOSTIC";

// מגדירים מתח עדין מאוד (5% מתוך רזולוציה של 8 ביט = 13) 
// כדי לבדוק שהסלילים ממגנטים בלי לחמם את ה-DRV8871
#define SAFE_TEST_DUTY 13 

/**
 * בדיקה 1: קריאה סטרילית של חיישני ה-Hall הליניאריים
 * המטרה: לראות שהחיישנים מולחמים נכון ושאין נתק (הערכים צריכים לנוע סביב 2048)
 */
static void test_adc_sensors(void) {
    ESP_LOGI(TAG, "--- Starting ADC Sterile Test ---");
    ESP_LOGI(TAG, "Move a magnet over the sensors. Test ends after 100 samples.");
    
    adc_oneshot_unit_handle_t adc_handle;
    adc_oneshot_unit_init_cfg_t init_config = { .unit_id = ADC_UNIT_1 };
    adc_oneshot_new_unit(&init_config, &adc_handle);

    adc_oneshot_chan_cfg_t config = {
        .bitwidth = ADC_BITWIDTH_12,
        .atten = ADC_ATTEN_DB_12,
    };
    
    int channels[3] = {HALL1_ADC_CHANNEL, HALL2_ADC_CHANNEL, HALL3_ADC_CHANNEL};
    for (int i = 0; i < 3; i++) {
        adc_oneshot_config_channel(adc_handle, channels[i], &config);
    }

    int val[3];
    for(int i = 0; i < 100; i++) {
        adc_oneshot_read(adc_handle, channels[0], &val[0]);
        adc_oneshot_read(adc_handle, channels[1], &val[1]);
        adc_oneshot_read(adc_handle, channels[2], &val[2]);
        
        // מדפיס בפורמט ש-Serial Plotter יכול לקרוא ולצייר כגרף
        printf("X:%d, Y:%d, Z:%d\n", val[0], val[1], val[2]);
        vTaskDelay(pdMS_TO_TICKS(100));
    }
    
    adc_oneshot_del_unit(adc_handle);
    ESP_LOGI(TAG, "ADC Test Complete.\n");
}

/**
 * בדיקה 2: בדיקת שרירים (Coils & DRV8871)
 * המטרה: לוודא שהזרם מגיע לסלילים ויש שדה מגנטי (ניתן להרגיש עם מברג קטן)
 */
static void test_coils_safe_pwm(void) {
    ESP_LOGW(TAG, "--- Starting SAFE Coil PWM Test (5%% Power) ---");
    ESP_LOGI(TAG, "Place a screwdriver near Coil 1. It should vibrate slightly.");

    // נשתמש ב-LEDC הפשוט במקום ב-MCPWM המורכב רק לצורך הבדיקה הבסיסית
    ledc_timer_config_t ledc_timer = {
        .speed_mode       = LEDC_LOW_SPEED_MODE,
        .timer_num        = LEDC_TIMER_0,
        .duty_resolution  = LEDC_TIMER_8_BIT,
        .freq_hz          = 5000, 
        .clk_cfg          = LEDC_AUTO_CLK
    };
    ledc_timer_config(&ledc_timer);

    ledc_channel_config_t ledc_channel = {
        .speed_mode     = LEDC_LOW_SPEED_MODE,
        .channel        = LEDC_CHANNEL_0,
        .timer_sel      = LEDC_TIMER_0,
        .intr_type      = LEDC_INTR_DISABLE,
        .gpio_num       = 4, // COIL1_IN1_PIN 
        .duty           = 0, 
        .hpoint         = 0
    };
    ledc_channel_config(&ledc_channel);

    ESP_LOGI(TAG, "Energizing Coil 1 for 3 seconds...");
    ledc_set_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0, SAFE_TEST_DUTY);
    ledc_update_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0);
    
    vTaskDelay(pdMS_TO_TICKS(3000));
    
    ESP_LOGI(TAG, "Stopping coil.");
    ledc_set_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0, 0);
    ledc_update_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0);
    
    ESP_LOGI(TAG, "Coil Test Complete.\n");
}

/**
 * בדיקה 3: הרצת רקע של DRV8313 (Rotation) לבדיקת EMI על החיישנים
 */
static void test_rotation_emi(void) {
    ESP_LOGW(TAG, "--- Starting Rotation EMI Test ---");
    ESP_LOGI(TAG, "This will enable the DRV8313 Enable pin to check for short circuits.");
    
    // מפעילים רק את פין ה-Enable. אם הלוח קורס פה, יש קצר ב-DRV8313
    gpio_config_t io_conf = {
        .pin_bit_mask = (1ULL << 12), // ROT_EN_PIN
        .mode = GPIO_MODE_OUTPUT,
    };
    gpio_config(&io_conf);
    
    ESP_LOGI(TAG, "Setting DRV8313 EN to HIGH for 2 seconds...");
    gpio_set_level(12, 1);
    vTaskDelay(pdMS_TO_TICKS(2000));
    
    ESP_LOGI(TAG, "Disabling DRV8313.");
    gpio_set_level(12, 0);
    ESP_LOGI(TAG, "Rotation EMI Test Complete.\n");
}

/**
 * התפריט הראשי של הבדיקות
 */
void diagnostic_run_cli(void) {
    vTaskDelay(pdMS_TO_TICKS(1000)); // לתת לטרמינל זמן להתחבר
    
    while(1) {
        printf("\n===================================\n");
        printf("   SoundBoard Hardware Bring-Up\n");
        printf("===================================\n");
        printf("[1] Test ADC Hall Sensors (Sterile)\n");
        printf("[2] Test DRV8871 Coils (5%% Safe PWM)\n");
        printf("[3] Test DRV8313 Rotation Enable\n");
        printf("[4] System Reboot\n");
        printf("Enter choice (1-4): \n");

        int choice = 0;
        // ממתין לקלט מהמקלדת בטרמינל
        while (choice == 0 || choice == '\n' || choice == '\r') {
            choice = fgetc(stdin);
            vTaskDelay(pdMS_TO_TICKS(10));
        }

        switch(choice) {
            case '1': test_adc_sensors(); break;
            case '2': test_coils_safe_pwm(); break;
            case '3': test_rotation_emi(); break;
            case '4': 
                ESP_LOGI(TAG, "Rebooting...");
                vTaskDelay(pdMS_TO_TICKS(500));
                esp_restart(); 
                break;
            default:
                ESP_LOGE(TAG, "Invalid choice.");
                break;
        }
    }
}