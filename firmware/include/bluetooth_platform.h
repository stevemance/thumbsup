#ifndef BLUETOOTH_PLATFORM_H
#define BLUETOOTH_PLATFORM_H

#include <stdbool.h>
#include <controller/uni_gamepad.h>

// Platform status functions
bool bluetooth_platform_failsafe_active(void);
bool bluetooth_platform_is_armed(void);

// Inject a virtual gamepad sample (used for serial HITL).
void bluetooth_platform_inject_gamepad(const uni_gamepad_t* gp);

// Platform initialization
struct uni_platform* get_my_platform(void);

#endif // BLUETOOTH_PLATFORM_H
