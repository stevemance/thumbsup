#ifndef DSHOT_H
#define DSHOT_H

#include <stdint.h>
#include <stdbool.h>
#include "motor_control.h"

/**
 * DShot Protocol Implementation
 *
 * DShot is a digital ESC protocol that provides:
 * - More reliable communication than PWM
 * - Bidirectional telemetry (EDT - Extended DShot Telemetry)
 * - RPM, voltage, current, temperature feedback
 * - Faster update rates (up to 8kHz)
 *
 * DShot Frame Structure:
 * - 11 bits throttle value (0-2047)
 * - 1 bit telemetry request
 * - 4 bits CRC
 * Total: 16 bits per frame
 *
 * DShot Speeds:
 * - DShot150: 150kbit/s (6.67μs per bit)
 * - DShot300: 300kbit/s (3.33μs per bit)  ← Recommended for RP2040
 * - DShot600: 600kbit/s (1.67μs per bit)
 * - DShot1200: 1200kbit/s (0.83μs per bit)
 */

// DShot speed configuration
typedef enum {
    DSHOT_SPEED_150  = 150,   // 150kbit/s - most reliable
    DSHOT_SPEED_300  = 300,   // 300kbit/s - recommended
    DSHOT_SPEED_600  = 600,   // 600kbit/s - high performance
    DSHOT_SPEED_1200 = 1200   // 1200kbit/s - maximum speed
} dshot_speed_t;

// DShot special commands (throttle = 0, command in bits)
typedef enum {
    DSHOT_CMD_MOTOR_STOP        = 0,     // Stop motor
    DSHOT_CMD_BEEP1             = 1,     // Beep pattern 1
    DSHOT_CMD_BEEP2             = 2,     // Beep pattern 2
    DSHOT_CMD_BEEP3             = 3,     // Beep pattern 3
    DSHOT_CMD_BEEP4             = 4,     // Beep pattern 4
    DSHOT_CMD_BEEP5             = 5,     // Beep pattern 5
    DSHOT_CMD_ESC_INFO          = 6,     // Request ESC info
    DSHOT_CMD_SPIN_DIRECTION_1  = 7,     // Rotate direction 1
    DSHOT_CMD_SPIN_DIRECTION_2  = 8,     // Rotate direction 2
    DSHOT_CMD_3D_MODE_OFF       = 9,     // Disable 3D mode
    DSHOT_CMD_3D_MODE_ON        = 10,    // Enable 3D mode
    DSHOT_CMD_SETTINGS_REQUEST  = 11,    // Request settings
    DSHOT_CMD_SAVE_SETTINGS     = 12,    // Save settings to EEPROM
    DSHOT_CMD_SPIN_DIRECTION_NORMAL   = 20,  // Normal rotation
    DSHOT_CMD_SPIN_DIRECTION_REVERSED = 21,  // Reversed rotation
    DSHOT_CMD_LED0_ON           = 22,    // LED 0 on
    DSHOT_CMD_LED1_ON           = 23,    // LED 1 on
    DSHOT_CMD_LED2_ON           = 24,    // LED 2 on
    DSHOT_CMD_LED3_ON           = 25,    // LED 3 on
    DSHOT_CMD_LED0_OFF          = 26,    // LED 0 off
    DSHOT_CMD_LED1_OFF          = 27,    // LED 1 off
    DSHOT_CMD_LED2_OFF          = 28,    // LED 2 off
    DSHOT_CMD_LED3_OFF          = 29,    // LED 3 off
    DSHOT_CMD_AUDIO_STREAM      = 30,    // Audio stream mode
    DSHOT_CMD_SILENT_MODE       = 31,    // Silent mode
} dshot_command_t;

// EDT (Extended DShot Telemetry) frame structure
typedef struct {
    uint16_t erpm;              // Electrical RPM (mechanical RPM × pole pairs)
    uint16_t voltage_cV;        // Voltage in centi-volts (12.6V = 1260)
    uint16_t current_cA;        // Current in centi-amps (10.5A = 1050)
    uint8_t temperature_C;      // Temperature in Celsius
    uint8_t crc;                // CRC checksum
    bool valid;                 // True if telemetry is valid
    uint32_t timestamp_ms;      // When telemetry was received
} dshot_telemetry_t;

// DShot configuration
typedef struct {
    uint8_t gpio_pin;           // GPIO pin for DShot output
    dshot_speed_t speed;        // DShot speed (150/300/600/1200)
    bool bidirectional;         // Enable EDT telemetry
    uint8_t pole_pairs;         // Motor pole pairs (for RPM calculation)
} dshot_config_t;

/**
 * Initialize DShot for a motor channel
 *
 * @param motor Motor channel
 * @param config DShot configuration
 * @return true on success
 */
bool dshot_init(motor_channel_t motor, const dshot_config_t* config);

/**
 * Send DShot throttle command
 *
 * @param motor Motor channel
 * @param throttle Throttle value (0-2047, or 48-2047 for safety)
 * @param request_telemetry Request telemetry response
 * @return true on success
 */
bool dshot_send_throttle(motor_channel_t motor, uint16_t throttle, bool request_telemetry);

/**
 * Send DShot special command
 *
 * Must be sent 6+ times with 1ms delay to take effect
 *
 * @param motor Motor channel
 * @param cmd Special command
 * @return true on success
 */
bool dshot_send_command(motor_channel_t motor, dshot_command_t cmd);

/**
 * Read telemetry data (if bidirectional EDT enabled)
 *
 * @param motor Motor channel
 * @param telemetry Output telemetry data
 * @return true if new telemetry available
 */
bool dshot_read_telemetry(motor_channel_t motor, dshot_telemetry_t* telemetry);

/**
 * Convert electrical RPM to mechanical RPM
 *
 * @param erpm Electrical RPM from telemetry
 * @param pole_pairs Number of motor pole pairs (poles / 2)
 * @return Mechanical RPM
 */
uint16_t dshot_erpm_to_rpm(uint16_t erpm, uint8_t pole_pairs);

/**
 * Get latest telemetry for motor
 *
 * @param motor Motor channel
 * @param telemetry Output telemetry data
 * @return true if telemetry available
 */
bool dshot_get_telemetry(motor_channel_t motor, dshot_telemetry_t* telemetry);

/**
 * Calculate DShot CRC4
 *
 * @param packet 12-bit packet data
 * @return 4-bit CRC
 */
uint8_t dshot_calculate_crc(uint16_t packet);

/**
 * Convert throttle percentage to DShot value
 *
 * @param percent Throttle percentage (-100 to +100)
 * @return DShot throttle value (48-2047, 0 = disarmed)
 */
uint16_t dshot_throttle_from_percent(int8_t percent);

/**
 * Deinitialize DShot and free resources
 *
 * Stops the state machine, removes PIO program, and releases DMA channel.
 * Call this before switching back to PWM mode or when shutting down.
 *
 * @param motor Motor channel to deinitialize
 */
void dshot_deinit(motor_channel_t motor);

#endif // DSHOT_H
