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

#endif  // HITL_CONSOLE_H

