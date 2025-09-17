#ifndef DIAGNOSTIC_MODE_H
#define DIAGNOSTIC_MODE_H

#include <stdbool.h>
#include <stdint.h>

// WiFi Configuration
#define WIFI_SSID "ThumbsUp_Diag"
#define WIFI_PASSWORD "combat123"  // Change for security
#define WIFI_AUTH CYW43_AUTH_WPA2_AES_PSK
#define HTTP_PORT 80

// Telemetry update rate
#define TELEMETRY_UPDATE_MS 100
#define WEB_UPDATE_MS 250

// Maximum connections
#define MAX_WEB_CLIENTS 4

// Telemetry data structure
typedef struct {
    // System status
    uint32_t uptime_ms;
    bool armed;
    bool emergency_stopped;
    bool safety_button;

    // Battery
    uint32_t battery_voltage_mv;
    float battery_percentage;

    // Motors
    int8_t left_drive_speed;
    int8_t right_drive_speed;
    uint8_t weapon_speed;

    // Safety tests (from startup)
    bool safety_tests_passed;
    uint8_t safety_test_results;  // Bitmask of test results

    // Controller inputs (for testing)
    int8_t input_forward;
    int8_t input_turn;
    int8_t input_weapon;

    // Performance metrics
    uint32_t loop_time_us;
    uint32_t cpu_usage_percent;
    uint32_t free_memory_bytes;

    // Temperature (if sensor added)
    float temperature_c;

    // Event log (circular buffer)
    #define EVENT_LOG_SIZE 20
    #define EVENT_MSG_LEN 64
    char event_log[EVENT_LOG_SIZE][EVENT_MSG_LEN];
    uint8_t event_log_head;
    uint8_t event_log_count;

    // Statistics
    uint32_t total_runtime_seconds;
    uint32_t total_armed_time_seconds;
    uint32_t emergency_stop_count;
    uint32_t failsafe_trigger_count;
} telemetry_data_t;

// Control commands from web interface
typedef struct {
    bool arm_weapon;
    bool disarm_weapon;
    bool emergency_stop;
    bool clear_emergency_stop;
    int8_t drive_forward;
    int8_t drive_turn;
    uint8_t weapon_speed;
    bool reboot_system;
    bool run_safety_tests;
} web_control_t;

// Function declarations
bool diagnostic_mode_init(void);
void diagnostic_mode_run(void);
void diagnostic_mode_shutdown(void);

// Telemetry functions
void telemetry_update(telemetry_data_t* data);
void telemetry_log_event(const char* format, ...);
telemetry_data_t* telemetry_get_data(void);

// Web server functions
bool web_server_init(void);
void web_server_update(void);
void web_server_shutdown(void);
bool web_get_control(web_control_t* control);
void process_web_control(web_control_t* control);

// Mode selection
bool should_enter_diagnostic_mode(void);

#endif // DIAGNOSTIC_MODE_H