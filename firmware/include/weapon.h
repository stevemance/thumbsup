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

// Core weapon control functions
bool weapon_init(void);
void weapon_update(void);
bool weapon_arm(void);
bool weapon_disarm(void);
bool weapon_set_speed(uint8_t speed_percent);
weapon_state_t weapon_get_state(void);
uint8_t weapon_get_speed(void);
bool weapon_is_armed(void);
void weapon_emergency_stop(void);

// Mode switching functions (Critical Fix #2 & #6)
bool weapon_enable_dshot(void);
bool weapon_enable_pwm(void);
bool weapon_enter_config_mode(void);
weapon_control_mode_t weapon_get_control_mode(void);

#endif // WEAPON_H