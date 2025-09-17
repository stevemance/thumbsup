#include "safety.h"
#include "config.h"
#include "weapon.h"
#include "motor_control.h"
#include "hardware/gpio.h"
#include "pico/stdlib.h"
#include <stdio.h>

static bool safety_initialized = false;
static uint32_t last_safety_check = 0;
static uint32_t safety_violation_count = 0;

bool safety_init(void) {
    if (safety_initialized) {
        return true;
    }

    safety_initialized = true;
    DEBUG_PRINT("Safety system initialized\n");

    return true;
}

bool safety_check_arm_conditions(uint32_t battery_voltage_mv) {
    if (!safety_check_battery(battery_voltage_mv)) {
        DEBUG_PRINT("Cannot arm: Battery voltage too low (%.1fV)\n",
                    battery_voltage_mv / 1000.0f);
        return false;
    }

    if (safety_is_button_pressed()) {
        DEBUG_PRINT("Cannot arm: Safety button is pressed\n");
        return false;
    }

    return true;
}

bool safety_check_battery(uint32_t battery_voltage_mv) {
    return battery_voltage_mv >= BATTERY_LOW_VOLTAGE;
}

bool safety_is_button_pressed(void) {
    return !gpio_get(PIN_SAFETY_BUTTON);
}

void safety_update(void) {
    if (!safety_initialized) {
        return;
    }

    uint32_t current_time = to_ms_since_boot(get_absolute_time());

    // SAFETY: Perform continuous safety monitoring
    if (current_time - last_safety_check >= SAFETY_CHECK_INTERVAL) {
        // Read current battery voltage (declared in config.h)
        uint32_t battery_mv = read_battery_voltage();

        // Check for safety violations
        bool violation = false;

        if (!safety_check_battery(battery_mv)) {
            DEBUG_PRINT("SAFETY VIOLATION: Low battery %umV\n", battery_mv);
            violation = true;
        }

        if (safety_is_button_pressed()) {
            DEBUG_PRINT("SAFETY VIOLATION: Safety button pressed\n");
            violation = true;
        }

        // Count consecutive violations for emergency action
        if (violation) {
            safety_violation_count++;
            if (safety_violation_count > MAX_SAFETY_VIOLATIONS) {
                DEBUG_PRINT("CRITICAL: Multiple safety violations - initiating emergency stop\n");
                weapon_emergency_stop();
                motor_control_emergency_stop();
            }
        } else {
            safety_violation_count = 0;
        }

        last_safety_check = current_time;
    }
}