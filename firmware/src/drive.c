#include "drive.h"
#include "motor_control.h"
#include "config.h"
#include <stdio.h>
#include <math.h>

static uint8_t current_expo = DRIVE_EXPO;
static bool drive_enabled = false;

int8_t drive_apply_expo(int8_t input, uint8_t expo) {
    if (input == 0 || expo == 0) {
        return input;
    }

    float normalized = (float)input / 127.0f;
    float expo_factor = (float)expo / 100.0f;

    float linear = normalized;
    float cubic = normalized * normalized * normalized;

    float output = linear * (1.0f - expo_factor) + cubic * expo_factor;

    if (input < 0) {
        output = -output;
    }

    return (int8_t)(output * 127.0f);
}

drive_output_t drive_mix(int8_t forward, int8_t turn) {
    drive_output_t output;

    forward = drive_apply_expo(forward, current_expo);
    turn = drive_apply_expo(turn, current_expo);

    forward = (forward * MAX_DRIVE_SPEED) / 100;
    turn = (turn * MAX_DRIVE_SPEED) / 100;

    int16_t left = forward + turn;
    int16_t right = forward - turn;

    int16_t max_val = MAX(abs(left), abs(right));
    if (max_val > 100) {
        float scale = 100.0f / (float)max_val;
        left = (int16_t)(left * scale);
        right = (int16_t)(right * scale);
    }

    output.left_speed = CLAMP(left, -100, 100);
    output.right_speed = CLAMP(right, -100, 100);

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
    if (!control || !drive_enabled) {
        drive_stop();
        return;
    }

    if (!control->enabled) {
        drive_stop();
        return;
    }

    drive_output_t output = drive_mix(control->forward, control->turn);

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