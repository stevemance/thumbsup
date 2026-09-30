#include "dshot_rx.h"

// Sample timing produced by the PIO receive loop, in PIO cycles from the
// first sample: 2 cycles per sample, plus 2 extra cycles at each 32-sample
// word boundary (the outer loop's jmp and set).
#define RX_CYCLES_PER_SAMPLE 2
#define RX_CYCLES_PER_WORD   66

// Telemetry bit period in PIO cycles x16.  The spec rate is 5/4 of the DShot
// bit rate (12.8 cycles at 16 cycles per DShot bit); AM32 on the AT32F421
// sends ~3.9% fast (12.32 cycles, measured 2.567 us at DShot300).  12.56 sits
// between the two, so the longest run (3 bits) stays within 0.1 bit of an
// integer for either.
#define RX_BIT_CYCLES_X16 201

// The start edge falls between the last "high" poll and the first sample.
// The poll loop checks every 2 cycles and the first sample follows 3 cycles
// after detection, so the edge is on average ~4 cycles before sample 0.
#define RX_START_EDGE_CYCLES (-4)

#define RX_FRAME_BITS 21

static const uint8_t gcr_decode[32] = {
    0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
    0xFF, 0x09, 0x0A, 0x0B, 0xFF, 0x0D, 0x0E, 0x0F,
    0xFF, 0xFF, 0x02, 0x03, 0xFF, 0x05, 0x06, 0x07,
    0xFF, 0x00, 0x08, 0x01, 0xFF, 0x04, 0x0C, 0xFF,
};

static inline int sample_at(const uint32_t words[DSHOT_RX_WORDS], int k) {
    return (int)((words[k >> 5] >> (31 - (k & 31))) & 1u);
}

static inline int time_of(int k) {
    return RX_CYCLES_PER_WORD * (k >> 5) + RX_CYCLES_PER_SAMPLE * (k & 31);
}

static inline int run_bits(int run_cycles) {
    return (run_cycles * 16 + RX_BIT_CYCLES_X16 / 2) / RX_BIT_CYCLES_X16;
}

dshot_rx_result_t dshot_rx_decode_samples(const uint32_t words[DSHOT_RX_WORDS], uint16_t* value12) {
    if (sample_at(words, 0) != 0) {
        return DSHOT_RX_NO_START;
    }

    // Rebuild the 21 bit cells from run lengths.  A low line is a 1 bit.
    uint32_t raw = 0;
    int nbits = 0;
    int level = 0;
    int run_start = RX_START_EDGE_CYCLES;
    for (int k = 1; k < DSHOT_RX_SAMPLES; k++) {
        int s = sample_at(words, k);
        if (s == level) {
            continue;
        }
        int edge = (time_of(k - 1) + time_of(k)) / 2;
        int n = run_bits(edge - run_start);
        if (n < 1 || nbits + n > RX_FRAME_BITS) {
            return DSHOT_RX_BITCOUNT;
        }
        for (int i = 0; i < n; i++) {
            raw = (raw << 1) | (level == 0 ? 1u : 0u);
        }
        nbits += n;
        level = s;
        run_start = edge;
    }
    // The line ends high (idle) after the last transition; a frame that is
    // still low at the end of the capture is truncated.
    if (level == 0 || nbits >= RX_FRAME_BITS) {
        return DSHOT_RX_BITCOUNT;
    }
    raw <<= (RX_FRAME_BITS - nbits);

    uint32_t gcr = (raw ^ (raw >> 1)) & 0xFFFFFu;
    uint16_t value = 0;
    for (int shift = 15; shift >= 0; shift -= 5) {
        uint8_t nibble = gcr_decode[(gcr >> shift) & 0x1Fu];
        if (nibble == 0xFF) {
            return DSHOT_RX_GCR;
        }
        value = (uint16_t)((value << 4) | nibble);
    }

    uint16_t csum = value ^ (value >> 4) ^ (value >> 8) ^ (value >> 12);
    if ((csum & 0xFu) != 0xFu) {
        return DSHOT_RX_CRC;
    }
    *value12 = value >> 4;
    return DSHOT_RX_OK;
}

void dshot_rx_classify(uint16_t value12, dshot_frame_t* out) {
    out->raw = value12;
    out->erpm = 0;
    out->data = 0;

    if (value12 == 0xFFF) {
        out->kind = DSHOT_FRAME_STOPPED;
        return;
    }

    uint16_t exponent = value12 >> 9;
    uint16_t mantissa = value12 & 0x1FF;
    if (exponent != 0 && (mantissa & 0x100) == 0) {
        static const dshot_frame_kind_t edt_kinds[8] = {
            DSHOT_FRAME_EVENT,  // 0x0 cannot occur (exponent != 0)
            DSHOT_FRAME_TEMP,   DSHOT_FRAME_VOLT,   DSHOT_FRAME_CURR,
            DSHOT_FRAME_DEBUG1, DSHOT_FRAME_DEBUG2, DSHOT_FRAME_STRESS,
            DSHOT_FRAME_EVENT,
        };
        out->kind = edt_kinds[(value12 >> 9) & 0x7];
        out->data = (uint8_t)(value12 & 0xFF);
        return;
    }

    uint32_t period_us = (uint32_t)mantissa << exponent;
    out->kind = DSHOT_FRAME_ERPM;
    out->erpm = period_us ? 60000000u / period_us : 0;
}
