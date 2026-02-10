#ifndef HITL_CONSOLE_H
#define HITL_CONSOLE_H

#include <stdbool.h>
#include <stdint.h>

#include <controller/uni_gamepad.h>

#ifndef HITL_CONSOLE
#define HITL_CONSOLE 0
#endif

void hitl_console_init(void);
void hitl_console_set_controller_connected(bool connected);
void hitl_console_set_controller_ready(bool ready);

// Called on each controller report (keeps implementation simple without timers).
void hitl_console_on_gamepad(const uni_gamepad_t* gp);

// Latency tracking callbacks. No-ops when HITL_CONSOLE is 0.
// Called from the weapon/BT pipeline to timestamp internal events.
void hitl_latency_on_ry_change(int32_t ry);
void hitl_latency_on_target_set(uint8_t target);
void hitl_latency_on_dshot_sent(uint16_t throttle);
void hitl_latency_on_rpm_update(uint32_t rpm);

#endif  // HITL_CONSOLE_H

