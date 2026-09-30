#ifndef AM32_BOOTLOADER_H
#define AM32_BOOTLOADER_H

/**
 * AM32 ESC Bootloader Configuration Management
 *
 * This library communicates with AM32 ESCs in bootloader mode to read/write
 * the full 192-byte EEPROM configuration. Uses bit-banged half-duplex UART
 * on the signal pin (GP4) with CRC-16 (polynomial 0xA001).
 *
 * IMPORTANT: ESC must be in bootloader mode (signal HIGH during power cycle)
 *
 * Based on working code from phase6_am32_config.c
 */

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

// EEPROM size for AM32 ESC
#define AM32_EEPROM_SIZE 192
#define AM32_DEVICE_INFO_SIZE 9
#define AM32_FILE_NAME_SIZE 32

// Error codes
typedef enum {
    AM32_OK = 0,
    AM32_ERR_TIMEOUT,
    AM32_ERR_CRC,
    AM32_ERR_ACK,
    AM32_ERR_NOT_IN_BOOTLOADER,
    AM32_ERR_WRITE_FAILED,
    AM32_ERR_VERIFY_FAILED
} am32_bootloader_error_t;

// EEPROM field offsets (from AM32 eeprom.h)
#define AM32_OFF_RESERVED_0             0
#define AM32_OFF_EEPROM_VERSION         1
#define AM32_OFF_RESERVED_1             2
#define AM32_OFF_FW_VERSION_MAJOR       3
#define AM32_OFF_FW_VERSION_MINOR       4
#define AM32_OFF_MAX_RAMP               5
#define AM32_OFF_MIN_DUTY_CYCLE         6
#define AM32_OFF_DISABLE_STICK_CAL      7
#define AM32_OFF_ABS_VOLTAGE_CUTOFF     8
#define AM32_OFF_CURRENT_P              9
#define AM32_OFF_CURRENT_I              10
#define AM32_OFF_CURRENT_D              11
#define AM32_OFF_ACTIVE_BRAKE_POWER     12
#define AM32_OFF_RESERVED_3             13  // 13-16 reserved
#define AM32_OFF_DIR_REVERSED           17
#define AM32_OFF_BIDIRECTIONAL          18
#define AM32_OFF_USE_SINE_START         19
#define AM32_OFF_COMP_PWM               20
#define AM32_OFF_VARIABLE_PWM           21
#define AM32_OFF_STUCK_ROTOR_PROT       22
#define AM32_OFF_ADVANCE_LEVEL          23
#define AM32_OFF_PWM_FREQUENCY          24
#define AM32_OFF_STARTUP_POWER          25
#define AM32_OFF_MOTOR_KV               26
#define AM32_OFF_MOTOR_POLES            27
#define AM32_OFF_BRAKE_ON_STOP          28
#define AM32_OFF_STALL_PROTECTION       29
#define AM32_OFF_BEEP_VOLUME            30
#define AM32_OFF_TELEMETRY_INTERVAL     31
#define AM32_OFF_SERVO_LOW              32
#define AM32_OFF_SERVO_HIGH             33
#define AM32_OFF_SERVO_NEUTRAL          34
#define AM32_OFF_SERVO_DEADBAND         35
#define AM32_OFF_LOW_VOLTAGE_CUTOFF     36
#define AM32_OFF_LOW_CELL_VOLT_CUTOFF   37
#define AM32_OFF_RC_CAR_REVERSE         38
#define AM32_OFF_USE_HALL_SENSORS       39
#define AM32_OFF_SINE_MODE_CHANGEOVER   40
#define AM32_OFF_DRAG_BRAKE_STRENGTH    41
#define AM32_OFF_DRIVING_BRAKE_STRENGTH 42
#define AM32_OFF_TEMP_LIMIT             43
#define AM32_OFF_CURRENT_LIMIT          44
#define AM32_OFF_SINE_MODE_POWER        45
#define AM32_OFF_INPUT_TYPE             46
#define AM32_OFF_AUTO_ADVANCE           47
#define AM32_OFF_TUNE_ARRAY             48  // 48-175 (128 bytes)
#define AM32_OFF_CAN_NODE               176
#define AM32_OFF_ESC_INDEX              177
#define AM32_OFF_REQUIRE_ARMING         178
#define AM32_OFF_TELEM_RATE             179
#define AM32_OFF_REQUIRE_ZERO_THROTTLE  180
#define AM32_OFF_FILTER_HZ              181
#define AM32_OFF_DEBUG_RATE             182
#define AM32_OFF_TERM_ENABLE            183
// 184-191 reserved

/**
 * Initialize the AM32 bootloader communication GPIO
 * Sets up GP4 as the signal pin for bit-banged half-duplex UART
 */
void am32_bootloader_init(void);

/**
 * Drive the signal line HIGH using the bootloader PIO TX SM.
 * Keeps the line actively high between power cycles.
 */
void am32_bootloader_hold_high(void);

/**
 * Enter bootloader mode programmatically
 * Sends break condition and entry bytes - no power cycle needed
 *
 * @return AM32_OK on success, AM32_ERR_NOT_IN_BOOTLOADER on failure
 */
am32_bootloader_error_t am32_bootloader_enter(void);

/**
 * Read 192 bytes from ESC EEPROM
 * Call am32_bootloader_enter() first to enter bootloader mode
 *
 * @param buffer Output buffer for 192 bytes of config data
 * @return AM32_OK on success, error code on failure
 */
am32_bootloader_error_t am32_bootloader_read(uint8_t* buffer);

/**
 * Read bytes from a specific bootloader address.
 *
 * Address uses bootloader CMD_SET_ADDRESS semantics:
 * - magic values (0x20 eeprom, 0x21 filename, 0x22 continue) are supported
 * - raw word addresses are also supported
 *
 * @param address_word Address/magic value for CMD_SET_ADDRESS
 * @param out Output buffer
 * @param len Number of bytes to read (1..256)
 * @return AM32_OK on success
 */
am32_bootloader_error_t am32_bootloader_read_at(uint16_t address_word, uint8_t* out, uint16_t len);

/**
 * Write 192 bytes to ESC EEPROM
 * ESC must be in bootloader mode
 *
 * @param buffer Input buffer with 192 bytes of config data
 * @return AM32_OK on success, error code on failure
 */
am32_bootloader_error_t am32_bootloader_write(const uint8_t* buffer);

/**
 * Program a flash chunk at a specific address.
 *
 * Address uses bootloader CMD_SET_ADDRESS semantics (relative flash words).
 * Typical values are 0x1000+ for application firmware regions.
 *
 * @param address_word Address value for CMD_SET_ADDRESS
 * @param data Chunk payload to write
 * @param len Chunk size (1..256 bytes)
 * @return AM32_OK on success
 */
am32_bootloader_error_t am32_bootloader_program_flash(uint16_t address_word, const uint8_t* data, uint16_t len);

/**
 * Compare two configs and generate a diff mask
 *
 * @param current Current config read from ESC (192 bytes)
 * @param desired Desired config (192 bytes)
 * @param diff_mask Output: 1 for each byte that differs, 0 otherwise (192 bytes)
 * @return Number of bytes that differ
 */
uint16_t am32_bootloader_diff(const uint8_t* current, const uint8_t* desired, uint8_t* diff_mask);

/**
 * Print full parsed config to serial
 *
 * @param config Config data (192 bytes)
 */
void am32_bootloader_print(const uint8_t* config);

/**
 * Main config validation function for startup
 *
 * 1. Attempts to read ESC config (with timeout)
 * 2. If no response: prints warning and returns (ESC not in bootloader mode)
 * 3. If read succeeds: compares all 192 bytes with desired
 * 4. If different: prints which fields differ, writes new config, verifies write
 * 5. Prints final config
 *
 * @param desired Desired configuration (192 bytes)
 * @return AM32_OK if config matches or was successfully updated, error code otherwise
 */
am32_bootloader_error_t am32_bootloader_validate_and_update(const uint8_t* desired);

/**
 * Exit bootloader mode and run main firmware
 * Sends CMD_RUN (0x00) to ESC
 */
void am32_bootloader_run(void);

/**
 * Get cached bootloader device info from the BLHeli init handshake.
 *
 * Bytes are: {'4','7','1', pin_code, flash_size_code, 0x06, 0x06, proto_ver, 0x30}
 *
 * @param out Output 9-byte buffer
 * @return true if device info has been captured
 */
bool am32_bootloader_get_device_info(uint8_t out[AM32_DEVICE_INFO_SIZE]);

/**
 * Read firmware FILE_NAME region from bootloader address magic 0x21.
 *
 * @param out Output string buffer
 * @param out_len Output buffer length
 * @return AM32_OK on success
 */
am32_bootloader_error_t am32_bootloader_read_filename(char* out, size_t out_len);

/**
 * Get human-readable error string
 */
const char* am32_bootloader_error_str(am32_bootloader_error_t err);

/**
 * Get the baud rate that last produced a valid bootloader handshake.
 *
 * @return 0 if no successful handshake has occurred yet
 */
uint32_t am32_bootloader_get_last_baud(void);

#endif // AM32_BOOTLOADER_H
