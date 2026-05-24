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

#include "config.h"
#include "levitation.h"

static const char *TAG = "levitation";

levitation_state_t lev_state = {
    .hall_offsets = {0, 0, 0},
    .is_calibrated = false,
    .current_adc = {0, 0, 0},
    .pid = {{0}},
    .max_pwm_output = 100.0f,
};

static adc_oneshot_unit_handle_t s_adc_handle = NULL;
static gptimer_handle_t s_lev_timer = NULL;

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

esp_err_t levitation_hardware_init(void)
{
    if (s_adc_handle != NULL) {
        return ESP_OK;
    }

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

        float output = levitation_update_axis_pid(&lev_state.pid[i], (float)lev_state.hall_offsets[i], (float)lev_state.current_adc[i], 0.0001f);

        /*
         * Drive the DRV8871 IN1/IN2 PWM outputs here.
         * Positive output should map to IN1 PWM and zero IN2.
         * Negative output should map to IN2 PWM and zero IN1.
         */
        (void)output;
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
