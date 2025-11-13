#!/usr/bin/env python3
"""
Analyze motor calibration data and fit curves for linearization.

Fits power law curves of form: RPM = a * (throttle - deadband)^b
"""

import numpy as np
import csv
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt

def power_law_with_deadband(throttle, a, b, deadband):
    """
    Power law model: RPM = a * (throttle - deadband)^b for throttle > deadband
    """
    result = np.zeros_like(throttle, dtype=float)
    mask = throttle > deadband
    result[mask] = a * np.power(throttle[mask] - deadband, b)
    return result

def load_csv(filename):
    """Load throttle and RPM data from CSV file."""
    throttles = []
    left_rpms = []
    right_rpms = []

    with open(filename, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Convert "10%" to 10
            throttle = int(row['Throttle'].rstrip('%'))
            throttles.append(throttle)
            left_rpms.append(int(row['Left']))
            right_rpms.append(int(row['Right']))

    return np.array(throttles), np.array(left_rpms), np.array(right_rpms)

def fit_curve(throttle, rpm, direction_name, motor_name):
    """
    Fit power law curve to the data.

    Returns: (a, b, deadband, rmse)
    """
    # Filter out zero points for fitting (but keep for RMSE calculation)
    nonzero_mask = rpm > 0

    if np.sum(nonzero_mask) < 3:
        print(f"Warning: Not enough non-zero data points for {motor_name} {direction_name}")
        return None, None, None, None

    # Initial guess: deadband around 15%, exponent around 0.8, scale to match max RPM
    max_rpm = np.max(rpm)
    initial_guess = [max_rpm / 80**0.8, 0.8, 15.0]

    # Bounds: a > 0, 0.5 < b < 1.5, 0 < deadband < 25
    bounds = ([0.1, 0.5, 0.0], [1000.0, 1.5, 25.0])

    try:
        # Fit to all data (including zeros)
        params, _ = curve_fit(
            power_law_with_deadband,
            throttle,
            rpm,
            p0=initial_guess,
            bounds=bounds,
            maxfev=10000
        )

        a, b, deadband = params

        # Calculate RMSE over all points
        predicted = power_law_with_deadband(throttle, a, b, deadband)
        rmse = np.sqrt(np.mean((rpm - predicted)**2))

        # Calculate max error
        max_error = np.max(np.abs(rpm - predicted))

        print(f"\n{motor_name} {direction_name}:")
        print(f"  Fitted parameters:")
        print(f"    a (scale)    = {a:.3f}")
        print(f"    b (exponent) = {b:.3f}")
        print(f"    deadband     = {deadband:.1f}%")
        print(f"  Fit quality:")
        print(f"    RMSE         = {rmse:.1f} RPM")
        print(f"    Max error    = {max_error:.1f} RPM")
        print(f"  Predicted values at key throttles:")
        for t in [10, 15, 20, 30, 50, 75, 100]:
            pred = power_law_with_deadband(np.array([t]), a, b, deadband)[0]
            actual_idx = np.where(throttle == t)[0]
            actual = rpm[actual_idx[0]] if len(actual_idx) > 0 else None
            if actual is not None:
                error = pred - actual
                print(f"    {t:3d}%: pred={pred:5.0f} RPM, actual={actual:4d} RPM, error={error:+5.0f} RPM")
            else:
                print(f"    {t:3d}%: pred={pred:5.0f} RPM (no data)")

        return a, b, deadband, rmse

    except Exception as e:
        print(f"Error fitting {motor_name} {direction_name}: {e}")
        return None, None, None, None

def plot_fits(forward_throttle, forward_left, forward_right,
              reverse_throttle, reverse_left, reverse_right,
              left_fwd_params, right_fwd_params,
              left_rev_params, right_rev_params):
    """Plot the original data and fitted curves."""

    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 10))

    # Generate smooth curves for plotting
    throttle_smooth = np.linspace(0, 100, 200)

    # Left Forward
    if left_fwd_params[0] is not None:
        a, b, deadband = left_fwd_params[:3]
        fitted = power_law_with_deadband(throttle_smooth, a, b, deadband)
        ax1.plot(throttle_smooth, fitted, 'r-', label='Fitted curve', linewidth=2)
    ax1.plot(forward_throttle, forward_left, 'bo', label='Measured data', markersize=8)
    ax1.set_xlabel('Throttle (%)', fontsize=12)
    ax1.set_ylabel('RPM', fontsize=12)
    ax1.set_title('Left Motor - Forward', fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    ax1.set_xlim(0, 105)
    ax1.set_ylim(-50, 850)

    # Right Forward
    if right_fwd_params[0] is not None:
        a, b, deadband = right_fwd_params[:3]
        fitted = power_law_with_deadband(throttle_smooth, a, b, deadband)
        ax2.plot(throttle_smooth, fitted, 'r-', label='Fitted curve', linewidth=2)
    ax2.plot(forward_throttle, forward_right, 'go', label='Measured data', markersize=8)
    ax2.set_xlabel('Throttle (%)', fontsize=12)
    ax2.set_ylabel('RPM', fontsize=12)
    ax2.set_title('Right Motor - Forward', fontsize=14, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    ax2.legend()
    ax2.set_xlim(0, 105)
    ax2.set_ylim(-50, 850)

    # Left Reverse
    if left_rev_params[0] is not None:
        a, b, deadband = left_rev_params[:3]
        # For reverse, we work with absolute throttle values
        fitted = power_law_with_deadband(throttle_smooth, a, b, deadband)
        ax3.plot(throttle_smooth, fitted, 'r-', label='Fitted curve', linewidth=2)
    ax3.plot(reverse_throttle, reverse_left, 'bo', label='Measured data', markersize=8)
    ax3.set_xlabel('Throttle (% absolute)', fontsize=12)
    ax3.set_ylabel('RPM', fontsize=12)
    ax3.set_title('Left Motor - Reverse', fontsize=14, fontweight='bold')
    ax3.grid(True, alpha=0.3)
    ax3.legend()
    ax3.set_xlim(0, 105)
    ax3.set_ylim(-50, 850)

    # Right Reverse
    if right_rev_params[0] is not None:
        a, b, deadband = right_rev_params[:3]
        fitted = power_law_with_deadband(throttle_smooth, a, b, deadband)
        ax4.plot(throttle_smooth, fitted, 'r-', label='Fitted curve', linewidth=2)
    ax4.plot(reverse_throttle, reverse_right, 'go', label='Measured data', markersize=8)
    ax4.set_xlabel('Throttle (% absolute)', fontsize=12)
    ax4.set_ylabel('RPM', fontsize=12)
    ax4.set_title('Right Motor - Reverse', fontsize=14, fontweight='bold')
    ax4.grid(True, alpha=0.3)
    ax4.legend()
    ax4.set_xlim(0, 105)
    ax4.set_ylim(-50, 850)

    plt.tight_layout()
    plt.savefig('motor_calibration_fits.png', dpi=150, bbox_inches='tight')
    print(f"\nPlot saved to: motor_calibration_fits.png")

def generate_c_code(left_fwd_params, right_fwd_params, left_rev_params, right_rev_params):
    """Generate C code for the linearization functions."""

    print("\n" + "="*70)
    print("C CODE FOR IMPLEMENTATION")
    print("="*70)
    print("""
/*
 * Motor Linearization using fitted power law curves
 *
 * Model: RPM = a * (throttle - deadband)^b for throttle > deadband
 *        RPM = 0 for throttle <= deadband
 *
 * Inverse: throttle = deadband + (RPM / a)^(1/b)
 */

#include <math.h>

// Fitted curve parameters (from calibration data)
typedef struct {
    float a;         // Scale factor
    float b;         // Exponent
    float deadband;  // Deadband threshold (%)
    float inv_b;     // 1/b (precomputed for efficiency)
} motor_curve_params_t;
""")

    def print_params(name, params):
        if params[0] is not None:
            a, b, deadband, _ = params
            inv_b = 1.0 / b
            print(f"""
static const motor_curve_params_t {name} = {{
    .a = {a:.6f}f,
    .b = {b:.6f}f,
    .deadband = {deadband:.2f}f,
    .inv_b = {inv_b:.6f}f  // 1/b for inverse calculation
}};""")

    print_params("LEFT_FORWARD_CURVE", left_fwd_params)
    print_params("RIGHT_FORWARD_CURVE", right_fwd_params)
    print_params("LEFT_REVERSE_CURVE", left_rev_params)
    print_params("RIGHT_REVERSE_CURVE", right_rev_params)

    print("""
/**
 * Convert desired RPM to actual PWM throttle percentage needed
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
    float throttle = params->deadband + powf(desired_rpm / params->a, params->inv_b);

    // Clamp to valid range
    if (throttle < 0.0f) throttle = 0.0f;
    if (throttle > 100.0f) throttle = 100.0f;

    return throttle;
}

/**
 * Linearize motor command: Convert desired RPM to compensated PWM
 *
 * @param motor MOTOR_LEFT_DRIVE or MOTOR_RIGHT_DRIVE
 * @param desired_rpm_signed Desired RPM (negative for reverse)
 * @return PWM percentage (-100 to +100) to achieve the desired RPM
 */
int8_t linearize_motor_command(motor_id_t motor, int16_t desired_rpm_signed) {
    const motor_curve_params_t* params;
    bool is_reverse = (desired_rpm_signed < 0);
    float desired_rpm = fabsf((float)desired_rpm_signed);

    // Select appropriate curve
    if (motor == MOTOR_LEFT_DRIVE) {
        params = is_reverse ? &LEFT_REVERSE_CURVE : &LEFT_FORWARD_CURVE;
    } else {  // MOTOR_RIGHT_DRIVE
        params = is_reverse ? &RIGHT_REVERSE_CURVE : &RIGHT_FORWARD_CURVE;
    }

    // Calculate compensated throttle
    float throttle = rpm_to_throttle(desired_rpm, params);

    // Convert back to signed PWM percentage
    int8_t pwm = (int8_t)(is_reverse ? -throttle : throttle);

    return pwm;
}

/**
 * Alternative: Direct throttle-to-throttle linearization
 * This is what you'd call from drive.c to compensate controller input
 *
 * @param motor MOTOR_LEFT_DRIVE or MOTOR_RIGHT_DRIVE
 * @param desired_pwm_percent PWM from controller/expo curve (-100 to +100)
 * @return Compensated PWM percentage to achieve linear behavior
 */
int8_t linearize_throttle_command(motor_id_t motor, int8_t desired_pwm_percent) {
    // Convert desired PWM to target RPM (what user expects from that stick position)
    int16_t desired_rpm = (desired_pwm_percent * MAX_WHEEL_RPM) / 100;

    // Use linearization to get actual PWM needed
    return linearize_motor_command(motor, desired_rpm);
}
""")

    print("\n" + "="*70)
    print("USAGE IN drive.c")
    print("="*70)
    print("""
// In drive_mix() function, AFTER expo curve but BEFORE motor_control_set_speed():

// Apply linearization compensation
int8_t left_compensated = linearize_throttle_command(MOTOR_LEFT_DRIVE, output.left_speed);
int8_t right_compensated = linearize_throttle_command(MOTOR_RIGHT_DRIVE, output.right_speed);

// Set motor speeds with compensated values
motor_control_set_speed(MOTOR_LEFT_DRIVE, left_compensated);
motor_control_set_speed(MOTOR_RIGHT_DRIVE, right_compensated);
""")

def main():
    print("="*70)
    print("MOTOR CALIBRATION CURVE FITTING ANALYSIS")
    print("="*70)

    # Load data
    print("\nLoading calibration data...")
    forward_throttle, forward_left, forward_right = load_csv('forward.csv')
    reverse_throttle, reverse_left, reverse_right = load_csv('reverse.csv')

    print(f"  Forward: {len(forward_throttle)} data points")
    print(f"  Reverse: {len(reverse_throttle)} data points")

    # Fit curves
    print("\n" + "="*70)
    print("CURVE FITTING RESULTS")
    print("="*70)

    left_fwd_params = fit_curve(forward_throttle, forward_left, "Forward", "Left")
    right_fwd_params = fit_curve(forward_throttle, forward_right, "Forward", "Right")
    left_rev_params = fit_curve(reverse_throttle, reverse_left, "Reverse", "Left")
    right_rev_params = fit_curve(reverse_throttle, reverse_right, "Reverse", "Right")

    # Generate plots
    print("\n" + "="*70)
    print("GENERATING PLOTS")
    print("="*70)
    plot_fits(forward_throttle, forward_left, forward_right,
              reverse_throttle, reverse_left, reverse_right,
              left_fwd_params, right_fwd_params,
              left_rev_params, right_rev_params)

    # Generate C code
    generate_c_code(left_fwd_params, right_fwd_params, left_rev_params, right_rev_params)

    print("\n" + "="*70)
    print("ANALYSIS COMPLETE")
    print("="*70)
    print("\nNext steps:")
    print("  1. Review the plots in motor_calibration_fits.png")
    print("  2. Create firmware/src/motor_linearization.c with the generated code")
    print("  3. Add motor_linearization.h header file")
    print("  4. Integrate linearize_throttle_command() in drive.c")
    print("  5. Test and verify improved control!")

if __name__ == '__main__':
    main()
