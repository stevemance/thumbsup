/**
 * AM32 ESC Serial Configuration Protocol Implementation
 *
 * CRITICAL FIX #5: Comprehensive protocol documentation
 * CRITICAL FIX #3 (Iteration 2): Hardware requirements documentation
 *
 * ============================================================================
 * HARDWARE REQUIREMENTS - READ THIS BEFORE USING AM32 CONFIG MODE
 * ============================================================================
 *
 * AM32 configuration mode requires BIDIRECTIONAL UART communication.
 * This means you MUST have both TX and RX lines connected:
 *
 *   GP4 (UART1 TX) ---> ESC signal wire (data TO ESC)
 *   GP5 (UART1 RX) <--- ESC signal wire (data FROM ESC)
 *
 * IMPORTANT WIRING NOTES:
 * 1. Standard ESC wiring uses ONE signal wire - this is NOT sufficient!
 * 2. For AM32 config to work, you need SEPARATE TX and RX connections
 * 3. Options for wiring:
 *    a) Use ESC with dedicated TX/RX pads (bench testing setup)
 *    b) Use special bidirectional adapter cable
 *    c) Wire ESC signal pad to GP4, find ESC's MCU UART RX pad and wire to GP5
 *
 * WARNING: If only GP4 is connected, AM32 config mode will FAIL silently!
 * The code will send commands but never receive responses.
 *
 * PRODUCTION USE:
 * For production robots, it's recommended to configure the ESC once on the bench
 * with proper TX/RX wiring, then use standard PWM or DShot control in operation.
 * AM32 config mode is primarily for initial setup and testing.
 *
 * ============================================================================
 * PROTOCOL OVERVIEW:
 * ============================================================================
 *
 * The AM32 ESC uses a serial UART protocol for configuration and monitoring.
 * Communication occurs at 19200 baud (8N1) for normal operation, and 115200
 * baud for bootloader mode.
 *
 * COMMAND PACKET FORMAT:
 * All commands follow this structure:
 *   [CMD] [LEN_L] [LEN_H] [DATA...] [CHECKSUM]
 *
 * Where:
 *   CMD       = 1 byte command identifier (see AM32_CMD_* defines)
 *   LEN_L     = Low byte of data length (little-endian 16-bit)
 *   LEN_H     = High byte of data length
 *   DATA      = Variable length payload (0-65535 bytes)
 *   CHECKSUM  = XOR of all preceding bytes: CMD ^ LEN_L ^ LEN_H ^ DATA[0] ^ ... ^ DATA[n-1]
 *
 * RESPONSE PACKET FORMAT:
 * Responses from the ESC follow this structure:
 *   [LEN_L] [LEN_H] [DATA...]
 *
 * Where:
 *   LEN_L     = Low byte of response length
 *   LEN_H     = High byte of response length
 *   DATA      = Response payload
 *
 * Note: Responses do NOT include a checksum byte
 *
 * CHECKSUM CALCULATION:
 * Standard AM32/MSP checksum is a simple XOR of all packet bytes:
 *   checksum = 0
 *   checksum ^= CMD
 *   checksum ^= LEN_L
 *   checksum ^= LEN_H
 *   for each byte in DATA:
 *       checksum ^= byte
 *
 * TIMING REQUIREMENTS:
 * - Config entry: 10 pulses of 100us high, 900us low on PWM line
 * - EEPROM write: 500ms delay required after save command
 * - Reply timeout: 100ms maximum wait for ESC response
 * - Mode switch: 100ms delay after entering/exiting config mode
 *
 * HARDWARE TESTING REQUIREMENTS (CRITICAL #7):
 * Before production use, the following MUST be validated on actual hardware:
 * 1. Verify ESC enters config mode reliably with pulse pattern
 * 2. Confirm 19200 baud communication works at operating voltage range (6-25V)
 * 3. Test EEPROM write persistence across power cycles
 * 4. Validate telemetry data accuracy (voltage, current, temperature, RPM)
 * 5. Confirm bootloader mode entry and firmware flash procedure
 * 6. Test all protection limits (temp, current, voltage cutoff)
 * 7. Verify bidirectional operation if using DShot mode
 * 8. Test passthrough mode with external configurator software
 * 9. Validate MSP protocol compatibility if using MSP commands
 * 10. Confirm watchdog handling during long operations
 *
 * REFERENCE:
 * https://github.com/AlkaMotors/AM32-MultiRotor-ESC-firmware
 */

#include "am32_config.h"
#include "config.h"
#include "motor_control.h"
#include "pico/stdlib.h"
#include "hardware/uart.h"
#include "hardware/gpio.h"
#include "hardware/pwm.h"
#include "hardware/watchdog.h"
#include "hardware/structs/watchdog.h"
#include <stdio.h>
#include <string.h>

// UART instance for AM32 communication
#define AM32_UART uart1
#define AM32_TX_PIN 4   // GP4 - UART1 TX (dedicated AM32 serial)
#define AM32_RX_PIN 5   // GP5 - UART1 RX (for bidirectional communication)

// AM32 config entry signal timing (in microseconds)
#define AM32_CONFIG_ENTRY_PULSE_US   100   // High pulse width
#define AM32_CONFIG_ENTRY_GAP_US     900   // Low gap between pulses
#define AM32_CONFIG_ENTRY_PULSES     10    // Number of pulses to send
#define AM32_CONFIG_ENTRY_TIMEOUT_MS 100   // Wait time after signal

// AM32 calibration timing
#define AM32_CALIBRATION_MAX_DELAY_MS  3000  // Max throttle hold time
#define AM32_CALIBRATION_STEP_DELAY_MS 500   // Step delay

// AM32 general timeouts
#define AM32_MODE_SWITCH_DELAY_MS 100   // Delay after mode switch
// MAJOR FIX #2: EEPROM write requires 200-500ms for reliable persistence
#define AM32_SAVE_DELAY_MS        500   // EEPROM write delay (minimum 200ms, using 500ms for safety)

// MINOR FIX: Named constants for response size validation
#define AM32_MIN_SETTINGS_SIZE    32    // Minimum expected settings response size
#define AM32_MIN_INFO_SIZE        16    // Minimum expected info response size
#define AM32_MIN_TELEMETRY_SIZE   12    // Minimum expected telemetry response size
#define AM32_MIN_STATUS_SIZE      8     // Minimum expected status response size

static bool am32_configured = false;
static bool am32_in_config_mode = false;
static am32_config_t current_config;

// Convert to UART mode for AM32 communication
static bool switch_to_uart_mode(void) {
    // Configure pins for UART (GP4=TX, GP5=RX)
    gpio_set_function(AM32_TX_PIN, GPIO_FUNC_UART);
    gpio_set_function(AM32_RX_PIN, GPIO_FUNC_UART);

    // Initialize UART
    uart_init(AM32_UART, AM32_BAUD_RATE);
    uart_set_format(AM32_UART, 8, 1, UART_PARITY_NONE);
    uart_set_fifo_enabled(AM32_UART, true);

    return true;
}

// Disable UART mode
static bool switch_to_pwm_mode(void) {
    // De-init UART
    uart_deinit(AM32_UART);

    // Set pins back to SIO (safe state)
    gpio_set_function(AM32_TX_PIN, GPIO_FUNC_SIO);
    gpio_set_function(AM32_RX_PIN, GPIO_FUNC_SIO);
    gpio_set_dir(AM32_TX_PIN, GPIO_IN);
    gpio_set_dir(AM32_RX_PIN, GPIO_IN);

    return true;
}

// Send special signal pattern to enter config mode
static bool send_config_entry_signal(void) {
    // AM32 expects specific pulse pattern to enter config mode
    // Typically: series of short pulses outside normal PWM range
    // This is sent on the weapon PWM signal line, NOT the UART pins

    // Configure weapon pin as GPIO temporarily
    gpio_set_function(PIN_WEAPON_PWM, GPIO_FUNC_SIO);
    gpio_set_dir(PIN_WEAPON_PWM, GPIO_OUT);

    // Send config entry pulse sequence
    for (int i = 0; i < AM32_CONFIG_ENTRY_PULSES; i++) {
        gpio_put(PIN_WEAPON_PWM, 1);
        sleep_us(AM32_CONFIG_ENTRY_PULSE_US);
        gpio_put(PIN_WEAPON_PWM, 0);
        sleep_us(AM32_CONFIG_ENTRY_GAP_US);
    }

    // Wait for ESC to enter config mode
    sleep_ms(AM32_CONFIG_ENTRY_TIMEOUT_MS);

    return true;
}

bool am32_init(void) {
    if (am32_configured) {
        return true;
    }

    // Initialize with default weapon configuration
    am32_apply_weapon_defaults(&current_config);

    am32_configured = true;
    DEBUG_PRINT("AM32 configuration module initialized\n");

    return true;
}

bool am32_enter_config_mode(void) {
    if (am32_in_config_mode) {
        return true;
    }

    DEBUG_PRINT("Entering AM32 config mode...\n");

    // Stop motor control
    motor_control_set_pulse(MOTOR_WEAPON, PWM_MIN_PULSE);
    sleep_ms(AM32_MODE_SWITCH_DELAY_MS);

    // Send special signal to enter config mode
    send_config_entry_signal();

    // Switch pin to UART mode
    if (!switch_to_uart_mode()) {
        DEBUG_PRINT("Failed to switch to UART mode\n");
        return false;
    }

    // Send keepalive to verify connection
    uint8_t keepalive = AM32_CMD_KEEPALIVE;
    if (!am32_send_command(keepalive, NULL, 0)) {
        DEBUG_PRINT("Failed to establish AM32 connection\n");
        switch_to_pwm_mode();
        return false;
    }

    // CRITICAL FIX #3 (Iteration 2): Verify bidirectional communication works
    // Try to receive a response to confirm RX line is functional
    uint8_t response[4];
    uint16_t resp_len = sizeof(response);
    if (!am32_receive_response(response, &resp_len, AM32_REPLY_TIMEOUT)) {
        DEBUG_PRINT("ERROR: No response from ESC - check GP5 RX wiring!\n");
        DEBUG_PRINT("AM32 config requires BIDIRECTIONAL UART communication:\n");
        DEBUG_PRINT("  GP4 (TX) -> ESC signal input\n");
        DEBUG_PRINT("  GP5 (RX) <- ESC signal output\n");
        DEBUG_PRINT("Standard single-wire ESC connection is NOT sufficient.\n");
        DEBUG_PRINT("See file header for wiring options.\n");
        switch_to_pwm_mode();
        return false;
    }

    am32_in_config_mode = true;
    DEBUG_PRINT("AM32 config mode active (bidirectional link verified)\n");

    return true;
}

bool am32_exit_config_mode(void) {
    if (!am32_in_config_mode) {
        return true;
    }

    DEBUG_PRINT("Exiting AM32 config mode...\n");

    // Send exit command
    uint8_t exit_cmd = 0x00;
    am32_send_command(exit_cmd, NULL, 0);

    // Switch back to PWM mode
    switch_to_pwm_mode();

    // Reset motor to safe state
    motor_control_set_pulse(MOTOR_WEAPON, PWM_MIN_PULSE);

    am32_in_config_mode = false;
    DEBUG_PRINT("AM32 config mode exited\n");

    return true;
}

bool am32_send_command(uint8_t cmd, const uint8_t* data, uint16_t len) {
    if (!am32_in_config_mode && cmd != AM32_CMD_KEEPALIVE) {
        return false;
    }

    // Send command byte
    uart_putc_raw(AM32_UART, cmd);

    // Send length if data present
    if (data && len > 0) {
        uart_putc_raw(AM32_UART, len & 0xFF);
        uart_putc_raw(AM32_UART, (len >> 8) & 0xFF);

        // Send data
        for (uint16_t i = 0; i < len; i++) {
            uart_putc_raw(AM32_UART, data[i]);
        }

        // CRITICAL FIX #1: Standard AM32/MSP checksum - simple XOR of all bytes
        // Protocol format: [CMD] [LEN_L] [LEN_H] [DATA...] [CHECKSUM]
        // Checksum = CMD ^ LEN_L ^ LEN_H ^ DATA[0] ^ DATA[1] ^ ... ^ DATA[n-1]
        uint8_t checksum = cmd;
        checksum ^= (len & 0xFF);
        checksum ^= ((len >> 8) & 0xFF);
        for (uint16_t i = 0; i < len; i++) {
            checksum ^= data[i];
        }
        uart_putc_raw(AM32_UART, checksum);
    }

    return true;
}

bool am32_receive_response(uint8_t* buffer, uint16_t* len, uint32_t timeout_ms) {
    // SAFETY: Validate parameters
    if (buffer == NULL || len == NULL || *len == 0) {
        DEBUG_PRINT("CRITICAL: Invalid parameters to am32_receive_response\n");
        return false;
    }

    uint32_t start_time = to_ms_since_boot(get_absolute_time());
    uint16_t received = 0;
    uint16_t expected_len = 0;
    bool got_header = false;
    uint16_t max_buffer_size = *len; // Store original buffer size

    while ((to_ms_since_boot(get_absolute_time()) - start_time) < timeout_ms) {
        if (uart_is_readable(AM32_UART)) {
            uint8_t byte = uart_getc(AM32_UART);

            if (!got_header) {
                // First two bytes are length
                if (received == 0) {
                    expected_len = byte;
                } else if (received == 1) {
                    expected_len |= (byte << 8);
                    // MAJOR FIX #5 (Iteration 2): Check actual buffer size FIRST, then sanity check
                    // This ensures we protect against buffer overflow before other validations
                    if (expected_len > max_buffer_size) {
                        DEBUG_PRINT("ERROR: Response too large for buffer (%u > %u)\n",
                                   expected_len, max_buffer_size);
                        return false;
                    }
                    // MAJOR FIX #1: Validate max length to prevent timeout on huge values
                    // Maximum reasonable response is 512 bytes (prevents waiting for len=65535)
                    #define AM32_MAX_RESPONSE_LEN 512
                    if (expected_len > AM32_MAX_RESPONSE_LEN) {
                        DEBUG_PRINT("ERROR: Response exceeds maximum (%u > %u)\n",
                                   expected_len, AM32_MAX_RESPONSE_LEN);
                        return false;
                    }
                    got_header = true;
                }
                received++;
            } else {
                // SAFETY: Strict bounds checking
                uint16_t data_index = received - 2;
                if (data_index < expected_len && data_index < max_buffer_size) {
                    buffer[data_index] = byte;
                } else {
                    DEBUG_PRINT("WARNING: AM32 buffer overflow prevented\n");
                }
                received++;

                if (received >= expected_len + 2) {
                    *len = (expected_len < max_buffer_size) ? expected_len : max_buffer_size;
                    return true;
                }
            }
        }

        sleep_ms(1);
    }

    DEBUG_PRINT("AM32 receive timeout after %ums\n", timeout_ms);
    return false;
}

bool am32_read_settings(am32_config_t* config) {
    if (!am32_in_config_mode) {
        if (!am32_enter_config_mode()) {
            return false;
        }
    }

    DEBUG_PRINT("Reading AM32 settings...\n");

    // Send get settings command
    if (!am32_send_command(AM32_CMD_GET_SETTINGS, NULL, 0)) {
        return false;
    }

    // Receive settings data
    uint8_t buffer[256];
    uint16_t len = sizeof(buffer);

    if (!am32_receive_response(buffer, &len, AM32_REPLY_TIMEOUT)) {
        DEBUG_PRINT("Failed to receive AM32 settings\n");
        return false;
    }

    // Parse settings from buffer
    if (len >= AM32_MIN_SETTINGS_SIZE) {
        config->motor_direction = buffer[AM32_ADDR_MOTOR_DIRECTION];
        config->bidirectional = buffer[AM32_ADDR_BIDIRECTIONAL];
        config->brake_on_stop = buffer[AM32_ADDR_BRAKE_ON_STOP];
        config->startup_power = buffer[AM32_ADDR_STARTUP_POWER];
        config->motor_timing = buffer[AM32_ADDR_MOTOR_TIMING];
        config->pwm_frequency = buffer[AM32_ADDR_PWM_FREQUENCY];
        config->demag_compensation = buffer[AM32_ADDR_DEMAG_COMP];
        config->temperature_limit = buffer[AM32_ADDR_TEMP_LIMIT];
        config->current_limit = buffer[AM32_ADDR_CURRENT_LIMIT];
        config->throttle_min = buffer[AM32_ADDR_THROTTLE_MIN] | (buffer[AM32_ADDR_THROTTLE_MIN + 1] << 8);
        config->throttle_max = buffer[AM32_ADDR_THROTTLE_MAX] | (buffer[AM32_ADDR_THROTTLE_MAX + 1] << 8);

        DEBUG_PRINT("AM32 settings read successfully\n");
        return true;
    }

    return false;
}

bool am32_write_settings(const am32_config_t* config) {
    // SAFETY: Validate parameters
    if (config == NULL) {
        DEBUG_PRINT("CRITICAL: NULL config pointer in am32_write_settings\n");
        return false;
    }

    // MINOR FIX: Validate config parameter ranges before writing to ESC
    // This prevents sending invalid values that could damage the ESC or motor
    if (config->temperature_limit > 150) {
        DEBUG_PRINT("ERROR: Temperature limit too high (%d > 150°C)\n", config->temperature_limit);
        return false;
    }
    if (config->current_limit > 100) {
        DEBUG_PRINT("ERROR: Current limit too high (%d > 100A)\n", config->current_limit);
        return false;
    }
    if (config->startup_power < 1 || config->startup_power > 10) {
        DEBUG_PRINT("ERROR: Startup power out of range (%d, must be 1-10)\n", config->startup_power);
        return false;
    }
    if (config->motor_timing > 30) {
        DEBUG_PRINT("ERROR: Motor timing too high (%d > 30°)\n", config->motor_timing);
        return false;
    }
    if (config->pwm_frequency != 24 && config->pwm_frequency != 48 && config->pwm_frequency != 96) {
        DEBUG_PRINT("ERROR: Invalid PWM frequency (%d, must be 24, 48, or 96 kHz)\n", config->pwm_frequency);
        return false;
    }

    if (!am32_in_config_mode) {
        if (!am32_enter_config_mode()) {
            return false;
        }
    }

    DEBUG_PRINT("Writing AM32 settings...\n");

    // Prepare settings buffer
    uint8_t buffer[256] = {0};

    buffer[AM32_ADDR_MOTOR_DIRECTION] = config->motor_direction;
    buffer[AM32_ADDR_BIDIRECTIONAL] = config->bidirectional;
    buffer[AM32_ADDR_BRAKE_ON_STOP] = config->brake_on_stop;
    buffer[AM32_ADDR_STARTUP_POWER] = config->startup_power;
    buffer[AM32_ADDR_MOTOR_TIMING] = config->motor_timing;
    buffer[AM32_ADDR_PWM_FREQUENCY] = config->pwm_frequency;
    buffer[AM32_ADDR_DEMAG_COMP] = config->demag_compensation;
    buffer[AM32_ADDR_TEMP_LIMIT] = config->temperature_limit;
    buffer[AM32_ADDR_CURRENT_LIMIT] = config->current_limit;
    buffer[AM32_ADDR_THROTTLE_MIN] = config->throttle_min & 0xFF;
    buffer[AM32_ADDR_THROTTLE_MIN + 1] = (config->throttle_min >> 8) & 0xFF;
    buffer[AM32_ADDR_THROTTLE_MAX] = config->throttle_max & 0xFF;
    buffer[AM32_ADDR_THROTTLE_MAX + 1] = (config->throttle_max >> 8) & 0xFF;

    // Calculate checksum
    buffer[AM32_ADDR_SETTINGS_CHECKSUM] = am32_calculate_checksum(buffer, AM32_ADDR_SETTINGS_CHECKSUM);

    // Send set settings command
    if (!am32_send_command(AM32_CMD_SET_SETTINGS, buffer, 256)) {
        return false;
    }

    // Wait for confirmation
    uint8_t response[4];
    uint16_t resp_len = sizeof(response);

    if (!am32_receive_response(response, &resp_len, AM32_REPLY_TIMEOUT)) {
        DEBUG_PRINT("Failed to confirm AM32 settings write\n");
        return false;
    }

    DEBUG_PRINT("AM32 settings written successfully\n");

    // Update current config
    memcpy(&current_config, config, sizeof(am32_config_t));

    return true;
}

bool am32_calibrate_throttle(void) {
    if (!am32_in_config_mode) {
        if (!am32_enter_config_mode()) {
            return false;
        }
    }

    DEBUG_PRINT("Starting AM32 throttle calibration...\n");
    DEBUG_PRINT("Move throttle to maximum position\n");

    // Send calibration start command
    uint8_t cal_cmd = 0xCA;
    if (!am32_send_command(cal_cmd, NULL, 0)) {
        return false;
    }

    // Wait for user to set max throttle
    sleep_ms(AM32_CALIBRATION_MAX_DELAY_MS);

    // Send max throttle value (2000us)
    motor_control_set_pulse(MOTOR_WEAPON, PWM_MAX_PULSE);
    sleep_ms(AM32_CALIBRATION_STEP_DELAY_MS);

    DEBUG_PRINT("Move throttle to minimum position\n");

    // Send min throttle value (1000us)
    motor_control_set_pulse(MOTOR_WEAPON, PWM_MIN_PULSE);
    sleep_ms(AM32_CALIBRATION_STEP_DELAY_MS);

    // Send calibration complete
    uint8_t cal_done = 0xCB;
    if (!am32_send_command(cal_done, NULL, 0)) {
        return false;
    }

    DEBUG_PRINT("Throttle calibration complete\n");

    return true;
}

bool am32_save_settings(void) {
    if (!am32_in_config_mode) {
        return false;
    }

    DEBUG_PRINT("Saving AM32 settings to EEPROM...\n");

    uint8_t save_cmd = 0xEE;
    if (!am32_send_command(save_cmd, NULL, 0)) {
        return false;
    }

    // Wait for EEPROM write
    sleep_ms(AM32_SAVE_DELAY_MS);

    DEBUG_PRINT("Settings saved\n");

    return true;
}

uint8_t am32_calculate_checksum(const uint8_t* data, uint16_t len) {
    uint8_t checksum = 0;
    for (uint16_t i = 0; i < len; i++) {
        checksum ^= data[i];
    }
    return checksum;
}

void am32_apply_weapon_defaults(am32_config_t* config) {
    config->motor_direction = 0;        // Forward only
    config->bidirectional = 0;          // Unidirectional
    config->brake_on_stop = 0;          // No brake for weapon
    config->startup_power = 6;          // Medium-high power
    config->motor_timing = 16;          // 16 degrees
    config->motor_kv = 1100;            // F2822-1100KV
    config->motor_poles = 14;           // Standard outrunner
    config->pwm_frequency = 24;         // 24kHz
    config->throttle_min = 1000;        // 1000us minimum
    config->throttle_max = 2000;        // 2000us maximum
    config->temperature_limit = 80;     // 80°C limit
    config->current_limit = 40;         // 40A limit
    config->low_voltage_cutoff = 0;     // Disabled (robot handles this)
    config->demag_compensation = 2;     // High for weapon loads
    config->sine_mode = 0;              // Trapezoidal
    config->telemetry = 0;              // Off
    config->servo_center = 1500;        // Not used in uni mode
    config->deadband = 2;               // 2us deadband
}

bool am32_passthrough_mode(void) {
    DEBUG_PRINT("Entering AM32 passthrough mode for external configurator\n");
    DEBUG_PRINT("Connect external configurator to USB serial\n");
    DEBUG_PRINT("Press ESC to exit passthrough mode\n");

    if (!am32_enter_config_mode()) {
        return false;
    }

    // MINOR FIX: Intentional infinite loop for passthrough mode
    // This loop bridges USB serial <-> AM32 UART until user presses ESC key
    // Escape mechanism: ESC key (0x1B) breaks the loop at line 453
    // Watchdog is fed inside loop to prevent system reset during long config sessions
    while (true) {
        // SAFETY: Feed watchdog to prevent resets (only if enabled)
        if (watchdog_hw->ctrl & WATCHDOG_CTRL_ENABLE_BITS) {
            watchdog_update();
        }

        // USB -> AM32
        if (getchar_timeout_us(0) != PICO_ERROR_TIMEOUT) {
            int c = getchar();
            if (c == 0x1B) {  // ESC key to exit
                DEBUG_PRINT("ESC key pressed, exiting passthrough mode\n");
                break;
            }
            uart_putc_raw(AM32_UART, c);
        }

        // AM32 -> USB
        if (uart_is_readable(AM32_UART)) {
            uint8_t byte = uart_getc(AM32_UART);
            putchar(byte);
        }

        // Small yield to prevent hogging CPU
        tight_loop_contents();
    }

    am32_passthrough_exit();
    return true;
}

void am32_passthrough_exit(void) {
    DEBUG_PRINT("Exiting AM32 passthrough mode\n");
    am32_exit_config_mode();
}

bool am32_get_info(am32_info_t* info) {
    // SAFETY: Validate parameters
    if (info == NULL) {
        DEBUG_PRINT("CRITICAL: NULL info pointer in am32_get_info\n");
        return false;
    }

    if (!am32_in_config_mode) {
        if (!am32_enter_config_mode()) {
            return false;
        }
    }

    DEBUG_PRINT("Reading AM32 ESC info...\n");

    // Send get info command
    if (!am32_send_command(AM32_CMD_GET_INFO, NULL, 0)) {
        return false;
    }

    // Receive info data
    uint8_t buffer[64];
    uint16_t len = sizeof(buffer);

    if (!am32_receive_response(buffer, &len, AM32_REPLY_TIMEOUT)) {
        DEBUG_PRINT("Failed to receive AM32 info\n");
        return false;
    }

    // Parse info from buffer
    if (len >= AM32_MIN_INFO_SIZE) {
        info->firmware_version[0] = buffer[0];  // Major
        info->firmware_version[1] = buffer[1];  // Minor
        info->firmware_version[2] = buffer[2];  // Patch

        // Copy firmware name (null-terminated string)
        uint8_t name_len = (len - 3) < 16 ? (len - 3) : 15;
        memcpy(info->firmware_name, &buffer[3], name_len);
        info->firmware_name[name_len] = '\0';

        DEBUG_PRINT("AM32 Firmware: %s v%d.%d.%d\n",
                    info->firmware_name,
                    info->firmware_version[0],
                    info->firmware_version[1],
                    info->firmware_version[2]);

        return true;
    }

    return false;
}

bool am32_reset_to_defaults(void) {
    if (!am32_in_config_mode) {
        if (!am32_enter_config_mode()) {
            return false;
        }
    }

    DEBUG_PRINT("Resetting AM32 to factory defaults...\n");

    // Send reset command
    if (!am32_send_command(AM32_CMD_RESET, NULL, 0)) {
        return false;
    }

    // Wait for reset
    sleep_ms(AM32_MODE_SWITCH_DELAY_MS);

    DEBUG_PRINT("AM32 reset to defaults\n");

    return true;
}

bool am32_enter_bootloader(void) {
    if (!am32_in_config_mode) {
        if (!am32_enter_config_mode()) {
            return false;
        }
    }

    DEBUG_PRINT("Entering AM32 bootloader mode...\n");

    // Send bootloader command
    if (!am32_send_command(AM32_CMD_BOOTLOADER, NULL, 0)) {
        return false;
    }

    // ESC will reboot into bootloader
    // Switch to bootloader baud rate (115200)
    uart_deinit(AM32_UART);
    uart_init(AM32_UART, AM32_BAUDRATE_CMD);
    uart_set_format(AM32_UART, 8, 1, UART_PARITY_NONE);
    uart_set_fifo_enabled(AM32_UART, true);

    sleep_ms(500);

    DEBUG_PRINT("AM32 in bootloader mode (115200 baud)\n");
    DEBUG_PRINT("Ready for firmware flashing\n");

    return true;
}

bool am32_read_telemetry(am32_telemetry_t* telemetry) {
    if (telemetry == NULL) {
        DEBUG_PRINT("CRITICAL: NULL telemetry pointer\n");
        return false;
    }

    if (!am32_in_config_mode) {
        if (!am32_enter_config_mode()) {
            return false;
        }
    }

    if (!am32_send_command(AM32_CMD_GET_TELEMETRY, NULL, 0)) {
        return false;
    }

    uint8_t buffer[32];
    uint16_t len = sizeof(buffer);

    if (!am32_receive_response(buffer, &len, AM32_REPLY_TIMEOUT)) {
        return false;
    }

    if (len >= AM32_MIN_TELEMETRY_SIZE) {
        telemetry->voltage_mv = (buffer[0] << 8) | buffer[1];
        telemetry->current_ma = (buffer[2] << 8) | buffer[3];
        telemetry->consumption_mah = buffer[4];
        telemetry->erpm = (buffer[5] << 8) | buffer[6];
        telemetry->temperature_c = buffer[7];

        if (current_config.motor_poles > 0) {
            telemetry->rpm = telemetry->erpm / (current_config.motor_poles / 2);
        } else {
            telemetry->rpm = 0;
        }

        telemetry->valid = true;
        telemetry->timestamp_ms = to_ms_since_boot(get_absolute_time());

        return true;
    }

    return false;
}

bool am32_get_status(am32_status_t* status) {
    if (status == NULL) {
        DEBUG_PRINT("CRITICAL: NULL status pointer\n");
        return false;
    }

    if (!am32_in_config_mode) {
        if (!am32_enter_config_mode()) {
            return false;
        }
    }

    if (!am32_send_command(AM32_CMD_GET_STATUS, NULL, 0)) {
        return false;
    }

    uint8_t buffer[16];
    uint16_t len = sizeof(buffer);

    if (!am32_receive_response(buffer, &len, AM32_REPLY_TIMEOUT)) {
        return false;
    }

    if (len >= AM32_MIN_STATUS_SIZE) {
        uint8_t status_flags = buffer[0];
        status->armed = (status_flags & 0x01) != 0;
        status->motor_running = (status_flags & 0x02) != 0;
        status->signal_detected = (status_flags & 0x04) != 0;
        status->temperature_warning = (status_flags & 0x08) != 0;
        status->current_warning = (status_flags & 0x10) != 0;
        status->error_code = buffer[1];
        status->uptime_ms = (buffer[2] << 24) | (buffer[3] << 16) |
                            (buffer[4] << 8) | buffer[5];

        return true;
    }

    return false;
}

bool am32_set_motor_speed(uint16_t speed_percent) {
    if (speed_percent > 100) {
        speed_percent = 100;
    }

    uint8_t speed_cmd[2];
    speed_cmd[0] = (speed_percent >> 8) & 0xFF;
    speed_cmd[1] = speed_percent & 0xFF;

    return am32_send_command(AM32_CMD_KEEPALIVE, speed_cmd, 2);
}

bool am32_beep(uint8_t beep_pattern) {
    uint8_t beep_cmd[1] = { beep_pattern };
    return am32_send_command(AM32_CMD_BEEP, beep_cmd, 1);
}

bool am32_set_led(uint8_t led_state) {
    uint8_t led_cmd[1] = { led_state };
    return am32_send_command(AM32_CMD_SET_LED, led_cmd, 1);
}

bool am32_msp_send(uint8_t cmd, const uint8_t* payload, uint16_t len) {
    uint8_t msp_buffer[256];
    uint16_t idx = 0;

    msp_buffer[idx++] = '$';
    msp_buffer[idx++] = 'M';
    msp_buffer[idx++] = '<';
    msp_buffer[idx++] = len & 0xFF;
    msp_buffer[idx++] = cmd;

    uint8_t checksum = len ^ cmd;

    if (payload && len > 0) {
        for (uint16_t i = 0; i < len; i++) {
            msp_buffer[idx++] = payload[i];
            checksum ^= payload[i];
        }
    }

    msp_buffer[idx++] = checksum;

    for (uint16_t i = 0; i < idx; i++) {
        uart_putc_raw(AM32_UART, msp_buffer[i]);
    }

    return true;
}

bool am32_msp_receive(uint8_t* cmd, uint8_t* payload, uint16_t* len) {
    if (cmd == NULL || payload == NULL || len == NULL) {
        return false;
    }

    uint32_t start_time = to_ms_since_boot(get_absolute_time());
    uint8_t state = 0;
    uint8_t payload_len = 0;
    uint8_t checksum = 0;
    uint8_t calc_checksum = 0;
    uint16_t idx = 0;

    while ((to_ms_since_boot(get_absolute_time()) - start_time) < AM32_REPLY_TIMEOUT) {
        if (!uart_is_readable(AM32_UART)) {
            sleep_ms(1);
            continue;
        }

        uint8_t byte = uart_getc(AM32_UART);

        switch (state) {
            case 0:  // Wait for '$'
                if (byte == '$') state = 1;
                break;
            case 1:  // Wait for 'M'
                if (byte == 'M') state = 2;
                else state = 0;
                break;
            case 2:  // Wait for '>'
                if (byte == '>') state = 3;
                else state = 0;
                break;
            case 3:  // Payload length
                payload_len = byte;
                calc_checksum = byte;
                state = 4;
                break;
            case 4:  // Command
                *cmd = byte;
                calc_checksum ^= byte;
                idx = 0;
                if (payload_len == 0) {
                    state = 6;
                } else {
                    state = 5;
                }
                break;
            case 5:  // Payload
                payload[idx++] = byte;
                calc_checksum ^= byte;
                if (idx >= payload_len) {
                    state = 6;
                }
                break;
            case 6:  // Checksum
                checksum = byte;
                *len = payload_len;
                return (checksum == calc_checksum);
        }
    }

    return false;
}

bool am32_flash_firmware(const uint8_t* firmware_data, uint32_t size) {
    if (firmware_data == NULL || size == 0) {
        DEBUG_PRINT("CRITICAL: Invalid firmware data\n");
        return false;
    }

    if (!am32_enter_bootloader()) {
        DEBUG_PRINT("ERROR: Failed to enter bootloader\n");
        return false;
    }

    DEBUG_PRINT("Flashing firmware: %lu bytes\n", size);

    #define FLASH_PAGE_SIZE 128
    uint32_t pages = (size + FLASH_PAGE_SIZE - 1) / FLASH_PAGE_SIZE;

    for (uint32_t page = 0; page < pages; page++) {
        uint32_t offset = page * FLASH_PAGE_SIZE;
        uint16_t page_size = FLASH_PAGE_SIZE;

        if (offset + page_size > size) {
            page_size = size - offset;
        }

        uint8_t flash_cmd[FLASH_PAGE_SIZE + 4];
        flash_cmd[0] = 0x31;  // Write memory command
        flash_cmd[1] = (offset >> 8) & 0xFF;
        flash_cmd[2] = offset & 0xFF;
        flash_cmd[3] = page_size;

        memcpy(&flash_cmd[4], &firmware_data[offset], page_size);

        for (uint16_t i = 0; i < page_size + 4; i++) {
            uart_putc_raw(AM32_UART, flash_cmd[i]);
        }

        uint8_t response[2];
        uint16_t resp_len = sizeof(response);

        if (!am32_receive_response(response, &resp_len, 1000)) {
            DEBUG_PRINT("ERROR: Flash page %lu failed\n", page);
            return false;
        }

        if ((page % 10) == 0) {
            DEBUG_PRINT("Progress: %lu%%\n", (page * 100) / pages);
        }
    }

    DEBUG_PRINT("Firmware flash complete\n");
    return true;
}

bool am32_verify_firmware(void) {
    if (!am32_in_config_mode) {
        if (!am32_enter_config_mode()) {
            return false;
        }
    }

    uint8_t verify_cmd = 0x85;
    if (!am32_send_command(verify_cmd, NULL, 0)) {
        return false;
    }

    uint8_t response[4];
    uint16_t len = sizeof(response);

    if (!am32_receive_response(response, &len, 2000)) {
        return false;
    }

    if (len >= 1 && response[0] == 0x01) {
        DEBUG_PRINT("Firmware verification: PASS\n");
        return true;
    }

    DEBUG_PRINT("Firmware verification: FAIL\n");
    return false;
}