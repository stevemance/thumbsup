#ifndef TRIM_MODE_H
#define TRIM_MODE_H

#include <stdint.h>
#include <stdbool.h>

// Motor trim calibration mode for combat robots - Dynamic Sample-Based System
// Allows operator to collect trim samples at various speeds and fits curves
// Supports forward and reverse calibration

// Maximum number of trim samples that can be stored
#define MAX_TRIM_SAMPLES 30

// Single trim calibration sample point
typedef struct {
    int8_t speed_percent;      // -100 to +100 (negative = reverse)
    int8_t turn_offset;        // The turn value needed to go straight at this speed
} trim_sample_t;

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

// Handle exit feedback timeout and LED restoration (call every frame)
void trim_mode_handle_exit_feedback(void);

// Update trim mode - process calibration inputs
// Returns true if trim mode is handling input (block normal driving)
bool trim_mode_update(trim_gamepad_ptr gp);

// Check if trim mode is currently active
bool trim_mode_is_active(void);

// Capture a trim sample at the current speed
// Called when A button is pressed during trim mode
// forward: Forward speed percent (-100 to +100)
// turn: Turn value needed to go straight (-100 to +100)
void trim_mode_capture_sample(int8_t forward, int8_t turn);

// Remove the last captured trim sample
// Called when B button is pressed during trim mode
void trim_mode_remove_last_sample(void);

// Get the interpolated trim offset for a given speed
// speed_percent: Current forward speed (-100 to +100)
// Returns: Turn offset to apply (-100 to +100)
int8_t trim_mode_get_offset(int8_t speed_percent);

// Process samples and fit curves (called on trim mode exit)
// Returns true if successful (enough samples), false if not enough data
bool trim_mode_fit_curves(void);

// Save current trim samples to flash
bool trim_mode_save(void);

// Load trim samples from flash
bool trim_mode_load(void);

// Reset trim to zero (clear all samples)
void trim_mode_reset(void);

#endif // TRIM_MODE_H
