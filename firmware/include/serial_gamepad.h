#ifndef SERIAL_GAMEPAD_H
#define SERIAL_GAMEPAD_H

#include <stdbool.h>

// Initialize the serial gamepad interface (USB CDC).
void serial_gamepad_init(void);

// Poll for serial input, returns true if a command was handled.
bool serial_gamepad_poll(void);

#endif  // SERIAL_GAMEPAD_H
