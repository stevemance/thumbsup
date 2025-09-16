#include "am32_config.h"
#include "config.h"
#include "motor_control.h"
#include "pico/stdlib.h"
#include "hardware/uart.h"
#include "hardware/gpio.h"
#include "hardware/pwm.h"
#include <stdio.h>
#include <string.h>

// UART instance for AM32 communication
#define AM32_UART uart1
#define AM32_TX_PIN PIN_WEAPON_PWM  // Use weapon PWM pin for serial

static bool am32_configured = false;
static bool am32_in_config_mode = false;
static am32_config_t current_config;

// Convert PWM pin to UART mode
static bool switch_to_uart_mode(void) {
    // Disable PWM on the weapon pin
    pwm_set_enabled(pwm_gpio_to_slice_num(AM32_TX_PIN), false);

    // Configure pin for UART TX (we'll use the same pin for RX via resistor)
    gpio_set_function(AM32_TX_PIN, GPIO_FUNC_UART);

    // Initialize UART
    uart_init(AM32_UART, AM32_BAUD_RATE);
    uart_set_format(AM32_UART, 8, 1, UART_PARITY_NONE);
    uart_set_fifo_enabled(AM32_UART, true);

    return true;
}

// Convert back to PWM mode
static bool switch_to_pwm_mode(void) {
    // De-init UART
    uart_deinit(AM32_UART);

    // Reconfigure pin for PWM
    gpio_set_function(AM32_TX_PIN, GPIO_FUNC_PWM);

    // Re-enable PWM
    uint8_t slice = pwm_gpio_to_slice_num(AM32_TX_PIN);
    pwm_set_enabled(slice, true);

    return true;
}

// Send special signal pattern to enter config mode
static bool send_config_entry_signal(void) {
    // AM32 expects specific pulse pattern to enter config mode
    // Typically: series of short pulses outside normal PWM range

    // Send 10 pulses at 1ms interval with 100us width
    for (int i = 0; i < 10; i++) {
        gpio_put(AM32_TX_PIN, 1);
        sleep_us(100);
        gpio_put(AM32_TX_PIN, 0);
        sleep_us(900);
    }

    // Wait for ESC to enter config mode
    sleep_ms(100);

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
    sleep_ms(100);

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

    am32_in_config_mode = true;
    DEBUG_PRINT("AM32 config mode active\n");

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

        // Send checksum
        uint8_t checksum = am32_calculate_checksum(data, len);
        uart_putc_raw(AM32_UART, checksum);
    }

    return true;
}

bool am32_receive_response(uint8_t* buffer, uint16_t* len, uint32_t timeout_ms) {
    uint32_t start_time = to_ms_since_boot(get_absolute_time());
    uint16_t received = 0;
    uint16_t expected_len = 0;
    bool got_header = false;

    while ((to_ms_since_boot(get_absolute_time()) - start_time) < timeout_ms) {
        if (uart_is_readable(AM32_UART)) {
            uint8_t byte = uart_getc(AM32_UART);

            if (!got_header) {
                // First two bytes are length
                if (received == 0) {
                    expected_len = byte;
                } else if (received == 1) {
                    expected_len |= (byte << 8);
                    got_header = true;
                }
                received++;
            } else {
                // Receive data
                if (received - 2 < expected_len && received - 2 < *len) {
                    buffer[received - 2] = byte;
                }
                received++;

                if (received >= expected_len + 2) {
                    *len = expected_len;
                    return true;
                }
            }
        }

        sleep_ms(1);
    }

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
    if (len >= 32) {  // Minimum expected settings size
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
    sleep_ms(3000);

    // Send max throttle value (2000us)
    motor_control_set_pulse(MOTOR_WEAPON, PWM_MAX_PULSE);
    sleep_ms(500);

    DEBUG_PRINT("Move throttle to minimum position\n");

    // Send min throttle value (1000us)
    motor_control_set_pulse(MOTOR_WEAPON, PWM_MIN_PULSE);
    sleep_ms(500);

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
    sleep_ms(100);

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

    if (!am32_enter_config_mode()) {
        return false;
    }

    // Bridge USB serial to AM32 UART
    while (true) {
        // USB -> AM32
        if (getchar_timeout_us(0) != PICO_ERROR_TIMEOUT) {
            int c = getchar();
            if (c == 0x1B) {  // ESC key to exit
                break;
            }
            uart_putc_raw(AM32_UART, c);
        }

        // AM32 -> USB
        if (uart_is_readable(AM32_UART)) {
            uint8_t byte = uart_getc(AM32_UART);
            putchar(byte);
        }
    }

    am32_passthrough_exit();
    return true;
}

void am32_passthrough_exit(void) {
    DEBUG_PRINT("Exiting AM32 passthrough mode\n");
    am32_exit_config_mode();
}