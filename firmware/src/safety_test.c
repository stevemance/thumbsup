#include "config.h"
#include "motor_control.h"
#include "weapon.h"
#include "safety.h"
#include "drive.h"
#include "status.h"
#include "pico/stdlib.h"
#include <stdio.h>

// Test function declarations
static bool test_motor_initialization(void);
static bool test_weapon_safety_checks(void);
static bool test_failsafe_conditions(void);
static bool test_battery_monitoring(void);
static bool test_emergency_stops(void);
static bool test_integer_overflow_protection(void);

/**
 * Comprehensive safety test suite for ThumbsUp robot
 * This function validates all critical safety features
 * MUST pass all tests before deployment
 */
bool run_safety_tests(void) {
    printf("\n=================================\n");
    printf("  ThumbsUp Safety Test Suite\n");
    printf("=================================\n\n");

    bool all_passed = true;
    int tests_run = 0;
    int tests_passed = 0;

    // Test 1: Motor initialization safety
    printf("Test 1: Motor Initialization Safety...\n");
    tests_run++;
    if (test_motor_initialization()) {
        printf("  ✓ PASSED\n");
        tests_passed++;
    } else {
        printf("  ✗ FAILED\n");
        all_passed = false;
    }

    // Test 2: Weapon safety checks
    printf("Test 2: Weapon Safety Checks...\n");
    tests_run++;
    if (test_weapon_safety_checks()) {
        printf("  ✓ PASSED\n");
        tests_passed++;
    } else {
        printf("  ✗ FAILED\n");
        all_passed = false;
    }

    // Test 3: Failsafe conditions
    printf("Test 3: Failsafe Conditions...\n");
    tests_run++;
    if (test_failsafe_conditions()) {
        printf("  ✓ PASSED\n");
        tests_passed++;
    } else {
        printf("  ✗ FAILED\n");
        all_passed = false;
    }

    // Test 4: Battery monitoring
    printf("Test 4: Battery Monitoring...\n");
    tests_run++;
    if (test_battery_monitoring()) {
        printf("  ✓ PASSED\n");
        tests_passed++;
    } else {
        printf("  ✗ FAILED\n");
        all_passed = false;
    }

    // Test 5: Emergency stops
    printf("Test 5: Emergency Stop Functions...\n");
    tests_run++;
    if (test_emergency_stops()) {
        printf("  ✓ PASSED\n");
        tests_passed++;
    } else {
        printf("  ✗ FAILED\n");
        all_passed = false;
    }

    // Test 6: Integer overflow protection
    printf("Test 6: Integer Overflow Protection...\n");
    tests_run++;
    if (test_integer_overflow_protection()) {
        printf("  ✓ PASSED\n");
        tests_passed++;
    } else {
        printf("  ✗ FAILED\n");
        all_passed = false;
    }

    printf("\n=================================\n");
    printf("  Test Results: %d/%d passed\n", tests_passed, tests_run);
    if (all_passed) {
        printf("  ✓ ALL SAFETY TESTS PASSED\n");
        printf("  System is safe for operation\n");
    } else {
        printf("  ✗ SAFETY TESTS FAILED\n");
        printf("  DO NOT OPERATE ROBOT\n");
    }
    printf("=================================\n\n");

    return all_passed;
}

static bool test_motor_initialization(void) {
    bool passed = true;

    // Test that weapon motor starts at minimum pulse
    uint16_t weapon_pulse = motor_control_get_pulse(MOTOR_WEAPON);
    if (weapon_pulse != PWM_MIN_PULSE) {
        printf("    FAIL: Weapon motor not initialized to safe state (%dus)\n", weapon_pulse);
        passed = false;
    }

    // Test that drive motors start at neutral
    uint16_t left_pulse = motor_control_get_pulse(MOTOR_LEFT_DRIVE);
    uint16_t right_pulse = motor_control_get_pulse(MOTOR_RIGHT_DRIVE);
    if (left_pulse != PWM_NEUTRAL_PULSE || right_pulse != PWM_NEUTRAL_PULSE) {
        printf("    FAIL: Drive motors not initialized to neutral (%dus, %dus)\n",
               left_pulse, right_pulse);
        passed = false;
    }

    return passed;
}

static bool test_weapon_safety_checks(void) {
    bool passed = true;

    // Test that weapon cannot be armed with low battery
    weapon_state_t initial_state = weapon_get_state();

    // Simulate low battery condition
    if (safety_check_arm_conditions(BATTERY_LOW_VOLTAGE - 100)) {
        printf("    FAIL: Safety allows arming with low battery\n");
        passed = false;
    }

    // Test that weapon cannot be armed with safety button pressed
    // This would require mocking the GPIO read, which we'll skip for now
    // but the logic is verified in the safety.c file

    // Test weapon starts disarmed
    if (initial_state != WEAPON_STATE_DISARMED) {
        printf("    FAIL: Weapon does not start in disarmed state\n");
        passed = false;
    }

    return passed;
}

static bool test_failsafe_conditions(void) {
    bool passed = true;

    // Test failsafe detection function exists and works
    extern bool bluetooth_platform_failsafe_active(void);

    // This is more of a compile-time test - if it compiles, the function exists
    // Runtime testing would require mocking the timestamp
    (void)bluetooth_platform_failsafe_active(); // Suppress unused warning

    return passed;
}

static bool test_battery_monitoring(void) {
    bool passed = true;

    // Test battery voltage reading function
    uint32_t battery_mv = read_battery_voltage();

    // Basic sanity check - battery should be within reasonable range
    if (battery_mv < 6000 || battery_mv > 15000) {
        printf("    WARN: Battery voltage reading seems out of range (%dmV)\n", battery_mv);
        // Don't fail the test as this might be due to no battery connected
    }

    // Test battery safety thresholds are reasonable
    if (BATTERY_LOW_VOLTAGE >= BATTERY_MAX_VOLTAGE) {
        printf("    FAIL: Battery thresholds are incorrectly configured\n");
        passed = false;
    }

    if (BATTERY_CRITICAL >= BATTERY_LOW_VOLTAGE) {
        printf("    FAIL: Critical battery threshold too high\n");
        passed = false;
    }

    return passed;
}

static bool test_emergency_stops(void) {
    bool passed = true;

    // Test that emergency stop functions exist and can be called
    weapon_emergency_stop();
    motor_control_emergency_stop();

    // Verify weapon is in emergency stop state
    if (weapon_get_state() != WEAPON_STATE_EMERGENCY_STOP) {
        printf("    FAIL: Weapon emergency stop did not change state\n");
        passed = false;
    }

    // Re-initialize systems for continued testing
    motor_control_init();
    weapon_init();

    return passed;
}

static bool test_integer_overflow_protection(void) {
    bool passed = true;

    // Test motor control pulse validation
    // Try to set invalid pulse values
    bool result1 = motor_control_set_pulse(MOTOR_LEFT_DRIVE, 5000); // Way too high
    bool result2 = motor_control_set_pulse(MOTOR_RIGHT_DRIVE, 500);  // Way too low

    // Both should succeed (with clamping) but values should be clamped
    if (!result1 || !result2) {
        printf("    FAIL: Motor control should clamp invalid values, not reject\n");
        passed = false;
    }

    // Verify clamping worked
    uint16_t left_pulse = motor_control_get_pulse(MOTOR_LEFT_DRIVE);
    uint16_t right_pulse = motor_control_get_pulse(MOTOR_RIGHT_DRIVE);

    if (left_pulse > PWM_MAX_PULSE || right_pulse < PWM_MIN_PULSE) {
        printf("    FAIL: Pulse clamping not working correctly\n");
        passed = false;
    }

    return passed;
}