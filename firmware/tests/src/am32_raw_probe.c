#include <stdio.h>
#include <string.h>

#include "pico/stdlib.h"
#include "hardware/gpio.h"
#include "hardware/sync.h"

#define AM32_PIN 4

#define ENTRY_PULSES 10
#define ENTRY_PULSE_US 100
#define ENTRY_GAP_US 900

static bool tx_push_pull = false;
static uint32_t bit_us = 52;
static uint32_t half_bit_us = 26;

static void set_baud(uint32_t baud) {
    if (baud == 0) {
        baud = 19200;
    }
    bit_us = (1000000u + (baud / 2u)) / baud;
    if (bit_us == 0) {
        bit_us = 1;
    }
    half_bit_us = bit_us / 2u;
    if (half_bit_us == 0) {
        half_bit_us = 1;
    }
}

static inline void line_low(void) {
    gpio_set_dir(AM32_PIN, GPIO_OUT);
    gpio_put(AM32_PIN, 0);
}

static inline void line_high(void) {
    gpio_set_dir(AM32_PIN, GPIO_OUT);
    gpio_put(AM32_PIN, 1);
}

static inline void line_release(void) {
    gpio_set_dir(AM32_PIN, GPIO_IN);
    gpio_pull_up(AM32_PIN);
}

static inline void line_tx_one(void) {
    if (tx_push_pull) {
        line_high();
    } else {
        line_release();
    }
}

static void tx_byte(uint8_t byte) {
    uint32_t irq = save_and_disable_interrupts();
    line_low();
    busy_wait_us_32(bit_us);
    for (int i = 0; i < 8; i++) {
        if ((byte >> i) & 1u) {
            line_tx_one();
        } else {
            line_low();
        }
        busy_wait_us_32(bit_us);
    }
    line_tx_one();
    busy_wait_us_32(bit_us);
    line_release();
    restore_interrupts(irq);
}

static int rx_byte(uint32_t timeout_us) {
    uint32_t start = time_us_32();
    line_release();

    // Require idle-high.
    while (!gpio_get(AM32_PIN)) {
        if ((time_us_32() - start) > timeout_us) {
            return -1;
        }
        tight_loop_contents();
    }
    // Wait for start low.
    while (gpio_get(AM32_PIN)) {
        if ((time_us_32() - start) > timeout_us) {
            return -1;
        }
        tight_loop_contents();
    }

    uint32_t irq = save_and_disable_interrupts();
    busy_wait_us_32(bit_us + half_bit_us);
    if (gpio_get(AM32_PIN)) {
        restore_interrupts(irq);
        return -2;
    }
    uint8_t v = 0;
    for (int i = 0; i < 8; i++) {
        if (gpio_get(AM32_PIN)) {
            v |= (uint8_t)(1u << i);
        }
        busy_wait_us_32(bit_us);
    }
    bool stop_high = gpio_get(AM32_PIN);
    restore_interrupts(irq);
    if (!stop_high) {
        return -3;
    }
    return (int)v;
}

static uint8_t xor_checksum(uint8_t cmd, const uint8_t* payload, uint16_t len) {
    uint8_t c = cmd ^ (uint8_t)(len & 0xFFu) ^ (uint8_t)(len >> 8);
    for (uint16_t i = 0; i < len; i++) {
        c ^= payload[i];
    }
    return c;
}

static void send_frame(uint8_t cmd, const uint8_t* payload, uint16_t len) {
    uint8_t c = xor_checksum(cmd, payload, len);
    tx_byte(cmd);
    tx_byte((uint8_t)(len & 0xFFu));
    tx_byte((uint8_t)(len >> 8));
    for (uint16_t i = 0; i < len; i++) {
        tx_byte(payload[i]);
    }
    tx_byte(c);
}

static bool read_response(uint8_t* out, uint16_t out_cap, uint16_t* out_len, uint32_t timeout_us) {
    if (!out || !out_len || out_cap == 0) {
        return false;
    }
    int h0 = rx_byte(timeout_us);
    if (h0 < 0) {
        return false;
    }
    int h1 = rx_byte(timeout_us);
    if (h1 < 0) {
        return false;
    }
    uint16_t len = (uint16_t)((uint16_t)h0 | ((uint16_t)h1 << 8));
    if (len == 0) {
        *out_len = 0;
        return true;
    }
    if (len > out_cap) {
        return false;
    }
    for (uint16_t i = 0; i < len; i++) {
        int b = rx_byte(timeout_us);
        if (b < 0) {
            return false;
        }
        out[i] = (uint8_t)b;
    }
    *out_len = len;
    return true;
}

static uint32_t count_edges(uint32_t duration_us) {
    uint32_t edges = 0;
    uint32_t start = time_us_32();
    bool last = gpio_get(AM32_PIN);
    while ((time_us_32() - start) < duration_us) {
        bool now = gpio_get(AM32_PIN);
        if (now != last) {
            edges++;
            last = now;
        }
    }
    return edges;
}

static bool read_response_scan(uint8_t* out, uint16_t out_cap, uint16_t* out_len, uint32_t timeout_us) {
    uint8_t stream[768] = {0};
    uint16_t n = 0;
    uint32_t start = time_us_32();
    while ((time_us_32() - start) < timeout_us && n < sizeof(stream)) {
        int b = rx_byte(timeout_us - (time_us_32() - start));
        if (b < 0) {
            break;
        }
        stream[n++] = (uint8_t)b;
        if (n < 2) {
            continue;
        }
        for (uint16_t off = 0; off + 2 <= n; off++) {
            uint16_t len = (uint16_t)(stream[off] | ((uint16_t)stream[off + 1] << 8));
            if (len == 0) {
                *out_len = 0;
                return true;
            }
            if (len > out_cap) {
                continue;
            }
            if ((uint16_t)(off + 2 + len) <= n) {
                memcpy(out, &stream[off + 2], len);
                *out_len = len;
                return true;
            }
        }
    }
    return false;
}

static void send_entry_pulses(bool low_then_high) {
    for (int i = 0; i < ENTRY_PULSES; i++) {
        if (low_then_high) {
            line_low();
            sleep_us(ENTRY_PULSE_US);
            line_high();
            sleep_us(ENTRY_GAP_US);
        } else {
            line_high();
            sleep_us(ENTRY_PULSE_US);
            line_low();
            sleep_us(ENTRY_GAP_US);
        }
    }
    line_release();
}

static void dump_hex(const uint8_t* data, uint16_t len) {
    for (uint16_t i = 0; i < len; i++) {
        printf("%02X ", data[i]);
        if ((i + 1) % 16 == 0) {
            printf("\n");
        }
    }
    if (len % 16 != 0) {
        printf("\n");
    }
}

static bool run_variant(const char* name, bool push_pull, bool use_pulses, bool low_then_high, uint32_t baud) {
    uint8_t buf[512] = {0};
    uint16_t len = 0;
    bool got_plausible = false;

    tx_push_pull = push_pull;
    set_baud(baud);
    line_release();

    printf("\n--- Variant: %s ---\n", name);
    printf("  baud=%lu push_pull=%d pulses=%d low_then_high=%d\n", baud, push_pull ? 1 : 0, use_pulses ? 1 : 0, low_then_high ? 1 : 0);
    printf("  line before: %s\n", gpio_get(AM32_PIN) ? "HIGH" : "LOW");

    if (use_pulses) {
        send_entry_pulses(low_then_high);
        sleep_ms(250);
    }

    // KEEPALIVE
    send_frame(0xFF, NULL, 0);
    len = sizeof(buf);
    if (read_response_scan(buf, sizeof(buf), &len, 300000)) {
        printf("  KEEPALIVE len=%u\n", len);
    } else {
        printf("  KEEPALIVE no response (edges=%lu)\n", count_edges(20000));
    }

    // GET_INFO
    memset(buf, 0, sizeof(buf));
    send_frame(0xCC, NULL, 0);
    len = sizeof(buf);
    if (read_response_scan(buf, sizeof(buf), &len, 350000)) {
        printf("  GET_INFO len=%u\n", len);
        if (len > 0) {
            dump_hex(buf, len < 64 ? len : 64);
            if (len >= 4 && !(buf[0] == 0 && buf[1] == 0 && buf[2] == 0)) {
                got_plausible = true;
            }
        }
    } else {
        printf("  GET_INFO no response (edges=%lu)\n", count_edges(20000));
    }

    // GET_SETTINGS
    memset(buf, 0, sizeof(buf));
    send_frame(0xBB, NULL, 0);
    len = sizeof(buf);
    if (read_response_scan(buf, sizeof(buf), &len, 500000)) {
        printf("  GET_SETTINGS len=%u\n", len);
        if (len >= 32) {
            got_plausible = true;
            printf("  settings[17..31]: ");
            for (int i = 17; i <= 31; i++) {
                printf("%02X ", buf[i]);
            }
            printf("\n");
        }
    } else {
        printf("  GET_SETTINGS no response (edges=%lu)\n", count_edges(20000));
    }

    return got_plausible;
}

int main(void) {
    stdio_init_all();
    sleep_ms(2000);

    gpio_init(AM32_PIN);
    gpio_set_function(AM32_PIN, GPIO_FUNC_SIO);
    line_release();

    printf("\n========================================\n");
    printf("  AM32 Raw One-Wire Probe\n");
    printf("========================================\n");
    printf("Signal: GP4 + GND\n");
    printf("This sweeps signaling variants to find a valid AM32 config link.\n");

    bool ok = false;
    ok |= run_variant("open-drain + pulses low-high @19200", false, true, true, 19200);
    ok |= run_variant("open-drain + pulses high-low @19200", false, true, false, 19200);
    ok |= run_variant("push-pull + pulses low-high @19200", true, true, true, 19200);
    ok |= run_variant("push-pull + pulses high-low @19200", true, true, false, 19200);
    ok |= run_variant("open-drain + no-pulse @19200", false, false, true, 19200);
    ok |= run_variant("push-pull + no-pulse @19200", true, false, true, 19200);
    ok |= run_variant("open-drain + pulses low-high @38400", false, true, true, 38400);
    ok |= run_variant("push-pull + pulses low-high @38400", true, true, true, 38400);

    printf("\n========================================\n");
    if (ok) {
        printf("Probe found at least one plausible response path.\n");
    } else {
        printf("Probe found no plausible AM32 responses.\n");
    }
    printf("========================================\n");

    while (1) {
        sleep_ms(1000);
    }
}
