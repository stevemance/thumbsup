#ifndef DSHOT_RX_H
#define DSHOT_RX_H

// Bidirectional DShot telemetry receive decoding.
//
// The PIO program (dshot_bidirectional in dshot.pio) waits for the ESC's start
// bit, then takes DSHOT_RX_SAMPLES samples of the line, 2 PIO cycles apart,
// pushed as DSHOT_RX_WORDS words (first sample in bit 31 of word 0).  At the
// DShot300 PIO clock (16 cycles per DShot bit) that is ~6 samples per
// telemetry bit.  The frame is recovered from run lengths, then must pass the
// GCR table and the 4-bit checksum exactly: there is no guessing of alignment
// or bit choices, so a corrupted reply is dropped rather than "repaired".
//
// Pure C with no hardware dependencies so it can be unit tested on the host.

#include <stdbool.h>
#include <stdint.h>

#define DSHOT_RX_WORDS   4
#define DSHOT_RX_SAMPLES (DSHOT_RX_WORDS * 32)

typedef enum {
    DSHOT_RX_OK = 0,
    DSHOT_RX_NO_START,   // first sample is not the start bit (line high)
    DSHOT_RX_BITCOUNT,   // run lengths do not add up to a 21-bit frame
    DSHOT_RX_GCR,        // a 5-bit group is not a valid GCR code
    DSHOT_RX_CRC,        // checksum mismatch
    DSHOT_RX_RESULT_COUNT
} dshot_rx_result_t;

typedef enum {
    DSHOT_FRAME_ERPM = 0,
    DSHOT_FRAME_STOPPED,   // 0xFFF: ESC reports the motor is not turning
    DSHOT_FRAME_TEMP,      // EDT 0x2: degrees C
    DSHOT_FRAME_VOLT,      // EDT 0x4: 0.25 V per step
    DSHOT_FRAME_CURR,      // EDT 0x6: amps (scale depends on ESC firmware)
    DSHOT_FRAME_DEBUG1,    // EDT 0x8
    DSHOT_FRAME_DEBUG2,    // EDT 0xA
    DSHOT_FRAME_STRESS,    // EDT 0xC
    DSHOT_FRAME_EVENT,     // EDT 0xE: 0xE00 = EDT enabled, 0xEFF = disabled
    DSHOT_FRAME_KIND_COUNT
} dshot_frame_kind_t;

typedef struct {
    dshot_frame_kind_t kind;
    uint16_t raw;      // 12-bit payload
    uint32_t erpm;     // DSHOT_FRAME_ERPM only
    uint8_t data;      // EDT frames: 8-bit data field
} dshot_frame_t;

// Decodes one captured reply into its 12-bit payload.
dshot_rx_result_t dshot_rx_decode_samples(const uint32_t words[DSHOT_RX_WORDS], uint16_t* value12);

// Classifies a 12-bit payload per the EDT spec: an eRPM value always has
// mantissa bit 8 set when its exponent is non-zero, so exponent != 0 with
// bit 8 clear marks an extended frame.
void dshot_rx_classify(uint16_t value12, dshot_frame_t* out);

#endif  // DSHOT_RX_H
