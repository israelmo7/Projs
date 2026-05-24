#ifndef LEVITATION_H
#define LEVITATION_H

/**
 * @file levitation.h
 * @brief High-speed Active Levitation Control Loop (10kHz) for ESP32-S3
 */

#include <stdint.h>
#include <stdbool.h>
#include "esp_err.h"
#include "esp_attr.h"
#include "driver/gptimer.h"

/* ============================================================
 * TYPE DEFINITIONS
 * ============================================================ */

/**
 * @brief Single-Axis PID Controller Configuration and State
 */
typedef struct {
    // מקדמי הבקרה (Tuning Parameters)
    float kp;
    float ki;
    float kd;

    // משתני זיכרון של הלולאה (History)
    float integral;
    float prev_error;
    float derivative;
    float last_output;
} pid_controller_t;

/**
 * @brief Global Levitation System State
 * Tracks all 3 independent stabilization axes aligned with config.h
 */
typedef struct {
    // נתוני הכיול (נקודות האפס של החיישנים)
    int hall_offsets[3];
    bool is_calibrated;

    // קריאות ה-ADC האחרונות בזמן אמת
    int current_adc[3];

    // שלושה בקרי PID נפרדים למניעת Wobble (הטיה של הדיסק)
    pid_controller_t pid[3];
    
    // אילוצי בטיחות (הגבלת זרם מקסימלי לסלילים ב-PWM)
    float max_pwm_output;
} levitation_state_t;

/* ============================================================
 * GLOBAL VARIABLE EXTERN
 * ============================================================ */
extern levitation_state_t lev_state;

/* ============================================================
 * FUNCTION DECLARATIONS
 * ============================================================ */

/**
 * @brief Initializes ADC units, MCPWM channels for drivers, and internal PID structures.
 */
esp_err_t levitation_hardware_init(void);

/**
 * @brief Runs the Power-on Auto-Calibration routine. Must be called with empty stator.
 * @return true if calibration succeeded and offsets are within safe baseline bounds.
 */
bool levitation_calibrate_halls(void);

/**
 * @brief Configures and starts the 10kHz hardware gptimer interrupt loop.
 */
esp_err_t levitation_start_loop(void);

/**
 * @brief Core PID math logic. Marked as IRAM_ATTR to execute directly from RAM.
 * Calculates the next PWM duty cycle based on configured target and current measurement.
 */
float levitation_update_axis_pid(pid_controller_t *pid, float target, float current, float dt);

/**
 * @brief ESP-IDF compliant timer callback. Executes at 10kHz on Core 0.
 */
bool levitation_timer_cb(gptimer_handle_t timer, const gptimer_alarm_event_data_t *edata, void *user_ctx);

#endif /* LEVITATION_H */