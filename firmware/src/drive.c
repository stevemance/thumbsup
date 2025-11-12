#include "drive.h"
#include "motor_control.h"
#include "trim_mode.h"
#include "config.h"
#include <stdio.h>
#include <stdlib.h>
#include <math.h>

static uint8_t current_expo = DRIVE_EXPO;
static bool drive_enabled = false;

int8_t drive_apply_expo(int8_t input, uint8_t expo) {
    // SAFETY: Validate inputs to prevent overflow
    if (input == 0 || expo == 0) {
        return input;
    }

    // Clamp expo to valid range
    expo = expo > 100 ? 100 : expo;

    float normalized = (float)input / 127.0f;
    float expo_factor = (float)expo / 100.0f;

    float linear = normalized;
    float cubic = normalized * normalized * normalized;

    // Cubic of negative is already negative, so no need to invert
    float output = linear * (1.0f - expo_factor) + cubic * expo_factor;

    // SAFETY: Clamp output to valid int8_t range
    float result = output * 127.0f;
    if (result > 127.0f) result = 127.0f;
    if (result < -127.0f) result = -127.0f;

    return (int8_t)result;
}

drive_output_t drive_mix(int8_t forward, int8_t turn) {
    drive_output_t output = {0, 0}; // SAFETY: Initialize to safe defaults

    // SAFETY: Validate inputs
    forward = CLAMP(forward, -127, 127);
    turn = CLAMP(turn, -127, 127);

    int8_t forward_before_expo = forward;
    int8_t turn_before_expo = turn;

    forward = drive_apply_expo(forward, current_expo);
    turn = drive_apply_expo(turn, current_expo);

    // DEBUG: Log expo transformation
    static uint32_t last_expo_debug = 0;
    uint32_t now = to_ms_since_boot(get_absolute_time());
    if (now - last_expo_debug > 500) {
        if (forward_before_expo != 0 || turn_before_expo != 0) {
            printf("EXPO: F %d→%d, T %d→%d\n",
                   forward_before_expo, forward, turn_before_expo, turn);
        }
        last_expo_debug = now;
    }

    // SAFETY: Use 32-bit arithmetic to prevent overflow during scaling
    int32_t scaled_forward = ((int32_t)forward * MAX_DRIVE_SPEED) / 100;
    int32_t scaled_turn = ((int32_t)turn * MAX_DRIVE_SPEED) / 100;

    // SAFETY: Clamp after scaling to prevent overflow
    scaled_forward = CLAMP(scaled_forward, -100, 100);
    scaled_turn = CLAMP(scaled_turn, -100, 100);

    int32_t left = scaled_forward + scaled_turn;
    int32_t right = scaled_forward - scaled_turn;

    // SAFETY: Find max value safely
    int32_t max_val = (left < 0 ? -left : left);
    int32_t right_abs = (right < 0 ? -right : right);
    if (right_abs > max_val) max_val = right_abs;

    if (max_val > 100) {
        // SAFETY: Use double precision for scaling calculation
        double scale = 100.0 / (double)max_val;
        left = (int32_t)(left * scale);
        right = (int32_t)(right * scale);
    }

    output.left_speed = (int8_t)CLAMP(left, -100, 100);
    output.right_speed = (int8_t)CLAMP(right, -100, 100);

    // DEBUG: Log final output speeds
    static uint32_t last_mix_debug = 0;
    uint32_t now2 = to_ms_since_boot(get_absolute_time());
    if (now2 - last_mix_debug > 500) {
        if (output.left_speed != 0 || output.right_speed != 0) {
            printf("MIX: L=%d R=%d\n", output.left_speed, output.right_speed);
        }
        last_mix_debug = now2;
    }

    return output;
}

bool drive_init(void) {
    drive_enabled = true;
    current_expo = DRIVE_EXPO;

    motor_control_set_speed(MOTOR_LEFT_DRIVE, 0);
    motor_control_set_speed(MOTOR_RIGHT_DRIVE, 0);

    DEBUG_PRINT("Drive system initialized with expo=%d\n", current_expo);

    return true;
}

void drive_update(drive_control_t* control) {
    // SAFETY: Validate input parameters
    if (!control || !drive_enabled) {
        DEBUG_PRINT("Drive update: invalid parameters or disabled\n");
        drive_stop();
        return;
    }

    if (!control->enabled) {
        drive_stop();
        return;
    }

    // SAFETY: Additional validation of control inputs
    if (control->forward < -127 || control->forward > 127 ||
        control->turn < -127 || control->turn > 127) {
        DEBUG_PRINT("Drive update: invalid control values (%d, %d)\n",
                    control->forward, control->turn);
        drive_stop();
        return;
    }

    int8_t forward = control->forward;
    int8_t turn = control->turn;

    // TRIM MODE: Pass through normal driving (no overrides, no trim applied)
    if (trim_mode_is_active()) {
        // In trim mode, drive normally without any trim correction
        // User adjusts steering to make robot go straight, then captures samples
        drive_output_t output = drive_mix(forward, turn);

        // SAFETY: Verify output is within expected range
        if (output.left_speed < -100 || output.left_speed > 100 ||
            output.right_speed < -100 || output.right_speed > 100) {
            DEBUG_PRINT("CRITICAL: Drive mix produced invalid output (%d, %d)\n",
                        output.left_speed, output.right_speed);
            drive_stop();
            return;
        }

        motor_control_set_speed(MOTOR_LEFT_DRIVE, output.left_speed);
        motor_control_set_speed(MOTOR_RIGHT_DRIVE, output.right_speed);
        return;
    }

    // NORMAL MODE: Apply dynamic trim based on current speed
    // Calculate speed as signed percentage (-100 to +100)
    int8_t speed_percent = (int8_t)((forward * 100) / 127);

    // Get interpolated trim offset based on current speed (supports forward and reverse)
    int8_t trim_offset = trim_mode_get_offset(speed_percent);

    // Apply trim to turn value
    int32_t adjusted_turn = (int32_t)turn + trim_offset;
    turn = (int8_t)CLAMP(adjusted_turn, -127, 127);

    drive_output_t output = drive_mix(forward, turn);

    // SAFETY: Verify output is within expected range before sending to motors
    if (output.left_speed < -100 || output.left_speed > 100 ||
        output.right_speed < -100 || output.right_speed > 100) {
        DEBUG_PRINT("CRITICAL: Drive mix produced invalid output (%d, %d)\n",
                    output.left_speed, output.right_speed);
        drive_stop();
        return;
    }

    motor_control_set_speed(MOTOR_LEFT_DRIVE, output.left_speed);
    motor_control_set_speed(MOTOR_RIGHT_DRIVE, output.right_speed);
}

void drive_stop(void) {
    motor_control_set_speed(MOTOR_LEFT_DRIVE, 0);
    motor_control_set_speed(MOTOR_RIGHT_DRIVE, 0);
}

void drive_set_expo(uint8_t expo_value) {
    current_expo = CLAMP(expo_value, 0, 100);
}