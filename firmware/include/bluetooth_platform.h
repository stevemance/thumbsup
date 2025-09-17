#ifndef BLUETOOTH_PLATFORM_H
#define BLUETOOTH_PLATFORM_H

#include <stdbool.h>

// Platform status functions
bool bluetooth_platform_failsafe_active(void);
bool bluetooth_platform_is_armed(void);

// Platform initialization
struct uni_platform* get_my_platform(void);

#endif // BLUETOOTH_PLATFORM_H