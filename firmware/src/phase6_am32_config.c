/*
 * Phase 6: AM32 ESC Configuration Reader
 *
 * Uses AM32 bootloader protocol to read settings
 * Baud: 19200, CRC-16 (0xA001)
 */

#include <stdio.h>
#include <string.h>
#include <pico/stdlib.h>
#include "hardware/gpio.h"
#include "config.h"

// Bit-banged half-duplex UART on signal pin
#define AM32_PIN 4
#define BAUDRATE 19200
#define BITTIME 52      // 1000000/19200
#define HALFBITTIME 26

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

#define ADDRESS_MAGIC_EEPROM 0x20

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

// Bit-bang transmit one byte
static void bb_tx_byte(uint8_t byte) {
    gpio_set_dir(AM32_PIN, GPIO_OUT);

    // Start bit (low)
    gpio_put(AM32_PIN, 0);
    sleep_us(BITTIME);

    // Data bits (LSB first)
    for (int i = 0; i < 8; i++) {
        gpio_put(AM32_PIN, (byte >> i) & 1);
        sleep_us(BITTIME);
    }

    // Stop bit (high)
    gpio_put(AM32_PIN, 1);
    sleep_us(BITTIME);
}

// Bit-bang receive one byte with timeout
static int bb_rx_byte(uint32_t timeout_us) {
    gpio_set_dir(AM32_PIN, GPIO_IN);
    gpio_pull_up(AM32_PIN);

    // Wait for start bit (falling edge)
    uint32_t start = time_us_32();
    while (gpio_get(AM32_PIN)) {
        if ((time_us_32() - start) > timeout_us) {
            return -1;
        }
    }

    // Sample in middle of first data bit
    sleep_us(BITTIME + HALFBITTIME);

    // Read 8 data bits (LSB first)
    uint8_t byte = 0;
    for (int i = 0; i < 8; i++) {
        if (gpio_get(AM32_PIN)) {
            byte |= (1 << i);
        }
        sleep_us(BITTIME);
    }

    return byte;
}

// Send command with CRC
static void send_with_crc(const uint8_t* data, uint16_t len) {
    uint16_t crc = crc16(data, len);

    // Set to transmit mode with delay
    gpio_set_dir(AM32_PIN, GPIO_OUT);
    gpio_put(AM32_PIN, 1);
    sleep_us(BITTIME);

    for (uint16_t i = 0; i < len; i++) {
        bb_tx_byte(data[i]);
    }
    bb_tx_byte(crc & 0xFF);
    bb_tx_byte((crc >> 8) & 0xFF);
}

// Receive multiple bytes
static int receive_bytes(uint8_t* buf, uint16_t len, uint32_t timeout_us) {
    for (uint16_t i = 0; i < len; i++) {
        int b = bb_rx_byte(timeout_us);
        if (b < 0) return i;
        buf[i] = b;
    }
    return len;
}

int main() {
    stdio_init_all();
    sleep_ms(3000);

    printf("\n========================================\n");
    printf("  Phase 6: AM32 Bootloader Config Read\n");
    printf("========================================\n\n");

    printf("This uses the AM32 BOOTLOADER protocol.\n");
    printf("The ESC must be in bootloader mode!\n\n");
    printf("To enter bootloader mode:\n");
    printf("1. Signal pin will be held HIGH\n");
    printf("2. Power cycle the ESC NOW\n");
    printf("3. Waiting 5 seconds...\n\n");

    // Setup LED
    const uint LED_PIN = 25;
    gpio_init(LED_PIN);
    gpio_set_dir(LED_PIN, GPIO_OUT);

    // Hold signal HIGH to keep ESC in bootloader
    gpio_init(AM32_PIN);
    gpio_set_dir(AM32_PIN, GPIO_OUT);
    gpio_put(AM32_PIN, 1);

    // Wait for user to power cycle ESC
    for (int i = 5; i > 0; i--) {
        printf("%d...\n", i);
        gpio_put(LED_PIN, 1);
        sleep_ms(500);
        gpio_put(LED_PIN, 0);
        sleep_ms(500);
    }

    printf("\nAttempting to read settings...\n");
    gpio_put(LED_PIN, 1);

    // Step 1: Set address to 0x7C00 (EEPROM location for AT32F421)
    // From AM32 targets.h: EEPROM_START_ADD = 0x08007C00
    printf("Setting address to 0x7C00 (AT32F421 EEPROM)...\n");
    uint8_t set_addr[] = {CMD_SET_ADDRESS, 0x00, 0x7C, 0x00};  // Address = 0x7C00
    send_with_crc(set_addr, sizeof(set_addr));

    // Wait for ACK
    int ack = bb_rx_byte(100000);  // 100ms timeout
    printf("Address ACK: 0x%02X %s\n", ack, ack == ACK_OK ? "(OK)" : "(FAIL)");

    if (ack != ACK_OK) {
        printf("\n*** Failed to set address ***\n");
        printf("ESC may not be in bootloader mode.\n");
        printf("Try power cycling the ESC while signal is held high.\n");

        gpio_put(LED_PIN, 0);
        while (1) {
            gpio_put(LED_PIN, 1);
            sleep_ms(100);
            gpio_put(LED_PIN, 0);
            sleep_ms(900);
        }
    }

    // Step 2: Read 192 bytes using CMD_READ_FLASH_SIL
    printf("Reading 192 bytes of settings...\n");
    uint8_t read_cmd[] = {CMD_READ_FLASH_SIL, 192};
    send_with_crc(read_cmd, sizeof(read_cmd));

    // Receive: 192 data bytes + 2 CRC bytes + 1 ACK
    uint8_t response[195];
    int received = receive_bytes(response, 195, 500000);  // 500ms timeout

    printf("Received %d bytes\n", received);

    if (received < 195) {
        printf("\n*** Incomplete response ***\n");
        printf("Expected 195 bytes, got %d\n", received);

        // Print what we got
        if (received > 0) {
            printf("Raw data: ");
            for (int i = 0; i < received && i < 32; i++) {
                printf("%02X ", response[i]);
            }
            printf("\n");
        }

        gpio_put(LED_PIN, 0);
        while (1) sleep_ms(1000);
    }

    // Verify CRC
    uint8_t* settings = response;
    uint16_t recv_crc = response[192] | (response[193] << 8);
    uint8_t final_ack = response[194];
    uint16_t calc_crc = crc16(settings, 192);

    printf("CRC: recv=0x%04X calc=0x%04X %s\n", recv_crc, calc_crc,
           recv_crc == calc_crc ? "(OK)" : "(MISMATCH)");
    printf("Final ACK: 0x%02X %s\n", final_ack, final_ack == ACK_OK ? "(OK)" : "(FAIL)");

    if (recv_crc != calc_crc || final_ack != ACK_OK) {
        printf("\n*** CRC or ACK failed ***\n");
        gpio_put(LED_PIN, 0);
        while (1) sleep_ms(1000);
    }

    // Dump all bytes for analysis
    printf("\n========================================\n");
    printf("  Raw EEPROM Dump (192 bytes)\n");
    printf("========================================\n\n");

    for (int row = 0; row < 12; row++) {
        printf("%3d: ", row * 16);
        for (int col = 0; col < 16; col++) {
            printf("%02X ", settings[row * 16 + col]);
        }
        printf("\n");
    }

    // Parse and display settings
    printf("\n========================================\n");
    printf("  ESC Settings (using AM32 offsets)\n");
    printf("========================================\n\n");

    printf("EEPROM Version:    %d\n", settings[1]);
    printf("FW Version:        %d.%d\n", settings[3], settings[4]);
    printf("Dir Reversed:      %d\n", settings[17]);
    printf("Bidirectional:     %d %s\n", settings[18], settings[18] ? "(3D MODE!)" : "");
    printf("Advance Level:     %d\n", settings[23]);
    printf("PWM Frequency:     %d kHz\n", settings[24]);
    printf("Startup Power:     %d\n", settings[25]);
    printf("Motor KV:          %d\n", settings[26]);
    printf("Motor Poles:       %d\n", settings[27]);

    // Check for issues
    printf("\n=== Potential Issues ===\n");
    if (settings[18]) {
        printf("*** 3D/BIDIRECTIONAL MODE IS ON ***\n");
        printf("    This expects 1500us = stop!\n");
    }

    printf("\n========================================\n");
    printf("Settings read complete!\n");
    printf("========================================\n");

    gpio_put(LED_PIN, 0);

    // Blink LED to indicate success
    while (1) {
        gpio_put(LED_PIN, 1);
        sleep_ms(100);
        gpio_put(LED_PIN, 0);
        sleep_ms(100);
        gpio_put(LED_PIN, 1);
        sleep_ms(100);
        gpio_put(LED_PIN, 0);
        sleep_ms(700);
    }

    return 0;
}
