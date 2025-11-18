#include "weapon.h"
#include "motor_control.h"
#include "safety.h"
#include "status.h"
#include "config.h"
#include "dshot.h"
#include "am32_config.h"
#include "pico/stdlib.h"
#include "pico/mutex.h"
#include <stdio.h>
#include <stdlib.h>

// MINOR FIX: Move extern declarations to file scope for cleaner code organization
extern uint32_t read_battery_voltage(void);

// CRITICAL FIX #2 & #6: Add mutex for safe mode switching (enum is in weapon.h)
static weapon_state_t weapon_state = WEAPON_STATE_DISARMED;
static weapon_control_mode_t control_mode = WEAPON_MODE_PWM;  // Default to PWM
static mutex_t mode_mutex;  // Mutex for thread-safe mode switching
static uint8_t current_speed = 0;
static uint8_t target_speed = 0;
static uint32_t arm_start_time = 0;
static uint32_t last_ramp_time = 0;
static bool initialized = false;
static bool dshot_initialized = false;

static uint16_t weapon_speed_to_pulse(uint8_t speed_percent) {
    if (speed_percent == 0) {
        return PWM_MIN_PULSE;
    }

    uint16_t range = PWM_MAX_PULSE - PWM_MIN_PULSE;
    return PWM_MIN_PULSE + (speed_percent * range) / 100;
}

// CRITICAL FIX #2 & #6: Mode switching functions with mutex protection
static bool weapon_set_control_mode(weapon_control_mode_t new_mode) {
    // Must be disarmed to change modes
    if (weapon_state != WEAPON_STATE_DISARMED) {
        DEBUG_PRINT("Cannot change control mode while armed (state=%d)\n", weapon_state);
        return false;
    }

    mutex_enter_blocking(&mode_mutex);

    if (control_mode == new_mode) {
        mutex_exit(&mode_mutex);
        return true;  // Already in requested mode
    }

    // Disable current mode
    switch (control_mode) {
        case WEAPON_MODE_PWM:
            motor_control_set_pulse(MOTOR_WEAPON, PWM_MIN_PULSE);
            break;

        case WEAPON_MODE_DSHOT:
            if (dshot_initialized) {
                dshot_send_throttle(MOTOR_WEAPON, 0, false);  // Send stop command
                sleep_ms(10);  // Allow command to complete
                dshot_deinit(MOTOR_WEAPON);
                dshot_initialized = false;
            }
            break;

        case WEAPON_MODE_CONFIG:
            am32_exit_config_mode();
            break;
    }

    // Enable new mode
    switch (new_mode) {
        case WEAPON_MODE_PWM:
            motor_control_set_pulse(MOTOR_WEAPON, PWM_MIN_PULSE);
            DEBUG_PRINT("Weapon control mode: PWM\n");
            break;

        case WEAPON_MODE_DSHOT:
            {
                dshot_config_t dshot_config = {
                    .gpio_pin = PIN_WEAPON_PWM,
                    .speed = DSHOT_SPEED_300,  // 300kbit/s recommended for RP2040
                    .bidirectional = true,     // Enable EDT telemetry
                    .pole_pairs = 7            // 14 poles = 7 pole pairs
                };
                if (dshot_init(MOTOR_WEAPON, &dshot_config)) {
                    dshot_initialized = true;
                    DEBUG_PRINT("Weapon control mode: DShot300 with EDT\n");
                } else {
                    DEBUG_PRINT("ERROR: Failed to initialize DShot\n");
                    mutex_exit(&mode_mutex);
                    return false;
                }
            }
            break;

        case WEAPON_MODE_CONFIG:
            if (!am32_enter_config_mode()) {
                DEBUG_PRINT("ERROR: Failed to enter AM32 config mode\n");
                mutex_exit(&mode_mutex);
                return false;
            }
            DEBUG_PRINT("Weapon control mode: AM32 Config\n");
            break;
    }

    control_mode = new_mode;
    mutex_exit(&mode_mutex);
    return true;
}

// Public mode switching functions
bool weapon_enable_dshot(void) {
    return weapon_set_control_mode(WEAPON_MODE_DSHOT);
}

bool weapon_enable_pwm(void) {
    return weapon_set_control_mode(WEAPON_MODE_PWM);
}

bool weapon_enter_config_mode(void) {
    return weapon_set_control_mode(WEAPON_MODE_CONFIG);
}

weapon_control_mode_t weapon_get_control_mode(void) {
    return control_mode;
}

bool weapon_init(void) {
    if (initialized) {
        return true;
    }

    // CRITICAL FIX #6: Initialize mode switching mutex
    mutex_init(&mode_mutex);

    weapon_state = WEAPON_STATE_DISARMED;
    current_speed = 0;
    target_speed = 0;
    control_mode = WEAPON_MODE_PWM;  // Start in PWM mode
    dshot_initialized = false;

    motor_control_set_pulse(MOTOR_WEAPON, PWM_MIN_PULSE);

    initialized = true;
    DEBUG_PRINT("Weapon system initialized in PWM mode\n");

    return true;
}

void weapon_update(void) {
    if (!initialized) {
        return;
    }

    uint32_t current_time = to_ms_since_boot(get_absolute_time());

    // CONTINUOUS SAFETY CHECK: Always verify safety conditions before allowing operation
    if (weapon_state != WEAPON_STATE_DISARMED && weapon_state != WEAPON_STATE_EMERGENCY_STOP) {
        uint32_t battery_mv = read_battery_voltage();

        // Emergency disarm if safety conditions are violated
        if (!safety_check_arm_conditions(battery_mv)) {
            DEBUG_PRINT("SAFETY VIOLATION: Force disarming weapon\n");
            weapon_emergency_stop();
            return;
        }
    }

    switch (weapon_state) {
        case WEAPON_STATE_ARMING:
            if (current_time - arm_start_time > WEAPON_ARM_TIMEOUT) {
                weapon_state = WEAPON_STATE_ARMED;
                DEBUG_PRINT("Weapon armed\n");
                status_set_weapon(WEAPON_STATUS_ARMED, LED_EFFECT_SOLID);
            }
            break;

        case WEAPON_STATE_ARMED:
        case WEAPON_STATE_SPINNING:
            if (current_speed != target_speed) {
                if (current_time - last_ramp_time > (WEAPON_SPINUP_TIME / WEAPON_RAMP_STEPS)) {
                    // MAJOR FIX #5: Static ramp calculation is intentional for performance
                    // Using 'static const' allows compile-time calculation of ramp_step,
                    // avoiding repeated division on every update cycle. This is critical
                    // for real-time motor control where microseconds matter.
                    // If WEAPON_RAMP_STEPS needs to be runtime-configurable, change to:
                    //   uint8_t ramp_step = (100 + weapon_ramp_steps - 1) / weapon_ramp_steps;
                    static const uint8_t ramp_step = (100 + WEAPON_RAMP_STEPS - 1) / WEAPON_RAMP_STEPS;
                    if (target_speed > current_speed) {
                        current_speed = MIN(current_speed + ramp_step, target_speed);
                    } else {
                        current_speed = MAX((int16_t)current_speed - (int16_t)ramp_step, target_speed);
                    }

                    // CRITICAL FIX #2: Send commands based on control mode
                    mutex_enter_blocking(&mode_mutex);
                    switch (control_mode) {
                        case WEAPON_MODE_PWM: {
                            uint16_t pulse = weapon_speed_to_pulse(current_speed);
                            motor_control_set_pulse(MOTOR_WEAPON, pulse);
                            break;
                        }

                        case WEAPON_MODE_DSHOT:
                            if (dshot_initialized) {
                                // Convert speed percentage to DShot throttle (48-2047)
                                uint16_t dshot_throttle = dshot_throttle_from_percent(current_speed);
                                dshot_send_throttle(MOTOR_WEAPON, dshot_throttle, false);
                            }
                            break;

                        case WEAPON_MODE_CONFIG:
                            // Cannot control motor while in config mode
                            break;
                    }
                    mutex_exit(&mode_mutex);

                    last_ramp_time = current_time;

                    if (current_speed > 0 && weapon_state != WEAPON_STATE_SPINNING) {
                        weapon_state = WEAPON_STATE_SPINNING;
                        status_set_weapon(WEAPON_STATUS_SPINNING, LED_EFFECT_SOLID);
                    } else if (current_speed == 0 && weapon_state == WEAPON_STATE_SPINNING) {
                        weapon_state = WEAPON_STATE_ARMED;
                        status_set_weapon(WEAPON_STATUS_ARMED, LED_EFFECT_SOLID);
                    }
                }
            }
            break;

        case WEAPON_STATE_DISARMED:
        case WEAPON_STATE_EMERGENCY_STOP:
            current_speed = 0;
            target_speed = 0;

            // CRITICAL FIX #2: Stop motor in all modes
            mutex_enter_blocking(&mode_mutex);
            switch (control_mode) {
                case WEAPON_MODE_PWM:
                    motor_control_set_pulse(MOTOR_WEAPON, PWM_MIN_PULSE);
                    break;

                case WEAPON_MODE_DSHOT:
                    if (dshot_initialized) {
                        dshot_send_throttle(MOTOR_WEAPON, 0, false);
                    }
                    break;

                case WEAPON_MODE_CONFIG:
                    // Motor already stopped in config mode
                    break;
            }
            mutex_exit(&mode_mutex);
            break;
    }
}

bool weapon_arm(void) {
    if (weapon_state != WEAPON_STATE_DISARMED) {
        DEBUG_PRINT("Cannot arm: Weapon not disarmed (state=%d)\n", weapon_state);
        return false;
    }

    // CRITICAL SAFETY CHECK: Read actual battery voltage before arming
    // This is a safety-critical function that must not be bypassed
    uint32_t battery_mv = read_battery_voltage();

    // Verify all safety conditions before allowing weapon to arm
    if (!safety_check_arm_conditions(battery_mv)) {
        DEBUG_PRINT("Cannot arm: Safety conditions not met\n");
        return false;
    }

    weapon_state = WEAPON_STATE_ARMING;
    arm_start_time = to_ms_since_boot(get_absolute_time());
    DEBUG_PRINT("Weapon arming... (Battery: %.1fV)\n", battery_mv / 1000.0f);
    status_set_weapon(WEAPON_STATUS_ARMING, LED_EFFECT_BLINK_MEDIUM);

    return true;
}

bool weapon_disarm(void) {
    weapon_state = WEAPON_STATE_DISARMED;
    current_speed = 0;
    target_speed = 0;

    // CRITICAL FIX #2: Stop motor in all modes
    mutex_enter_blocking(&mode_mutex);
    switch (control_mode) {
        case WEAPON_MODE_PWM:
            motor_control_set_pulse(MOTOR_WEAPON, PWM_MIN_PULSE);
            break;

        case WEAPON_MODE_DSHOT:
            if (dshot_initialized) {
                dshot_send_throttle(MOTOR_WEAPON, 0, false);
            }
            break;

        case WEAPON_MODE_CONFIG:
            // Motor already stopped in config mode
            break;
    }
    mutex_exit(&mode_mutex);

    DEBUG_PRINT("Weapon disarmed\n");
    status_set_weapon(WEAPON_STATUS_DISARMED, LED_EFFECT_SOLID);

    return true;
}

bool weapon_set_speed(uint8_t speed_percent) {
    if (weapon_state != WEAPON_STATE_ARMED && weapon_state != WEAPON_STATE_SPINNING) {
        return false;
    }

    speed_percent = CLAMP(speed_percent, 0, MAX_WEAPON_SPEED);
    target_speed = speed_percent;

    // Apply exponential curve to weapon speed for better control feel
    if (WEAPON_EXPO > 0) {
        float normalized = (float)speed_percent / 100.0f;
        float expo_factor = (float)WEAPON_EXPO / 100.0f;
        float linear = normalized;
        float cubic = normalized * normalized * normalized;
        float output = linear * (1.0f - expo_factor) + cubic * expo_factor;
        target_speed = (uint8_t)(output * 100.0f);
    } else {
        target_speed = speed_percent;
    }

    return true;
}

weapon_state_t weapon_get_state(void) {
    return weapon_state;
}

uint8_t weapon_get_speed(void) {
    return current_speed;
}

bool weapon_is_armed(void) {
    return (weapon_state == WEAPON_STATE_ARMED ||
            weapon_state == WEAPON_STATE_SPINNING ||
            weapon_state == WEAPON_STATE_ARMING);
}

void weapon_emergency_stop(void) {
    weapon_state = WEAPON_STATE_EMERGENCY_STOP;
    current_speed = 0;
    target_speed = 0;

    // CRITICAL FIX #2: Emergency stop in all modes
    mutex_enter_blocking(&mode_mutex);
    switch (control_mode) {
        case WEAPON_MODE_PWM:
            motor_control_set_pulse(MOTOR_WEAPON, PWM_MIN_PULSE);
            break;

        case WEAPON_MODE_DSHOT:
            if (dshot_initialized) {
                dshot_send_throttle(MOTOR_WEAPON, 0, false);
            }
            break;

        case WEAPON_MODE_CONFIG:
            // Motor already stopped in config mode
            break;
    }
    mutex_exit(&mode_mutex);

    DEBUG_PRINT("WEAPON EMERGENCY STOP!\n");
    status_set_weapon(WEAPON_STATUS_EMERGENCY, LED_EFFECT_BLINK_FAST);
}