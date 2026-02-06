#ifndef HITL_OVERRIDES_H
#define HITL_OVERRIDES_H

#include <stdbool.h>
#include <stdint.h>

// HITL overrides are compiled into all builds but are only active when
// HITL_CONSOLE is enabled. This keeps production behavior unchanged.
#ifndef HITL_CONSOLE
#define HITL_CONSOLE 0
#endif

void hitl_overrides_init(void);

// Battery voltage override (mV). When set, read_battery_voltage() will return
// this value instead of the ADC-derived value.
void hitl_overrides_set_battery_mv(uint32_t mv);
void hitl_overrides_clear_battery_mv(void);
bool hitl_overrides_get_battery_mv(uint32_t* out_mv);

#endif  // HITL_OVERRIDES_H

