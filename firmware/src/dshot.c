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
#define DSHOT_BIDIR_CLKDIV_SCALE 1.0f
#define DSHOT_TELEM_PATH_LOCK_HITS 1
#define DSHOT_TELEM_PATH_LOCK_ENABLE 1
#define DSHOT_TELEM_PATH_MAX_FAILURES 3
#define DSHOT_TELEM_PATH_FAST_ONLY 0

typedef struct {
    bool msb_first;
    bool inverted;
    uint8_t offset;
} dshot_decode_path_t;

// Per-motor DShot state
typedef struct {
    bool initialized;
    dshot_config_t config;
    PIO pio;
    uint sm;                    // State machine ID
    uint pio_offset;            // PIO program offset
    int dma_chan;               // DMA channel for transmission
    dshot_telemetry_t last_telemetry;
    uint32_t last_packet;       // Last transmitted packet (left-aligned for MSB-first shift)
    int8_t crc_invert_override; // -1 = use config, 0 = normal, 1 = invert
    bool extended_telem_active; // True when ESC is sending extended telemetry frames
    bool extended_telem_seen;   // True after any extended telemetry frame decoded
    bool telem_path_valid;      // True if we have a locked telemetry decode path
    dshot_decode_path_t telem_path;
    dshot_decode_path_t telem_path_candidate;
    uint8_t telem_path_candidate_hits;
    uint8_t telem_path_failures;
    uint32_t telem_type_counts[16];
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

// CRC-4 calculation for DShot packets (xor of three nibbles)
uint8_t dshot_calculate_crc(uint16_t packet) {
    // DShot checksum is XOR of the 3 nibbles in the 12-bit payload
    return (packet ^ (packet >> 4) ^ (packet >> 8)) & 0x0F;
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

uint16_t dshot_throttle_from_percent_unidir(uint8_t percent) {
    if (percent == 0) {
        return 0;
    }

    percent = (uint8_t)CLAMP(percent, 0, 100);
    int32_t throttle_range = DSHOT_THROTTLE_MAX - DSHOT_THROTTLE_MIN;
    int32_t value = DSHOT_THROTTLE_MIN + ((int32_t)percent * throttle_range) / 100;

    if (value < DSHOT_THROTTLE_MIN) {
        value = DSHOT_THROTTLE_MIN;
    }
    if (value > DSHOT_THROTTLE_MAX) {
        value = DSHOT_THROTTLE_MAX;
    }

    return (uint16_t)value;
}

// Encode DShot packet with CRC
static uint16_t encode_dshot_packet(uint16_t throttle, bool telemetry_request, bool invert_crc) {
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
    if (invert_crc) {
        crc = (uint8_t)(~crc) & 0x0F;
    }

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

    // CRITICAL FIX #1 (Iteration 2): PIO program uses 16 cycles per bit
    // Each bit in dshot.pio consists of:
    //   1. out y, 1              = 1 cycle
    //   2. jmp !y, bit_zero      = 1 cycle
    //   3. set pins, 1 [7 or 3]  = 8 or 4 cycles
    //   4. set pins, 0 [3 or 7]  = 4 or 8 cycles
    //   5. jmp x--, bitloop      = 1 cycle
    //   Total: 1+1+12+1+1 = 16 cycles (bit 1)
    //   Total: 1+1+6+7+1  = 16 cycles (bit 0)
    uint32_t cycles_per_bit = 16;

    // Calculate required PIO frequency to achieve desired bit timing
    // Formula: pio_freq = (1 MHz * cycles_per_bit * 1000) / bit_period_ns
    //
    // CRITICAL FIX #1: Updated calculations for 16 cycles per bit
    // DShot150 (6670ns):  pio_freq = (1,000,000 * 16 * 1000) / 6670 = 2,398,801 Hz (~2.40 MHz)
    //                     clk_div = 125 MHz / 2.40 MHz = 52.10
    // DShot300 (3330ns):  pio_freq = (1,000,000 * 16 * 1000) / 3330 = 4,801,920 Hz (~4.80 MHz)
    //                     clk_div = 125 MHz / 4.80 MHz = 26.03
    // DShot600 (1670ns):  pio_freq = (1,000,000 * 16 * 1000) / 1670 = 9,580,838 Hz (~9.58 MHz)
    //                     clk_div = 125 MHz / 9.58 MHz = 13.05
    // DShot1200 (830ns):  pio_freq = (1,000,000 * 16 * 1000) / 830 = 19,277,108 Hz (~19.3 MHz)
    //                     clk_div = 125 MHz / 19.3 MHz = 6.48
    //
    // IMPORTANT: Use uint64_t to prevent overflow
    //   Max intermediate: 1,000,000 * 16 * 1000 = 16,000,000,000 (fits in uint64_t)
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

// EDT telemetry CRC calculation (4-bit, inverted XOR of nibbles)
static uint8_t edt_calculate_crc(uint16_t data) {
    uint8_t crc = 0;
    uint16_t csum_data = data & 0x0FFF;
    for (int i = 0; i < 3; i++) {
        crc ^= csum_data;
        csum_data >>= 4;
    }
    crc = (uint8_t)(~crc) & 0x0F;
    return crc;
}

static bool dshot_extended_frame_plausible(uint8_t type, uint8_t data);
static uint16_t decode_throttle_hint = 0;

static uint32_t dshot_candidate_score(const dshot_telemetry_t* telemetry) {
    if (telemetry == NULL || !telemetry->valid) {
        return 0;
    }
    if (telemetry->type == 0xE &&
        (telemetry->value == 0xE00 || telemetry->value == 0xEFF)) {
        return UINT32_MAX;
    }
    if (telemetry->value == 0xFFF) {
        return 1;
    }
    if (decode_throttle_hint <= (DSHOT_THROTTLE_MIN + 200)) {
        return UINT32_MAX - telemetry->erpm;
    }
    return telemetry->erpm;
}

typedef struct {
    bool have;
    uint32_t score;
    dshot_telemetry_t telemetry;
    dshot_decode_path_t path;
} dshot_candidate_t;

static void dshot_candidate_consider(dshot_candidate_t* best,
                                     const dshot_telemetry_t* telemetry,
                                     const dshot_decode_path_t* path) {
    if (best == NULL || telemetry == NULL || path == NULL) {
        return;
    }

    uint32_t score = dshot_candidate_score(telemetry);
    if (score == 0) {
        return;
    }

    if (!best->have || score > best->score) {
        best->have = true;
        best->score = score;
        best->telemetry = *telemetry;
        best->path = *path;
    }
}

// Parse EDT telemetry frame (GCR decoded)
static bool decode_edt_payload(uint32_t gcr_stream, dshot_telemetry_t* telemetry,
                               bool extended_active) {
    uint8_t gcr[4];
    gcr[0] = (gcr_stream >> 15) & 0x1F;
    gcr[1] = (gcr_stream >> 10) & 0x1F;
    gcr[2] = (gcr_stream >> 5) & 0x1F;
    gcr[3] = gcr_stream & 0x1F;

    uint8_t nibbles[4];
    for (int i = 0; i < 4; i++) {
        nibbles[i] = gcr_decode_table[gcr[i]];
        if (nibbles[i] == 0xFF) {
            return false;
        }
    }

    uint16_t decoded = (nibbles[0] << 12) | (nibbles[1] << 8) |
                       (nibbles[2] << 4) | nibbles[3];
    uint16_t value = (decoded >> 4) & 0xFFF;
    uint8_t rx_crc = decoded & 0x0F;
    uint8_t calc_crc = edt_calculate_crc(value);
    if (rx_crc != calc_crc) {
        return false;
    }

    uint8_t type = (value >> 8) & 0x0F;
    uint8_t data = value & 0xFF;
    telemetry->type = type;
    telemetry->value = value;

    if (type == 0xE && (extended_active || value == 0xE00 || value == 0xEFF)) {
        // Event/status frame (EDT init/deinit). Accept but do not overwrite fields.
    } else if (extended_active && type == 0x2) {
        if (!dshot_extended_frame_plausible(type, data)) {
            return false;
        }
        telemetry->temperature_C = data;
    } else if (extended_active && type == 0x4) {
        if (!dshot_extended_frame_plausible(type, data)) {
            return false;
        }
        telemetry->voltage_cV = (uint16_t)data * 25;
    } else if (extended_active && type == 0x6) {
        if (!dshot_extended_frame_plausible(type, data)) {
            return false;
        }
        telemetry->current_cA = (uint16_t)data * 50;
    } else {
        uint8_t exponent = (value >> 9) & 0x07;
        uint16_t mantissa = value & 0x01FF;
        uint32_t period_us = (uint32_t)mantissa << exponent;
        if (period_us > 0) {
            uint32_t erpm = 60000000u / period_us;
            telemetry->erpm = erpm;
        } else {
            telemetry->erpm = 0;
        }
    }

    telemetry->crc = rx_crc;
    telemetry->valid = true;
    telemetry->timestamp_ms = to_ms_since_boot(get_absolute_time());

    return true;
}

static void extract_oversample_bits(uint64_t raw_samples, bool msb_first, uint8_t samples[42]) {
    if (msb_first) {
        for (int i = 0; i < 32; i++) {
            samples[i] = (raw_samples >> (63 - i)) & 1;
        }
        for (int i = 0; i < 10; i++) {
            samples[32 + i] = (raw_samples >> (9 - i)) & 1;
        }
    } else {
        for (int i = 0; i < 32; i++) {
            samples[i] = (raw_samples >> i) & 1;
        }
        for (int i = 0; i < 10; i++) {
            samples[32 + i] = (raw_samples >> (32 + i)) & 1;
        }
    }
}

static inline int telemetry_state_index(int prev_level, int sym_len, int sym_bits, int xor_acc) {
    return ((((prev_level * 5) + sym_len) * 16 + sym_bits) * 16 + xor_acc);
}

static inline void telemetry_state_unpack(int idx, int* prev_level, int* sym_len,
                                          int* sym_bits, int* xor_acc) {
    int rem = idx;
    *prev_level = rem / (5 * 16 * 16);
    rem %= (5 * 16 * 16);
    *sym_len = rem / (16 * 16);
    rem %= (16 * 16);
    *sym_bits = rem / 16;
    *xor_acc = rem % 16;
}

static bool dp_find_choices(const uint8_t even[20], const uint8_t odd[20],
                            bool enforce_crc, uint8_t* start_prev,
                            uint8_t choices[20]) {
    enum { POS_COUNT = 20, STATE_COUNT = 2560 };
    static uint8_t reachable[POS_COUNT + 1][STATE_COUNT];

    memset(reachable, 0, sizeof(reachable));

    for (int prev = 0; prev < 2; prev++) {
        int idx = telemetry_state_index(prev, 0, 0, 0);
        reachable[0][idx] = 1;
    }

    for (int pos = 0; pos < POS_COUNT; pos++) {
        memset(reachable[pos + 1], 0, STATE_COUNT);
        for (int idx = 0; idx < STATE_COUNT; idx++) {
            if (!reachable[pos][idx]) {
                continue;
            }

            int prev_level;
            int sym_len;
            int sym_bits;
            int xor_acc;
            telemetry_state_unpack(idx, &prev_level, &sym_len, &sym_bits, &xor_acc);

            for (int choice = 0; choice < 2; choice++) {
                uint8_t level = (choice == 0) ? even[pos] : odd[pos];
                uint8_t gcr_bit = level ^ (uint8_t)prev_level;

                int next_prev = level;
                int next_sym_len;
                int next_sym_bits;
                int next_xor = xor_acc;

                if (sym_len == 4) {
                    uint8_t symbol = (uint8_t)(((sym_bits << 1) | gcr_bit) & 0x1F);
                    uint8_t nibble = gcr_decode_table[symbol];
                    if (nibble == 0xFF) {
                        continue;
                    }

                    int symbol_index = pos / 5;
                    if (symbol_index < 3) {
                        next_xor = xor_acc ^ nibble;
                    } else if (enforce_crc) {
                        uint8_t expected_crc = (uint8_t)(~xor_acc) & 0x0F;
                        if (nibble != expected_crc) {
                            continue;
                        }
                    }

                    next_sym_len = 0;
                    next_sym_bits = 0;
                } else {
                    next_sym_len = sym_len + 1;
                    next_sym_bits = (uint8_t)(((sym_bits << 1) | gcr_bit) & 0x0F);
                }

                int next_idx = telemetry_state_index(next_prev, next_sym_len, next_sym_bits, next_xor);
                reachable[pos + 1][next_idx] = 1;
            }
        }
    }

    for (int prev_level = 0; prev_level < 2; prev_level++) {
        for (int xor_acc = 0; xor_acc < 16; xor_acc++) {
            int end_idx = telemetry_state_index(prev_level, 0, 0, xor_acc);
            if (!reachable[POS_COUNT][end_idx]) {
                continue;
            }

            int current = end_idx;
            bool backtrack_ok = true;

            for (int pos = POS_COUNT; pos > 0; pos--) {
                int bit = pos - 1;
                bool found = false;

                for (int idx = 0; idx < STATE_COUNT; idx++) {
                    if (!reachable[pos - 1][idx]) {
                        continue;
                    }

                    int prev_state_level;
                    int sym_len;
                    int sym_bits;
                    int xor_state;
                    telemetry_state_unpack(idx, &prev_state_level, &sym_len, &sym_bits, &xor_state);

                    for (int choice = 0; choice < 2; choice++) {
                        uint8_t level = (choice == 0) ? even[bit] : odd[bit];
                        uint8_t gcr_bit = level ^ (uint8_t)prev_state_level;

                        int next_prev = level;
                        int next_sym_len;
                        int next_sym_bits;
                        int next_xor = xor_state;

                        if (sym_len == 4) {
                            uint8_t symbol = (uint8_t)(((sym_bits << 1) | gcr_bit) & 0x1F);
                            uint8_t nibble = gcr_decode_table[symbol];
                            if (nibble == 0xFF) {
                                continue;
                            }

                            int symbol_index = bit / 5;
                            if (symbol_index < 3) {
                                next_xor = xor_state ^ nibble;
                            } else if (enforce_crc) {
                                uint8_t expected_crc = (uint8_t)(~xor_state) & 0x0F;
                                if (nibble != expected_crc) {
                                    continue;
                                }
                            }

                            next_sym_len = 0;
                            next_sym_bits = 0;
                        } else {
                            next_sym_len = sym_len + 1;
                            next_sym_bits = (uint8_t)(((sym_bits << 1) | gcr_bit) & 0x0F);
                        }

                        int next_idx = telemetry_state_index(next_prev, next_sym_len, next_sym_bits, next_xor);
                        if (next_idx == current) {
                            choices[bit] = (uint8_t)choice;
                            current = idx;
                            found = true;
                            break;
                        }
                    }

                    if (found) {
                        break;
                    }
                }

                if (!found) {
                    backtrack_ok = false;
                    break;
                }
            }

            if (!backtrack_ok) {
                continue;
            }

            int start_state;
            int sym_len;
            int sym_bits;
            int xor_state;
            telemetry_state_unpack(current, &start_state, &sym_len, &sym_bits, &xor_state);
            (void)sym_len;
            (void)sym_bits;
            (void)xor_state;
            *start_prev = (uint8_t)start_state;
            return true;
        }
    }

    return false;
}

static uint32_t build_gcr_stream(const uint8_t even[20], const uint8_t odd[20],
                                 const uint8_t choices[20], uint8_t start_prev) {
    uint32_t gcr_stream = 0;
    uint8_t prev = start_prev;

    for (int i = 0; i < 20; i++) {
        uint8_t level = (choices[i] == 0) ? even[i] : odd[i];
        uint8_t gcr_bit = level ^ prev;
        gcr_stream = (gcr_stream << 1) | (gcr_bit & 0x01);
        prev = level;
    }

    return gcr_stream;
}

static bool decode_oversampled_choices(const uint8_t even[20], const uint8_t odd[20],
                                       dshot_telemetry_t* telemetry, bool extended_active) {
    enum { POS_COUNT = 20, STATE_COUNT = 2560 };
    static uint8_t reachable[POS_COUNT + 1][STATE_COUNT];
    uint8_t choices[POS_COUNT] = {0};
    dshot_candidate_t best = {0};

    memset(reachable, 0, sizeof(reachable));

    for (int prev = 0; prev < 2; prev++) {
        int idx = telemetry_state_index(prev, 0, 0, 0);
        reachable[0][idx] = 1;
    }

    for (int pos = 0; pos < POS_COUNT; pos++) {
        memset(reachable[pos + 1], 0, STATE_COUNT);
        for (int idx = 0; idx < STATE_COUNT; idx++) {
            if (!reachable[pos][idx]) {
                continue;
            }

            int prev_level;
            int sym_len;
            int sym_bits;
            int xor_acc;
            telemetry_state_unpack(idx, &prev_level, &sym_len, &sym_bits, &xor_acc);

            for (int choice = 0; choice < 2; choice++) {
                uint8_t level = (choice == 0) ? even[pos] : odd[pos];
                uint8_t gcr_bit = level ^ (uint8_t)prev_level;

                int next_prev = level;
                int next_sym_len;
                int next_sym_bits;
                int next_xor = xor_acc;

                if (sym_len == 4) {
                    uint8_t symbol = (uint8_t)(((sym_bits << 1) | gcr_bit) & 0x1F);
                    uint8_t nibble = gcr_decode_table[symbol];
                    if (nibble == 0xFF) {
                        continue;
                    }

                    int symbol_index = pos / 5;
                    if (symbol_index < 3) {
                        next_xor = xor_acc ^ nibble;
                    } else {
                        uint8_t expected_crc = (uint8_t)(~xor_acc) & 0x0F;
                        if (nibble != expected_crc) {
                            continue;
                        }
                    }

                    next_sym_len = 0;
                    next_sym_bits = 0;
                } else {
                    next_sym_len = sym_len + 1;
                    next_sym_bits = (uint8_t)(((sym_bits << 1) | gcr_bit) & 0x0F);
                }

                int next_idx = telemetry_state_index(next_prev, next_sym_len, next_sym_bits, next_xor);
                reachable[pos + 1][next_idx] = 1;
            }
        }
    }

    for (int prev_level = 0; prev_level < 2; prev_level++) {
        for (int xor_acc = 0; xor_acc < 16; xor_acc++) {
            int end_idx = telemetry_state_index(prev_level, 0, 0, xor_acc);
            if (!reachable[POS_COUNT][end_idx]) {
                continue;
            }

            int current = end_idx;
            bool backtrack_ok = true;

            for (int pos = POS_COUNT; pos > 0; pos--) {
                int bit = pos - 1;
                bool found = false;

                for (int idx = 0; idx < STATE_COUNT; idx++) {
                    if (!reachable[pos - 1][idx]) {
                        continue;
                    }

                    int prev_state_level;
                    int sym_len;
                    int sym_bits;
                    int xor_state;
                    telemetry_state_unpack(idx, &prev_state_level, &sym_len, &sym_bits, &xor_state);

                    for (int choice = 0; choice < 2; choice++) {
                        uint8_t level = (choice == 0) ? even[bit] : odd[bit];
                        uint8_t gcr_bit = level ^ (uint8_t)prev_state_level;

                        int next_prev = level;
                        int next_sym_len;
                        int next_sym_bits;
                        int next_xor = xor_state;

                        if (sym_len == 4) {
                            uint8_t symbol = (uint8_t)(((sym_bits << 1) | gcr_bit) & 0x1F);
                            uint8_t nibble = gcr_decode_table[symbol];
                            if (nibble == 0xFF) {
                                continue;
                            }

                            int symbol_index = bit / 5;
                            if (symbol_index < 3) {
                                next_xor = xor_state ^ nibble;
                            } else {
                                uint8_t expected_crc = (uint8_t)(~xor_state) & 0x0F;
                                if (nibble != expected_crc) {
                                    continue;
                                }
                            }

                            next_sym_len = 0;
                            next_sym_bits = 0;
                        } else {
                            next_sym_len = sym_len + 1;
                            next_sym_bits = (uint8_t)(((sym_bits << 1) | gcr_bit) & 0x0F);
                        }

                        int next_idx = telemetry_state_index(next_prev, next_sym_len, next_sym_bits, next_xor);
                        if (next_idx == current) {
                            choices[bit] = (uint8_t)choice;
                            current = idx;
                            found = true;
                            break;
                        }
                    }

                    if (found) {
                        break;
                    }
                }

                if (!found) {
                    backtrack_ok = false;
                    break;
                }
            }

            if (!backtrack_ok) {
                continue;
            }

            int start_prev;
            int sym_len;
            int sym_bits;
            int xor_state;
            telemetry_state_unpack(current, &start_prev, &sym_len, &sym_bits, &xor_state);
            (void)sym_len;
            (void)sym_bits;
            (void)xor_state;

            uint32_t gcr_stream = 0;
            uint8_t prev = (uint8_t)start_prev;
            for (int i = 0; i < POS_COUNT; i++) {
                uint8_t level = (choices[i] == 0) ? even[i] : odd[i];
                uint8_t gcr_bit = level ^ prev;
                gcr_stream = (gcr_stream << 1) | (gcr_bit & 0x01);
                prev = level;
            }

            if (decode_edt_payload(gcr_stream, telemetry, extended_active)) {
                uint32_t score = dshot_candidate_score(telemetry);
                if (score > 0 && (!best.have || score > best.score)) {
                    best.have = true;
                    best.score = score;
                    best.telemetry = *telemetry;
                }
            }
        }
    }

    if (best.have) {
        *telemetry = best.telemetry;
        return true;
    }

    return false;
}

static bool decode_path_equal(const dshot_decode_path_t* a, const dshot_decode_path_t* b) {
    return a->msb_first == b->msb_first &&
           a->inverted == b->inverted &&
           a->offset == b->offset;
}

static bool dshot_extended_frame_plausible(uint8_t type, uint8_t data) {
    if (type == 0x4) {
        uint16_t voltage_cV = (uint16_t)data * 25;
        uint16_t max_cV = (uint16_t)(BATTERY_MAX_VOLTAGE / 10) * 2;
        return voltage_cV > 0 && voltage_cV <= max_cV;
    }
    if (type == 0x6) {
        uint16_t current_cA = (uint16_t)data * 50;
        return current_cA <= 20000;
    }
    if (type == 0x2) {
        return data <= 150;
    }
    return false;
}

static bool dshot_should_track_path(const dshot_motor_state_t* state,
                                    const dshot_telemetry_t* telemetry) {
    (void)state;
    if (telemetry == NULL || !telemetry->valid) {
        return false;
    }
    return telemetry->value != 0xFFF;
}

static void dshot_track_decode_path(dshot_motor_state_t* state, const dshot_decode_path_t* path) {
    if (state->telem_path_valid && decode_path_equal(path, &state->telem_path)) {
        state->telem_path_candidate_hits = 0;
        return;
    }

    if (state->telem_path_candidate_hits == 0 ||
        !decode_path_equal(path, &state->telem_path_candidate)) {
        state->telem_path_candidate = *path;
        state->telem_path_candidate_hits = 1;
    } else if (state->telem_path_candidate_hits < UINT8_MAX) {
        state->telem_path_candidate_hits++;
    }

    if (state->telem_path_candidate_hits >= DSHOT_TELEM_PATH_LOCK_HITS) {
        state->telem_path = state->telem_path_candidate;
        state->telem_path_valid = true;
        state->telem_path_candidate_hits = 0;
        state->telem_path_failures = 0;
    }
}

static bool parse_edt_telemetry_with_path(uint64_t raw_samples, dshot_telemetry_t* telemetry,
                                          bool extended_active, const dshot_decode_path_t* path) {
    if (telemetry == NULL || path == NULL) {
        return false;
    }

    uint8_t samples[42];
    uint8_t even[20];
    uint8_t odd[20];
    uint8_t choices[20];

    extract_oversample_bits(raw_samples, path->msb_first, samples);
    if ((path->offset + 40) > sizeof(samples)) {
        return false;
    }

    for (int i = 0; i < 20; i++) {
        uint8_t even_level = samples[path->offset + (i * 2)];
        uint8_t odd_level = samples[path->offset + (i * 2) + 1];
        if (path->inverted) {
            even_level ^= 1;
            odd_level ^= 1;
        }
        even[i] = even_level;
        odd[i] = odd_level;
    }

    memset(choices, 0, sizeof(choices));
    for (int start = 0; start < 2; start++) {
        uint32_t gcr_stream = build_gcr_stream(even, odd, choices, (uint8_t)start);
        dshot_telemetry_t candidate = *telemetry;
        if (decode_edt_payload(gcr_stream, &candidate, extended_active)) {
            *telemetry = candidate;
            return true;
        }
    }

    memset(choices, 1, sizeof(choices));
    for (int start = 0; start < 2; start++) {
        uint32_t gcr_stream = build_gcr_stream(even, odd, choices, (uint8_t)start);
        dshot_telemetry_t candidate = *telemetry;
        if (decode_edt_payload(gcr_stream, &candidate, extended_active)) {
            *telemetry = candidate;
            return true;
        }
    }

#if !DSHOT_TELEM_PATH_FAST_ONLY
    dshot_telemetry_t candidate = *telemetry;
    if (decode_oversampled_choices(even, odd, &candidate, extended_active)) {
        *telemetry = candidate;
        return true;
    }
#endif
    return false;
}

static bool parse_edt_telemetry(uint64_t raw_samples, dshot_telemetry_t* telemetry,
                                bool extended_active, dshot_decode_path_t* out_path) {
    if (telemetry == NULL) {
        return false;
    }

    uint8_t samples[42];
    uint8_t even[20];
    uint8_t odd[20];
    uint8_t choices[20];
    uint8_t start_prev = 0;
    const uint8_t offsets[] = {0, 2};
    const bool orders[] = {true, false};
    for (size_t order_index = 0; order_index < sizeof(orders) / sizeof(orders[0]); order_index++) {
        bool msb_first = orders[order_index];
        extract_oversample_bits(raw_samples, msb_first, samples);

        for (size_t offset_index = 0; offset_index < sizeof(offsets) / sizeof(offsets[0]);
             offset_index++) {
            uint8_t offset = offsets[offset_index];
            if ((offset + 40) > sizeof(samples)) {
                continue;
            }

            for (int invert = 0; invert < 2; invert++) {
                dshot_decode_path_t path = {
                    .msb_first = msb_first,
                    .inverted = (invert != 0),
                    .offset = offset,
                };
                for (int i = 0; i < 20; i++) {
                    uint8_t even_level = samples[offset + (i * 2)];
                    uint8_t odd_level = samples[offset + (i * 2) + 1];
                    if (invert) {
                        even_level ^= 1;
                        odd_level ^= 1;
                    }
                    even[i] = even_level;
                    odd[i] = odd_level;
                }

                memset(choices, 0, sizeof(choices));
                for (int start = 0; start < 2; start++) {
                    uint32_t gcr_stream = build_gcr_stream(even, odd, choices, (uint8_t)start);
                    dshot_telemetry_t candidate = *telemetry;
                    if (decode_edt_payload(gcr_stream, &candidate, extended_active)) {
                        *telemetry = candidate;
                        if (out_path != NULL) {
                            *out_path = path;
                        }
                        return true;
                    }
                }

                memset(choices, 1, sizeof(choices));
                for (int start = 0; start < 2; start++) {
                    uint32_t gcr_stream = build_gcr_stream(even, odd, choices, (uint8_t)start);
                    dshot_telemetry_t candidate = *telemetry;
                    if (decode_edt_payload(gcr_stream, &candidate, extended_active)) {
                        *telemetry = candidate;
                        if (out_path != NULL) {
                            *out_path = path;
                        }
                        return true;
                    }
                }

                if (dp_find_choices(even, odd, true, &start_prev, choices)) {
                    uint32_t gcr_stream = build_gcr_stream(even, odd, choices, start_prev);
                    dshot_telemetry_t candidate = *telemetry;
                    if (decode_edt_payload(gcr_stream, &candidate, extended_active)) {
                        *telemetry = candidate;
                        if (out_path != NULL) {
                            *out_path = path;
                        }
                        return true;
                    }
                }

                dshot_telemetry_t candidate = *telemetry;
                if (decode_oversampled_choices(even, odd, &candidate, extended_active)) {
                    *telemetry = candidate;
                    if (out_path != NULL) {
                        *out_path = path;
                    }
                    return true;
                }
            }
        }
    }

    return false;
}

static void dshot_update_extended_state(dshot_motor_state_t* state) {
    if (state->last_telemetry.type != 0xE) {
        return;
    }

    if (state->last_telemetry.value == 0xE00) {
        state->extended_telem_active = true;
        state->extended_telem_seen = false;
        state->last_telemetry.voltage_cV = 0;
        state->last_telemetry.current_cA = 0;
        state->last_telemetry.temperature_C = 0;
    } else if (state->last_telemetry.value == 0xEFF) {
        state->extended_telem_active = false;
        state->extended_telem_seen = false;
        state->last_telemetry.voltage_cV = 0;
        state->last_telemetry.current_cA = 0;
        state->last_telemetry.temperature_C = 0;
    }
}

bool dshot_decode_telemetry_raw(motor_channel_t motor, uint64_t raw_samples,
                                dshot_telemetry_t* telemetry) {
    if (motor >= MAX_DSHOT_MOTORS) {
        return false;
    }

    dshot_motor_state_t* state = &motor_states[motor];
    if (!state->initialized || !state->config.bidirectional) {
        return false;
    }
    uint16_t last_packet = (uint16_t)(state->last_packet >> 16);
    decode_throttle_hint = (last_packet >> 5) & 0x7FF;

    bool decoded = false;
#if DSHOT_TELEM_PATH_LOCK_ENABLE
    if (state->telem_path_valid) {
        decoded = parse_edt_telemetry_with_path(raw_samples, &state->last_telemetry,
                                                state->extended_telem_active,
                                                &state->telem_path);
        if (decoded) {
            state->telem_path_failures = 0;
        } else {
            if (state->telem_path_failures < UINT8_MAX) {
                state->telem_path_failures++;
            }
            if (state->telem_path_failures < DSHOT_TELEM_PATH_MAX_FAILURES) {
                return false;
            }
            state->telem_path_valid = false;
            state->telem_path_failures = 0;
            state->telem_path_candidate_hits = 0;
        }
    }
#endif

    if (!decoded) {
        dshot_decode_path_t path = {0};
        decoded = parse_edt_telemetry(raw_samples, &state->last_telemetry,
                                      state->extended_telem_active, &path);
        if (decoded && dshot_should_track_path(state, &state->last_telemetry)) {
            dshot_track_decode_path(state, &path);
        }
    } else {
        state->telem_path_candidate_hits = 0;
    }

    if (!decoded) {
        return false;
    }

    state->telem_type_counts[state->last_telemetry.type & 0x0F]++;
    dshot_update_extended_state(state);
    if (state->extended_telem_active) {
        uint8_t type = state->last_telemetry.type;
        if (type == 0x2 || type == 0x4 || type == 0x6) {
            state->extended_telem_seen = true;
        }
    }

    if (telemetry != NULL) {
        memcpy(telemetry, &state->last_telemetry, sizeof(dshot_telemetry_t));
    }

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

        float clk_div = calculate_clk_div(config->speed);
        clk_div *= DSHOT_BIDIR_CLKDIV_SCALE;
        dshot_bidirectional_program_init(state->pio, state->sm, state->pio_offset,
                                         config->gpio_pin, clk_div);
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
        state->last_telemetry.type = 0;
        state->last_telemetry.value = 0;
        state->extended_telem_active = false;
        state->extended_telem_seen = false;
        state->telem_path_valid = false;
        state->telem_path_candidate_hits = 0;
        state->telem_path_failures = 0;
        return false;
    }

    // Configure DMA for PIO TX FIFO
    dma_channel_config dma_config = dma_channel_get_default_config(state->dma_chan);
    channel_config_set_transfer_data_size(&dma_config, DMA_SIZE_32);  // 32-bit transfers
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
    state->last_telemetry.erpm = 0;
    state->last_telemetry.voltage_cV = 0;
    state->last_telemetry.current_cA = 0;
    state->last_telemetry.temperature_C = 0;
    state->last_telemetry.crc = 0;
    state->last_telemetry.timestamp_ms = 0;
    state->last_telemetry.type = 0;
    state->last_telemetry.value = 0;
    state->extended_telem_active = false;
    state->extended_telem_seen = false;
    state->telem_path_valid = false;
    state->telem_path_candidate_hits = 0;
    state->telem_path_failures = 0;
    state->crc_invert_override = -1;
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
    bool invert_crc = state->config.bidirectional;
    if (state->crc_invert_override >= 0) {
        invert_crc = (state->crc_invert_override != 0);
    }
    uint16_t packet = encode_dshot_packet(throttle, request_telemetry, invert_crc);
    // Left-align 16-bit packet so MSB shifts out first with left-shift OSR.
    state->last_packet = ((uint32_t)packet) << 16;

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

    // DShot commands must be sent 6-10 times with small delays
    for (int i = 0; i < 10; i++) {
        if (!dshot_send_throttle(motor, (uint16_t)cmd, false)) {
            return false;
        }
        sleep_ms(2);
    }

    dshot_motor_state_t* state = &motor_states[motor];
    if (state->initialized) {
        if (cmd == DSHOT_CMD_EXTENDED_TELEMETRY_ENABLE) {
            // Assume EDT active immediately; some ESCs omit explicit init events.
            state->extended_telem_active = true;
            state->extended_telem_seen = false;
            state->last_telemetry.voltage_cV = 0;
            state->last_telemetry.current_cA = 0;
            state->last_telemetry.temperature_C = 0;
        } else if (cmd == DSHOT_CMD_EXTENDED_TELEMETRY_DISABLE) {
            state->extended_telem_active = false;
            state->extended_telem_seen = false;
            state->last_telemetry.voltage_cV = 0;
            state->last_telemetry.current_cA = 0;
            state->last_telemetry.temperature_C = 0;
        }
    }

    return true;
}

// Read raw EDT telemetry frame (bidirectional mode only)
bool dshot_read_telemetry_raw(motor_channel_t motor, uint64_t* raw_data) {
    if (motor >= MAX_DSHOT_MOTORS || raw_data == NULL) {
        return false;
    }

    dshot_motor_state_t* state = &motor_states[motor];
    if (!state->initialized || !state->config.bidirectional) {
        return false;
    }

    if (pio_sm_get_rx_fifo_level(state->pio, state->sm) < 2) {
        return false;
    }

    uint32_t word0 = pio_sm_get(state->pio, state->sm);
    uint32_t word1 = pio_sm_get(state->pio, state->sm);
    *raw_data = ((uint64_t)word0 << 32) | (uint64_t)word1;
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
    if (pio_sm_get_rx_fifo_level(state->pio, state->sm) < 2) {
        return false;  // No telemetry available
    }

    // Read telemetry frame from PIO (non-blocking since we verified FIFO has data)
    uint32_t word0 = pio_sm_get(state->pio, state->sm);
    uint32_t word1 = pio_sm_get(state->pio, state->sm);
    uint64_t raw_data = ((uint64_t)word0 << 32) | (uint64_t)word1;

    return dshot_decode_telemetry_raw(motor, raw_data, telemetry);
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

bool dshot_extended_telemetry_active(motor_channel_t motor) {
    if (motor >= MAX_DSHOT_MOTORS) {
        return false;
    }

    dshot_motor_state_t* state = &motor_states[motor];
    if (!state->initialized || !state->config.bidirectional) {
        return false;
    }

    return state->extended_telem_active;
}

bool dshot_extended_telemetry_seen(motor_channel_t motor) {
    if (motor >= MAX_DSHOT_MOTORS) {
        return false;
    }

    dshot_motor_state_t* state = &motor_states[motor];
    if (!state->initialized || !state->config.bidirectional) {
        return false;
    }

    return state->extended_telem_seen;
}

bool dshot_sm_is_enabled(motor_channel_t motor) {
    if (motor >= MAX_DSHOT_MOTORS) {
        return false;
    }

    dshot_motor_state_t* state = &motor_states[motor];
    if (!state->initialized || state->pio == NULL) {
        return false;
    }

    return (state->pio->ctrl & (1u << state->sm)) != 0;
}

bool dshot_get_fifo_levels(motor_channel_t motor, uint8_t* tx_level, uint8_t* rx_level) {
    if (motor >= MAX_DSHOT_MOTORS) {
        return false;
    }

    dshot_motor_state_t* state = &motor_states[motor];
    if (!state->initialized || state->pio == NULL) {
        return false;
    }

    if (tx_level != NULL) {
        *tx_level = pio_sm_get_tx_fifo_level(state->pio, state->sm);
    }
    if (rx_level != NULL) {
        *rx_level = pio_sm_get_rx_fifo_level(state->pio, state->sm);
    }

    return true;
}

void dshot_get_telemetry_type_counts(motor_channel_t motor, uint32_t counts[16]) {
    if (motor >= MAX_DSHOT_MOTORS || counts == NULL) {
        return;
    }

    dshot_motor_state_t* state = &motor_states[motor];
    if (!state->initialized) {
        memset(counts, 0, sizeof(uint32_t) * 16);
        return;
    }

    memcpy(counts, state->telem_type_counts, sizeof(state->telem_type_counts));
}

void dshot_reset_telemetry_type_counts(motor_channel_t motor) {
    if (motor >= MAX_DSHOT_MOTORS) {
        return;
    }

    dshot_motor_state_t* state = &motor_states[motor];
    if (!state->initialized) {
        return;
    }

    memset(state->telem_type_counts, 0, sizeof(state->telem_type_counts));
}

// Convert eRPM to actual RPM
uint32_t dshot_erpm_to_rpm(uint32_t erpm, uint8_t pole_pairs) {
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
    state->crc_invert_override = -1;

    DEBUG_PRINT("DShot deinitialized for motor %d\n", motor);
}

void dshot_set_crc_invert_override(motor_channel_t motor, int8_t invert) {
    if (motor >= MAX_DSHOT_MOTORS) {
        return;
    }

    dshot_motor_state_t* state = &motor_states[motor];
    if (!state->initialized) {
        return;
    }

    if (invert < -1) invert = -1;
    if (invert > 1) invert = 1;
    state->crc_invert_override = invert;
}
