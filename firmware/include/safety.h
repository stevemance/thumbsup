#ifndef SAFETY_H
#define SAFETY_H

#include <stdint.h>
#include <stdbool.h>

bool safety_init(void);
bool safety_check_arm_conditions(uint32_t battery_voltage_mv);
bool safety_check_battery(uint32_t battery_voltage_mv);
bool safety_is_button_pressed(void);
void safety_update(void);

#endif // SAFETY_H