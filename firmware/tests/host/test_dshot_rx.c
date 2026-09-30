// Host unit test for the bidirectional DShot telemetry decoder.
//   cc -I../../include -o test_dshot_rx test_dshot_rx.c ../../src/dshot_rx.c && ./test_dshot_rx
#include <stdint.h>
#include <stdio.h>
#include "dshot_rx.h"
#include "dshot_rx_fixtures.h"

static int failures = 0;
#define CHECK(cond, ...) do { if (!(cond)) { failures++; printf("FAIL: " __VA_ARGS__); printf("\n"); } } while (0)

static void test_classify(void) {
    dshot_frame_t f;
    dshot_rx_classify(0xFFF, &f);
    CHECK(f.kind == DSHOT_FRAME_STOPPED && f.erpm == 0, "0xFFF is stopped");
    dshot_rx_classify(0x232, &f);   // temp 0x32 = 50 C
    CHECK(f.kind == DSHOT_FRAME_TEMP && f.data == 0x32, "0x232 is temperature 50");
    dshot_rx_classify(0x432, &f);
    CHECK(f.kind == DSHOT_FRAME_VOLT && f.data == 0x32, "0x432 is voltage");
    dshot_rx_classify(0x67C, &f);
    CHECK(f.kind == DSHOT_FRAME_CURR && f.data == 0x7C, "0x67C is current");
    dshot_rx_classify(0xE00, &f);
    CHECK(f.kind == DSHOT_FRAME_EVENT && f.raw == 0xE00, "0xE00 is the EDT-enabled event");
    // eRPM: exponent 1, mantissa 0x135 (bit 8 set) -> period 618 us -> 97087 eRPM
    dshot_rx_classify((1 << 9) | 0x135, &f);
    CHECK(f.kind == DSHOT_FRAME_ERPM && f.erpm == 60000000u / (0x135u << 1), "eRPM decode");
    dshot_rx_classify(0x000, &f);
    CHECK(f.kind == DSHOT_FRAME_ERPM && f.erpm == 0, "zero period is 0 eRPM");
}

static void test_fixtures(void) {
    int decoded = 0, rejected = 0, wrong = 0;
    for (size_t i = 0; i < sizeof(rx_fixtures) / sizeof(rx_fixtures[0]); i++) {
        const rx_fixture_t* fx = &rx_fixtures[i];
        uint16_t v = 0;
        dshot_rx_result_t r = dshot_rx_decode_samples(fx->words, &v);
        if (r == DSHOT_RX_OK) {
            if (v != fx->value) {
                wrong++;
                CHECK(0, "fixture %zu decoded 0x%03x, expected 0x%03x", i, v, fx->value);
            }
            decoded++;
        } else {
            rejected++;
            CHECK(!fx->must_decode, "fixture %zu rejected (result %d), expected 0x%03x", i, r, fx->value);
        }
    }
    printf("fixtures: %d decoded, %d rejected, %d wrong\n", decoded, rejected, wrong);
}

static void test_idle_line(void) {
    const uint32_t idle[4] = {0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF};
    uint16_t v;
    CHECK(dshot_rx_decode_samples(idle, &v) == DSHOT_RX_NO_START, "idle line has no start bit");
    const uint32_t stuck_low[4] = {0, 0, 0, 0};
    CHECK(dshot_rx_decode_samples(stuck_low, &v) != DSHOT_RX_OK, "stuck-low line is rejected");
}

int main(void) {
    test_classify();
    test_idle_line();
    test_fixtures();
    printf(failures ? "FAILED (%d)\n" : "PASS\n", failures);
    return failures ? 1 : 0;
}
