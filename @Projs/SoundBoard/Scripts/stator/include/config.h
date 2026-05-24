#ifndef CONFIG_H
#define CONFIG_H

/**
 * @file config.h
 * @brief ESP32-S3 (Stator) Pin Mapping and Hardware Configuration
 * 
 * Cleanly separated into Levitation (3x DRV8871), Rotation (1x DRV8313),
 * Analog Inputs (3x DRV5055), and Audio Output (MAX98357A).
 */

/* ============================================================
 * ANALOG INPUTS: LINEAR HALL SENSORS (3x DRV5055)
 * Dedicated analog pins on ADC1, completely isolated from PWM.
 * ============================================================ */
#define HALL1_PIN            1       ///< GPIO 1 (ADC1_CHANNEL_0)
#define HALL2_PIN            2       ///< GPIO 2 (ADC1_CHANNEL_1)
#define HALL3_PIN            3       ///< GPIO 3 (ADC1_CHANNEL_2)

#define HALL1_ADC_CHANNEL    ADC1_CHANNEL_0
#define HALL2_ADC_CHANNEL    ADC1_CHANNEL_1
#define HALL3_ADC_CHANNEL    ADC1_CHANNEL_2

/* ============================================================
 * LEVITATION: ACTIVE STABILIZATION COILS (3x DRV8871 H-Bridges)
 * Each driver requires 2 PWM inputs for bidirectional current control.
 * ============================================================ */
#define COIL_Z1_IN1_PIN      4       ///< Levitation Coil 1 Forward
#define COIL_Z1_IN2_PIN      5       ///< Levitation Coil 1 Reverse

#define COIL_Z2_IN1_PIN      6       ///< Levitation Coil 2 Forward
#define COIL_Z2_IN2_PIN      7       ///< Levitation Coil 2 Reverse

#define COIL_Z3_IN1_PIN      8       ///< Levitation Coil 3 Forward
#define COIL_Z3_IN2_PIN      9       ///< Levitation Coil 3 Reverse

/* ============================================================
 * ROTATION: 3-PHASE AXIAL FLUX MOTOR (1x DRV8313)
 * Driving the printed planar coils with sinusoidal commutation.
 * ============================================================ */
#define MOTOR_PHASE_A_PIN    10      ///< DRV8313 IN1
#define MOTOR_PHASE_B_PIN    11      ///< DRV8313 IN2
#define MOTOR_PHASE_C_PIN    12      ///< DRV8313 IN3
#define MOTOR_EN_PIN         13      ///< DRV8313 EN (Common Reset/Enable)

/* ============================================================
 * AUDIO SYSTEM: I2S OUTPUT (MAX98357A Class-D)
 * Dedicated digital audio interface pins.
 * ============================================================ */
#define I2S_SCK_PIN          14      ///< Bit Clock (BCLK)
#define I2S_WS_PIN           15      ///< Word Select (LRCLK)
#define I2S_DOUT_PIN         16      ///< Data Out (DIN)

/* ============================================================
 * SYSTEM STATUS LEDS & USER INTERFACE
 * ============================================================ */
#define LED_GREEN            17      ///< Normal / Calibrated Status
#define LED_RED              18      ///< System Error / Out of Bounds
#define LED_BLUE             21      ///< Charging / Inductive link active

#define BTN_PLAY             39      
#define BTN_VOLUME           38      
#define BTN_POWER            37      

/* ============================================================
 * FREERTOS TASK STACK CONFIGURATIONS (In Bytes)
 * ============================================================ */
#define TASK_LEVITATION_STACK    8192
#define TASK_MOTOR_STACK         8192
#define TASK_AUDIO_STACK         16384
#define TASK_COMMS_STACK         8192
#define TASK_SAFETY_STACK        4096

#endif /* CONFIG_H */