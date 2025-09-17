#include "weapon.h"
#include "motor_control.h"
#include "safety.h"
#include "config.h"
#include "pico/stdlib.h"
#include <stdio.h>
#include <stdlib.h>

static weapon_state_t weapon_state = WEAPON_STATE_DISARMED;
static uint8_t current_speed = 0;
static uint8_t target_speed = 0;
static uint32_t arm_start_time = 0;
static uint32_t last_ramp_time = 0;
static bool initialized = false;

static uint16_t weapon_speed_to_pulse(uint8_t speed_percent) {
    if (speed_percent == 0) {
        return PWM_MIN_PULSE;
    }

    uint16_t range = PWM_MAX_PULSE - PWM_MIN_PULSE;
    return PWM_MIN_PULSE + (speed_percent * range) / 100;
}

bool weapon_init(void) {
    if (initialized) {
        return true;
    }

    weapon_state = WEAPON_STATE_DISARMED;
    current_speed = 0;
    target_speed = 0;

    motor_control_set_pulse(MOTOR_WEAPON, PWM_MIN_PULSE);

    initialized = true;
    DEBUG_PRINT("Weapon system initialized\n");

    return true;
}

void weapon_update(void) {
    if (!initialized) {
        return;
    }

    uint32_t current_time = to_ms_since_boot(get_absolute_time());

    // CONTINUOUS SAFETY CHECK: Always verify safety conditions before allowing operation
    if (weapon_state != WEAPON_STATE_DISARMED && weapon_state != WEAPON_STATE_EMERGENCY_STOP) {
        extern uint32_t read_battery_voltage(void);
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
            }
            break;

        case WEAPON_STATE_ARMED:
        case WEAPON_STATE_SPINNING:
            if (current_speed != target_speed) {
                if (current_time - last_ramp_time > (WEAPON_SPINUP_TIME / WEAPON_RAMP_STEPS)) {
                    if (target_speed > current_speed) {
                        current_speed = MIN(current_speed + (100 / WEAPON_RAMP_STEPS), target_speed);
                    } else {
                        current_speed = MAX(current_speed - (100 / WEAPON_RAMP_STEPS), target_speed);
                    }

                    uint16_t pulse = weapon_speed_to_pulse(current_speed);
                    motor_control_set_pulse(MOTOR_WEAPON, pulse);
                    last_ramp_time = current_time;

                    if (current_speed > 0) {
                        weapon_state = WEAPON_STATE_SPINNING;
                    } else if (weapon_state == WEAPON_STATE_SPINNING) {
                        weapon_state = WEAPON_STATE_ARMED;
                    }
                }
            }
            break;

        case WEAPON_STATE_DISARMED:
        case WEAPON_STATE_EMERGENCY_STOP:
            current_speed = 0;
            target_speed = 0;
            motor_control_set_pulse(MOTOR_WEAPON, PWM_MIN_PULSE);
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
    extern uint32_t read_battery_voltage(void);
    uint32_t battery_mv = read_battery_voltage();

    // Verify all safety conditions before allowing weapon to arm
    if (!safety_check_arm_conditions(battery_mv)) {
        DEBUG_PRINT("Cannot arm: Safety conditions not met\n");
        return false;
    }

    weapon_state = WEAPON_STATE_ARMING;
    arm_start_time = to_ms_since_boot(get_absolute_time());
    DEBUG_PRINT("Weapon arming... (Battery: %.1fV)\n", battery_mv / 1000.0f);

    return true;
}

bool weapon_disarm(void) {
    weapon_state = WEAPON_STATE_DISARMED;
    current_speed = 0;
    target_speed = 0;
    motor_control_set_pulse(MOTOR_WEAPON, PWM_MIN_PULSE);
    DEBUG_PRINT("Weapon disarmed\n");

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
    motor_control_set_pulse(MOTOR_WEAPON, PWM_MIN_PULSE);
    DEBUG_PRINT("WEAPON EMERGENCY STOP!\n");
}