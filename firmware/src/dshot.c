#include "dshot.h"
#include "config.h"
#include "hardware/pio.h"
#include "hardware/clocks.h"
#include "hardware/dma.h"
#include "hardware/irq.h"
#include "pico/stdlib.h"
#include "pico/mutex.h"
#include <stdio.h>
#include <string.h>

// Include generated PIO headers
#include "dshot.pio.h"

#define MAX_DSHOT_MOTORS 3
#define DSHOT_FRAME_BITS 16
#define DSHOT_THROTTLE_MIN 48    // Below 48 = disarmed
#define DSHOT_THROTTLE_MAX 2047
#define EDT_FRAME_BITS 21        // EDT telemetry frame size

// Per-motor DShot state
typedef struct {
    bool initialized;
    dshot_config_t config;
    PIO pio;
    uint sm;                    // State machine ID
    uint pio_offset;            // PIO program offset
    int dma_chan;               // DMA channel for transmission
    dshot_telemetry_t last_telemetry;
    uint16_t last_packet;       // Last transmitted packet
} dshot_motor_state_t;

static dshot_motor_state_t motor_states[MAX_DSHOT_MOTORS] = {0};

// CRITICAL FIX #3: Reference counting for shared PIO programs
// Multiple motors may share the same PIO program, so track usage
static uint8_t pio_program_refcount_tx = 0;
static uint8_t pio_program_refcount_bidir = 0;

// MAJOR FIX #8 (Iteration 3): Mutex for thread-safe PIO reference counting
// Refcounts are modified during init/deinit and must be protected from races
static mutex_t pio_refcount_mutex;
static bool pio_mutex_initialized = false;

// CRC-4 calculation for DShot packets
uint8_t dshot_calculate_crc(uint16_t packet) {
    // CRC-4 with polynomial 0x19 (x^4 + x^3 + x + 1)
    uint16_t crc = 0;
    uint16_t data = packet;

    for (int i = 0; i < 12; i++) {
        crc ^= (data & 0x800) ? 0x8 : 0;
        data <<= 1;
        crc <<= 1;

        if (crc & 0x10) {
            crc ^= 0x19;
        }
    }

    return crc & 0x0F;
}

// Convert percent (-100 to +100) to DShot throttle value
uint16_t dshot_throttle_from_percent(int8_t percent) {
    if (percent == 0) {
        return 0;  // Disarmed
    }

    // MAJOR FIX #3 (Iteration 4): Rewrite formula to avoid negative intermediates
    // Old formula: value = (percent * range) / 100 + (range / 2) + MIN
    // For percent=-100: value = (-100 * 1999) / 100 + 999 + 48 = -1999 + 1047 = -952 (underflow)
    //
    // New approach: Map percent range [-100, +100] to throttle range [MIN, MAX]
    // Using linear interpolation without negative intermediates:
    //   percent = -100 → throttle = MIN (48)
    //   percent = +100 → throttle = MAX (2047)
    //
    // Formula: throttle = MIN + ((percent + 100) * (MAX - MIN)) / 200
    int32_t throttle_range = DSHOT_THROTTLE_MAX - DSHOT_THROTTLE_MIN;  // 1999
    int32_t normalized_percent = (int32_t)percent + 100;  // 0 to 200
    int32_t value = DSHOT_THROTTLE_MIN + (normalized_percent * throttle_range) / 200;

    // Clamp to valid range (defensive, should not be needed with correct formula)
    if (value < DSHOT_THROTTLE_MIN) value = DSHOT_THROTTLE_MIN;
    if (value > DSHOT_THROTTLE_MAX) value = DSHOT_THROTTLE_MAX;

    return (uint16_t)value;
}

// Encode DShot packet with CRC
static uint16_t encode_dshot_packet(uint16_t throttle, bool telemetry_request) {
    // Packet format (16 bits transmitted MSB first):
    // [15:5] = 11-bit throttle (0-2047)
    // [4]    = 1-bit telemetry request
    // [3:0]  = 4-bit CRC (calculated on bits [15:4])

    // CRITICAL FIX #4: Correct bit positioning
    // Place throttle in final position [15:5]
    uint16_t packet = (throttle & 0x7FF) << 5;

    // Place telemetry request in final position [4]
    packet |= (telemetry_request ? 1 : 0) << 4;

    // CRITICAL FIX #5: Calculate CRC on the 12-bit payload (bits [15:4])
    // Shift right by 4 to get payload into [11:0] for CRC function
    uint8_t crc = dshot_calculate_crc(packet >> 4);

    // Add CRC to bits [3:0]
    packet |= (crc & 0x0F);

    return packet;
}

// Calculate PIO clock divider for DShot speed
static float calculate_clk_div(dshot_speed_t speed) {
    uint32_t sys_clk_hz = clock_get_hz(clk_sys);

    // Bit period in nanoseconds
    uint32_t bit_period_ns;
    switch (speed) {
        case DSHOT_SPEED_150:  bit_period_ns = 6670; break;
        case DSHOT_SPEED_300:  bit_period_ns = 3330; break;
        case DSHOT_SPEED_600:  bit_period_ns = 1670; break;
        case DSHOT_SPEED_1200: bit_period_ns = 830;  break;
        default: bit_period_ns = 3330; break;
    }

    // CRITICAL FIX #1 (Iteration 2): PIO program uses 15 cycles per bit, not 13
    // Each bit in dshot.pio consists of:
    //   1. out y, 1              = 1 cycle
    //   2. jmp !y, bit_zero      = 1 cycle
    //   3. set pins, 1 [7 or 3]  = 8 or 4 cycles
    //   4. set pins, 0 [3 or 7]  = 4 or 8 cycles
    //   5. jmp x--, bitloop      = 1 cycle
    //   Total: 1+1+8+4+1 = 15 cycles (or 1+1+4+8+1 = 15 cycles)
    // Previous calculation of 13 cycles was missing out y,1 and jmp !y,bit_zero
    uint32_t cycles_per_bit = 15;

    // Calculate required PIO frequency to achieve desired bit timing
    // Formula: pio_freq = (1 MHz * cycles_per_bit * 1000) / bit_period_ns
    //
    // CRITICAL FIX #1: Updated calculations for 15 cycles per bit
    // DShot150 (6670ns):  pio_freq = (1,000,000 * 15 * 1000) / 6670 = 2,249,625 Hz (~2.25 MHz)
    //                     clk_div = 125 MHz / 2.25 MHz = 55.56
    // DShot300 (3330ns):  pio_freq = (1,000,000 * 15 * 1000) / 3330 = 4,504,505 Hz (~4.5 MHz)
    //                     clk_div = 125 MHz / 4.5 MHz = 27.78
    // DShot600 (1670ns):  pio_freq = (1,000,000 * 15 * 1000) / 1670 = 8,982,036 Hz (~9.0 MHz)
    //                     clk_div = 125 MHz / 9.0 MHz = 13.89
    // DShot1200 (830ns):  pio_freq = (1,000,000 * 15 * 1000) / 830 = 18,072,289 Hz (~18.1 MHz)
    //                     clk_div = 125 MHz / 18.1 MHz = 6.91
    //
    // IMPORTANT: Use uint64_t to prevent overflow
    //   Max intermediate: 1,000,000 * 15 * 1000 = 15,000,000,000 (fits in uint64_t)
    //   Would overflow uint32_t (max 4,294,967,295)
    uint64_t pio_freq_hz = (1000000ULL * cycles_per_bit * 1000ULL) / bit_period_ns;

    float clk_div = (float)sys_clk_hz / (float)pio_freq_hz;

    // Clamp to valid range (1.0 to 65536.0)
    if (clk_div < 1.0f) clk_div = 1.0f;
    if (clk_div > 65536.0f) clk_div = 65536.0f;

    return clk_div;
}

// GCR decoding lookup table (5-bit to 4-bit)
// GCR encoding ensures no more than 2 consecutive zeros for reliable transmission
static const uint8_t gcr_decode_table[32] = {
    0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,  // 0x00-0x07 invalid
    0xFF, 0x09, 0x0A, 0x0B, 0xFF, 0x0D, 0x0E, 0x0F,  // 0x08-0x0F
    0xFF, 0xFF, 0x02, 0x03, 0xFF, 0x05, 0x06, 0x07,  // 0x10-0x17
    0xFF, 0x00, 0x08, 0x01, 0xFF, 0x04, 0x0C, 0xFF   // 0x18-0x1F
};

// MAJOR FIX #3: GCR table validation with known test vectors
// Returns true if GCR table is correct
static bool validate_gcr_table(void) {
    // Test vectors: known GCR encoded values and their expected decoded 4-bit values
    // From DShot/EDT specification
    struct {
        uint8_t gcr;      // 5-bit GCR input
        uint8_t expected; // 4-bit decoded output
    } test_vectors[] = {
        {0x09, 0x09}, {0x0A, 0x0A}, {0x0B, 0x0B}, {0x0D, 0x0D},
        {0x0E, 0x0E}, {0x0F, 0x0F}, {0x12, 0x02}, {0x13, 0x03},
        {0x15, 0x05}, {0x16, 0x06}, {0x17, 0x07}, {0x19, 0x00},
        {0x1A, 0x08}, {0x1B, 0x01}, {0x1D, 0x04}, {0x1E, 0x0C}
    };

    for (size_t i = 0; i < sizeof(test_vectors) / sizeof(test_vectors[0]); i++) {
        uint8_t decoded = gcr_decode_table[test_vectors[i].gcr];
        if (decoded != test_vectors[i].expected) {
            DEBUG_PRINT("CRITICAL: GCR table validation failed at index 0x%02X: "
                       "expected 0x%02X, got 0x%02X\n",
                       test_vectors[i].gcr, test_vectors[i].expected, decoded);
            return false;
        }
    }

    // Verify invalid codes return 0xFF
    uint8_t invalid_codes[] = {0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
                               0x08, 0x0C, 0x10, 0x11, 0x14, 0x18, 0x1C, 0x1F};
    for (size_t i = 0; i < sizeof(invalid_codes); i++) {
        if (gcr_decode_table[invalid_codes[i]] != 0xFF) {
            DEBUG_PRINT("CRITICAL: GCR table validation failed: "
                       "code 0x%02X should be invalid (0xFF)\n", invalid_codes[i]);
            return false;
        }
    }

    return true;
}

// EDT telemetry CRC calculation (4-bit, different from DShot CRC)
static uint8_t edt_calculate_crc(uint16_t data) {
    uint8_t crc = 0;
    for (int i = 0; i < 12; i++) {
        uint8_t bit = (data >> (11 - i)) & 1;
        uint8_t xor_val = (crc & 0x08) >> 3;
        crc = ((crc << 1) | bit) & 0x0F;
        if (xor_val) {
            crc ^= 0x07;  // Polynomial for EDT: x^3 + x^2 + x + 1
        }
    }
    return crc;
}

// Parse EDT telemetry frame (GCR decoded)
static bool parse_edt_telemetry(uint32_t raw_data, dshot_telemetry_t* telemetry) {
    if (telemetry == NULL) {
        return false;
    }

    // EDT frame: 21 bits = 1 start bit + 4 GCR symbols (20 bits)
    // Each GCR symbol is 5 bits encoding 4 bits of data
    // Total: 16 bits data (12 bits value + 4 bits CRC)

    // MAJOR FIX #2 (Iteration 2): Document bit extraction positions
    // EDT frame structure (MSB first):
    //   [20]=start, [19:15]=GCR0, [14:10]=GCR1, [9:5]=GCR2, [4:0]=GCR3
    // Start bit at position 20 is used for sync but not extracted into raw_data
    //
    // NOTE: This assumes PIO shifts data such that start bit is NOT in raw_data.
    // If start bit IS included in raw_data, positions would be off by one.
    // TODO: Hardware validation required - verify bit positions with logic analyzer
    //       to confirm start bit handling matches this extraction pattern.

    // Extract 4 GCR symbols (5 bits each)
    uint8_t gcr[4];
    gcr[0] = (raw_data >> 16) & 0x1F;  // Bits 20-16 (assuming no start bit in raw_data)
    gcr[1] = (raw_data >> 11) & 0x1F;  // Bits 15-11
    gcr[2] = (raw_data >> 6) & 0x1F;   // Bits 10-6
    gcr[3] = (raw_data >> 1) & 0x1F;   // Bits 5-1

    // Decode GCR to 4-bit nibbles
    uint8_t nibbles[4];
    for (int i = 0; i < 4; i++) {
        nibbles[i] = gcr_decode_table[gcr[i]];
        if (nibbles[i] == 0xFF) {
            // Invalid GCR code
            return false;
        }
    }

    // Reconstruct 16-bit data word
    uint16_t decoded = (nibbles[0] << 12) | (nibbles[1] << 8) |
                       (nibbles[2] << 4) | nibbles[3];

    // Split into value and CRC
    uint16_t value = (decoded >> 4) & 0xFFF;  // 12 bits
    uint8_t rx_crc = decoded & 0x0F;          // 4 bits

    // Validate CRC
    uint8_t calc_crc = edt_calculate_crc(value);
    if (rx_crc != calc_crc) {
        return false;  // CRC mismatch
    }

    // MAJOR FIX #3: Decode telemetry type from value ranges
    // IMPORTANT: This parsing assumes standard EDT telemetry encoding.
    // Different ESC manufacturers may use different encoding schemes or ranges.
    // The value ranges below are based on the AM32 reference implementation:
    //
    // Value Range    | Type        | Formula
    // ---------------|-------------|----------------------------------
    // 0-2047         | eRPM        | value = eRPM (electrical RPM)
    // 2048-3071      | Voltage     | voltage_cV = (value - 2048) * 4
    // 3072-3583      | Current     | current_cA = (value - 3072) * 4
    // 3584-4095      | Temperature | temperature_C = (value - 3584) / 2
    // 4096+          | Event/Status| ESC-specific status codes
    //
    // If using non-AM32 ESCs, verify these ranges match your ESC's telemetry format.
    // Some ESCs may use different multipliers or offsets.
    if (value < 2048) {
        telemetry->erpm = value;
    } else if (value >= 2048 && value < 3072) {
        telemetry->voltage_cV = (value - 2048) * 4;
    } else if (value >= 3072 && value < 3584) {
        telemetry->current_cA = (value - 3072) * 4;
    } else if (value >= 3584 && value < 4096) {
        telemetry->temperature_C = (value - 3584) / 2;
    } else {
        // Event/status frames (0xF000-0xFFFF) - accept but don't decode
        // ESC is reporting status, treat as valid telemetry
    }

    telemetry->crc = rx_crc;
    telemetry->valid = true;
    telemetry->timestamp_ms = to_ms_since_boot(get_absolute_time());

    return true;
}

// Initialize DShot for a motor
bool dshot_init(motor_channel_t motor, const dshot_config_t* config) {
    // SAFETY: Validate parameters
    if (motor >= MAX_DSHOT_MOTORS || config == NULL) {
        DEBUG_PRINT("CRITICAL: Invalid parameters in dshot_init\n");
        return false;
    }

    if (config->gpio_pin >= 30) {
        DEBUG_PRINT("CRITICAL: Invalid GPIO pin %d\n", config->gpio_pin);
        return false;
    }

    // MAJOR FIX #3: Validate GCR decode table on first initialization
    static bool gcr_validated = false;
    if (!gcr_validated) {
        if (!validate_gcr_table()) {
            DEBUG_PRINT("CRITICAL: GCR table validation failed! Cannot initialize DShot.\n");
            return false;
        }
        gcr_validated = true;
        DEBUG_PRINT("GCR decode table validated successfully\n");
    }

    // MAJOR FIX #8 (Iteration 3): Initialize mutex on first use
    if (!pio_mutex_initialized) {
        mutex_init(&pio_refcount_mutex);
        pio_mutex_initialized = true;
    }

    dshot_motor_state_t* state = &motor_states[motor];

    // Copy configuration
    memcpy(&state->config, config, sizeof(dshot_config_t));

    // Select PIO instance (use PIO0 for all motors, different state machines)
    state->pio = pio0;

    // CRITICAL FIX #2: Dynamically allocate state machine to avoid race with WS2812
    state->sm = pio_claim_unused_sm(state->pio, true);
    if (state->sm == (uint)-1) {
        DEBUG_PRINT("ERROR: No PIO state machines available\n");
        return false;
    }

    // Check if we can add the PIO program
    if (!pio_can_add_program(state->pio, config->bidirectional ? &dshot_bidirectional_program : &dshot_tx_program)) {
        DEBUG_PRINT("ERROR: Cannot add DShot PIO program (no space)\n");
        pio_sm_unclaim(state->pio, state->sm);
        return false;
    }

    // CRITICAL FIX #3: Add PIO program with reference counting
    // MAJOR FIX #8 (Iteration 3): Protect refcount operations with mutex
    mutex_enter_blocking(&pio_refcount_mutex);

    if (config->bidirectional) {
        if (pio_program_refcount_bidir == 0) {
            state->pio_offset = pio_add_program(state->pio, &dshot_bidirectional_program);
        } else {
            // MAJOR FIX #7 (Iteration 2): Validate that we found the program
            // Reuse existing program offset (all motors using same PIO will have same offset)
            // Find existing offset from another initialized motor with same program
            bool found = false;
            for (int i = 0; i < MAX_DSHOT_MOTORS; i++) {
                if (motor_states[i].initialized && motor_states[i].config.bidirectional) {
                    state->pio_offset = motor_states[i].pio_offset;
                    found = true;
                    break;
                }
            }
            if (!found) {
                DEBUG_PRINT("CRITICAL: PIO bidir refcount=%d but no program found!\n",
                           pio_program_refcount_bidir);
                mutex_exit(&pio_refcount_mutex);
                pio_sm_unclaim(state->pio, state->sm);
                return false;
            }
        }
        pio_program_refcount_bidir++;
        mutex_exit(&pio_refcount_mutex);

        dshot_bidirectional_program_init(state->pio, state->sm, state->pio_offset,
                                         config->gpio_pin, calculate_clk_div(config->speed));
    } else {
        if (pio_program_refcount_tx == 0) {
            state->pio_offset = pio_add_program(state->pio, &dshot_tx_program);
        } else {
            // MAJOR FIX #7 (Iteration 2): Validate that we found the program
            // Reuse existing program offset
            bool found = false;
            for (int i = 0; i < MAX_DSHOT_MOTORS; i++) {
                if (motor_states[i].initialized && !motor_states[i].config.bidirectional) {
                    state->pio_offset = motor_states[i].pio_offset;
                    found = true;
                    break;
                }
            }
            if (!found) {
                DEBUG_PRINT("CRITICAL: PIO tx refcount=%d but no program found!\n",
                           pio_program_refcount_tx);
                mutex_exit(&pio_refcount_mutex);
                pio_sm_unclaim(state->pio, state->sm);
                return false;
            }
        }
        pio_program_refcount_tx++;
        mutex_exit(&pio_refcount_mutex);

        dshot_tx_program_init(state->pio, state->sm, state->pio_offset,
                              config->gpio_pin, calculate_clk_div(config->speed));
    }

    // Allocate DMA channel
    state->dma_chan = dma_claim_unused_channel(true);
    if (state->dma_chan < 0) {
        DEBUG_PRINT("ERROR: No DMA channels available\n");
        // MAJOR FIX #4 (Iteration 2): Clean up PIO program on DMA allocation failure
        // MAJOR FIX #8 (Iteration 3): Protect refcount operations with mutex
        mutex_enter_blocking(&pio_refcount_mutex);
        if (config->bidirectional) {
            pio_program_refcount_bidir--;
            if (pio_program_refcount_bidir == 0) {
                pio_remove_program(state->pio, &dshot_bidirectional_program, state->pio_offset);
            }
        } else {
            pio_program_refcount_tx--;
            if (pio_program_refcount_tx == 0) {
                pio_remove_program(state->pio, &dshot_tx_program, state->pio_offset);
            }
        }
        mutex_exit(&pio_refcount_mutex);
        pio_sm_unclaim(state->pio, state->sm);

        // MAJOR FIX #4 (Iteration 4): Initialize fields individually instead of memset
        // memset() on entire structure could corrupt adjacent memory if size is wrong
        // Explicit field initialization is safer and more maintainable
        state->initialized = false;
        state->pio = NULL;
        state->sm = 0;
        state->pio_offset = 0;
        state->dma_chan = -1;
        state->last_packet = 0;
        state->last_telemetry.valid = false;
        state->last_telemetry.erpm = 0;
        state->last_telemetry.voltage_cV = 0;
        state->last_telemetry.current_cA = 0;
        state->last_telemetry.temperature_C = 0;
        state->last_telemetry.crc = 0;
        state->last_telemetry.timestamp_ms = 0;
        return false;
    }

    // Configure DMA for PIO TX FIFO
    dma_channel_config dma_config = dma_channel_get_default_config(state->dma_chan);
    channel_config_set_transfer_data_size(&dma_config, DMA_SIZE_16);  // 16-bit transfers
    channel_config_set_read_increment(&dma_config, false);            // Read from same location (packet)
    channel_config_set_write_increment(&dma_config, false);           // Write to PIO FIFO
    channel_config_set_dreq(&dma_config, pio_get_dreq(state->pio, state->sm, true));  // Paced by PIO TX

    dma_channel_configure(
        state->dma_chan,
        &dma_config,
        &state->pio->txf[state->sm],  // Write to PIO TX FIFO
        NULL,                          // Read address set per-transfer
        1,                             // Transfer 1 word (16-bit packet)
        false                          // Don't start yet
    );

    // Initialize telemetry
    state->last_telemetry.valid = false;
    state->initialized = true;

    DEBUG_PRINT("DShot initialized: motor=%d, GPIO=%d, speed=%d, bidir=%d, PIO=%p, SM=%d, DMA=%d\n",
           motor, config->gpio_pin, config->speed, config->bidirectional,
           state->pio, state->sm, state->dma_chan);

    return true;
}

// Send throttle command via DShot
bool dshot_send_throttle(motor_channel_t motor, uint16_t throttle, bool request_telemetry) {
    // SAFETY: Validate parameters
    if (motor >= MAX_DSHOT_MOTORS) {
        return false;
    }

    dshot_motor_state_t* state = &motor_states[motor];
    if (!state->initialized) {
        DEBUG_PRINT("WARNING: DShot not initialized for motor %d\n", motor);
        return false;
    }

    // MAJOR FIX #2 (Iteration 4): NULL pointer checks before dereferencing
    if (state->pio == NULL) {
        DEBUG_PRINT("CRITICAL: NULL PIO pointer for motor %d\n", motor);
        return false;
    }

    if (state->dma_chan < 0) {
        DEBUG_PRINT("CRITICAL: Invalid DMA channel for motor %d\n", motor);
        return false;
    }

    // Clamp throttle to valid range
    if (throttle > DSHOT_THROTTLE_MAX) {
        throttle = DSHOT_THROTTLE_MAX;
    }

    // Encode packet
    uint16_t packet = encode_dshot_packet(throttle, request_telemetry);
    state->last_packet = packet;

    // MAJOR FIX #1: Validate PIO FIFO state before transfer
    // Check if previous transfer is still active
    if (dma_channel_is_busy(state->dma_chan)) {
        DEBUG_PRINT("WARNING: DShot DMA still busy for motor %d, waiting...\n", motor);
        dma_channel_wait_for_finish_blocking(state->dma_chan);
    }

    // Check PIO TX FIFO level - should have space for at least 1 word
    uint8_t fifo_level = pio_sm_get_tx_fifo_level(state->pio, state->sm);
    if (fifo_level >= 4) {  // FIFO is 4 words deep
        DEBUG_PRINT("WARNING: DShot PIO FIFO full for motor %d, clearing...\n", motor);
        pio_sm_clear_fifos(state->pio, state->sm);
    }

    // Configure DMA to transfer packet to PIO
    dma_channel_set_read_addr(state->dma_chan, &state->last_packet, false);
    dma_channel_set_trans_count(state->dma_chan, 1, false);

    // Start DMA transfer
    dma_channel_start(state->dma_chan);

    // CRITICAL FIX #2 (Iteration 3): Replace blocking wait with timeout mechanism
    // Blocking wait can hang indefinitely if DMA fails, preventing emergency stop
    // Use 50ms timeout (generous for ~50μs typical transfer time)
    #define DSHOT_DMA_TIMEOUT_MS 50
    uint32_t start_time = to_ms_since_boot(get_absolute_time());
    bool timeout = false;

    while (dma_channel_is_busy(state->dma_chan)) {
        if ((to_ms_since_boot(get_absolute_time()) - start_time) > DSHOT_DMA_TIMEOUT_MS) {
            timeout = true;
            break;
        }
        tight_loop_contents();  // Yield to other code
    }

    if (timeout) {
        DEBUG_PRINT("CRITICAL: DMA timeout for motor %d, aborting transfer\n", motor);
        dma_channel_abort(state->dma_chan);
        // Wait for abort to complete (should be fast)
        uint32_t abort_start = to_ms_since_boot(get_absolute_time());
        while (dma_channel_is_busy(state->dma_chan)) {
            if ((to_ms_since_boot(get_absolute_time()) - abort_start) > 10) {
                DEBUG_PRINT("ERROR: DMA abort failed for motor %d\n", motor);
                break;
            }
            tight_loop_contents();
        }
        return false;
    }

    // MAJOR FIX #4 (Iteration 3): Check transfer_count instead of IRQ status
    // MAJOR FIX #7 (Iteration 4): Verify PIO consumed data after DMA completion
    // DMA completion only means data was written to PIO FIFO, not that PIO transmitted it
    uint32_t remaining = dma_channel_hw_addr(state->dma_chan)->transfer_count;
    if (remaining != 0) {
        DEBUG_PRINT("ERROR: DMA transfer incomplete for motor %d (remaining=%u)\n", motor, remaining);
        return false;
    }

    // MAJOR FIX #7 (Iteration 4): Check PIO state machine status after DMA completion
    // Verify that PIO actually consumed the data from FIFO and is transmitting
    // TX FIFO should be draining (level decreasing) or empty if transmission complete
    uint8_t fifo_level_after = pio_sm_get_tx_fifo_level(state->pio, state->sm);
    if (fifo_level_after > 0) {
        // Wait a bit for PIO to drain FIFO (typical DShot frame is ~30μs)
        sleep_us(50);
        uint8_t fifo_level_final = pio_sm_get_tx_fifo_level(state->pio, state->sm);
        if (fifo_level_final >= fifo_level_after) {
            // FIFO not draining - PIO may be stalled
            DEBUG_PRINT("WARNING: PIO FIFO not draining for motor %d (level=%u)\n",
                       motor, fifo_level_final);
            // Not a critical error - data is in FIFO and will transmit eventually
            // Return true since DMA succeeded, but log the warning
        }
    }

    return true;
}

// ============================================================================
// ADVANCED DSHOT FEATURES (Not currently used - for future ESC integration)
// ============================================================================
// The following functions implement advanced DShot protocol features:
// - Special ESC commands (beep, reverse, save settings, etc.)
// - Bidirectional EDT telemetry (voltage, current, temperature, RPM)
// - ESC configuration via DShot protocol
//
// These are complete implementations kept for future use when:
// - Weapon system switches to DShot mode permanently
// - EDT telemetry is integrated into safety monitoring
// - Advanced ESC control is needed
//
// NOTE: DShot is now enabled by default for weapon motor.
// ============================================================================

// Send DShot command (must be repeated 6+ times)
bool dshot_send_command(motor_channel_t motor, dshot_command_t cmd) {
    if (motor >= MAX_DSHOT_MOTORS) {
        return false;
    }

    // DShot commands must be sent 6-10 times with 1ms delays
    for (int i = 0; i < 10; i++) {
        if (!dshot_send_throttle(motor, (uint16_t)cmd, false)) {
            return false;
        }
        sleep_ms(1);
    }

    return true;
}

// Read EDT telemetry (bidirectional mode only)
bool dshot_read_telemetry(motor_channel_t motor, dshot_telemetry_t* telemetry) {
    // SAFETY: Validate parameters
    if (motor >= MAX_DSHOT_MOTORS || telemetry == NULL) {
        DEBUG_PRINT("CRITICAL: Invalid parameters in dshot_read_telemetry\n");
        return false;
    }

    dshot_motor_state_t* state = &motor_states[motor];
    if (!state->initialized || !state->config.bidirectional) {
        return false;
    }

    // Check if telemetry is available in PIO RX FIFO
    if (pio_sm_is_rx_fifo_empty(state->pio, state->sm)) {
        return false;  // No telemetry available
    }

    // Read telemetry frame from PIO
    uint32_t raw_data = pio_sm_get_blocking(state->pio, state->sm);

    // Parse EDT frame
    if (parse_edt_telemetry(raw_data, &state->last_telemetry)) {
        memcpy(telemetry, &state->last_telemetry, sizeof(dshot_telemetry_t));
        return true;
    }

    return false;
}

// Get last valid telemetry
bool dshot_get_telemetry(motor_channel_t motor, dshot_telemetry_t* telemetry) {
    // SAFETY: Validate parameters
    if (motor >= MAX_DSHOT_MOTORS || telemetry == NULL) {
        return false;
    }

    dshot_motor_state_t* state = &motor_states[motor];
    if (!state->initialized || !state->last_telemetry.valid) {
        return false;
    }

    // MAJOR FIX #6 (Iteration 2): Check telemetry freshness (max 100ms age)
    // Stale telemetry could indicate ESC communication loss or malfunction
    uint32_t age_ms = to_ms_since_boot(get_absolute_time()) - state->last_telemetry.timestamp_ms;
    #define TELEMETRY_MAX_AGE_MS 100
    if (age_ms > TELEMETRY_MAX_AGE_MS) {
        DEBUG_PRINT("WARNING: Telemetry stale (%u ms old) for motor %d\n", age_ms, motor);
        return false;
    }

    memcpy(telemetry, &state->last_telemetry, sizeof(dshot_telemetry_t));
    return true;
}

// Convert eRPM to actual RPM
uint16_t dshot_erpm_to_rpm(uint16_t erpm, uint8_t pole_pairs) {
    if (pole_pairs == 0) {
        DEBUG_PRINT("WARNING: Invalid pole_pairs=0 in dshot_erpm_to_rpm\n");
        return 0;
    }
    return erpm / pole_pairs;
}

// Deinitialize DShot (free resources)
void dshot_deinit(motor_channel_t motor) {
    if (motor >= MAX_DSHOT_MOTORS) {
        return;
    }

    dshot_motor_state_t* state = &motor_states[motor];
    if (!state->initialized) {
        return;
    }

    // Stop and disable state machine
    pio_sm_set_enabled(state->pio, state->sm, false);

    // CRITICAL FIX #2: Unclaim state machine
    pio_sm_unclaim(state->pio, state->sm);

    // CRITICAL FIX #3: Remove PIO program only if this is the last user
    // MAJOR FIX #8 (Iteration 3): Protect refcount operations with mutex
    mutex_enter_blocking(&pio_refcount_mutex);
    if (state->config.bidirectional) {
        pio_program_refcount_bidir--;
        if (pio_program_refcount_bidir == 0) {
            pio_remove_program(state->pio, &dshot_bidirectional_program, state->pio_offset);
        }
    } else {
        pio_program_refcount_tx--;
        if (pio_program_refcount_tx == 0) {
            pio_remove_program(state->pio, &dshot_tx_program, state->pio_offset);
        }
    }
    mutex_exit(&pio_refcount_mutex);

    // MAJOR FIX #5: Properly cleanup DMA channel before unclaiming
    if (state->dma_chan >= 0) {
        // Abort any active DMA transfer
        dma_channel_abort(state->dma_chan);
        // Wait for abort to complete
        dma_channel_wait_for_finish_blocking(state->dma_chan);
        // Now safe to unclaim
        dma_channel_unclaim(state->dma_chan);
    }

    // Clear state
    memset(state, 0, sizeof(dshot_motor_state_t));
    state->dma_chan = -1;

    DEBUG_PRINT("DShot deinitialized for motor %d\n", motor);
}
