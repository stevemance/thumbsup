/**
 * AM32 ESC Bootloader Configuration Management
 *
 * Based on working code from phase6_am32_config.c
 * Uses bit-banged half-duplex UART on GP4 at 19200 baud with CRC-16 (0xA001)
 */

#include "am32_bootloader.h"
#include "config.h"
#include <stdio.h>
#include <string.h>
#include <pico/stdlib.h>
#include "hardware/gpio.h"
#include "hardware/pio.h"
#include "hardware/clocks.h"
#include "pio_uart.pio.h"

// PIO UART on signal pin
#define AM32_PIN 4
#define BAUDRATE 19200

// PIO state
static PIO pio_uart = pio0;
static uint sm_tx = 0;
static uint sm_rx = 1;
static uint offset_tx;
static uint offset_rx;
static bool pio_initialized = false;

// AM32 Bootloader Commands
#define CMD_RUN             0x00
#define CMD_PROG_FLASH      0x01
#define CMD_ERASE_FLASH     0x02
#define CMD_READ_FLASH_SIL  0x03
#define CMD_READ_EEPROM     0x04
#define CMD_PROG_EEPROM     0x05
#define CMD_KEEP_ALIVE      0xFD
#define CMD_SET_BUFFER      0xFE
#define CMD_SET_ADDRESS     0xFF

#define ACK_OK      0x30
#define NACK_CMD    0xC1
#define NACK_CRC    0xC2

// AT32F421 EEPROM address
#define EEPROM_ADDRESS 0x7C00

// Timeouts
#define TIMEOUT_ADDRESS_US  100000   // 100ms for address set
#define TIMEOUT_READ_US     500000   // 500ms for data read
#define TIMEOUT_WRITE_US    500000   // 500ms for write

// CRC-16 with polynomial 0xA001
static uint16_t crc16(const uint8_t* data, uint16_t length) {
    uint16_t crc = 0;
    for (uint16_t i = 0; i < length; i++) {
        uint8_t xb = data[i];
        for (uint8_t j = 0; j < 8; j++) {
            if (((xb & 0x01) ^ (crc & 0x0001)) != 0) {
                crc >>= 1;
                crc ^= 0xA001;
            } else {
                crc >>= 1;
            }
            xb >>= 1;
        }
    }
    return crc;
}

// Switch to TX mode (enable TX SM, disable RX SM)
static void switch_to_tx_mode(void) {
    pio_sm_set_enabled(pio_uart, sm_rx, false);

    // Set pin high before enabling TX (idle state)
    gpio_put(AM32_PIN, 1);
    pio_sm_set_consecutive_pindirs(pio_uart, sm_tx, AM32_PIN, 1, true);

    // Restart TX SM to ensure it starts at pull instruction
    pio_sm_clear_fifos(pio_uart, sm_tx);
    pio_sm_restart(pio_uart, sm_tx);
    pio_sm_set_enabled(pio_uart, sm_tx, true);
}

// Switch to RX mode (enable RX SM, disable TX SM)
static void switch_to_rx_mode(void) {
    pio_sm_set_enabled(pio_uart, sm_tx, false);

    // Set pin as input with pull-up
    pio_sm_set_consecutive_pindirs(pio_uart, sm_rx, AM32_PIN, 1, false);
    gpio_pull_up(AM32_PIN);

    // Restart RX SM to wait for start bit
    pio_sm_clear_fifos(pio_uart, sm_rx);
    pio_sm_restart(pio_uart, sm_rx);
    pio_sm_set_enabled(pio_uart, sm_rx, true);
}

// PIO transmit one byte
static void pio_tx_byte(uint8_t byte) {
    pio_sm_put_blocking(pio_uart, sm_tx, byte);
}

// PIO receive one byte with timeout
static int pio_rx_byte(uint32_t timeout_us) {
    uint32_t start = time_us_32();
    while (pio_sm_is_rx_fifo_empty(pio_uart, sm_rx)) {
        if ((time_us_32() - start) > timeout_us) {
            return -1;
        }
    }
    // With right shift and autopush at 8, data is in bits 31:24
    uint32_t raw = pio_sm_get(pio_uart, sm_rx);
    return (raw >> 24) & 0xFF;
}

// Send command with CRC using PIO
static void send_with_crc(const uint8_t* data, uint16_t len) {
    uint16_t crc = crc16(data, len);

    switch_to_tx_mode();

    for (uint16_t i = 0; i < len; i++) {
        pio_tx_byte(data[i]);
    }
    pio_tx_byte(crc & 0xFF);
    pio_tx_byte((crc >> 8) & 0xFF);

    // Wait for TX to complete (each byte ~520us at 19200)
    sleep_us(520 * (len + 2));

    switch_to_rx_mode();
}

// Receive multiple bytes
static int receive_bytes(uint8_t* buf, uint16_t len, uint32_t timeout_us) {
    for (uint16_t i = 0; i < len; i++) {
        int b = pio_rx_byte(timeout_us);
        if (b < 0) return i;
        buf[i] = b;
    }
    return len;
}

void am32_bootloader_init(void) {
    if (pio_initialized) return;

    // Initialize GPIO for PIO once
    pio_gpio_init(pio_uart, AM32_PIN);
    gpio_pull_up(AM32_PIN);

    // Load PIO programs
    offset_tx = pio_add_program(pio_uart, &pio_uart_tx_program);
    offset_rx = pio_add_program(pio_uart, &pio_uart_rx_program);

    // Configure TX state machine
    pio_sm_config c_tx = pio_uart_tx_program_get_default_config(offset_tx);
    sm_config_set_out_pins(&c_tx, AM32_PIN, 1);
    sm_config_set_sideset_pins(&c_tx, AM32_PIN);
    sm_config_set_out_shift(&c_tx, true, true, 8);
    float div = (float)clock_get_hz(clk_sys) / (8 * BAUDRATE);
    sm_config_set_clkdiv(&c_tx, div);
    pio_sm_init(pio_uart, sm_tx, offset_tx, &c_tx);

    // Configure RX state machine
    pio_sm_config c_rx = pio_uart_rx_program_get_default_config(offset_rx);
    sm_config_set_in_pins(&c_rx, AM32_PIN);
    sm_config_set_in_shift(&c_rx, true, true, 8);
    sm_config_set_clkdiv(&c_rx, div);
    pio_sm_init(pio_uart, sm_rx, offset_rx, &c_rx);

    // Start in TX mode with line high (idle)
    pio_sm_set_consecutive_pindirs(pio_uart, sm_tx, AM32_PIN, 1, true);
    pio_sm_set_enabled(pio_uart, sm_tx, true);

    pio_initialized = true;
}

void am32_bootloader_hold_high(void) {
    am32_bootloader_init();
    switch_to_tx_mode();
    gpio_put(AM32_PIN, 1);
}

// Enter bootloader mode programmatically (no power cycle needed)
// 1. Hold signal HIGH (UART idle) to stop DShot
// 2. Wait for firmware timeout (~2.5s) which triggers software reset
// 3. Bootloader sees HIGH signal and stays active
// 4. Send BLHeli init sequence
am32_bootloader_error_t am32_bootloader_enter(void) {
    // Try keep-alive to see if already in bootloader mode
    uint8_t keep_alive[] = {CMD_KEEP_ALIVE};
    send_with_crc(keep_alive, 1);

    int ack = pio_rx_byte(100000);
    if (ack == ACK_OK) {
        printf("ESC already in bootloader mode\n");
        return AM32_OK;
    }

    // Try BLHeli init sequence (for auto-entry after firmware timeout)
    printf("Trying BLHeli init sequence...\n");
    uint8_t init_seq[] = {
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x0D, 0x42, 0x4C, 0x48, 0x65, 0x6C, 0x69,  // 0x0D + "BLHeli"
        0xF4, 0x7D  // CRC over "BLHeli" only
    };

    switch_to_tx_mode();
    for (int i = 0; i < (int)sizeof(init_seq); i++) {
        pio_tx_byte(init_seq[i]);
    }
    sleep_us(520 * sizeof(init_seq));
    switch_to_rx_mode();

    // Wait for response
    sleep_ms(50);
    uint8_t response[40];
    int received = receive_bytes(response, 30, 500000);

    printf("BLHeli init response: %d bytes\n", received);
    if (received > 0) {
        printf("Data: ");
        for (int i = 0; i < received && i < 32; i++) {
            printf("%02X ", response[i]);
        }
        printf("\n");
    }

    // Check for device info response
    if (received >= 9) {
        if (response[0] == '4' || (received >= 30 && response[21] == '4')) {
            printf("ESC in bootloader mode!\n");
            return AM32_OK;
        }
    }

    // Not in bootloader - need power cycle
    printf("ESC not in bootloader mode.\n");
    printf("Please power cycle the ESC while signal is HIGH...\n");

    // Wait for ESC to be power cycled
    for (int retry = 0; retry < 20; retry++) {
        sleep_ms(500);

        send_with_crc(keep_alive, 1);
        ack = pio_rx_byte(100000);

        if (ack == ACK_OK) {
            printf("ESC entered bootloader mode!\n");
            return AM32_OK;
        }
        printf(".");
    }

    printf("\nTimeout waiting for bootloader\n");
    return AM32_ERR_NOT_IN_BOOTLOADER;
}

am32_bootloader_error_t am32_bootloader_read(uint8_t* buffer) {
    if (!buffer) {
        return AM32_ERR_NOT_IN_BOOTLOADER;
    }

    // Step 1: Set address to 0x7C00 (EEPROM location for AT32F421)
    uint8_t set_addr[] = {CMD_SET_ADDRESS, 0x00, 0x7C, 0x00};
    send_with_crc(set_addr, sizeof(set_addr));

    // Wait for ACK
    int ack = pio_rx_byte(TIMEOUT_ADDRESS_US);
    if (ack != ACK_OK) {
        return AM32_ERR_NOT_IN_BOOTLOADER;
    }

    // Step 2: Read 192 bytes using CMD_READ_FLASH_SIL
    uint8_t read_cmd[] = {CMD_READ_FLASH_SIL, AM32_EEPROM_SIZE};
    send_with_crc(read_cmd, sizeof(read_cmd));

    // Receive: 192 data bytes + 2 CRC bytes + 1 ACK
    uint8_t response[195];
    int received = receive_bytes(response, 195, TIMEOUT_READ_US);

    if (received < 195) {
        return AM32_ERR_TIMEOUT;
    }

    // Verify CRC
    uint16_t recv_crc = response[192] | (response[193] << 8);
    uint8_t final_ack = response[194];
    uint16_t calc_crc = crc16(response, 192);

    if (recv_crc != calc_crc) {
        return AM32_ERR_CRC;
    }

    if (final_ack != ACK_OK) {
        return AM32_ERR_ACK;
    }

    // Copy data to output buffer
    memcpy(buffer, response, AM32_EEPROM_SIZE);

    return AM32_OK;
}

am32_bootloader_error_t am32_bootloader_write(const uint8_t* buffer) {
    if (!buffer) {
        return AM32_ERR_NOT_IN_BOOTLOADER;
    }

    // Step 1: Set address to 0x7C00
    uint8_t set_addr[] = {CMD_SET_ADDRESS, 0x00, 0x7C, 0x00};
    send_with_crc(set_addr, sizeof(set_addr));

    // Wait for ACK
    int ack = pio_rx_byte(TIMEOUT_ADDRESS_US);
    if (ack != ACK_OK) {
        return AM32_ERR_NOT_IN_BOOTLOADER;
    }

    // Step 2: Send EEPROM data using CMD_PROG_EEPROM
    // Format: CMD + length + data + CRC
    uint8_t write_buffer[2 + AM32_EEPROM_SIZE];
    write_buffer[0] = CMD_PROG_EEPROM;
    write_buffer[1] = AM32_EEPROM_SIZE;
    memcpy(&write_buffer[2], buffer, AM32_EEPROM_SIZE);
    send_with_crc(write_buffer, sizeof(write_buffer));

    // Wait for write completion ACK (flash write takes time)
    ack = pio_rx_byte(TIMEOUT_WRITE_US);
    if (ack != ACK_OK) {
        return AM32_ERR_WRITE_FAILED;
    }

    return AM32_OK;
}

uint16_t am32_bootloader_diff(const uint8_t* current, const uint8_t* desired, uint8_t* diff_mask) {
    uint16_t diff_count = 0;

    for (int i = 0; i < AM32_EEPROM_SIZE; i++) {
        if (current[i] != desired[i]) {
            if (diff_mask) {
                diff_mask[i] = 1;
            }
            diff_count++;
        } else {
            if (diff_mask) {
                diff_mask[i] = 0;
            }
        }
    }

    return diff_count;
}

void am32_bootloader_print(const uint8_t* config) {
    printf("\n========================================\n");
    printf("  AM32 ESC Configuration\n");
    printf("========================================\n\n");

    // Basic info
    printf("EEPROM Version:      %d\n", config[AM32_OFF_EEPROM_VERSION]);
    printf("Firmware Version:    %d.%d\n", config[AM32_OFF_FW_VERSION_MAJOR], config[AM32_OFF_FW_VERSION_MINOR]);

    // Motor settings
    printf("\n--- Motor Settings ---\n");
    printf("Motor KV:            %d\n", config[AM32_OFF_MOTOR_KV]);
    printf("Motor Poles:         %d\n", config[AM32_OFF_MOTOR_POLES]);
    printf("Direction Reversed:  %s\n", config[AM32_OFF_DIR_REVERSED] ? "Yes" : "No");
    printf("Bidirectional:       %s\n", config[AM32_OFF_BIDIRECTIONAL] ? "Yes (3D)" : "No");
    printf("Brake on Stop:       %s\n", config[AM32_OFF_BRAKE_ON_STOP] ? "Yes" : "No");
    printf("Stall Protection:    %s\n", config[AM32_OFF_STALL_PROTECTION] ? "Yes" : "No");

    // Startup settings
    printf("\n--- Startup Settings ---\n");
    printf("Startup Power:       %d\n", config[AM32_OFF_STARTUP_POWER]);
    printf("Use Sine Start:      %s\n", config[AM32_OFF_USE_SINE_START] ? "Yes" : "No");
    printf("Sine Mode Power:     %d\n", config[AM32_OFF_SINE_MODE_POWER]);
    printf("Sine Changeover:     %d\n", config[AM32_OFF_SINE_MODE_CHANGEOVER]);

    // Timing and PWM
    printf("\n--- Timing/PWM ---\n");
    printf("Advance Level:       %d degrees\n", config[AM32_OFF_ADVANCE_LEVEL]);
    printf("Auto Advance:        %s\n", config[AM32_OFF_AUTO_ADVANCE] ? "Yes" : "No");
    printf("PWM Frequency:       %d kHz\n", config[AM32_OFF_PWM_FREQUENCY]);
    printf("Comp PWM:            %s\n", config[AM32_OFF_COMP_PWM] ? "Yes" : "No");
    printf("Variable PWM:        %s\n", config[AM32_OFF_VARIABLE_PWM] ? "Yes" : "No");

    // Throttle/Servo settings
    printf("\n--- Input Settings ---\n");
    printf("Input Type:          %d\n", config[AM32_OFF_INPUT_TYPE]);
    printf("Servo Low:           %d\n", config[AM32_OFF_SERVO_LOW]);
    printf("Servo High:          %d\n", config[AM32_OFF_SERVO_HIGH]);
    printf("Servo Neutral:       %d\n", config[AM32_OFF_SERVO_NEUTRAL]);
    printf("Servo Deadband:      %d\n", config[AM32_OFF_SERVO_DEADBAND]);
    printf("Disable Stick Cal:   %s\n", config[AM32_OFF_DISABLE_STICK_CAL] ? "Yes" : "No");

    // Braking
    printf("\n--- Braking ---\n");
    printf("Active Brake Power:  %d\n", config[AM32_OFF_ACTIVE_BRAKE_POWER]);
    printf("Drag Brake Strength: %d\n", config[AM32_OFF_DRAG_BRAKE_STRENGTH]);
    printf("Driving Brake:       %d\n", config[AM32_OFF_DRIVING_BRAKE_STRENGTH]);
    printf("RC Car Reverse:      %s\n", config[AM32_OFF_RC_CAR_REVERSE] ? "Yes" : "No");

    // Protection settings
    printf("\n--- Protection ---\n");
    printf("Temperature Limit:   %d C\n", config[AM32_OFF_TEMP_LIMIT]);
    printf("Current Limit:       %d A\n", config[AM32_OFF_CURRENT_LIMIT]);
    printf("Low Voltage Cutoff:  %s\n", config[AM32_OFF_LOW_VOLTAGE_CUTOFF] ? "Yes" : "No");
    printf("Low Cell Volt Cut:   %d\n", config[AM32_OFF_LOW_CELL_VOLT_CUTOFF]);
    printf("Abs Voltage Cutoff:  %d (x0.5V)\n", config[AM32_OFF_ABS_VOLTAGE_CUTOFF]);
    printf("Stuck Rotor Prot:    %s\n", config[AM32_OFF_STUCK_ROTOR_PROT] ? "Yes" : "No");

    // Current PID
    printf("\n--- Current Control ---\n");
    printf("Current P:           %d\n", config[AM32_OFF_CURRENT_P]);
    printf("Current I:           %d\n", config[AM32_OFF_CURRENT_I]);
    printf("Current D:           %d\n", config[AM32_OFF_CURRENT_D]);
    printf("Max Ramp:            %d\n", config[AM32_OFF_MAX_RAMP]);
    printf("Min Duty Cycle:      %d\n", config[AM32_OFF_MIN_DUTY_CYCLE]);

    // Misc
    printf("\n--- Misc ---\n");
    printf("Beep Volume:         %d\n", config[AM32_OFF_BEEP_VOLUME]);
    printf("Telemetry Interval:  %d\n", config[AM32_OFF_TELEMETRY_INTERVAL]);
    printf("Use Hall Sensors:    %s\n", config[AM32_OFF_USE_HALL_SENSORS] ? "Yes" : "No");

    // CAN settings
    printf("\n--- CAN Settings ---\n");
    printf("CAN Node:            %d\n", config[AM32_OFF_CAN_NODE]);
    printf("ESC Index:           %d\n", config[AM32_OFF_ESC_INDEX]);
    printf("Require Arming:      %s\n", config[AM32_OFF_REQUIRE_ARMING] ? "Yes" : "No");
    printf("Telem Rate:          %d\n", config[AM32_OFF_TELEM_RATE]);
    printf("Require Zero:        %s\n", config[AM32_OFF_REQUIRE_ZERO_THROTTLE] ? "Yes" : "No");
    printf("Filter Hz:           %d\n", config[AM32_OFF_FILTER_HZ]);
    printf("Debug Rate:          %d\n", config[AM32_OFF_DEBUG_RATE]);
    printf("Term Enable:         %s\n", config[AM32_OFF_TERM_ENABLE] ? "Yes" : "No");

    printf("\n========================================\n");
}

static void print_field_diff(const char* name, uint8_t current, uint8_t desired) {
    printf("  %s: %d -> %d\n", name, current, desired);
}

am32_bootloader_error_t am32_bootloader_validate_and_update(const uint8_t* desired) {
    printf("Checking AM32 ESC configuration...\n");

    // Initialize GPIO
    am32_bootloader_init();

    // Attempt to read current config
    uint8_t current[AM32_EEPROM_SIZE];
    am32_bootloader_error_t err = am32_bootloader_read(current);

    if (err != AM32_OK) {
        printf("WARNING: ESC not in bootloader mode, skipping config check\n");
        printf("         (To configure: hold signal HIGH during ESC power cycle)\n");
        return err;
    }

    printf("ESC config read successfully\n");

    // Compare configs
    uint8_t diff_mask[AM32_EEPROM_SIZE];
    uint16_t diff_count = am32_bootloader_diff(current, desired, diff_mask);

    if (diff_count == 0) {
        printf("ESC configuration matches desired - no update needed\n");
        am32_bootloader_print(current);
        return AM32_OK;
    }

    printf("Found %d bytes different, updating ESC config...\n", diff_count);

    // Print which fields differ
    printf("\nConfiguration differences:\n");
    if (diff_mask[AM32_OFF_EEPROM_VERSION]) print_field_diff("EEPROM Version", current[AM32_OFF_EEPROM_VERSION], desired[AM32_OFF_EEPROM_VERSION]);
    if (diff_mask[AM32_OFF_MOTOR_KV]) print_field_diff("Motor KV", current[AM32_OFF_MOTOR_KV], desired[AM32_OFF_MOTOR_KV]);
    if (diff_mask[AM32_OFF_MOTOR_POLES]) print_field_diff("Motor Poles", current[AM32_OFF_MOTOR_POLES], desired[AM32_OFF_MOTOR_POLES]);
    if (diff_mask[AM32_OFF_DIR_REVERSED]) print_field_diff("Direction Reversed", current[AM32_OFF_DIR_REVERSED], desired[AM32_OFF_DIR_REVERSED]);
    if (diff_mask[AM32_OFF_BIDIRECTIONAL]) print_field_diff("Bidirectional", current[AM32_OFF_BIDIRECTIONAL], desired[AM32_OFF_BIDIRECTIONAL]);
    if (diff_mask[AM32_OFF_BRAKE_ON_STOP]) print_field_diff("Brake on Stop", current[AM32_OFF_BRAKE_ON_STOP], desired[AM32_OFF_BRAKE_ON_STOP]);
    if (diff_mask[AM32_OFF_STARTUP_POWER]) print_field_diff("Startup Power", current[AM32_OFF_STARTUP_POWER], desired[AM32_OFF_STARTUP_POWER]);
    if (diff_mask[AM32_OFF_ADVANCE_LEVEL]) print_field_diff("Advance Level", current[AM32_OFF_ADVANCE_LEVEL], desired[AM32_OFF_ADVANCE_LEVEL]);
    if (diff_mask[AM32_OFF_PWM_FREQUENCY]) print_field_diff("PWM Frequency", current[AM32_OFF_PWM_FREQUENCY], desired[AM32_OFF_PWM_FREQUENCY]);
    if (diff_mask[AM32_OFF_TEMP_LIMIT]) print_field_diff("Temperature Limit", current[AM32_OFF_TEMP_LIMIT], desired[AM32_OFF_TEMP_LIMIT]);
    if (diff_mask[AM32_OFF_CURRENT_LIMIT]) print_field_diff("Current Limit", current[AM32_OFF_CURRENT_LIMIT], desired[AM32_OFF_CURRENT_LIMIT]);
    if (diff_mask[AM32_OFF_INPUT_TYPE]) print_field_diff("Input Type", current[AM32_OFF_INPUT_TYPE], desired[AM32_OFF_INPUT_TYPE]);
    if (diff_mask[AM32_OFF_TELEMETRY_INTERVAL]) print_field_diff("Telemetry", current[AM32_OFF_TELEMETRY_INTERVAL], desired[AM32_OFF_TELEMETRY_INTERVAL]);
    if (diff_mask[AM32_OFF_BEEP_VOLUME]) print_field_diff("Beep Volume", current[AM32_OFF_BEEP_VOLUME], desired[AM32_OFF_BEEP_VOLUME]);

    // Write new config
    err = am32_bootloader_write(desired);
    if (err != AM32_OK) {
        printf("ERROR: Failed to write config: %s\n", am32_bootloader_error_str(err));
        return err;
    }

    printf("Config written, verifying...\n");

    // Verify write
    uint8_t verify[AM32_EEPROM_SIZE];
    err = am32_bootloader_read(verify);
    if (err != AM32_OK) {
        printf("ERROR: Failed to verify config: %s\n", am32_bootloader_error_str(err));
        return err;
    }

    if (memcmp(verify, desired, AM32_EEPROM_SIZE) != 0) {
        printf("ERROR: Config verification failed - data mismatch\n");
        return AM32_ERR_VERIFY_FAILED;
    }

    printf("ESC configuration updated and verified successfully!\n");
    am32_bootloader_print(verify);

    return AM32_OK;
}

void am32_bootloader_run(void) {
    // Send CMD_RUN to exit bootloader
    uint8_t run_cmd[] = {CMD_RUN};
    send_with_crc(run_cmd, sizeof(run_cmd));

    // Small delay to allow ESC to start
    sleep_ms(100);
}

const char* am32_bootloader_error_str(am32_bootloader_error_t err) {
    switch (err) {
        case AM32_OK: return "OK";
        case AM32_ERR_TIMEOUT: return "Timeout";
        case AM32_ERR_CRC: return "CRC mismatch";
        case AM32_ERR_ACK: return "No ACK received";
        case AM32_ERR_NOT_IN_BOOTLOADER: return "ESC not in bootloader mode";
        case AM32_ERR_WRITE_FAILED: return "Write failed";
        case AM32_ERR_VERIFY_FAILED: return "Verification failed";
        default: return "Unknown error";
    }
}
