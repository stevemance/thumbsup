#ifndef CALIBRATION_MODE_H
#define CALIBRATION_MODE_H

#include <stdint.h>
#include <stdbool.h>

// Opaque gamepad pointer (to avoid including uni.h everywhere)
typedef void* calibration_gamepad_ptr;

// Initialize calibration mode system
bool calibration_mode_init(void);

// Check if calibration mode should be activated/deactivated
// Call this every frame with gamepad data
void calibration_mode_check_activation(calibration_gamepad_ptr gp);

// Update calibration mode - process button inputs and step through values
// Returns true if calibration mode is handling input (block normal driving)
bool calibration_mode_update(calibration_gamepad_ptr gp);

// Check if calibration mode is currently active
bool calibration_mode_is_active(void);

#endif // CALIBRATION_MODE_H
