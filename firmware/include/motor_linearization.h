#ifndef MOTOR_LINEARIZATION_H
#define MOTOR_LINEARIZATION_H

#include <stdint.h>
#include <stdbool.h>
#include "motor_control.h"

/**
 * Motor Linearization System
 *
 * Compensates for non-linear ESC+motor response curves and left/right motor asymmetry.
 * Uses fitted power law curves (square root model) from calibration data.
 *
 * Model: RPM = a * sqrt(throttle - deadband) for throttle > deadband
 * Inverse: throttle = deadband + (RPM / a)^2
 *
 * This provides:
 * 1. Linear control feel (stick position proportional to actual speed)
 * 2. Compensation for left/right motor differences (fixes rotation center)
 * 3. Smooth behavior in deadband region (0-15% throttle)
 */

/**
 * Initialize motor linearization system
 *
 * @return true on success
 */
bool motor_linearization_init(void);

/**
 * Linearize motor command: Convert desired PWM to compensated PWM
 *
 * This is the main function to call from drive.c after expo curve.
 * It converts the "desired" PWM (what the user expects from stick position)
 * into the actual PWM needed to achieve that performance, accounting for
 * motor response curves and left/right asymmetry.
 *
 * @param motor Motor ID (MOTOR_LEFT_DRIVE or MOTOR_RIGHT_DRIVE)
 * @param desired_pwm_percent Desired PWM from controller/expo (-100 to +100)
 * @return Compensated PWM percentage to send to motor
 */
int8_t motor_linearization_compensate(motor_channel_t motor, int8_t desired_pwm_percent);

/**
 * Get curve parameters for a specific motor and direction (for debugging/testing)
 *
 * @param motor Motor ID
 * @param is_reverse true for reverse direction
 * @param a_out Output: scale factor
 * @param b_out Output: exponent
 * @param deadband_out Output: deadband threshold
 */
void motor_linearization_get_params(motor_channel_t motor, bool is_reverse,
                                     float* a_out, float* b_out, float* deadband_out);

#endif // MOTOR_LINEARIZATION_H
