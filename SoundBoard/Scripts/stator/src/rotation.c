#include "rotation.h"

#include <math.h>
#include <stdint.h>
#include <stdbool.h>

#include "esp_err.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/mcpwm_prelude.h"
#include "driver/gpio.h"

#include "stator/include/config.h"
#include "stator/include/rotation.h"

static const char *TAG = "ROTATION";

// PWM Config for DRV8313 (20kHz for silent operation)
#define ROT_PWM_FREQ_HZ 20000
#define ROT_PWM_PERIOD_TICKS 400 // 8MHz / 20kHz = 400
#define SINE_TABLE_SIZE 360

// Fallback pins if config.h is not updated yet
#ifndef ROT_IN1_PIN
#define ROT_IN1_PIN 9
#define ROT_IN2_PIN 10
#define ROT_IN3_PIN 11
#define ROT_EN_PIN  12 // Common Enable pin for DRV8313
#endif

static uint32_t s_sine_table[SINE_TABLE_SIZE];
static mcpwm_cmpr_handle_t s_cmpr[3] = {NULL};
static TaskHandle_t s_rotation_task_handle = NULL;
static int s_current_phase_angle = 0;
static int s_rotation_speed_delay_ms = 10; // Controls RPM (lower = faster)

/**
 * Pre-computes the SPWM values into a Look-Up Table to save CPU cycles
 */
static void generate_sine_table(void)
{
    for (int i = 0; i < SINE_TABLE_SIZE; i++) {
        // Calculate Sine wave from 0 to 2*PI, normalize to 0.0-1.0, scale to PWM period
        float angle_rad = (float)i * (M_PI / 180.0f);
        float sin_val = (sinf(angle_rad) + 1.0f) / 2.0f; 
        s_sine_table[i] = (uint32_t)(sin_val * (float)ROT_PWM_PERIOD_TICKS);
    }
    ESP_LOGI(TAG, "SPWM Sine Table generated.");
}

/**
 * FreeRTOS Task running the SPWM sequence
 */
static void rotation_task(void *arg)
{
    ESP_LOGI(TAG, "Rotation task started.");
    while (1) {
        // 120 degrees phase shift between the 3 coils
        int angle_a = s_current_phase_angle;
        int angle_b = (s_current_phase_angle + 120) % SINE_TABLE_SIZE;
        int angle_c = (s_current_phase_angle + 240) % SINE_TABLE_SIZE;

        mcpwm_comparator_set_compare_value(s_cmpr[0], s_sine_table[angle_a]);
        mcpwm_comparator_set_compare_value(s_cmpr[1], s_sine_table[angle_b]);
        mcpwm_comparator_set_compare_value(s_cmpr[2], s_sine_table[angle_c]);

        // Advance the angle
        s_current_phase_angle = (s_current_phase_angle + 1) % SINE_TABLE_SIZE;

        // Task delay controls the rotation speed
        vTaskDelay(pdMS_TO_TICKS(s_rotation_speed_delay_ms));
    }
}

esp_err_t rotation_init(void)
{
    ESP_LOGI(TAG, "Initializing DRV8313 SPWM rotation...");

    generate_sine_table();

    // 1. Enable Pin Setup (Keep DRV8313 active)
    gpio_config_t io_conf = {
        .pin_bit_mask = (1ULL << ROT_EN_PIN),
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE
    };
    gpio_config(&io_conf);
    gpio_set_level(ROT_EN_PIN, 1);

    // 2. MCPWM Setup for 3 phases
    mcpwm_timer_handle_t timer = NULL;
    mcpwm_timer_config_t timer_config = {
        .group_id = 1, // Use group 1 to avoid conflicts with Levitation (Group 0)
        .clk_src = MCPWM_TIMER_CLK_SRC_DEFAULT,
        .resolution_hz = 8000000,
        .period_ticks = ROT_PWM_PERIOD_TICKS,
        .count_mode = MCPWM_TIMER_COUNT_MODE_UP,
    };
    ESP_ERROR_CHECK(mcpwm_new_timer(&timer_config, &timer));

    int pins[3] = {ROT_IN1_PIN, ROT_IN2_PIN, ROT_IN3_PIN};

    for (int i = 0; i < 3; i++) {
        mcpwm_oper_handle_t oper = NULL;
        mcpwm_operator_config_t oper_config = { .group_id = 1 };
        ESP_ERROR_CHECK(mcpwm_new_operator(&oper_config, &oper));
        ESP_ERROR_CHECK(mcpwm_operator_connect_timer(oper, timer));

        mcpwm_comparator_config_t cmpr_config = { .flags.update_cmp_on_tez = true };
        ESP_ERROR_CHECK(mcpwm_new_comparator(oper, &cmpr_config, &s_cmpr[i]));

        mcpwm_gen_handle_t gen = NULL;
        mcpwm_generator_config_t gen_config = { .gen_gpio_num = pins[i] };
        ESP_ERROR_CHECK(mcpwm_new_generator(oper, &gen_config, &gen));

        ESP_ERROR_CHECK(mcpwm_generator_set_action_on_timer_event(gen,
            MCPWM_GEN_TIMER_EVENT_ACTION(MCPWM_TIMER_DIRECTION_UP, MCPWM_TIMER_EVENT_EMPTY, MCPWM_GEN_ACTION_HIGH)));
        ESP_ERROR_CHECK(mcpwm_generator_set_action_on_compare_event(gen,
            MCPWM_GEN_COMPARE_EVENT_ACTION(MCPWM_TIMER_DIRECTION_UP, s_cmpr[i], MCPWM_GEN_ACTION_LOW)));
        
        mcpwm_comparator_set_compare_value(s_cmpr[i], 0);
    }

    ESP_ERROR_CHECK(mcpwm_timer_enable(timer));
    ESP_ERROR_CHECK(mcpwm_timer_start_stop(timer, MCPWM_TIMER_START_NO_STOP));

    return ESP_OK;
}

esp_err_t rotation_start(void)
{
    if (s_rotation_task_handle != NULL) {
        return ESP_OK; // Already running
    }
    
    // Create the rotation task pinned to Core 0 (alongside the levitation ISR)
    xTaskCreatePinnedToCore(rotation_task, "rotation_task", 4096, NULL, 5, &s_rotation_task_handle, 0);
    return ESP_OK;
}

void rotation_set_speed(int delay_ms)
{
    if (delay_ms > 0) {
        s_rotation_speed_delay_ms = delay_ms;
    }
}