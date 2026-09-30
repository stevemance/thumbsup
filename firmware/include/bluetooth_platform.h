#ifndef BLUETOOTH_PLATFORM_H
#define BLUETOOTH_PLATFORM_H

#include <stdbool.h>
#include <controller/uni_gamepad.h>

// Platform status functions
bool bluetooth_platform_failsafe_active(void);
bool bluetooth_platform_is_armed(void);

// Inject a virtual gamepad sample (used for serial HITL).
void bluetooth_platform_inject_gamepad(const uni_gamepad_t* gp);

// Bluetooth inquiry policy: when enabled, the robot scans+autoconnects at boot
// and resumes scanning after a controller disconnect.  Competition builds
// default on; HITL builds default off (see HITL_NO_SCAN) and enable it via the
// console for disconnect/re-pair tests.
void bluetooth_platform_set_autoscan(bool enabled);
bool bluetooth_platform_get_autoscan(void);

// Prints controller report inter-arrival statistics ("HITL RXSTATS ...").
void bluetooth_platform_print_rx_stats(bool reset);

// Feedback to the connected controller.  Return false if no controller is
// ready or it does not support the feature.
bool bluetooth_platform_controller_rumble(uint16_t duration_ms, uint8_t weak, uint8_t strong);
bool bluetooth_platform_controller_player_leds(uint8_t mask);

// Platform initialization
struct uni_platform* get_my_platform(void);

#endif // BLUETOOTH_PLATFORM_H
