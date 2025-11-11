#ifndef WS2812_H
#define WS2812_H

#include <stdint.h>
#include <stdbool.h>
#include "hardware/pio.h"

// WS2812/SK6812 addressable LED driver
// Uses PIO for precise timing

// Initialize the WS2812 driver
// pin: GPIO pin number for data line
// num_leds: Number of LEDs in the chain
// Returns: true on success, false on failure
bool ws2812_init(uint pin, uint num_leds);

// Set a single LED color
// led_index: Index of LED (0-based)
// grb_color: 24-bit color in GRB format (0x00GGRRBB)
void ws2812_set_pixel(uint led_index, uint32_t grb_color);

// Update all LEDs with the current pixel buffer
// Call this after setting pixels to actually display them
void ws2812_show(void);

// Clear all LEDs (set to black/off)
void ws2812_clear(void);

// Set all LEDs to the same color
void ws2812_fill(uint32_t grb_color);

// Get the current color of a specific LED
uint32_t ws2812_get_pixel(uint led_index);

// Put a single pixel directly (bypasses buffer)
// grb_color: 24-bit color in GRB format
static inline void ws2812_put_pixel(uint32_t grb_color);

// Deinitialize the WS2812 driver
void ws2812_deinit(void);

#endif // WS2812_H
