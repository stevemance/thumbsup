#include "safety.h"
#include "config.h"
#include "hardware/gpio.h"
#include <stdio.h>

static bool safety_initialized = false;

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
}