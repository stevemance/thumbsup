#ifndef AM32_CONFIG_H
#define AM32_CONFIG_H

#include <stdint.h>
#include <stdbool.h>

// AM32 Serial Protocol Constants
#define AM32_BAUD_RATE          19200
#define AM32_BAUDRATE_CMD       115200  // For bootloader mode
#define AM32_SIGNAL_PIN         PIN_WEAPON_PWM
#define AM32_REPLY_TIMEOUT      100     // ms

// AM32 Protocol Commands
#define AM32_CMD_KEEPALIVE      0xFF
#define AM32_CMD_SET_SETTINGS   0xAA
#define AM32_CMD_GET_SETTINGS   0xBB
#define AM32_CMD_GET_INFO       0xCC
#define AM32_CMD_RESET          0xDD
#define AM32_CMD_BOOTLOADER     0xEE

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

#endif // AM32_CONFIG_H