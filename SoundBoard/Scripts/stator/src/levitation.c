#include <math.h>
#include <stdint.h>
#include <stdbool.h>

#include "esp_attr.h"
#include "esp_err.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_adc/adc_oneshot.h"
#include "driver/gptimer.h"
#include "driver/mcpwm_prelude.h"

#include "stator/include/config.h"
#include "stator/include/levitation.h"

static const char *TAG = "LEVITATION";

// הגדרות תדר ה-PWM עבור ה-DRV8871 (20kHz זה תדר קלאסי שקט לאוזן אנושית)
#define LEV_PWM_FREQ_HZ 20000 
#define LEV_PWM_PERIOD_TICKS 400 // רזולוציה: 8MHz / 20kHz = 400 Ticks למחזור

// מנגנון גיבוי לפינים במקרה ו-config.h עדיין לא מעודכן
#ifndef COIL1_IN1_PIN
#define COIL1_IN1_PIN 4
#define COIL1_IN2_PIN 5
#define COIL2_IN1_PIN 6
#define COIL2_IN2_PIN 7
#define COIL3_IN1_PIN 15
#define COIL3_IN2_PIN 16
#endif

levitation_state_t lev_state = {
    .hall_offsets = {0, 0, 0},
    .is_calibrated = false,
    .current_adc = {0, 0, 0},
    .pid = {{0}},
    .max_pwm_output = 100.0f,
};

static adc_oneshot_unit_handle_t s_adc_handle = NULL;
static gptimer_handle_t s_lev_timer = NULL;

// משתנים גלובליים לניהול הקומפרטורים של ה-PWM (כדי לעדכן אותם מתוך ה-ISR)
static mcpwm_cmpr_handle_t s_cmpr_in1[3] = {NULL};
static mcpwm_cmpr_handle_t s_cmpr_in2[3] = {NULL};

static inline float clampf_float(float value, float min_value, float max_value)
{
    if (value < min_value) {
        return min_value;
    }
    if (value > max_value) {
        return max_value;
    }
    return value;
}

/**
 * אתחול יחידת ה-MCPWM עבור 3 דרייברי ה-DRV8871
 */
static esp_err_t levitation_pwm_init(void)
{
    ESP_LOGI(TAG, "Initializing MCPWM for 3 axes...");

    // 1. יצירת טיימר משותף לכל הצירים
    mcpwm_timer_handle_t timer = NULL;
    mcpwm_timer_config_t timer_config = {
        .group_id = 0,
        .clk_src = MCPWM_TIMER_CLK_SRC_DEFAULT,
        .resolution_hz = 8000000, // 8MHz base clock
        .period_ticks = LEV_PWM_PERIOD_TICKS,
        .count_mode = MCPWM_TIMER_COUNT_MODE_UP,
    };
    ESP_ERROR_CHECK(mcpwm_new_timer(&timer_config, &timer));

    int in1_pins[3] = {COIL1_IN1_PIN, COIL2_IN1_PIN, COIL3_IN1_PIN};
    int in2_pins[3] = {COIL1_IN2_PIN, COIL2_IN2_PIN, COIL3_IN2_PIN};

    // 2. קישור אופרטורים וקומפרטורים לכל ציר
    for (int i = 0; i < 3; i++) {
        mcpwm_oper_handle_t oper = NULL;
        mcpwm_operator_config_t oper_config = {
            .group_id = 0, // משתמשים באותו טיימר
        };
        ESP_ERROR_CHECK(mcpwm_new_operator(&oper_config, &oper));
        ESP_ERROR_CHECK(mcpwm_operator_connect_timer(oper, timer));

        mcpwm_comparator_config_t cmpr_config = {
            .flags.update_cmp_on_tez = true,
        };
        ESP_ERROR_CHECK(mcpwm_new_comparator(oper, &cmpr_config, &s_cmpr_in1[i]));
        ESP_ERROR_CHECK(mcpwm_new_comparator(oper, &cmpr_config, &s_cmpr_in2[i]));

        // 3. הגדרת מחוללי האות (Generators) לפינים הפיזיים
        mcpwm_gen_handle_t gen1 = NULL;
        mcpwm_gen_handle_t gen2 = NULL;
        mcpwm_generator_config_t gen_config1 = { .gen_gpio_num = in1_pins[i] };
        mcpwm_generator_config_t gen_config2 = { .gen_gpio_num = in2_pins[i] };
        ESP_ERROR_CHECK(mcpwm_new_generator(oper, &gen_config1, &gen1));
        ESP_ERROR_CHECK(mcpwm_new_generator(oper, &gen_config2, &gen2));

        // 4. התנהגות הסיגנל - מתחיל HIGH, יורד ל-LOW כשהטיימר מגיע לקומפרטור
        ESP_ERROR_CHECK(mcpwm_generator_set_action_on_timer_event(gen1,
            MCPWM_GEN_TIMER_EVENT_ACTION(MCPWM_TIMER_DIRECTION_UP, MCPWM_TIMER_EVENT_EMPTY, MCPWM_GEN_ACTION_HIGH)));
        ESP_ERROR_CHECK(mcpwm_generator_set_action_on_compare_event(gen1,
            MCPWM_GEN_COMPARE_EVENT_ACTION(MCPWM_TIMER_DIRECTION_UP, s_cmpr_in1[i], MCPWM_GEN_ACTION_LOW)));

        ESP_ERROR_CHECK(mcpwm_generator_set_action_on_timer_event(gen2,
            MCPWM_GEN_TIMER_EVENT_ACTION(MCPWM_TIMER_DIRECTION_UP, MCPWM_TIMER_EVENT_EMPTY, MCPWM_GEN_ACTION_HIGH)));
        ESP_ERROR_CHECK(mcpwm_generator_set_action_on_compare_event(gen2,
            MCPWM_GEN_COMPARE_EVENT_ACTION(MCPWM_TIMER_DIRECTION_UP, s_cmpr_in2[i], MCPWM_GEN_ACTION_LOW)));

        // איפוס ראשוני - כל הפינים ב-0
        ESP_ERROR_CHECK(mcpwm_comparator_set_compare_value(s_cmpr_in1[i], 0));
        ESP_ERROR_CHECK(mcpwm_comparator_set_compare_value(s_cmpr_in2[i], 0));
    }

    ESP_ERROR_CHECK(mcpwm_timer_enable(timer));
    ESP_ERROR_CHECK(mcpwm_timer_start_stop(timer, MCPWM_TIMER_START_NO_STOP));

    return ESP_OK;
}

esp_err_t levitation_hardware_init(void)
{
    if (s_adc_handle != NULL) {
        return ESP_OK;
    }

    // אתחול ה-ADC
    adc_oneshot_unit_init_cfg_t adc_init = {
        .unit_id = ADC_UNIT_1,
        .clk_src = ADC_DIGI_CLK_SRC_DEFAULT,
        .ulp_mode = ADC_ULP_MODE_DISABLE,
    };

    esp_err_t err = adc_oneshot_new_unit(&adc_init, &s_adc_handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "ADC init failed: %s", esp_err_to_name(err));
        return err;
    }

    const adc_channel_t channels[3] = {
        HALL1_ADC_CHANNEL,
        HALL2_ADC_CHANNEL,
        HALL3_ADC_CHANNEL,
    };

    adc_oneshot_chan_cfg_t chan_cfg = {
        .atten = ADC_ATTEN_DB_12,
        .bitwidth = ADC_BITWIDTH_12,
    };

    for (int i = 0; i < 3; ++i) {
        err = adc_oneshot_config_channel(s_adc_handle, channels[i], &chan_cfg);
        if (err != ESP_OK) {
            ESP_LOGE(TAG, "ADC channel %d config failed: %s", channels[i], esp_err_to_name(err));
            return err;
        }
    }

    // אתחול מערכת ה-PWM
    err = levitation_pwm_init();
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "PWM Init failed!");
        return err;
    }

    lev_state.is_calibrated = false;
    lev_state.max_pwm_output = 100.0f;

    return ESP_OK;
}

bool levitation_calibrate_halls(void)
{
    if (s_adc_handle == NULL) {
        ESP_LOGE(TAG, "ADC handle not initialized");
        return false;
    }

    vTaskDelay(pdMS_TO_TICKS(500));

    int64_t accumulator[3] = {0, 0, 0};
    int raw_value = 0;
    const adc_channel_t channels[3] = {
        HALL1_ADC_CHANNEL,
        HALL2_ADC_CHANNEL,
        HALL3_ADC_CHANNEL,
    };

    for (int sample = 0; sample < 256; ++sample) {
        for (int i = 0; i < 3; ++i) {
            esp_err_t err = adc_oneshot_read(s_adc_handle, channels[i], &raw_value);
            if (err != ESP_OK) {
                ESP_LOGE(TAG, "ADC read failed for HALL%d: %s", i + 1, esp_err_to_name(err));
                return false;
            }
            accumulator[i] += raw_value;
        }
        vTaskDelay(pdMS_TO_TICKS(1));
    }

    for (int i = 0; i < 3; ++i) {
        int average = (int)(accumulator[i] / 256);
        if (average < 1500 || average > 2700) {
            ESP_LOGE(TAG, "Hall %d baseline %d out of bounds", i + 1, average);
            lev_state.is_calibrated = false;
            return false;
        }

        lev_state.hall_offsets[i] = average;
        lev_state.current_adc[i] = average;
        lev_state.pid[i].integral = 0.0f;
        lev_state.pid[i].prev_error = 0.0f;
        lev_state.pid[i].derivative = 0.0f;
        lev_state.pid[i].last_output = 0.0f;
    }

    lev_state.is_calibrated = true;
    return true;
}

static inline float clamp_output(float value)
{
    return clampf_float(value, -lev_state.max_pwm_output, lev_state.max_pwm_output);
}

float IRAM_ATTR levitation_update_axis_pid(pid_controller_t *pid, float target, float current, float dt)
{
    if (pid == NULL || dt <= 0.0f) {
        return 0.0f;
    }

    float error = target - current;
    pid->integral += error * dt;
    pid->derivative = (error - pid->prev_error) / dt;
    float output = (pid->kp * error) + (pid->ki * pid->integral) + (pid->kd * pid->derivative);
    output = clamp_output(output);
    pid->prev_error = error;
    pid->last_output = output;
    return output;
}

bool IRAM_ATTR levitation_timer_cb(gptimer_handle_t timer, const gptimer_alarm_event_data_t *edata, void *user_ctx)
{
    (void)timer;
    (void)edata;
    (void)user_ctx;

    if (s_adc_handle == NULL || !lev_state.is_calibrated) {
        return false;
    }

    const adc_channel_t channels[3] = {
        HALL1_ADC_CHANNEL,
        HALL2_ADC_CHANNEL,
        HALL3_ADC_CHANNEL,
    };

    for (int i = 0; i < 3; ++i) {
        int raw_value = 0;
        if (adc_oneshot_read(s_adc_handle, channels[i], &raw_value) == ESP_OK) {
            lev_state.current_adc[i] = raw_value;
        }

        // חישוב פלט מנוע ה-PID (-100 עד 100)
        float output = levitation_update_axis_pid(&lev_state.pid[i], (float)lev_state.hall_offsets[i], (float)lev_state.current_adc[i], 0.0001f);

        // תרגום ה-PID (אחוזים) למספר 'קליקים' בטיימר ה-MCPWM
        uint32_t duty_ticks = (uint32_t)(fabs(output) / lev_state.max_pwm_output * LEV_PWM_PERIOD_TICKS);
        
        // הגנה מפני חריגה כפולה בטיימר
        if (duty_ticks > LEV_PWM_PERIOD_TICKS) {
            duty_ticks = LEV_PWM_PERIOD_TICKS;
        }

        // הזרקת הסיגנלים לפיני ה-IN1 / IN2 בהתאם לכיוון התנועה
        if (output > 0.0f) {
            mcpwm_comparator_set_compare_value(s_cmpr_in1[i], duty_ticks);
            mcpwm_comparator_set_compare_value(s_cmpr_in2[i], 0);
        } else if (output < 0.0f) {
            mcpwm_comparator_set_compare_value(s_cmpr_in1[i], 0);
            mcpwm_comparator_set_compare_value(s_cmpr_in2[i], duty_ticks);
        } else {
            // ניתוק כוח מלא כשהפלט הוא בדיוק 0
            mcpwm_comparator_set_compare_value(s_cmpr_in1[i], 0);
            mcpwm_comparator_set_compare_value(s_cmpr_in2[i], 0);
        }
    }

    return false;
}

esp_err_t levitation_start_loop(void)
{
    if (s_lev_timer != NULL) {
        return ESP_OK;
    }

    gptimer_config_t timer_cfg = {
        .clk_src = GPTIMER_CLK_SRC_DEFAULT,
        .direction = GPTIMER_COUNT_UP,
        .resolution_hz = 1000000,
        .intr_priority = 1,
        .flags = {
            .intr_shared = 0,
            .allow_pd = 0,
        },
    };

    esp_err_t err = gptimer_new_timer(&timer_cfg, &s_lev_timer);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "GPTimer new timer failed: %s", esp_err_to_name(err));
        return err;
    }

    gptimer_event_callbacks_t cbs = {
        .on_alarm = levitation_timer_cb,
    };

    err = gptimer_register_event_callbacks(s_lev_timer, &cbs, NULL);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "GPTimer register callbacks failed: %s", esp_err_to_name(err));
        return err;
    }

    static gptimer_alarm_config_t alarm_cfg = {
        .alarm_count = 100,
        .reload_count = 100,
        .flags = {
            .auto_reload_on_alarm = true,
        },
    };

    err = gptimer_set_alarm_action(s_lev_timer, &alarm_cfg);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "GPTimer set alarm failed: %s", esp_err_to_name(err));
        return err;
    }

    err = gptimer_enable(s_lev_timer);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "GPTimer enable failed: %s", esp_err_to_name(err));
        return err;
    }

    err = gptimer_start(s_lev_timer);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "GPTimer start failed: %s", esp_err_to_name(err));
        return err;
    }

    return ESP_OK;
}