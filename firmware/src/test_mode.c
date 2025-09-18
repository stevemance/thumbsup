#include "test_mode.h"
#include <stdio.h>
#include "pico/time.h"
#include <uni.h>  // For full gamepad structure definition

// ANSI escape codes for terminal control
#define ANSI_CLEAR_SCREEN "\033[2J"
#define ANSI_HOME "\033[H"
#define ANSI_HIDE_CURSOR "\033[?25l"
#define ANSI_SHOW_CURSOR "\033[?25h"
#define ANSI_BOLD "\033[1m"
#define ANSI_NORMAL "\033[0m"
#define ANSI_RED "\033[31m"
#define ANSI_GREEN "\033[32m"
#define ANSI_YELLOW "\033[33m"
#define ANSI_BLUE "\033[34m"
#define ANSI_CYAN "\033[36m"
#define ANSI_WHITE "\033[37m"
#define ANSI_GOTO(row, col) printf("\033[%d;%dH", row, col)

// Test mode state
static bool test_mode_active = false;
static uint32_t last_update_time = 0;
static uint32_t activation_hold_start = 0;
static bool activation_buttons_held = false;

#define ACTIVATION_HOLD_TIME_MS 1000  // Hold L2+R2 for 1 second to enter/exit
#define UPDATE_RATE_MS 50              // Update display at 20Hz

// Trigger threshold for activation (analog triggers)
#define TRIGGER_ACTIVATION_THRESHOLD 500  // Triggers range 0-1023

void test_mode_init(void) {
    test_mode_active = false;
    last_update_time = 0;
    activation_hold_start = 0;
    activation_buttons_held = false;
}

bool test_mode_is_active(void) {
    return test_mode_active;
}

void test_mode_check_activation(test_mode_gamepad_ptr gp_ptr) {
    uni_gamepad_t *gp = (uni_gamepad_t*)gp_ptr;
    uint32_t current_time = to_ms_since_boot(get_absolute_time());

    // Check if both L and R buttons are pressed
    // On Switch controller: L=0x0040, R=0x0080
    bool both_triggers = (gp->buttons & 0x0040) && (gp->buttons & 0x0080);

    if (both_triggers) {
        if (!activation_buttons_held) {
            // Just started holding
            activation_buttons_held = true;
            activation_hold_start = current_time;
        } else if (current_time - activation_hold_start >= ACTIVATION_HOLD_TIME_MS) {
            // Held long enough - toggle test mode
            test_mode_active = !test_mode_active;

            if (test_mode_active) {
                // Entering test mode - clear screen and hide cursor
                printf(ANSI_CLEAR_SCREEN ANSI_HOME ANSI_HIDE_CURSOR);
                printf(ANSI_BOLD ANSI_CYAN "=== CONTROLLER TEST MODE ===" ANSI_NORMAL "\n");
                printf("Hold L+R shoulder buttons for 1 second to exit\n\n");
            } else {
                // Exiting test mode - restore cursor and clear
                printf(ANSI_SHOW_CURSOR ANSI_CLEAR_SCREEN ANSI_HOME);
                printf("Exited test mode - returning to normal operation\n");
            }

            // Reset to prevent immediate re-trigger
            activation_buttons_held = false;
            activation_hold_start = 0;
        }
    } else {
        // Triggers released - reset
        activation_buttons_held = false;
        activation_hold_start = 0;
    }
}

// Helper to draw a progress bar
static void draw_bar(int value, int min, int max, int width) {
    int normalized = ((value - min) * width) / (max - min);
    if (normalized < 0) normalized = 0;
    if (normalized > width) normalized = width;

    printf("[");
    for (int i = 0; i < width; i++) {
        if (i < normalized) {
            printf("=");
        } else {
            printf(" ");
        }
    }
    printf("]");
}

// Helper to show button state with color
static void show_button(const char* name, bool pressed) {
    if (pressed) {
        printf(ANSI_GREEN "[X] %s" ANSI_NORMAL, name);
    } else {
        printf("[ ] %s", name);
    }
}

void test_mode_update(test_mode_gamepad_ptr gp_ptr) {
    uni_gamepad_t *gp = (uni_gamepad_t*)gp_ptr;
    if (!test_mode_active) return;

    uint32_t current_time = to_ms_since_boot(get_absolute_time());

    // Rate limit updates to reduce flicker
    if (current_time - last_update_time < UPDATE_RATE_MS) {
        return;
    }
    last_update_time = current_time;

    // Move cursor to home position (after header)
    ANSI_GOTO(4, 1);

    // === ANALOG STICKS ===
    printf(ANSI_BOLD "Analog Sticks (range -512 to 511):" ANSI_NORMAL "\n");
    printf("  Left Stick:\n");
    printf("    X: %+5d ", gp->axis_x);
    draw_bar(gp->axis_x, -512, 511, 20);
    printf(" [%+4d%%]\n", (gp->axis_x * 100) / 512);
    printf("    Y: %+5d ", gp->axis_y);
    draw_bar(gp->axis_y, -512, 511, 20);
    printf(" [%+4d%%]\n", (gp->axis_y * 100) / 512);

    printf("  Right Stick:\n");
    printf("    X: %+5d ", gp->axis_rx);
    draw_bar(gp->axis_rx, -512, 511, 20);
    printf(" [%+4d%%]\n", (gp->axis_rx * 100) / 512);
    printf("    Y: %+5d ", gp->axis_ry);
    draw_bar(gp->axis_ry, -512, 511, 20);
    printf(" [%+4d%%]\n\n", (gp->axis_ry * 100) / 512);

    // === SHOULDER/TRIGGER BUTTONS ===
    printf(ANSI_BOLD "Shoulder & Trigger Buttons:" ANSI_NORMAL "\n");
    printf("  L (main):  %s     R (main):  %s\n",
           (gp->buttons & 0x0040) ? ANSI_GREEN "PRESSED" ANSI_NORMAL : "-------",
           (gp->buttons & 0x0080) ? ANSI_GREEN "PRESSED" ANSI_NORMAL : "-------");
    printf("  ZL (top):  %s     ZR (top):  %s\n",
           (gp->buttons & 0x0010) ? ANSI_GREEN "PRESSED" ANSI_NORMAL : "-------",
           (gp->buttons & 0x0020) ? ANSI_GREEN "PRESSED" ANSI_NORMAL : "-------");
    printf("  Note: L/R are digital only on Switch controllers\n");
    printf("\n");

    // === BUTTONS ===
    printf(ANSI_BOLD "Face Buttons:" ANSI_NORMAL "\n");
    printf("  ");
    show_button("A", gp->buttons & 0x0001);
    printf("  ");
    show_button("B", gp->buttons & 0x0002);
    printf("  ");
    show_button("X", gp->buttons & 0x0004);
    printf("  ");
    show_button("Y", gp->buttons & 0x0008);
    printf("\n");

    // Check if L3/R3 are actually 0x0100/0x0200 (seems to be the case)
    printf("  ");
    show_button("L3 (stick)", gp->buttons & 0x0100);  // Left stick click
    printf("  ");
    show_button("R3 (stick)", gp->buttons & 0x0200);  // Right stick click
    printf("\n");

    // Minus/Plus buttons - check all possible locations
    printf("  ");
    show_button("Minus (-)", (gp->misc_buttons & 0x02) || (gp->buttons & 0x0400));
    printf("  ");
    show_button("Plus (+)", (gp->misc_buttons & 0x04) || (gp->buttons & 0x0800));
    printf("\n");

    printf("  ");
    show_button("Home", gp->misc_buttons & 0x01);
    printf("  ");
    show_button("Capture", gp->misc_buttons & 0x08);
    printf("\n");

    // Debug line to see actual misc button values
    printf("  (Debug: buttons=0x%04X misc=0x%02X)\n\n", gp->buttons, gp->misc_buttons);

    // === D-PAD ===
    printf(ANSI_BOLD "D-Pad:" ANSI_NORMAL " ");
    // Always show raw value for debugging
    printf("(raw=0x%02X) ", gp->dpad);

    // Switch Pro Controller D-pad mapping (from actual testing)
    switch(gp->dpad) {
        case 0x00: printf("CENTER    "); break;
        case 0x01: printf("UP        "); break;
        case 0x02: printf("DOWN      "); break;
        case 0x04: printf("RIGHT     "); break;
        case 0x05: printf("UP-RIGHT  "); break;
        case 0x06: printf("DOWN-RIGHT"); break;
        case 0x08: printf("LEFT      "); break;
        case 0x09: printf("UP-LEFT   "); break;
        case 0x0A: printf("DOWN-LEFT "); break;
        case 0x0F: printf("CENTER    "); break;  // Alternative neutral
        default:   printf("UNKNOWN   "); break;
    }
    printf("\n\n");

    // === MOTION SENSORS ===
    printf(ANSI_BOLD "Motion Sensors:" ANSI_NORMAL "\n");

    // Based on Nintendo Switch Reverse Engineering documentation:
    // https://github.com/dekuNukem/Nintendo_Switch_Reverse_Engineering/blob/master/imu_sensor_notes.md
    //
    // The Switch Pro Controller uses LSM6DS3 IMU with:
    // - Gyroscope: ±2000 deg/s range, raw * 0.070 = deg/s
    // - Accelerometer: ±8G range, raw * 0.000244 = g
    //
    // Bluepad32 calculation: gyro = mult_frac((1000 * (raw - offset)), scale, divisor)
    // With defaults: offset=0, scale=13371, divisor=13371
    // This simplifies to: gyro = 1000 * raw
    //
    // Therefore to get deg/s: (gyro / 1000) * 0.070 = gyro / 14285.7
    const float GYRO_SCALE = 14285.7f;  // Convert Bluepad32 output to deg/s

    // Gyroscope: convert to degrees/second
    // Cast to float first to avoid integer division
    float gyro_x_dps = (float)gp->gyro[0] / GYRO_SCALE;
    float gyro_y_dps = (float)gp->gyro[1] / GYRO_SCALE;
    float gyro_z_dps = (float)gp->gyro[2] / GYRO_SCALE;

    // Apply bias correction (values when stationary)
    // Based on your stationary readings: [-10000, +3000, -12000]
    // These translate to degrees/second bias
    float gyro_bias_x = -10000.0f / GYRO_SCALE;  // -0.7°/s
    float gyro_bias_y = +3000.0f / GYRO_SCALE;   // +0.2°/s
    float gyro_bias_z = -12000.0f / GYRO_SCALE;  // -0.8°/s

    gyro_x_dps -= gyro_bias_x;
    gyro_y_dps -= gyro_bias_y;
    gyro_z_dps -= gyro_bias_z;

    // Convert to radians/second for SI units
    const float DEG_TO_RAD = 3.14159265f / 180.0f;
    float gyro_x_rads = gyro_x_dps * DEG_TO_RAD;
    float gyro_y_rads = gyro_y_dps * DEG_TO_RAD;
    float gyro_z_rads = gyro_z_dps * DEG_TO_RAD;

    printf("  Gyroscope (bias-corrected):\n");
    printf("    X: %+8.3f rad/s  (%+8.1f°/s)    \n", gyro_x_rads, gyro_x_dps);
    printf("    Y: %+8.3f rad/s  (%+8.1f°/s)    \n", gyro_y_rads, gyro_y_dps);
    printf("    Z: %+8.3f rad/s  (%+8.1f°/s)    \n", gyro_z_rads, gyro_z_dps);

    // Accelerometer: per Nintendo docs, raw * 0.000244 = g
    // But Bluepad32 applies calibration, empirically ~4096 counts = 1g
    const float ACCEL_SCALE = 4096.0f;  // Bluepad32 calibrated counts per g
    const float GRAVITY = 9.80665f;     // m/s² per g

    float accel_x_g = gp->accel[0] / ACCEL_SCALE;
    float accel_y_g = gp->accel[1] / ACCEL_SCALE;
    float accel_z_g = gp->accel[2] / ACCEL_SCALE;

    // Convert to m/s² for SI units
    float accel_x_ms2 = accel_x_g * GRAVITY;
    float accel_y_ms2 = accel_y_g * GRAVITY;
    float accel_z_ms2 = accel_z_g * GRAVITY;

    printf("  Accelerometer:\n");
    printf("    X: %+8.2f m/s²  (%+7.3fg)    \n", accel_x_ms2, accel_x_g);
    printf("    Y: %+8.2f m/s²  (%+7.3fg)    \n", accel_y_ms2, accel_y_g);
    printf("    Z: %+8.2f m/s²  (%+7.3fg)    \n", accel_z_ms2, accel_z_g);

    // Show raw values for debugging
    printf("  Raw values (Bluepad32 output):\n");
    printf("    Gyro:  [%+7d, %+7d, %+7d] (x1000)    \n", gp->gyro[0], gp->gyro[1], gp->gyro[2]);
    printf("    Accel: [%+7d, %+7d, %+7d] counts    \n", gp->accel[0], gp->accel[1], gp->accel[2]);

    // Also show what the actual 16-bit raw values would be
    printf("  Estimated raw sensor values (÷1000):\n");
    printf("    Gyro:  [%+7d, %+7d, %+7d] (16-bit)  \n",
            gp->gyro[0]/1000, gp->gyro[1]/1000, gp->gyro[2]/1000);
    printf("\n");

    // === MISC INFO ===
    printf(ANSI_BOLD "Misc:" ANSI_NORMAL "\n");
    printf("  Raw buttons: 0x%04X   ", gp->buttons);
    printf("Misc buttons: 0x%02X   ", gp->misc_buttons);
    printf("Time: %10lu ms   \n", current_time);

    // Clear remaining lines to prevent artifacts
    printf("\033[J");
}