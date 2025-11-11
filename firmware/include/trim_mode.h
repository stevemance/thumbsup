#ifndef TRIM_MODE_H
#define TRIM_MODE_H

#include <stdint.h>
#include <stdbool.h>

// Motor trim calibration mode for combat robots
// Allows operator to calibrate motor differences so robot drives straight

// Trim mode power levels for calibration
typedef enum {
    TRIM_LEVEL_30_PERCENT,  // Low speed calibration
    TRIM_LEVEL_70_PERCENT   // High speed calibration
} trim_level_t;

// Trim mode state
typedef enum {
    TRIM_MODE_INACTIVE,
    TRIM_MODE_ACTIVE
} trim_mode_state_t;

// Opaque gamepad pointer (to avoid including uni.h everywhere)
typedef void* trim_gamepad_ptr;

// Initialize trim mode system and load saved trim from flash
bool trim_mode_init(void);

// Check if trim mode should be activated/deactivated
// Call this every frame with gamepad data
void trim_mode_check_activation(trim_gamepad_ptr gp);

// Update trim mode - process calibration inputs
// Returns true if trim mode is handling input (block normal driving)
bool trim_mode_update(trim_gamepad_ptr gp);

// Check if trim mode is currently active
bool trim_mode_is_active(void);

// Get the current trim offset (-100 to +100)
// This is added to the turn value in drive calculations
// If in trim mode, returns the working trim being adjusted
// If not in trim mode, interpolates between saved 30% and 70% trims based on drive power
int8_t trim_mode_get_offset(uint8_t drive_power_percent);

// Get current calibration level
trim_level_t trim_mode_get_level(void);

// Save current trim to flash (called on exit)
bool trim_mode_save(void);

// Load trim from flash (called on init)
bool trim_mode_load(void);

// Reset trim to zero (for testing)
void trim_mode_reset(void);

#endif // TRIM_MODE_H
