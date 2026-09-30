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
#include "hardware/sync.h"

// One-wire half-duplex UART on signal pin
#define AM32_PIN 4

static bool io_initialized = false;
static uint32_t bittime_us = 52u;
static uint32_t halfbit_us = 26u;
static uint32_t last_handshake_baud = 0;

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
#define ADDRESS_MAGIC_EEPROM 0x20
#define ADDRESS_MAGIC_FILE_NAME 0x21
#define BLHELI_INIT_SCAN_BYTES 64
#define FILE_NAME_FALLBACK_ADDRESS (EEPROM_ADDRESS - AM32_FILE_NAME_SIZE)

// Timeouts
#define TIMEOUT_ADDRESS_US  100000   // 100ms for address set
#define TIMEOUT_READ_US     500000   // 500ms for data read
#define TIMEOUT_WRITE_US    500000   // 500ms for write
#define AUTO_ENTRY_RETRIES  6
#define AUTO_ENTRY_LOW_MS   2600     // Some firmwares reset more reliably with sustained LOW
#define AUTO_ENTRY_RECOVER_MS 300
#define INIT_PROBE_WINDOW_MS 700
#define INIT_SHORT_RESPONSE_TIMEOUT_US 20000
#define INIT_INTER_BURST_DELAY_MS 2
#define CONFIG_ENTRY_PULSE_US   100
#define CONFIG_ENTRY_GAP_US     900
#define CONFIG_ENTRY_PULSES     10
#define CONFIG_ENTRY_SETTLE_MS  300

static const uint32_t bootloader_baud_candidates[] = {19200u, 38400u, 57600u, 115200u};
static const uint32_t auto_entry_high_idle_ms[] = {3000u, 5000u, 8000u, 12000u, 16000u, 20000u};

static bool bootloader_device_info_valid = false;
static uint8_t bootloader_device_info[AM32_DEVICE_INFO_SIZE];

static bool bootloader_supports_magic_address(void) {
    // Protocol v2+ supports ADDRESS_MAGIC_EEPROM / ADDRESS_MAGIC_FILE_NAME.
    return bootloader_device_info_valid && bootloader_device_info[7] >= 2;
}

static void am32_set_timing_for_baud(uint32_t baud) {
    if (baud == 0) {
        baud = 19200;
    }
    // Round to nearest microsecond.
    bittime_us = (1000000u + (baud / 2u)) / baud;
    if (bittime_us == 0) {
        bittime_us = 1;
    }
    halfbit_us = bittime_us / 2u;
    if (halfbit_us == 0) {
        halfbit_us = 1;
    }
}

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

static inline void line_drive_low(void) {
    gpio_set_dir(AM32_PIN, GPIO_OUT);
    gpio_put(AM32_PIN, 0);
}

static inline void line_drive_high(void) {
    gpio_set_dir(AM32_PIN, GPIO_OUT);
    gpio_put(AM32_PIN, 1);
}

static inline void line_release_high(void) {
    // one-wire open-drain high: input with pull-up
    gpio_set_dir(AM32_PIN, GPIO_IN);
    gpio_pull_up(AM32_PIN);
}

static void switch_to_tx_mode(void) {
    line_drive_high();
}

static void switch_to_rx_mode(void) {
    line_release_high();
}

static void bb_tx_byte(uint8_t byte) {
    // Keep bit timing deterministic.
    uint32_t irq_state = save_and_disable_interrupts();

    // Start bit.
    line_drive_low();
    busy_wait_us_32(bittime_us);

    // Data bits, LSB first.
    for (int i = 0; i < 8; i++) {
        if ((byte >> i) & 1u) {
            line_drive_high();
        } else {
            line_drive_low();
        }
        busy_wait_us_32(bittime_us);
    }

    // Stop bit.
    line_drive_high();
    busy_wait_us_32(bittime_us);

    restore_interrupts(irq_state);
}

static int bb_rx_byte(uint32_t timeout_us) {
    line_release_high();

    uint32_t start = time_us_32();

    // Require a true UART idle-high period first. This filters out
    // "line stuck low" cases that previously produced false 0x00 bytes.
    while (!gpio_get(AM32_PIN)) {
        if ((time_us_32() - start) > timeout_us) {
            return -1;
        }
        tight_loop_contents();
    }

    // Wait for start bit (falling edge).
    while (gpio_get(AM32_PIN)) {
        if ((time_us_32() - start) > timeout_us) {
            return -1;
        }
        tight_loop_contents();
    }

    uint32_t irq_state = save_and_disable_interrupts();

    // Confirm we're in the middle of a low start bit.
    busy_wait_us_32(halfbit_us);
    if (gpio_get(AM32_PIN)) {
        restore_interrupts(irq_state);
        return -2;  // start-bit framing error
    }

    uint8_t byte = 0;
    for (int i = 0; i < 8; i++) {
        // Sample each bit at its midpoint.
        busy_wait_us_32(bittime_us);
        if (gpio_get(AM32_PIN)) {
            byte |= (uint8_t)(1u << i);
        }
    }

    // Stop bit midpoint.
    busy_wait_us_32(bittime_us);
    bool stop_bit_high = gpio_get(AM32_PIN);
    restore_interrupts(irq_state);
    if (!stop_bit_high) {
        return -3;  // stop-bit framing error
    }

    return byte;
}

// Returns first valid byte or -1 on timeout.
static int rx_valid_byte(uint32_t timeout_us) {
    uint32_t start = time_us_32();
    while ((time_us_32() - start) <= timeout_us) {
        uint32_t remain = timeout_us - (time_us_32() - start);
        int b = bb_rx_byte(remain);
        if (b >= 0) {
            return b;
        }
        if (b == -1) {
            return -1;
        }
        // framing error: keep scanning until timeout
    }
    return -1;
}

static void drain_rx_quick(uint32_t budget_us) {
    uint32_t start = time_us_32();
    while ((time_us_32() - start) < budget_us) {
        int b = bb_rx_byte(200);
        if (b < 0) {
            break;
        }
    }
}

static void send_with_crc(const uint8_t* data, uint16_t len) {
    uint16_t crc = crc16(data, len);

    drain_rx_quick(2000);
    switch_to_tx_mode();
    for (uint16_t i = 0; i < len; i++) {
        bb_tx_byte(data[i]);
    }
    bb_tx_byte(crc & 0xFF);
    bb_tx_byte((crc >> 8) & 0xFF);

    switch_to_rx_mode();
}

// Receive multiple bytes
static int receive_bytes(uint8_t* buf, uint16_t len, uint32_t timeout_us) {
    uint32_t start = time_us_32();
    for (uint16_t i = 0; i < len; i++) {
        uint32_t elapsed = time_us_32() - start;
        if (elapsed >= timeout_us) {
            return i;
        }
        int b = rx_valid_byte(timeout_us - elapsed);
        if (b < 0) {
            return i;
        }
        buf[i] = b;
    }
    return len;
}

static bool is_keepalive_response(int ack) {
    // AM32 bootloader responds to CMD_KEEP_ALIVE with 0xC1.
    // Some variants can reply 0x30, so accept both.
    return ack == NACK_CMD || ack == ACK_OK;
}

static bool capture_device_info_from_stream(const uint8_t* data, int len) {
    if (!data || len < AM32_DEVICE_INFO_SIZE) {
        return false;
    }

    for (int i = 0; i <= (len - AM32_DEVICE_INFO_SIZE); i++) {
        if (data[i] == '4' &&
            data[i + 1] == '7' &&
            data[i + 2] == '1' &&
            data[i + 8] == ACK_OK) {
            memcpy(bootloader_device_info, &data[i], AM32_DEVICE_INFO_SIZE);
            bootloader_device_info_valid = true;
            return true;
        }
    }

    return false;
}

static void send_blheli_init_sequence(void) {
    // Bootloader scans stream for 0x0D,'B' and matching CRC trailer.
    static const uint8_t init_seq[] = {
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x0D, 0x42, 0x4C, 0x48,
        0x65, 0x6C, 0x69, 0xF4, 0x7D
    };

    switch_to_tx_mode();
    for (size_t i = 0; i < sizeof(init_seq); i++) {
        bb_tx_byte(init_seq[i]);
    }
    switch_to_rx_mode();
}

static void send_config_entry_signal(void) {
    // Match AM32 config-mode entry: 10x (100us low + 900us high) pulses.
    switch_to_tx_mode();
    for (int i = 0; i < CONFIG_ENTRY_PULSES; i++) {
        line_drive_low();
        sleep_us(CONFIG_ENTRY_PULSE_US);
        line_drive_high();
        sleep_us(CONFIG_ENTRY_GAP_US);
    }
    switch_to_rx_mode();
    sleep_ms(CONFIG_ENTRY_SETTLE_MS);
}

static void send_config_frame_xor(uint8_t cmd, const uint8_t* payload, uint16_t len) {
    uint8_t checksum = cmd ^ (uint8_t)(len & 0xFFu) ^ (uint8_t)(len >> 8);
    switch_to_tx_mode();
    bb_tx_byte(cmd);
    bb_tx_byte((uint8_t)(len & 0xFFu));
    bb_tx_byte((uint8_t)(len >> 8));
    for (uint16_t i = 0; i < len; i++) {
        uint8_t b = payload ? payload[i] : 0;
        bb_tx_byte(b);
        checksum ^= b;
    }
    bb_tx_byte(checksum);
    switch_to_rx_mode();
}

static bool read_config_response(uint8_t* out, uint16_t* inout_len, uint32_t timeout_us) {
    if (!out || !inout_len || *inout_len == 0) {
        return false;
    }

    int h0 = rx_valid_byte(timeout_us);
    if (h0 < 0) {
        return false;
    }
    int h1 = rx_valid_byte(timeout_us);
    if (h1 < 0) {
        return false;
    }
    uint16_t expected_len = (uint16_t)((uint16_t)h0 | ((uint16_t)h1 << 8));
    if (expected_len == 0) {
        *inout_len = 0;
        return true;
    }
    if (expected_len > *inout_len) {
        return false;
    }

    uint32_t start = time_us_32();
    for (uint16_t i = 0; i < expected_len; i++) {
        uint32_t elapsed = time_us_32() - start;
        if (elapsed >= timeout_us) {
            return false;
        }
        int b = rx_valid_byte(timeout_us - elapsed);
        if (b < 0) {
            return false;
        }
        out[i] = (uint8_t)b;
    }
    *inout_len = expected_len;
    return true;
}

static bool trigger_bootloader_via_config_mode(void) {
    // AM32 config protocol commands (XOR framed).
    const uint8_t CMD_KEEPALIVE_CFG = 0xFF;
    const uint8_t CMD_GET_INFO_CFG = 0xCC;
    const uint8_t CMD_BOOTLOADER_CFG = 0xEE;

    printf("Fallback: entering AM32 config mode via pulse sequence...\n");
    send_config_entry_signal();

    uint8_t resp[64] = {0};
    uint16_t resp_len = sizeof(resp);

    bool link_ok = false;
    send_config_frame_xor(CMD_KEEPALIVE_CFG, NULL, 0);
    (void)read_config_response(resp, &resp_len, 200000);

    resp_len = sizeof(resp);
    send_config_frame_xor(CMD_GET_INFO_CFG, NULL, 0);
    if (read_config_response(resp, &resp_len, 200000) && resp_len >= 4) {
        if (!(resp[0] == 0 && resp[1] == 0 && resp[2] == 0)) {
            link_ok = true;
        }
    }

    if (!link_ok) {
        printf("Fallback: config link failed\n");
        return false;
    }

    printf("Fallback: config link OK, sending bootloader command 0xEE\n");
    send_config_frame_xor(CMD_BOOTLOADER_CFG, NULL, 0);
    sleep_ms(300);
    return true;
}

static am32_bootloader_error_t am32_set_address(uint16_t address_word) {
    uint8_t set_addr[] = {
        CMD_SET_ADDRESS,
        0x00,
        (uint8_t)((address_word >> 8) & 0xFF),
        (uint8_t)(address_word & 0xFF)
    };
    send_with_crc(set_addr, sizeof(set_addr));

    int ack = rx_valid_byte(TIMEOUT_ADDRESS_US);
    if (ack != ACK_OK) {
        return AM32_ERR_NOT_IN_BOOTLOADER;
    }
    return AM32_OK;
}

static am32_bootloader_error_t am32_set_eeprom_address(void) {
    am32_bootloader_error_t err = am32_set_address(ADDRESS_MAGIC_EEPROM);
    if (err == AM32_OK) {
        return AM32_OK;
    }
    return am32_set_address(EEPROM_ADDRESS);
}

static am32_bootloader_error_t am32_set_filename_address(void) {
    am32_bootloader_error_t err = am32_set_address(ADDRESS_MAGIC_FILE_NAME);
    if (err == AM32_OK) {
        return AM32_OK;
    }
    return am32_set_address(FILE_NAME_FALLBACK_ADDRESS);
}

static am32_bootloader_error_t am32_read_flash_sil(uint8_t* out, uint16_t len) {
    if (!out || len == 0 || len > 256) {
        return AM32_ERR_ACK;
    }

    uint8_t read_cmd[] = {
        CMD_READ_FLASH_SIL,
        (len == 256) ? 0 : (uint8_t)len
    };
    send_with_crc(read_cmd, sizeof(read_cmd));

    const uint16_t response_len = len + 3;  // data + crc16 + final ack
    uint8_t response[259] = {0};
    int received = receive_bytes(response, response_len, TIMEOUT_READ_US);
    if (received < response_len) {
        return AM32_ERR_TIMEOUT;
    }

    uint16_t recv_crc = response[len] | (response[len + 1] << 8);
    uint8_t final_ack = response[len + 2];
    uint16_t calc_crc = crc16(response, len);

    if (recv_crc != calc_crc) {
        return AM32_ERR_CRC;
    }
    if (final_ack != ACK_OK) {
        return AM32_ERR_ACK;
    }

    memcpy(out, response, len);
    return AM32_OK;
}

static am32_bootloader_error_t am32_set_buffer_size(uint16_t len) {
    if (len == 0 || len > 256) {
        return AM32_ERR_ACK;
    }

    uint8_t set_buf[] = {
        CMD_SET_BUFFER,
        0x00,
        (len == 256) ? 0x01 : 0x00,
        (len == 256) ? 0x00 : (uint8_t)len
    };
    send_with_crc(set_buf, sizeof(set_buf));
    // Bootloader does not ACK CMD_SET_BUFFER directly.
    return AM32_OK;
}

// After a rejected or unanswered payload the bootloader can still be waiting
// for payload bytes, and would swallow (and ACK) the next command frame as
// data.  A KEEP_ALIVE frame resynchronises it: 0x30 means it was taken as
// the pending payload, 0xC1 means the bootloader was already in command mode.
static void am32_resync_after_payload_error(void) {
    uint8_t keep_alive[] = {CMD_KEEP_ALIVE};
    send_with_crc(keep_alive, sizeof(keep_alive));
    int ack = rx_valid_byte(TIMEOUT_WRITE_US);
    printf("AM32 resync after payload error: reply=%d (%s)\n", ack,
           ack == ACK_OK ? "swallowed as payload" : ack == NACK_CMD ? "command mode" : "no reply");
}

static am32_bootloader_error_t am32_send_payload_buffer(const uint8_t* data, uint16_t len) {
    if (!data || len == 0 || len > 256) {
        return AM32_ERR_ACK;
    }

    send_with_crc(data, len);
    int ack = rx_valid_byte(TIMEOUT_WRITE_US);
    if (ack != ACK_OK) {
        am32_resync_after_payload_error();
        return AM32_ERR_WRITE_FAILED;
    }
    return AM32_OK;
}

void am32_bootloader_init(void) {
    if (io_initialized) {
        return;
    }
    gpio_init(AM32_PIN);
    gpio_set_function(AM32_PIN, GPIO_FUNC_SIO);
    am32_set_timing_for_baud(19200u);
    line_release_high();
    io_initialized = true;
}

void am32_bootloader_hold_high(void) {
    am32_bootloader_init();
    line_drive_high();
}

// Enter bootloader mode programmatically (no power cycle needed)
// 1. Hold signal HIGH (UART idle) to stop DShot
// 2. Wait for firmware timeout (~2.5s) which triggers software reset
// 3. Bootloader sees HIGH signal and stays active
// 4. Send BLHeli init sequence
am32_bootloader_error_t am32_bootloader_enter(void) {
    bootloader_device_info_valid = false;

    uint8_t keep_alive[] = {CMD_KEEP_ALIVE};
    uint8_t response[BLHELI_INIT_SCAN_BYTES] = {0};
    bool tried_config_bootloader = false;

    // Match web configurator flow for direct adapters:
    // 1) hold line high and quiet long enough for firmware timeout reset
    // 2) send BLHeli preamble and parse device info.
    for (int attempt = 0; attempt < AUTO_ENTRY_RETRIES; attempt++) {
        memset(response, 0, sizeof(response));
        // Try both reset polarities:
        // - HIGH idle is the standard AM32 software-reset path.
        // - LOW idle fallback catches variants that won't timeout while line is held high.
        if (attempt == 2 || attempt == 5) {
            printf("Auto-entry attempt %d/%d: low-idle %ums then recover high %ums...\n",
                   attempt + 1, AUTO_ENTRY_RETRIES, AUTO_ENTRY_LOW_MS, AUTO_ENTRY_RECOVER_MS);
            line_drive_low();
            sleep_ms(AUTO_ENTRY_LOW_MS);
            am32_bootloader_hold_high();
            sleep_ms(AUTO_ENTRY_RECOVER_MS);
        } else {
            am32_bootloader_hold_high();
            uint32_t quiet_ms = auto_entry_high_idle_ms[attempt < AUTO_ENTRY_RETRIES ? attempt : 0];
            printf("Auto-entry attempt %d/%d: high-idle %lums...\n",
                   attempt + 1, AUTO_ENTRY_RETRIES, quiet_ms);
            sleep_ms(quiet_ms);
        }

        for (size_t bi = 0; bi < (sizeof(bootloader_baud_candidates) / sizeof(bootloader_baud_candidates[0])); bi++) {
            const uint32_t baud = bootloader_baud_candidates[bi];
            am32_set_timing_for_baud(baud);

            switch_to_rx_mode();
            sleep_us(100);
            int level_before = gpio_get(AM32_PIN) ? 1 : 0;
            printf("Line level before BLHeli init @%lu: %d\n", baud, level_before);

            uint32_t probe_start = to_ms_since_boot(get_absolute_time());
            uint32_t bursts = 0;
            bool saw_any_data = false;

            while ((to_ms_since_boot(get_absolute_time()) - probe_start) < INIT_PROBE_WINDOW_MS) {
                memset(response, 0, sizeof(response));
                send_blheli_init_sequence();
                // Sweep short guard offsets across bursts to avoid phase-locking
                // on a truncated response boundary.
                uint32_t guard_bits = 1u + (bursts % 6u);
                sleep_us(bittime_us * guard_bits);

                int received = receive_bytes(response, BLHELI_INIT_SCAN_BYTES, INIT_SHORT_RESPONSE_TIMEOUT_US);
                if (received > 0) {
                    saw_any_data = true;
                    printf("BLHeli init response @%lu: %d bytes\n", baud, received);
                    printf("Data @%lu: ", baud);
                    for (int i = 0; i < received && i < BLHELI_INIT_SCAN_BYTES; i++) {
                        printf("%02X ", response[i]);
                    }
                    printf("\n");
                }

                if (capture_device_info_from_stream(response, received)) {
                    last_handshake_baud = baud;
                    printf("ESC in bootloader mode (device info captured @%lu)\n", baud);
                    return AM32_OK;
                }

                // Some boards may not emit device info every attempt; keepalive still proves liveness.
                send_with_crc(keep_alive, 1);
                int ack = rx_valid_byte(INIT_SHORT_RESPONSE_TIMEOUT_US);
                if (is_keepalive_response(ack)) {
                    last_handshake_baud = baud;
                    printf("ESC in bootloader mode (keepalive response @%lu)\n", baud);
                    return AM32_OK;
                }

                bursts++;
                sleep_ms(INIT_INTER_BURST_DELAY_MS);
            }

            int level_after = gpio_get(AM32_PIN) ? 1 : 0;
            printf("Line level after BLHeli probe window @%lu: %d (bursts=%lu, data=%s)\n",
                   baud, level_after, bursts, saw_any_data ? "yes" : "no");
        }

        if (!tried_config_bootloader && attempt >= 1) {
            tried_config_bootloader = true;
            if (trigger_bootloader_via_config_mode()) {
                printf("Fallback bootloader request sent, retrying BLHeli init\n");
            }
        }
    }

    printf("ESC not in bootloader mode.\n");
    printf("If ESC is powered, verify one-wire wiring and that line idles high.\n");
    return AM32_ERR_NOT_IN_BOOTLOADER;
}

am32_bootloader_error_t am32_bootloader_read(uint8_t* buffer) {
    if (!buffer) {
        return AM32_ERR_NOT_IN_BOOTLOADER;
    }

    return am32_bootloader_read_at(ADDRESS_MAGIC_EEPROM, buffer, AM32_EEPROM_SIZE);
}

am32_bootloader_error_t am32_bootloader_read_at(uint16_t address_word, uint8_t* out, uint16_t len) {
    if (!out || len == 0 || len > 256) {
        return AM32_ERR_ACK;
    }
    am32_bootloader_error_t err = AM32_ERR_NOT_IN_BOOTLOADER;

    if (address_word == ADDRESS_MAGIC_EEPROM && !bootloader_supports_magic_address()) {
        err = am32_set_address(EEPROM_ADDRESS);
    } else if (address_word == ADDRESS_MAGIC_FILE_NAME && !bootloader_supports_magic_address()) {
        err = am32_set_address(FILE_NAME_FALLBACK_ADDRESS);
    } else {
        err = am32_set_address(address_word);
    }

    if (err != AM32_OK && address_word == ADDRESS_MAGIC_EEPROM) {
        // Fallback for older bootloaders or ambiguous ACKs.
        err = am32_set_address(EEPROM_ADDRESS);
    } else if (err != AM32_OK && address_word == ADDRESS_MAGIC_FILE_NAME) {
        err = am32_set_address(FILE_NAME_FALLBACK_ADDRESS);
    }
    if (err != AM32_OK) {
        return err;
    }
    return am32_read_flash_sil(out, len);
}

am32_bootloader_error_t am32_bootloader_program_flash(uint16_t address_word, const uint8_t* data, uint16_t len) {
    if (!data || len == 0 || len > 256) {
        return AM32_ERR_ACK;
    }

    am32_bootloader_error_t err = am32_set_address(address_word);
    if (err != AM32_OK) {
        return err;
    }

    err = am32_set_buffer_size(len);
    if (err != AM32_OK) {
        return err;
    }

    err = am32_send_payload_buffer(data, len);
    if (err != AM32_OK) {
        return err;
    }

    // Program payload to flash at the address set above.
    uint8_t prog_cmd[] = {
        CMD_PROG_FLASH,
        0x01
    };
    send_with_crc(prog_cmd, sizeof(prog_cmd));

    int ack = rx_valid_byte(TIMEOUT_WRITE_US);
    if (ack != ACK_OK) {
        return AM32_ERR_WRITE_FAILED;
    }
    return AM32_OK;
}

am32_bootloader_error_t am32_bootloader_write(const uint8_t* buffer) {
    if (!buffer) {
        return AM32_ERR_NOT_IN_BOOTLOADER;
    }

    am32_bootloader_error_t err = am32_set_eeprom_address();
    if (err != AM32_OK) {
        return err;
    }

    // Send EEPROM data using CMD_PROG_EEPROM.
    uint8_t write_buffer[2 + AM32_EEPROM_SIZE];
    write_buffer[0] = CMD_PROG_EEPROM;
    write_buffer[1] = AM32_EEPROM_SIZE;
    memcpy(&write_buffer[2], buffer, AM32_EEPROM_SIZE);
    send_with_crc(write_buffer, sizeof(write_buffer));

    int ack = rx_valid_byte(TIMEOUT_WRITE_US);
    if (ack != ACK_OK) {
        return AM32_ERR_WRITE_FAILED;
    }

    return AM32_OK;
}

bool am32_bootloader_get_device_info(uint8_t out[AM32_DEVICE_INFO_SIZE]) {
    if (!out || !bootloader_device_info_valid) {
        return false;
    }
    memcpy(out, bootloader_device_info, AM32_DEVICE_INFO_SIZE);
    return true;
}

am32_bootloader_error_t am32_bootloader_read_filename(char* out, size_t out_len) {
    if (!out || out_len == 0) {
        return AM32_ERR_ACK;
    }

    out[0] = '\0';

    uint8_t raw_name[AM32_FILE_NAME_SIZE] = {0};
    am32_bootloader_error_t err = am32_bootloader_read_at(ADDRESS_MAGIC_FILE_NAME, raw_name, AM32_FILE_NAME_SIZE);
    if (err != AM32_OK) {
        return err;
    }

    size_t n = 0;
    while (n < AM32_FILE_NAME_SIZE && n < (out_len - 1)) {
        uint8_t c = raw_name[n];
        if (c == 0x00 || c == 0xFF) {
            break;
        }
        out[n] = (c >= 0x20 && c <= 0x7E) ? (char)c : '?';
        n++;
    }
    out[n] = '\0';

    if (n == 0 && out_len >= 8) {
        memcpy(out, "<empty>", 8);
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

uint32_t am32_bootloader_get_last_baud(void) {
    return last_handshake_baud;
}
