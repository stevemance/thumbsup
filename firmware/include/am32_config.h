#ifndef AM32_CONFIG_H
#define AM32_CONFIG_H

#include <stdint.h>
#include <stdbool.h>

// AM32 Serial Protocol Constants
#define AM32_BAUD_RATE          19200
#define AM32_BAUDRATE_CMD       115200  // For bootloader mode
#define AM32_SIGNAL_PIN         PIN_WEAPON_PWM
// MAJOR FIX #6: Reply timeout may need adjustment based on hardware testing
// 100ms should be sufficient for most operations, but slow ESCs or operations
// like EEPROM read/write may require longer timeouts. Monitor actual response
// times during hardware testing and increase if timeouts occur frequently.
#define AM32_REPLY_TIMEOUT      100     // ms (may need increase for slow operations)

// AM32 Protocol Commands
#define AM32_CMD_KEEPALIVE      0xFF
#define AM32_CMD_SET_SETTINGS   0xAA
#define AM32_CMD_GET_SETTINGS   0xBB
#define AM32_CMD_GET_INFO       0xCC
#define AM32_CMD_RESET          0xDD
#define AM32_CMD_BOOTLOADER     0xEE
#define AM32_CMD_GET_TELEMETRY  0x0A
#define AM32_CMD_SET_LED        0x4C  // 'L'
#define AM32_CMD_BEEP           0x42  // 'B'
#define AM32_CMD_GET_STATUS     0x53  // 'S'

// MSP Protocol Commands
#define MSP_API_VERSION         1
#define MSP_FC_VARIANT          2
#define MSP_FC_VERSION          3
#define MSP_BOARD_INFO          4
#define MSP_BUILD_INFO          5
#define MSP_NAME                10
#define MSP_SET_NAME            11
#define MSP_MOTOR               104
#define MSP_SET_MOTOR           214
#define MSP_ESC_SENSOR_DATA     139

// AM32 EEPROM Addresses (simplified subset)
typedef enum {
    AM32_ADDR_VERSION           = 0x00,
    AM32_ADDR_MOTOR_DIRECTION   = 0x01,
    AM32_ADDR_BIDIRECTIONAL     = 0x02,
    AM32_ADDR_BRAKE_ON_STOP     = 0x03,
    AM32_ADDR_STARTUP_POWER     = 0x04,
    AM32_ADDR_MOTOR_TIMING      = 0x05,
    AM32_ADDR_PWM_FREQUENCY     = 0x06,
    AM32_ADDR_DEMAG_COMP        = 0x07,
    AM32_ADDR_TEMP_LIMIT        = 0x08,
    AM32_ADDR_CURRENT_LIMIT     = 0x09,
    AM32_ADDR_THROTTLE_MIN      = 0x0A,
    AM32_ADDR_THROTTLE_MAX      = 0x0C,
    AM32_ADDR_THROTTLE_CAL      = 0x0E,
    AM32_ADDR_MOTOR_KV          = 0x10,
    AM32_ADDR_MOTOR_POLES       = 0x12,
    AM32_ADDR_TELEMETRY         = 0x14,
    AM32_ADDR_SERVO_CENTER      = 0x15,
    AM32_ADDR_DEADBAND          = 0x17,
    AM32_ADDR_LOW_VOLTAGE_CUTOFF = 0x18,
    AM32_ADDR_SINE_MODE         = 0x19,
    AM32_ADDR_SETTINGS_CHECKSUM = 0xFF
} am32_address_t;

// AM32 Configuration Structure
typedef struct {
    // Basic settings
    uint8_t motor_direction;     // 0=forward, 1=reverse
    uint8_t bidirectional;        // 0=unidirectional, 1=bidirectional
    uint8_t brake_on_stop;        // 0=off, 1=on

    // Motor settings
    uint8_t startup_power;        // 1-10 (low to high)
    uint8_t motor_timing;         // 0-30 degrees
    uint16_t motor_kv;            // Motor KV rating
    uint8_t motor_poles;          // Number of motor poles

    // PWM settings
    uint8_t pwm_frequency;        // 24, 48, 96 kHz
    uint16_t throttle_min;        // Minimum pulse width (us)
    uint16_t throttle_max;        // Maximum pulse width (us)

    // Protection settings
    uint8_t temperature_limit;    // Celsius
    uint8_t current_limit;        // Amps
    uint8_t low_voltage_cutoff;   // 0=disabled, 1=enabled
    uint8_t demag_compensation;   // 0=off, 1=low, 2=high

    // Advanced settings
    uint8_t sine_mode;            // 0=trapezoidal, 1=sinusoidal
    uint8_t telemetry;            // 0=off, 1=on
    uint16_t servo_center;        // Center pulse width for bidirectional
    uint8_t deadband;             // Deadband width in us
} am32_config_t;

// AM32 Info Structure
typedef struct {
    uint8_t firmware_version[3];  // Major, minor, patch
    char firmware_name[16];
    uint8_t mcu_type;
    uint16_t flash_size;
    bool bootloader_version;
} am32_info_t;

// AM32 Live Telemetry Structure
typedef struct {
    uint16_t rpm;                 // Actual motor RPM
    uint16_t voltage_mv;          // Voltage in millivolts
    uint16_t current_ma;          // Current in milliamps
    uint8_t temperature_c;        // Temperature in Celsius
    uint8_t consumption_mah;      // Consumed mAh
    uint16_t erpm;                // Electrical RPM
    bool valid;                   // Data is valid
    uint32_t timestamp_ms;        // When telemetry was read
} am32_telemetry_t;

// AM32 ESC Status
typedef struct {
    bool armed;                   // ESC is armed
    bool motor_running;           // Motor is running
    bool signal_detected;         // Input signal detected
    bool temperature_warning;     // Over temperature
    bool current_warning;         // Over current
    uint8_t error_code;           // Last error code
    uint32_t uptime_ms;           // ESC uptime
} am32_status_t;

// Function prototypes
bool am32_init(void);
bool am32_enter_config_mode(void);
bool am32_exit_config_mode(void);
bool am32_read_settings(am32_config_t* config);
bool am32_write_settings(const am32_config_t* config);
bool am32_get_info(am32_info_t* info);
bool am32_calibrate_throttle(void);
bool am32_save_settings(void);
bool am32_reset_to_defaults(void);
bool am32_enter_bootloader(void);

// Utility functions
bool am32_send_command(uint8_t cmd, const uint8_t* data, uint16_t len);
bool am32_receive_response(uint8_t* buffer, uint16_t* len, uint32_t timeout_ms);
uint8_t am32_calculate_checksum(const uint8_t* data, uint16_t len);
void am32_apply_weapon_defaults(am32_config_t* config);

// Serial passthrough for external configurator
bool am32_passthrough_mode(void);
void am32_passthrough_exit(void);

// Live telemetry and monitoring
bool am32_read_telemetry(am32_telemetry_t* telemetry);
bool am32_get_status(am32_status_t* status);

// Motor control and testing
bool am32_set_motor_speed(uint16_t speed_percent);
bool am32_beep(uint8_t beep_pattern);
bool am32_set_led(uint8_t led_state);

// MSP protocol support
bool am32_msp_send(uint8_t cmd, const uint8_t* payload, uint16_t len);
// CRITICAL FIX #3 (Iteration 4): Add buffer_size parameter to prevent overflow
bool am32_msp_receive(uint8_t* cmd, uint8_t* payload, uint16_t buffer_size, uint16_t* len);

// Firmware update (bootloader mode)
bool am32_flash_firmware(const uint8_t* firmware_data, uint32_t size);
bool am32_verify_firmware(void);

/**
 * AM32 ESC Serial Protocol Implementation
 *
 * Protocol reference:
 * https://github.com/AlkaMotors/AM32-MultiRotor-ESC-firmware
 *
 * Hardware: RP2040 UART1 on GP4 (TX) and GP5 (RX)
 * Baud rates: 19200 (config), 115200 (bootloader)
 * Format: 8N1, XOR checksum
 */

#endif // AM32_CONFIG_H