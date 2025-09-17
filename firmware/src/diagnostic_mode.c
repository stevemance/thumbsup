#include "diagnostic_mode.h"
#include "config.h"
#include "motor_control.h"
#include "drive.h"
#include "weapon.h"
#include "safety.h"
#include "status.h"

#include <stdio.h>
#include <string.h>
#include <stdarg.h>
#include <pico/stdlib.h>
#include <pico/cyw43_arch.h>
#include <hardware/adc.h>
#include <hardware/gpio.h>
#include <hardware/watchdog.h>
#include <lwip/tcp.h>

// Global telemetry data
static telemetry_data_t g_telemetry = {0};
static bool diagnostic_mode_active = false;

// External functions
extern uint32_t read_battery_voltage(void);
extern bool bluetooth_platform_failsafe_active(void);
extern bool bluetooth_platform_is_armed(void);

// HTML page embedded as string (we'll generate this)
static const char* html_page = NULL;

// Initialize diagnostic mode
bool diagnostic_mode_init(void) {
    printf("\n=================================\n");
    printf("  DIAGNOSTIC MODE STARTING\n");
    printf("=================================\n\n");

    // Initialize CYW43 with WiFi support
    if (cyw43_arch_init()) {
        printf("Failed to initialize CYW43\n");
        return false;
    }

    // Enable WiFi AP mode
    cyw43_arch_enable_ap_mode(WIFI_SSID, WIFI_PASSWORD, WIFI_AUTH);

    printf("WiFi Access Point started\n");
    printf("SSID: %s\n", WIFI_SSID);
    printf("Password: %s\n", WIFI_PASSWORD);
    printf("IP: 192.168.4.1\n\n");

    // Initialize web server
    if (!web_server_init()) {
        printf("Failed to start web server\n");
        return false;
    }

    // Initialize telemetry
    memset(&g_telemetry, 0, sizeof(g_telemetry));
    telemetry_log_event("Diagnostic mode initialized");

    diagnostic_mode_active = true;

    // Turn on WiFi LED indicator
    cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, 1);

    return true;
}

// Main diagnostic mode loop
void diagnostic_mode_run(void) {
    uint32_t last_telemetry_update = 0;
    uint32_t last_web_update = 0;
    uint32_t start_time = to_ms_since_boot(get_absolute_time());

    // Initialize hardware
    motor_control_init();
    drive_init();
    weapon_init();
    status_init();

    telemetry_log_event("Systems initialized");

    printf("Diagnostic mode running...\n");
    printf("Connect to WiFi AP and navigate to http://192.168.4.1\n\n");

    while (diagnostic_mode_active) {
        uint32_t current_time = to_ms_since_boot(get_absolute_time());
        uint32_t loop_start = time_us_32();

        // Update telemetry
        if (current_time - last_telemetry_update >= TELEMETRY_UPDATE_MS) {
            telemetry_update(&g_telemetry);
            last_telemetry_update = current_time;
        }

        // Update web server
        if (current_time - last_web_update >= WEB_UPDATE_MS) {
            web_server_update();
            last_web_update = current_time;
        }

        // Process any web control commands
        // Note: web_get_control is defined in web_server.c

        // Update motor outputs
        motor_control_update();
        weapon_update();

        // Update status LEDs
        status_update();

        // Calculate loop time
        g_telemetry.loop_time_us = time_us_32() - loop_start;
        g_telemetry.uptime_ms = current_time - start_time;

        // Small delay
        sleep_ms(5);

        // Check for exit condition (hold safety button for 5 seconds)
        static uint32_t exit_hold_start = 0;
        if (safety_is_button_pressed()) {
            if (exit_hold_start == 0) {
                exit_hold_start = current_time;
                telemetry_log_event("Hold safety button %ds to exit diagnostic mode", DIAGNOSTIC_EXIT_HOLD_TIME / 1000);
            } else if (current_time - exit_hold_start > DIAGNOSTIC_EXIT_HOLD_TIME) {
                diagnostic_mode_active = false;
                telemetry_log_event("Exiting diagnostic mode");
            }
        } else {
            exit_hold_start = 0;
        }
    }

    diagnostic_mode_shutdown();
}

// Shutdown diagnostic mode
void diagnostic_mode_shutdown(void) {
    printf("Shutting down diagnostic mode...\n");

    // Stop all motors for safety
    motor_control_emergency_stop();
    weapon_emergency_stop();

    // Shutdown web server
    web_server_shutdown();

    // Disable WiFi
    cyw43_arch_disable_ap_mode();
    cyw43_arch_deinit();

    // Turn off WiFi LED
    cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, 0);

    printf("Diagnostic mode stopped. Rebooting...\n");

    // Reboot to return to normal mode
    watchdog_reboot(0, 0, 100);
}

// Update telemetry data
void telemetry_update(telemetry_data_t* data) {
    // System status
    data->armed = weapon_get_state() == WEAPON_STATE_ARMED;
    data->emergency_stopped = weapon_get_state() == WEAPON_STATE_EMERGENCY_STOP;
    data->safety_button = safety_is_button_pressed();

    // Battery
    data->battery_voltage_mv = read_battery_voltage();
    data->battery_percentage = ((float)(data->battery_voltage_mv - 10000) / 2600.0f) * 100.0f;
    if (data->battery_percentage < 0) data->battery_percentage = 0;
    if (data->battery_percentage > 100) data->battery_percentage = 100;

    // Motors (get from actual motor states)
    // These would need getter functions added to motor_control.c
    data->left_drive_speed = 0;  // TODO: Add motor_control_get_speed(MOTOR_LEFT_DRIVE)
    data->right_drive_speed = 0; // TODO: Add motor_control_get_speed(MOTOR_RIGHT_DRIVE)
    data->weapon_speed = 0;       // TODO: Add weapon_get_speed()

    // Memory usage (approximate)
    extern char __StackLimit, __StackTop;
    uint32_t stack_size = &__StackTop - &__StackLimit;
    data->free_memory_bytes = stack_size;  // Rough estimate

    // CPU usage (rough calculation based on loop time)
    if (data->loop_time_us > 0) {
        data->cpu_usage_percent = (data->loop_time_us * 100) / (TELEMETRY_UPDATE_MS * 1000);
        if (data->cpu_usage_percent > 100) data->cpu_usage_percent = 100;
    }

    // Temperature (would need external sensor)
    data->temperature_c = 25.0f;  // Placeholder
}

// Log an event to the telemetry system
void telemetry_log_event(const char* format, ...) {
    va_list args;
    va_start(args, format);

    // Format the message
    char buffer[EVENT_MSG_LEN];
    vsnprintf(buffer, EVENT_MSG_LEN, format, args);

    // Add timestamp
    uint32_t timestamp = to_ms_since_boot(get_absolute_time());
    char timestamped[EVENT_MSG_LEN];
    snprintf(timestamped, EVENT_MSG_LEN, "[%u.%03u] %s",
             timestamp / 1000, timestamp % 1000, buffer);

    // Add to circular buffer
    strcpy(g_telemetry.event_log[g_telemetry.event_log_head], timestamped);
    g_telemetry.event_log_head = (g_telemetry.event_log_head + 1) % EVENT_LOG_SIZE;

    if (g_telemetry.event_log_count < EVENT_LOG_SIZE) {
        g_telemetry.event_log_count++;
    }

    // Also print to serial
    printf("%s\n", timestamped);

    va_end(args);
}

// Get telemetry data pointer
telemetry_data_t* telemetry_get_data(void) {
    return &g_telemetry;
}

// Process control commands from web interface
void process_web_control(web_control_t* control) {
    if (control->emergency_stop) {
        telemetry_log_event("Web: Emergency stop triggered");
        motor_control_emergency_stop();
        weapon_emergency_stop();
    }

    if (control->clear_emergency_stop) {
        telemetry_log_event("Web: Emergency stop cleared");
        // Re-initialize systems
        motor_control_init();
        weapon_init();
    }

    if (control->arm_weapon) {
        telemetry_log_event("Web: Weapon armed");
        weapon_arm();
    }

    if (control->disarm_weapon) {
        telemetry_log_event("Web: Weapon disarmed");
        weapon_disarm();
    }

    // Drive control
    if (control->drive_forward != 0 || control->drive_turn != 0) {
        drive_control_t drive_cmd = {
            .forward = control->drive_forward,
            .turn = control->drive_turn,
            .enabled = true
        };
        drive_update(&drive_cmd);
    }

    // Weapon speed
    if (g_telemetry.armed && control->weapon_speed > 0) {
        weapon_set_speed(control->weapon_speed);
    }

    if (control->run_safety_tests) {
        telemetry_log_event("Web: Running safety tests");
        extern bool run_safety_tests(void);
        bool passed = run_safety_tests();
        telemetry_log_event("Web: Safety tests %s", passed ? "PASSED" : "FAILED");
        g_telemetry.safety_tests_passed = passed;
    }

    if (control->reboot_system) {
        telemetry_log_event("Web: System reboot requested");
        diagnostic_mode_shutdown();
    }
}

// Check if we should enter diagnostic mode
bool should_enter_diagnostic_mode(void) {
    // Enter diagnostic mode if safety button is held during boot
    // But use a different duration than config mode (3 seconds)

    printf("Hold safety button for 3 seconds to enter diagnostic mode...\n");

    uint32_t start_time = to_ms_since_boot(get_absolute_time());
    uint32_t hold_duration = 0;

    while (hold_duration < 3000) {
        if (!safety_is_button_pressed()) {
            // Button released, continue normal boot
            return false;
        }

        hold_duration = to_ms_since_boot(get_absolute_time()) - start_time;

        // Show progress
        if (hold_duration % 500 == 0) {
            printf("Entering diagnostic mode in %d...\n", (3000 - hold_duration) / 1000);
        }

        sleep_ms(10);
    }

    // Button held for 3 seconds, enter diagnostic mode
    printf("Entering diagnostic mode!\n");
    return true;
}