#include "calibration_mode.h"
#include "config.h"
#include "motor_control.h"
#include "status.h"
#include "pico/stdlib.h"
#include <stdio.h>
#if !DIAGNOSTIC_MODE_BUILD
#include <uni.h>  // For full gamepad structure definition (competition mode only)
#endif

// Calibration step definition
typedef struct {
    int8_t pwm_percent;  // -100 to +100
    const char* description;
} calibration_step_t;

// Calibration sequence: 10% increments forward, then backward
static const calibration_step_t calibration_steps[] = {
    {0,    "NEUTRAL (0%)"},
    {10,   "10% Forward"},
    {20,   "20% Forward"},
    {30,   "30% Forward"},
    {40,   "40% Forward"},
    {50,   "50% Forward"},
    {60,   "60% Forward"},
    {70,   "70% Forward"},
    {80,   "80% Forward"},
    {90,   "90% Forward"},
    {100,  "100% Forward (MAX)"},
    {0,    "NEUTRAL (return)"},
    {-10,  "10% Reverse"},
    {-20,  "20% Reverse"},
    {-30,  "30% Reverse"},
    {-40,  "40% Reverse"},
    {-50,  "50% Reverse"},
    {-60,  "60% Reverse"},
    {-70,  "70% Reverse"},
    {-80,  "80% Reverse"},
    {-90,  "90% Reverse"},
    {-100, "100% Reverse (MAX)"},
    {0,    "NEUTRAL (complete)"}
};

#define NUM_CALIBRATION_STEPS (sizeof(calibration_steps) / sizeof(calibration_steps[0]))

// Calibration state
static bool calibration_active = false;
static uint32_t calibration_start_time = 0;
static int current_step = 0;

// Button debouncing
static uint32_t last_button_time = 0;
#define BUTTON_DEBOUNCE_MS 300

// LED color cycling for visual feedback
static uint32_t last_led_update = 0;
#define LED_CYCLE_MS 500

// Forward declarations
static void print_current_step(void);
static void apply_current_step(void);

bool calibration_mode_init(void) {
    calibration_active = false;
    current_step = 0;
    return true;
}

void calibration_mode_check_activation(calibration_gamepad_ptr gp_ptr) {
#if !DIAGNOSTIC_MODE_BUILD
    uni_gamepad_t* gp = (uni_gamepad_t*)gp_ptr;

    // Activation: Hold X + Y buttons simultaneously
    // This is intentionally hard to trigger accidentally
    static uint32_t activation_hold_start = 0;
    static bool activation_in_progress = false;

    bool x_pressed = (gp->buttons & BTN_X);
    bool y_pressed = (gp->buttons & BTN_Y);

    if (x_pressed && y_pressed) {
        if (!activation_in_progress) {
            activation_in_progress = true;
            activation_hold_start = to_ms_since_boot(get_absolute_time());
        } else {
            uint32_t hold_time = to_ms_since_boot(get_absolute_time()) - activation_hold_start;
            if (hold_time >= 1000) {  // Hold for 1 second
                if (!calibration_active) {
                    // ENTER calibration mode
                    calibration_active = true;
                    calibration_start_time = to_ms_since_boot(get_absolute_time());
                    current_step = 0;

                    printf("\n");
                    printf("╔════════════════════════════════════════════════════════╗\n");
                    printf("║        MOTOR CALIBRATION MODE ACTIVATED               ║\n");
                    printf("╚════════════════════════════════════════════════════════╝\n");
                    printf("\n");
                    printf("Instructions:\n");
                    printf("  1. Ensure robot is secure with wheels elevated\n");
                    printf("  2. Point optical tachometer at reflector on wheel\n");
                    printf("  3. Press A button to advance to next step\n");
                    printf("  4. Measure and record RPM for BOTH wheels at each step\n");
                    printf("  5. Press B button to repeat current step\n");
                    printf("  6. Hold X+Y again to exit calibration mode\n");
                    printf("\n");
                    printf("Total steps: %d\n", NUM_CALIBRATION_STEPS);
                    printf("\n");

                    // Set LED to purple to indicate calibration mode
                    status_set_led_color(0, 0x00100010, LED_EFFECT_SOLID);  // Purple
                    status_set_led_color(1, 0x00100010, LED_EFFECT_SOLID);  // Purple
                } else {
                    // EXIT calibration mode
                    calibration_active = false;
                    motor_control_set_speed(MOTOR_LEFT_DRIVE, 0);
                    motor_control_set_speed(MOTOR_RIGHT_DRIVE, 0);

                    printf("\n");
                    printf("╔════════════════════════════════════════════════════════╗\n");
                    printf("║        MOTOR CALIBRATION MODE COMPLETE                ║\n");
                    printf("╚════════════════════════════════════════════════════════╝\n");
                    printf("\n");
                    printf("Calibration data collection complete!\n");
                    printf("Analyze your recorded data to:\n");
                    printf("  - Verify ESC linearity\n");
                    printf("  - Measure actual max RPM\n");
                    printf("  - Check left/right motor matching\n");
                    printf("  - Update MAX_WHEEL_RPM in config.h if needed\n");
                    printf("\n");

                    // Restore normal LED state
                    status_set_system(SYSTEM_STATUS_CONNECTED, LED_EFFECT_SOLID);
                    status_set_weapon(WEAPON_STATUS_DISARMED, LED_EFFECT_SOLID);
                }
                activation_in_progress = false;
            }
        }
    } else {
        activation_in_progress = false;
    }
#else
    // Diagnostic mode: calibration mode not available
    (void)gp_ptr;
#endif
}

bool calibration_mode_update(calibration_gamepad_ptr gp_ptr) {
#if !DIAGNOSTIC_MODE_BUILD
    if (!calibration_active) {
        return false;
    }

    uni_gamepad_t* gp = (uni_gamepad_t*)gp_ptr;
    uint32_t now = to_ms_since_boot(get_absolute_time());

    // Cycle LED colors to show we're active
    if (now - last_led_update > LED_CYCLE_MS) {
        // Alternate between purple and cyan
        static bool led_state = false;
        if (led_state) {
            status_set_led_color(0, 0x00100010, LED_EFFECT_SOLID);  // Purple
            status_set_led_color(1, 0x00200020, LED_EFFECT_SOLID);  // Cyan
        } else {
            status_set_led_color(0, 0x00200020, LED_EFFECT_SOLID);  // Cyan
            status_set_led_color(1, 0x00100010, LED_EFFECT_SOLID);  // Purple
        }
        led_state = !led_state;
        last_led_update = now;
    }

    // Button debouncing
    if (now - last_button_time < BUTTON_DEBOUNCE_MS) {
        return true;  // Still in calibration mode, just ignoring buttons
    }

    // A button: Advance to next step
    static bool button_a_prev = false;
    bool button_a = (gp->buttons & BTN_A) != 0;
    if (button_a && !button_a_prev) {
        last_button_time = now;
        current_step++;

        if (current_step >= NUM_CALIBRATION_STEPS) {
            // Completed all steps
            printf("\n");
            printf("═══════════════════════════════════════════════════════\n");
            printf("  ALL CALIBRATION STEPS COMPLETE!\n");
            printf("═══════════════════════════════════════════════════════\n");
            printf("\n");
            printf("Hold X+Y to exit calibration mode.\n");
            printf("\n");

            // Stop motors
            motor_control_set_speed(MOTOR_LEFT_DRIVE, 0);
            motor_control_set_speed(MOTOR_RIGHT_DRIVE, 0);

            // Flash both LEDs green to indicate completion
            status_set_led_color(0, 0x00200000, LED_EFFECT_BLINK_SLOW);  // Green
            status_set_led_color(1, 0x00200000, LED_EFFECT_BLINK_SLOW);  // Green
        } else {
            // Show current step
            print_current_step();
            apply_current_step();
        }
    }
    button_a_prev = button_a;

    // B button: Repeat current step (useful if measurement was missed)
    static bool button_b_prev = false;
    bool button_b = (gp->buttons & BTN_B) != 0;
    if (button_b && !button_b_prev) {
        last_button_time = now;
        printf("\n");
        printf("─────────────────────────────────────────────────────\n");
        printf("  REPEATING CURRENT STEP\n");
        printf("─────────────────────────────────────────────────────\n");
        print_current_step();
        apply_current_step();
    }
    button_b_prev = button_b;

    return true;  // Calibration mode is handling input
#else
    // Diagnostic mode: calibration mode not available
    (void)gp_ptr;
    return false;
#endif
}

static void print_current_step(void) {
    if (current_step >= NUM_CALIBRATION_STEPS) {
        return;
    }

    const calibration_step_t* step = &calibration_steps[current_step];

    printf("\n");
    printf("┌────────────────────────────────────────────────────┐\n");
    printf("│ Step %2d/%d: %-40s │\n",
           current_step + 1, NUM_CALIBRATION_STEPS, step->description);
    printf("├────────────────────────────────────────────────────┤\n");
    printf("│ PWM Command:  %+4d%%                               │\n", step->pwm_percent);

    // Calculate expected values
    int expected_rpm = (step->pwm_percent * MAX_WHEEL_RPM) / 100;
    float expected_ms = (step->pwm_percent * MAX_VELOCITY_MS) / 100.0f;

    printf("│ Expected RPM: %4d RPM                            │\n", abs(expected_rpm));
    printf("│ Expected vel: %+.2f m/s                           │\n", expected_ms);
    printf("├────────────────────────────────────────────────────┤\n");
    printf("│ ACTION REQUIRED:                                   │\n");
    printf("│  1. Wait 2 seconds for motor to stabilize         │\n");
    printf("│  2. Measure LEFT wheel RPM with tachometer        │\n");
    printf("│  3. Measure RIGHT wheel RPM with tachometer       │\n");
    printf("│  4. Record both values in your table              │\n");
    printf("│  5. Press A to continue to next step              │\n");
    printf("│  6. Press B to repeat this step if needed         │\n");
    printf("└────────────────────────────────────────────────────┘\n");
    printf("\n");
}

static void apply_current_step(void) {
    if (current_step >= NUM_CALIBRATION_STEPS) {
        motor_control_set_speed(MOTOR_LEFT_DRIVE, 0);
        motor_control_set_speed(MOTOR_RIGHT_DRIVE, 0);
        return;
    }

    const calibration_step_t* step = &calibration_steps[current_step];

    // Set motor speeds
    motor_control_set_speed(MOTOR_LEFT_DRIVE, step->pwm_percent);
    motor_control_set_speed(MOTOR_RIGHT_DRIVE, step->pwm_percent);

    printf("Motors set to %+d%% - measuring now...\n", step->pwm_percent);
    printf("\n");
}

bool calibration_mode_is_active(void) {
    return calibration_active;
}

void calibration_mode_get_step_info(int* step_num, int* total_steps, int* pwm_percent) {
    if (step_num) *step_num = current_step;
    if (total_steps) *total_steps = NUM_CALIBRATION_STEPS;
    if (pwm_percent && current_step < NUM_CALIBRATION_STEPS) {
        *pwm_percent = calibration_steps[current_step].pwm_percent;
    }
}
