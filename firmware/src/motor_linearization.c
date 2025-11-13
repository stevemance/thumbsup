#include "motor_linearization.h"
#include "config.h"
#include <math.h>
#include <stdio.h>

/**
 * Motor Linearization Implementation
 *
 * Fitted curve parameters from calibration data (2025-11-12)
 * Model: RPM = a * (throttle - deadband)^b where b ≈ 0.5 (square root)
 * Inverse: throttle = deadband + (RPM / a)^(1/b)
 */

// Curve parameters structure
typedef struct {
    float a;         // Scale factor
    float b;         // Exponent (≈0.5 for square root)
    float deadband;  // Deadband threshold (%)
    float inv_b;     // 1/b (precomputed for efficiency)
} motor_curve_params_t;

// Fitted curves for each motor and direction
// Generated from analyze_curves.py using forward.csv and reverse.csv
static const motor_curve_params_t LEFT_FORWARD_CURVE = {
    .a = 87.962487f,
    .b = 0.500102f,
    .deadband = 10.00f,
    .inv_b = 1.999591f  // 1/b for inverse calculation
};

static const motor_curve_params_t RIGHT_FORWARD_CURVE = {
    .a = 94.404955f,
    .b = 0.500494f,
    .deadband = 10.00f,
    .inv_b = 1.998027f  // 1/b for inverse calculation
};

static const motor_curve_params_t LEFT_REVERSE_CURVE = {
    .a = 88.861438f,
    .b = 0.500001f,
    .deadband = 10.00f,
    .inv_b = 1.999998f  // 1/b for inverse calculation
};

static const motor_curve_params_t RIGHT_REVERSE_CURVE = {
    .a = 91.173282f,
    .b = 0.500000f,
    .deadband = 11.71f,
    .inv_b = 2.000000f  // 1/b for inverse calculation
};

/**
 * Convert desired RPM to actual PWM throttle percentage needed
 *
 * Uses inverse of the fitted power law curve to determine what PWM
 * percentage is needed to achieve a target RPM.
 *
 * @param desired_rpm Target wheel RPM (absolute value, always positive)
 * @param params Curve parameters for this motor/direction
 * @return PWM throttle percentage (0-100) needed to achieve desired RPM
 */
static float rpm_to_throttle(float desired_rpm, const motor_curve_params_t* params) {
    if (desired_rpm <= 0.0f) {
        return 0.0f;
    }

    // Inverse power law: throttle = deadband + (RPM / a)^(1/b)
    // For b ≈ 0.5 (square root), 1/b ≈ 2 (square)
    float throttle = params->deadband + powf(desired_rpm / params->a, params->inv_b);

    // Clamp to valid range
    if (throttle < 0.0f) {
        throttle = 0.0f;
    }
    if (throttle > 100.0f) {
        throttle = 100.0f;
    }

    return throttle;
}

/**
 * Select the appropriate curve for a motor and direction
 */
static const motor_curve_params_t* select_curve(motor_channel_t motor, bool is_reverse) {
    if (motor == MOTOR_LEFT_DRIVE) {
        return is_reverse ? &LEFT_REVERSE_CURVE : &LEFT_FORWARD_CURVE;
    } else {  // MOTOR_RIGHT_DRIVE
        return is_reverse ? &RIGHT_REVERSE_CURVE : &RIGHT_FORWARD_CURVE;
    }
}

bool motor_linearization_init(void) {
    printf("Motor Linearization: Initialized with per-motor calibration curves\n");
    printf("  Left Forward:  a=%.2f, b=%.3f, deadband=%.1f%%\n",
           LEFT_FORWARD_CURVE.a, LEFT_FORWARD_CURVE.b, LEFT_FORWARD_CURVE.deadband);
    printf("  Right Forward: a=%.2f, b=%.3f, deadband=%.1f%%\n",
           RIGHT_FORWARD_CURVE.a, RIGHT_FORWARD_CURVE.b, RIGHT_FORWARD_CURVE.deadband);
    printf("  Left Reverse:  a=%.2f, b=%.3f, deadband=%.1f%%\n",
           LEFT_REVERSE_CURVE.a, LEFT_REVERSE_CURVE.b, LEFT_REVERSE_CURVE.deadband);
    printf("  Right Reverse: a=%.2f, b=%.3f, deadband=%.1f%%\n",
           RIGHT_REVERSE_CURVE.a, RIGHT_REVERSE_CURVE.b, RIGHT_REVERSE_CURVE.deadband);
    return true;
}

int8_t motor_linearization_compensate(motor_channel_t motor, int8_t desired_pwm_percent) {
    // Handle zero case quickly
    if (desired_pwm_percent == 0) {
        return 0;
    }

    // Determine direction
    bool is_reverse = (desired_pwm_percent < 0);
    int8_t abs_pwm = is_reverse ? -desired_pwm_percent : desired_pwm_percent;

    // Convert desired PWM percentage to target RPM
    // This is what the user expects: 50% stick = 50% of max speed
    int16_t desired_rpm = (abs_pwm * MAX_WHEEL_RPM) / 100;

    // Select the appropriate curve for this motor and direction
    const motor_curve_params_t* params = select_curve(motor, is_reverse);

    // Use inverse curve to find actual PWM needed to achieve this RPM
    float compensated_throttle = rpm_to_throttle((float)desired_rpm, params);

    // Convert back to signed PWM percentage
    int8_t compensated_pwm = (int8_t)compensated_throttle;
    if (is_reverse) {
        compensated_pwm = -compensated_pwm;
    }

    // Clamp to valid range
    if (compensated_pwm < -100) compensated_pwm = -100;
    if (compensated_pwm > 100) compensated_pwm = 100;

    return compensated_pwm;
}

void motor_linearization_get_params(motor_channel_t motor, bool is_reverse,
                                     float* a_out, float* b_out, float* deadband_out) {
    const motor_curve_params_t* params = select_curve(motor, is_reverse);

    if (a_out) *a_out = params->a;
    if (b_out) *b_out = params->b;
    if (deadband_out) *deadband_out = params->deadband;
}
