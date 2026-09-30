#ifndef BATTERY_MONITOR_H
#define BATTERY_MONITOR_H

// Low-battery alerts from the weapon ESC's voltage telemetry.
//
// Alert only: this never limits or stops anything.  The ESC voltage sags hard
// during weapon spin-up, so it is smoothed and the levels have hysteresis.
// The ESC only reports voltage while the weapon is armed (DShot running); the
// last level is kept while disarmed.

#include <stdbool.h>
#include <stdint.h>

typedef enum {
    BATTERY_LEVEL_UNKNOWN = 0,  // no voltage reading yet
    BATTERY_LEVEL_OK,
    BATTERY_LEVEL_LOW,
    BATTERY_LEVEL_CRITICAL,
} battery_level_t;

void battery_monitor_init(void);
// Call periodically (tens of ms) from the Bluetooth/control context.
void battery_monitor_update(uint32_t now_ms);
battery_level_t battery_monitor_level(void);
// Smoothed voltage in mV, 0 until the first reading.
uint32_t battery_monitor_mv(void);
const char* battery_monitor_level_name(battery_level_t level);
// A controller became ready: resend the player-LED gauge to it.
void battery_monitor_controller_ready(void);

#endif  // BATTERY_MONITOR_H
