#include "ws2812.h"
#include "ws2812.pio.h"
#include "hardware/pio.h"
#include "hardware/clocks.h"
#include "pico/time.h"
#include <stdlib.h>
#include <string.h>

#define WS2812_FREQ 800000  // 800 kHz

static PIO pio = NULL;
static uint sm = 0;
static uint offset = 0;
static uint32_t *pixel_buffer = NULL;
static uint num_pixels = 0;
static bool initialized = false;

bool ws2812_init(uint pin, uint num_leds) {
    if (initialized) {
        return true;
    }

    // Allocate pixel buffer
    pixel_buffer = (uint32_t *)calloc(num_leds, sizeof(uint32_t));
    if (pixel_buffer == NULL) {
        return false;
    }
    num_pixels = num_leds;

    // Find a free PIO and state machine
    pio = pio0;
    sm = pio_claim_unused_sm(pio, false);
    if (sm == -1) {
        // Try PIO1 if PIO0 is full
        pio = pio1;
        sm = pio_claim_unused_sm(pio, false);
        if (sm == -1) {
            free(pixel_buffer);
            pixel_buffer = NULL;
            return false;
        }
    }

    // Load the PIO program
    offset = pio_add_program(pio, &ws2812_program);

    // Initialize the PIO program
    // false = RGB mode (not RGBW)
    ws2812_program_init(pio, sm, offset, pin, WS2812_FREQ, false);

    initialized = true;
    return true;
}

void ws2812_set_pixel(uint led_index, uint32_t grb_color) {
    if (!initialized || led_index >= num_pixels) {
        return;
    }
    pixel_buffer[led_index] = grb_color;
}

void ws2812_show(void) {
    if (!initialized) {
        return;
    }

    for (uint i = 0; i < num_pixels; i++) {
        // Convert GRB to the format expected by PIO (left-shifted for 24-bit mode)
        uint32_t pixel = pixel_buffer[i] << 8u;
        pio_sm_put_blocking(pio, sm, pixel);
    }

    // Add a small delay to meet the reset time requirement (>50us)
    sleep_us(60);
}

void ws2812_clear(void) {
    if (!initialized) {
        return;
    }
    memset(pixel_buffer, 0, num_pixels * sizeof(uint32_t));
}

void ws2812_fill(uint32_t grb_color) {
    if (!initialized) {
        return;
    }
    for (uint i = 0; i < num_pixels; i++) {
        pixel_buffer[i] = grb_color;
    }
}

uint32_t ws2812_get_pixel(uint led_index) {
    if (!initialized || led_index >= num_pixels) {
        return 0;
    }
    return pixel_buffer[led_index];
}

inline void ws2812_put_pixel(uint32_t grb_color) {
    if (!initialized) {
        return;
    }
    pio_sm_put_blocking(pio, sm, grb_color << 8u);
}

void ws2812_deinit(void) {
    if (!initialized) {
        return;
    }

    // Disable the state machine
    pio_sm_set_enabled(pio, sm, false);

    // Remove the program
    pio_remove_program(pio, &ws2812_program, offset);

    // Free the state machine
    pio_sm_unclaim(pio, sm);

    // Free pixel buffer
    if (pixel_buffer != NULL) {
        free(pixel_buffer);
        pixel_buffer = NULL;
    }

    num_pixels = 0;
    initialized = false;
}
