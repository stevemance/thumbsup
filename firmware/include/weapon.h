#ifndef WEAPON_H
#define WEAPON_H

#include <stdint.h>
#include <stdbool.h>

typedef enum {
    WEAPON_STATE_DISARMED,
    WEAPON_STATE_ARMING,
    WEAPON_STATE_ARMED,
    WEAPON_STATE_SPINNING,
    WEAPON_STATE_EMERGENCY_STOP
} weapon_state_t;

// Control mode for weapon (PWM, DShot, or AM32 Config)
typedef enum {
    WEAPON_MODE_PWM,      // Standard PWM control
    WEAPON_MODE_DSHOT,    // DShot digital protocol
    WEAPON_MODE_CONFIG    // AM32 configuration mode (UART)
} weapon_control_mode_t;

typedef struct {
    uint32_t erpm;           // Electrical RPM from ESC telemetry
    uint32_t rpm;            // Mechanical RPM (ERPM / pole pairs)
    uint16_t voltage_cV;     // Voltage in centi-volts
    uint16_t current_cA;     // Current in centi-amps
    uint8_t temperature_C;   // Temperature in Celsius
    uint8_t crc;             // CRC from ESC telemetry
    bool valid;              // True if telemetry is valid
    uint32_t timestamp_ms;   // When telemetry was received
} weapon_telemetry_t;

// Core weapon control functions
bool weapon_init(void);
void weapon_update(void);
bool weapon_arm(void);
bool weapon_disarm(void);
bool weapon_set_speed(uint8_t speed_percent);
weapon_state_t weapon_get_state(void);
uint8_t weapon_get_speed(void);
uint8_t weapon_get_target_speed(void);
bool weapon_is_armed(void);
void weapon_emergency_stop(void);
bool weapon_get_telemetry(weapon_telemetry_t* telemetry);
uint32_t weapon_get_dshot_failures(void);
uint16_t weapon_get_dshot_last_throttle(void);
void weapon_get_dshot_send_counts(uint32_t* attempts, uint32_t* successes);
void weapon_get_dshot_telemetry_counts(uint32_t* requests, uint32_t* responses);
void weapon_reset_dshot_telemetry_counts(void);
uint32_t weapon_get_telemetry_age_ms(void);
void weapon_get_dshot_telemetry_debug(uint32_t* raw, uint32_t* decode_fail);
void weapon_get_dshot_telemetry_timing(uint32_t* frames, uint64_t* total_us);
void weapon_set_dshot_raw_dump(uint16_t count);
void weapon_get_dshot_setup_state(bool* pending, bool* done);

// Mode switching functions (Critical Fix #2 & #6)
bool weapon_enable_dshot(void);
bool weapon_enable_pwm(void);
bool weapon_enter_config_mode(void);
weapon_control_mode_t weapon_get_control_mode(void);

#endif // WEAPON_H
