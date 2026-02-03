#include <stdio.h>
#include <string.h>
#include <pico/stdlib.h>
#include "config.h"
#include "dshot.h"

#define DSHOT_TEST_SPEED DSHOT_SPEED_300
#define TELEMETRY_LOG_INTERVAL_MS 1000
#define MOTOR_POLE_PAIRS 7
#define TELEMETRY_REQUEST_PERIOD 1
#define CRC_OVERRIDE_MODE -1  // -1 = use config, 0 = normal, 1 = inverted
#define MAX_UNIQUE_VALUES 32
#define RAW_DUMP_LIMIT 0
#define LOG_UNIQUE_FRAMES 0
#define LOG_RAW_DUMP 0
#define LOG_STATS 0
#define HOLD_THROTTLE 1500
#define HOLD_MS 30000

typedef enum {
    EDT_KIND_ERPM = 0,
    EDT_KIND_VOLTAGE,
    EDT_KIND_CURRENT,
    EDT_KIND_TEMP,
    EDT_KIND_EVENT,
    EDT_KIND_MAX
} edt_kind_t;

typedef enum {
    DECODE_OK = 0,
    DECODE_GCR_FAIL,
    DECODE_CRC_FAIL
} decode_result_t;

typedef struct {
    uint16_t values[MAX_UNIQUE_VALUES];
    uint8_t count;
    bool overflow;
} edt_value_set_t;

typedef struct {
    uint64_t raw_samples;
    uint16_t decoded;
    uint16_t value;
    uint8_t rx_crc;
    uint8_t calc_crc;
    bool gcr_ok;
    bool crc_ok;
    uint8_t type;
    uint8_t data;
    bool msb_first;
    bool inverted;
    uint8_t choice_mask;
    uint8_t sample_offset;
    edt_kind_t kind;
    uint32_t erpm;
    uint16_t voltage_cV;
    uint16_t current_cA;
    uint8_t temperature_C;
    uint16_t event_code;
    uint32_t period_us;
} edt_frame_t;

typedef struct {
    uint32_t packets;
    uint32_t gcr_fail;
    uint32_t crc_fail;
    uint32_t kind_counts[EDT_KIND_MAX];
    edt_value_set_t unique[EDT_KIND_MAX];
    bool last_valid[EDT_KIND_MAX];
    edt_frame_t last_by_kind[EDT_KIND_MAX];
    uint32_t last_log_ms;
    uint32_t frame_count;
    uint32_t send_errors;
    uint32_t decoded_ok;
    uint32_t decoded_fail;
    uint32_t order_ok[2];
    uint32_t invert_ok[2];
    uint32_t choice_even_only;
    uint32_t choice_odd_only;
    uint32_t choice_mixed;
    uint32_t raw_dump_remaining;
} telemetry_stats_t;

static const uint8_t gcr_decode_table[32] = {
    0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
    0xFF, 0x09, 0x0A, 0x0B, 0xFF, 0x0D, 0x0E, 0x0F,
    0xFF, 0xFF, 0x02, 0x03, 0xFF, 0x05, 0x06, 0x07,
    0xFF, 0x00, 0x08, 0x01, 0xFF, 0x04, 0x0C, 0xFF
};

static const char* edt_kind_label(edt_kind_t kind) {
    switch (kind) {
        case EDT_KIND_ERPM:
            return "erpm";
        case EDT_KIND_VOLTAGE:
            return "voltage";
        case EDT_KIND_CURRENT:
            return "current";
        case EDT_KIND_TEMP:
            return "temp";
        case EDT_KIND_EVENT:
            return "event";
        default:
            return "unknown";
    }
}

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
                                 const uint8_t choices[20], uint8_t start_prev,
                                 uint8_t* choice_mask) {
    uint32_t gcr_stream = 0;
    uint8_t mask = 0;
    uint8_t prev = start_prev;

    for (int i = 0; i < 20; i++) {
        uint8_t level = (choices[i] == 0) ? even[i] : odd[i];
        mask |= (choices[i] == 0) ? 0x1 : 0x2;
        uint8_t gcr_bit = level ^ prev;
        gcr_stream = (gcr_stream << 1) | (gcr_bit & 0x01);
        prev = level;
    }

    if (choice_mask != NULL) {
        *choice_mask = mask;
    }
    return gcr_stream;
}

static bool decode_edt_payload(uint32_t gcr_stream, edt_frame_t* frame) {
    uint8_t gcr[4];
    gcr[0] = (gcr_stream >> 15) & 0x1F;
    gcr[1] = (gcr_stream >> 10) & 0x1F;
    gcr[2] = (gcr_stream >> 5) & 0x1F;
    gcr[3] = gcr_stream & 0x1F;

    uint8_t nibbles[4];
    for (int i = 0; i < 4; i++) {
        nibbles[i] = gcr_decode_table[gcr[i]];
        if (nibbles[i] == 0xFF) {
            frame->gcr_ok = false;
            frame->crc_ok = false;
            return false;
        }
    }

    frame->gcr_ok = true;
    frame->decoded = (uint16_t)((nibbles[0] << 12) | (nibbles[1] << 8) |
                               (nibbles[2] << 4) | nibbles[3]);
    frame->value = (frame->decoded >> 4) & 0x0FFF;
    frame->rx_crc = frame->decoded & 0x0F;
    frame->calc_crc = edt_calculate_crc(frame->value);
    frame->crc_ok = (frame->rx_crc == frame->calc_crc);
    if (!frame->crc_ok) {
        return false;
    }

    frame->type = (frame->value >> 8) & 0x0F;
    frame->data = frame->value & 0xFF;

    switch (frame->type) {
        case 0x2:
            frame->kind = EDT_KIND_TEMP;
            frame->temperature_C = frame->data;
            break;
        case 0x4:
            frame->kind = EDT_KIND_VOLTAGE;
            frame->voltage_cV = (uint16_t)frame->data * 25;
            break;
        case 0x6:
            frame->kind = EDT_KIND_CURRENT;
            frame->current_cA = (uint16_t)frame->data * 50;
            break;
        case 0xE:
            frame->kind = EDT_KIND_EVENT;
            frame->event_code = frame->value;
            break;
        default: {
            uint8_t exponent = (frame->value >> 9) & 0x07;
            uint16_t mantissa = frame->value & 0x01FF;
            frame->kind = EDT_KIND_ERPM;
            frame->period_us = (uint32_t)mantissa << exponent;
            if (frame->period_us > 0) {
                frame->erpm = 60000000u / frame->period_us;
            }
            break;
        }
    }

    return true;
}

static decode_result_t decode_edt_frame_dp(uint64_t raw_samples, edt_frame_t* frame) {
    uint8_t samples[42];
    uint8_t even[20];
    uint8_t odd[20];
    uint8_t choices[20];
    uint8_t start_prev = 0;
    const uint8_t offsets[] = {0, 2};

    for (int order = 0; order < 2; order++) {
        extract_oversample_bits(raw_samples, order == 0, samples);
        for (size_t offset_index = 0; offset_index < sizeof(offsets) / sizeof(offsets[0]);
             offset_index++) {
            uint8_t offset = offsets[offset_index];
            if ((offset + 40) > sizeof(samples)) {
                continue;
            }
            for (int invert = 0; invert < 2; invert++) {
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
                    uint8_t choice_mask = 0;
                    uint32_t gcr_stream = build_gcr_stream(even, odd, choices, start, &choice_mask);
                    memset(frame, 0, sizeof(*frame));
                    frame->raw_samples = raw_samples;
                    if (!decode_edt_payload(gcr_stream, frame)) {
                        continue;
                    }
                    frame->msb_first = (order == 0);
                    frame->inverted = (invert != 0);
                    frame->choice_mask = choice_mask;
                    frame->sample_offset = offset;
                    return DECODE_OK;
                }

                memset(choices, 1, sizeof(choices));
                for (int start = 0; start < 2; start++) {
                    uint8_t choice_mask = 0;
                    uint32_t gcr_stream = build_gcr_stream(even, odd, choices, start, &choice_mask);
                    memset(frame, 0, sizeof(*frame));
                    frame->raw_samples = raw_samples;
                    if (!decode_edt_payload(gcr_stream, frame)) {
                        continue;
                    }
                    frame->msb_first = (order == 0);
                    frame->inverted = (invert != 0);
                    frame->choice_mask = choice_mask;
                    frame->sample_offset = offset;
                    return DECODE_OK;
                }

                if (!dp_find_choices(even, odd, true, &start_prev, choices)) {
                    continue;
                }

                uint8_t choice_mask = 0;
                uint32_t gcr_stream = build_gcr_stream(even, odd, choices, start_prev, &choice_mask);

                memset(frame, 0, sizeof(*frame));
                frame->raw_samples = raw_samples;
                if (!decode_edt_payload(gcr_stream, frame)) {
                    continue;
                }

                frame->msb_first = (order == 0);
                frame->inverted = (invert != 0);
                frame->choice_mask = choice_mask;
                frame->sample_offset = offset;
                return DECODE_OK;
            }
        }
    }

    for (int order = 0; order < 2; order++) {
        extract_oversample_bits(raw_samples, order == 0, samples);
        for (size_t offset_index = 0; offset_index < sizeof(offsets) / sizeof(offsets[0]);
             offset_index++) {
            uint8_t offset = offsets[offset_index];
            if ((offset + 40) > sizeof(samples)) {
                continue;
            }
            for (int invert = 0; invert < 2; invert++) {
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

                if (dp_find_choices(even, odd, false, &start_prev, choices)) {
                    return DECODE_CRC_FAIL;
                }
            }
        }
    }

    return DECODE_GCR_FAIL;
}

static bool value_set_add(edt_value_set_t* set, uint16_t value) {
    for (uint8_t i = 0; i < set->count; i++) {
        if (set->values[i] == value) {
            return false;
        }
    }

    if (set->count >= MAX_UNIQUE_VALUES) {
        set->overflow = true;
        return false;
    }

    set->values[set->count++] = value;
    return true;
}

static void log_frame(const edt_frame_t* frame, uint8_t pole_pairs) {
    printf("EDT %s: raw=0x%010llx decoded=0x%04x value=0x%03x type=0x%x data=0x%02x ",
           edt_kind_label(frame->kind),
           (unsigned long long)frame->raw_samples,
           frame->decoded,
           frame->value,
           frame->type,
           frame->data);

    switch (frame->kind) {
        case EDT_KIND_ERPM: {
            uint32_t rpm = (pole_pairs > 0) ? frame->erpm / pole_pairs : 0;
            printf("period=%luus erpm=%lu rpm=%lu",
                   (unsigned long)frame->period_us,
                   (unsigned long)frame->erpm,
                   (unsigned long)rpm);
            break;
        }
        case EDT_KIND_VOLTAGE:
            printf("voltage=%u.%02uV", frame->voltage_cV / 100, frame->voltage_cV % 100);
            break;
        case EDT_KIND_CURRENT:
            printf("current=%u.%02uA", frame->current_cA / 100, frame->current_cA % 100);
            break;
        case EDT_KIND_TEMP:
            printf("temp=%uC", frame->temperature_C);
            break;
        case EDT_KIND_EVENT:
            if (frame->event_code == 0xE00) {
                printf("event=EDT_INIT");
            } else if (frame->event_code == 0xEFF) {
                printf("event=EDT_DEINIT");
            } else {
                printf("event=0x%03x", frame->event_code);
            }
            break;
        default:
            printf("unknown");
            break;
    }

    const char* pick_label = "mixed";
    if (frame->choice_mask == 0x1) {
        pick_label = "even";
    } else if (frame->choice_mask == 0x2) {
        pick_label = "odd";
    }
    printf(" path=%s inv=%u pick=%s off=%u",
           frame->msb_first ? "msb" : "lsb",
           frame->inverted ? 1 : 0,
           pick_label,
           frame->sample_offset);

    printf("\n");
}

static void telemetry_init(telemetry_stats_t* stats) {
    memset(stats, 0, sizeof(*stats));
    stats->last_log_ms = to_ms_since_boot(get_absolute_time());
}

static bool telemetry_request_due(telemetry_stats_t* stats) {
#if TELEMETRY_REQUEST_PERIOD > 0
    stats->frame_count++;
    return (stats->frame_count % TELEMETRY_REQUEST_PERIOD) == 0;
#else
    (void)stats;
    return false;
#endif
}

static void telemetry_drain(telemetry_stats_t* stats) {
    uint64_t raw;
    while (dshot_read_telemetry_raw(MOTOR_WEAPON, &raw)) {
        stats->packets++;

        if (LOG_RAW_DUMP && stats->raw_dump_remaining > 0) {
            printf("EDT raw=0x%010llx\n", (unsigned long long)raw);
            stats->raw_dump_remaining--;
        }

        edt_frame_t frame;
        decode_result_t result = decode_edt_frame_dp(raw, &frame);
        if (result != DECODE_OK) {
            stats->decoded_fail++;
            if (result == DECODE_CRC_FAIL) {
                stats->crc_fail++;
            } else {
                stats->gcr_fail++;
            }
            continue;
        }

        stats->decoded_ok++;
        stats->order_ok[frame.msb_first ? 0 : 1]++;
        stats->invert_ok[frame.inverted ? 1 : 0]++;
        if (frame.choice_mask == 0x1) {
            stats->choice_even_only++;
        } else if (frame.choice_mask == 0x2) {
            stats->choice_odd_only++;
        } else {
            stats->choice_mixed++;
        }

        stats->kind_counts[frame.kind]++;
        stats->last_by_kind[frame.kind] = frame;
        stats->last_valid[frame.kind] = true;

        if (LOG_UNIQUE_FRAMES && value_set_add(&stats->unique[frame.kind], frame.value)) {
            log_frame(&frame, MOTOR_POLE_PAIRS);
        }
    }
}

static void telemetry_maybe_log(telemetry_stats_t* stats, uint8_t pole_pairs) {
    uint32_t now = to_ms_since_boot(get_absolute_time());
    if ((now - stats->last_log_ms) < TELEMETRY_LOG_INTERVAL_MS) {
        return;
    }

    stats->last_log_ms = now;
    printf("EDT stats: total=%lu ok=%lu fail=%lu gcr_fail=%lu crc_fail=%lu erpm=%lu volt=%lu curr=%lu temp=%lu event=%lu\n",
           (unsigned long)stats->packets,
           (unsigned long)stats->decoded_ok,
           (unsigned long)stats->decoded_fail,
           (unsigned long)stats->gcr_fail,
           (unsigned long)stats->crc_fail,
           (unsigned long)stats->kind_counts[EDT_KIND_ERPM],
           (unsigned long)stats->kind_counts[EDT_KIND_VOLTAGE],
           (unsigned long)stats->kind_counts[EDT_KIND_CURRENT],
           (unsigned long)stats->kind_counts[EDT_KIND_TEMP],
           (unsigned long)stats->kind_counts[EDT_KIND_EVENT]);

    printf("EDT unique: erpm=%u volt=%u curr=%u temp=%u event=%u\n",
           stats->unique[EDT_KIND_ERPM].count,
           stats->unique[EDT_KIND_VOLTAGE].count,
           stats->unique[EDT_KIND_CURRENT].count,
           stats->unique[EDT_KIND_TEMP].count,
           stats->unique[EDT_KIND_EVENT].count);

    printf("EDT path: msb=%lu lsb=%lu inv0=%lu inv1=%lu even=%lu odd=%lu mixed=%lu\n",
           (unsigned long)stats->order_ok[0],
           (unsigned long)stats->order_ok[1],
           (unsigned long)stats->invert_ok[0],
           (unsigned long)stats->invert_ok[1],
           (unsigned long)stats->choice_even_only,
           (unsigned long)stats->choice_odd_only,
           (unsigned long)stats->choice_mixed);

    if (stats->packets > 0) {
        uint32_t rate = (stats->decoded_ok * 100u) / stats->packets;
        printf("EDT success rate: %lu/%lu (%lu%%)\n",
               (unsigned long)stats->decoded_ok,
               (unsigned long)stats->packets,
               (unsigned long)rate);
    }

    printf("EDT last: ");
    if (stats->last_valid[EDT_KIND_ERPM]) {
        const edt_frame_t* frame = &stats->last_by_kind[EDT_KIND_ERPM];
        uint32_t rpm = (pole_pairs > 0) ? frame->erpm / pole_pairs : 0;
        printf("erpm=%lu rpm=%lu ", (unsigned long)frame->erpm, (unsigned long)rpm);
    } else {
        printf("erpm=-- ");
    }

    if (stats->last_valid[EDT_KIND_VOLTAGE]) {
        const edt_frame_t* frame = &stats->last_by_kind[EDT_KIND_VOLTAGE];
        printf("V=%u.%02u ", frame->voltage_cV / 100, frame->voltage_cV % 100);
    } else {
        printf("V=-- ");
    }

    if (stats->last_valid[EDT_KIND_CURRENT]) {
        const edt_frame_t* frame = &stats->last_by_kind[EDT_KIND_CURRENT];
        printf("I=%u.%02u ", frame->current_cA / 100, frame->current_cA % 100);
    } else {
        printf("I=-- ");
    }

    if (stats->last_valid[EDT_KIND_TEMP]) {
        const edt_frame_t* frame = &stats->last_by_kind[EDT_KIND_TEMP];
        printf("T=%u ", frame->temperature_C);
    } else {
        printf("T=-- ");
    }

    if (stats->last_valid[EDT_KIND_EVENT]) {
        const edt_frame_t* frame = &stats->last_by_kind[EDT_KIND_EVENT];
        if (frame->event_code == 0xE00) {
            printf("event=EDT_INIT");
        } else if (frame->event_code == 0xEFF) {
            printf("event=EDT_DEINIT");
        } else {
            printf("event=0x%03x", frame->event_code);
        }
    } else {
        printf("event=--");
    }

    printf("\n");
}

static void telemetry_log_summary(telemetry_stats_t* stats, uint8_t pole_pairs) {
    stats->last_log_ms = 0;
    telemetry_maybe_log(stats, pole_pairs);
}

static void send_throttle_for_ms(uint16_t throttle, uint32_t duration_ms,
                                 telemetry_stats_t* stats) {
    const uint32_t step_ms = 2;  // 500 Hz update rate
    uint32_t start_ms = to_ms_since_boot(get_absolute_time());

    while ((to_ms_since_boot(get_absolute_time()) - start_ms) < duration_ms) {
        telemetry_drain(stats);
        bool request = telemetry_request_due(stats);
        if (!dshot_send_throttle(MOTOR_WEAPON, throttle, request)) {
            stats->send_errors++;
        }
        sleep_ms(step_ms);
        telemetry_drain(stats);
        if (LOG_STATS) {
            telemetry_maybe_log(stats, MOTOR_POLE_PAIRS);
        }
    }
}

static void send_command_repeat(dshot_command_t cmd, const char* label, int repeats,
                                telemetry_stats_t* stats) {
    printf("Command: %s (cmd=%u) x%d\n", label, (unsigned)cmd, repeats);
    if (LOG_RAW_DUMP && cmd == DSHOT_CMD_EXTENDED_TELEMETRY_ENABLE &&
        stats->raw_dump_remaining == 0 && RAW_DUMP_LIMIT > 0) {
        stats->raw_dump_remaining = RAW_DUMP_LIMIT;
        printf("EDT raw dump enabled (%u frames)\n", (unsigned)RAW_DUMP_LIMIT);
    }
    for (int i = 0; i < repeats; i++) {
        telemetry_drain(stats);
        if (!dshot_send_throttle(MOTOR_WEAPON, (uint16_t)cmd, false)) {
            stats->send_errors++;
        }
        sleep_ms(2);
        telemetry_drain(stats);
        if (LOG_STATS) {
            telemetry_maybe_log(stats, MOTOR_POLE_PAIRS);
        }
    }
}

int main() {
    stdio_init_all();
    sleep_ms(2000);

    printf("\n========================================\n");
    printf("  DShot Telemetry Hold Test (Raw EDT)\n");
    printf("========================================\n\n");
    printf("Target: DShot%u on GP%d (bidirectional)\n",
           (unsigned)DSHOT_TEST_SPEED, PIN_WEAPON_PWM);
    printf("Sequence: bidir DShot -> EDT enable -> 3D off -> dir normal -> hold throttle\n");
    printf("Telemetry requests enabled (request bit set every frame)\n");
    printf("Hold throttle=%u for %ums\n", HOLD_THROTTLE, HOLD_MS);
    if (LOG_UNIQUE_FRAMES) {
        printf("Unique frame logging capped at %u per type\n\n", (unsigned)MAX_UNIQUE_VALUES);
    } else {
        printf("Unique frame logging disabled\n\n");
    }

    dshot_config_t config = {
        .gpio_pin = PIN_WEAPON_PWM,
        .speed = DSHOT_TEST_SPEED,
        .bidirectional = true,
        .pole_pairs = MOTOR_POLE_PAIRS
    };

    if (!dshot_init(MOTOR_WEAPON, &config)) {
        printf("ERROR: DShot init failed\n");
        while (1) {
            sleep_ms(1000);
        }
    }
    printf("OK: DShot initialized\n");

    telemetry_stats_t stats;
    telemetry_init(&stats);

    uint32_t cycle = 1;
    while (true) {
        int8_t crc_mode = CRC_OVERRIDE_MODE;
        const char* crc_label = (crc_mode < 0) ? "config" : (crc_mode == 1) ? "inverted" : "normal";
        printf("\n=== Cycle %lu (CRC %s) ===\n", cycle++, crc_label);
        dshot_set_crc_invert_override(MOTOR_WEAPON, crc_mode);

        printf("Arming (throttle=0, 5s)\n");
        send_throttle_for_ms(0, 5000, &stats);

        send_command_repeat(DSHOT_CMD_EXTENDED_TELEMETRY_ENABLE, "EDT_ENABLE", 6, &stats);
        send_command_repeat(DSHOT_CMD_3D_MODE_OFF, "3D_MODE_OFF", 6, &stats);
        send_command_repeat(DSHOT_CMD_SPIN_DIRECTION_NORMAL, "SPIN_DIR_NORMAL", 6, &stats);

    printf("Hold (throttle=%u, %ums)\n", HOLD_THROTTLE, HOLD_MS);
    uint32_t hold_start = to_ms_since_boot(get_absolute_time());
    send_throttle_for_ms(HOLD_THROTTLE, HOLD_MS, &stats);
    uint32_t hold_end = to_ms_since_boot(get_absolute_time());
    printf("Hold complete: elapsed=%lums\n", (unsigned long)(hold_end - hold_start));
    telemetry_log_summary(&stats, MOTOR_POLE_PAIRS);

        printf("Stop (throttle=0, 4s)\n");
        send_throttle_for_ms(0, 4000, &stats);
    }
}
