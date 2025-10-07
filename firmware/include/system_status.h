#ifndef SYSTEM_STATUS_H
#define SYSTEM_STATUS_H

#include <stdbool.h>

// System-wide status functions
// These must be implemented by the platform (bluetooth_platform.c or diagnostic_mode.c)

// Check if failsafe is currently active
bool system_failsafe_active(void);

// Check if weapon is armed
bool system_is_armed(void);

// Set armed state
void system_set_armed(bool armed);

// Set failsafe state
void system_set_failsafe(bool active);

#endif // SYSTEM_STATUS_H