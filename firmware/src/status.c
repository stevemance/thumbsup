#include "status.h"
#include "config.h"
#include "ws2812.h"
#include "pico/stdlib.h"
#include <stdio.h>

// LED state structure
typedef struct {
    uint32_t color;
    uint32_t target_color;
    led_effect_t effect;
    uint32_t last_update;
    bool state;  // For blinking
    uint8_t brightness;  // For pulse/fade effects
    int8_t brightness_delta;  // For pulse direction
} led_state_t;

static led_state_t leds[NUM_STATUS_LEDS] = {0};
static system_status_t current_system_status = SYSTEM_STATUS_BOOT;
static weapon_status_t current_weapon_status = WEAPON_STATUS_DISARMED;
static bool status_initialized = false;

// Color map for system status
static const uint32_t system_status_colors[] = {
    [SYSTEM_STATUS_BOOT]         = LED_COLOR_BOOT,
    [SYSTEM_STATUS_READY]        = LED_COLOR_READY,
    [SYSTEM_STATUS_CONNECTED]    = LED_COLOR_CONNECTED,
    [SYSTEM_STATUS_FAILSAFE]     = LED_COLOR_FAILSAFE,
    [SYSTEM_STATUS_LOW_BATTERY]  = LED_COLOR_LOW_BATTERY,
    [SYSTEM_STATUS_CRITICAL_BAT] = LED_COLOR_CRITICAL_BAT,
    [SYSTEM_STATUS_ERROR]        = LED_COLOR_ERROR,
    [SYSTEM_STATUS_EMERGENCY]    = LED_COLOR_EMERGENCY,
    [SYSTEM_STATUS_TEST_MODE]    = LED_COLOR_TEST_MODE
};

// Color map for weapon status
static const uint32_t weapon_status_colors[] = {
    [WEAPON_STATUS_DISARMED]  = LED_COLOR_WEAPON_OFF,
    [WEAPON_STATUS_ARMING]    = LED_COLOR_WEAPON_ARMING,
    [WEAPON_STATUS_ARMED]     = LED_COLOR_WEAPON_ARMED,
    [WEAPON_STATUS_SPINNING]  = LED_COLOR_WEAPON_SPIN,
    [WEAPON_STATUS_EMERGENCY] = LED_COLOR_WEAPON_ESTOP
};

// Helper function to get blink rate from effect
static uint32_t get_blink_rate(led_effect_t effect) {
    switch (effect) {
        case LED_EFFECT_BLINK_SLOW:   return LED_BLINK_SLOW;
        case LED_EFFECT_BLINK_MEDIUM: return LED_BLINK_MEDIUM;
        case LED_EFFECT_BLINK_FAST:   return LED_BLINK_FAST;
        default:                       return 0;
    }
}

// Helper to scale color by brightness (GRB format)
static uint32_t scale_color(uint32_t color, uint8_t brightness) {
    if (brightness == 255) return color;

    uint8_t g = (color >> 16) & 0xFF;
    uint8_t r = (color >> 8) & 0xFF;
    uint8_t b = color & 0xFF;

    g = (g * brightness) / 255;
    r = (r * brightness) / 255;
    b = (b * brightness) / 255;

    return ((uint32_t)g << 16) | ((uint32_t)r << 8) | b;
}

bool status_init(void) {
    if (status_initialized) {
        return true;
    }

    // Initialize WS2812 driver
    if (!ws2812_init(PIN_STATUS_LEDS, NUM_STATUS_LEDS)) {
        printf("ERROR: Failed to initialize WS2812 driver\n");
        return false;
    }

    // Initialize LED states
    for (int i = 0; i < NUM_STATUS_LEDS; i++) {
        leds[i].color = LED_COLOR_OFF;
        leds[i].target_color = LED_COLOR_OFF;
        leds[i].effect = LED_EFFECT_SOLID;
        leds[i].last_update = 0;
        leds[i].state = false;
        leds[i].brightness = 255;
        leds[i].brightness_delta = 5;
    }

    // Set initial boot status
    status_set_system(SYSTEM_STATUS_BOOT, LED_EFFECT_PULSE);
    status_set_weapon(WEAPON_STATUS_DISARMED, LED_EFFECT_SOLID);

    ws2812_show();
    status_initialized = true;

    printf("Status LED system initialized (SK6812)\n");
    return true;
}

void status_update(void) {
    if (!status_initialized) {
        return;
    }

    uint32_t current_time = to_ms_since_boot(get_absolute_time());

    for (int i = 0; i < NUM_STATUS_LEDS; i++) {
        led_state_t *led = &leds[i];
        uint32_t display_color = led->target_color;

        switch (led->effect) {
            case LED_EFFECT_SOLID:
                // Just display the color as-is
                ws2812_set_pixel(i, display_color);
                break;

            case LED_EFFECT_BLINK_SLOW:
            case LED_EFFECT_BLINK_MEDIUM:
            case LED_EFFECT_BLINK_FAST: {
                uint32_t blink_rate = get_blink_rate(led->effect);
                if ((current_time - led->last_update) >= blink_rate) {
                    led->state = !led->state;
                    led->last_update = current_time;
                }
                ws2812_set_pixel(i, led->state ? display_color : LED_COLOR_OFF);
                break;
            }

            case LED_EFFECT_PULSE: {
                // Smooth breathing effect
                if ((current_time - led->last_update) >= 20) {  // Update every 20ms
                    led->brightness += led->brightness_delta;

                    // Reverse direction at limits
                    if (led->brightness >= 255) {
                        led->brightness = 255;
                        led->brightness_delta = -5;
                    } else if (led->brightness <= 32) {
                        led->brightness = 32;
                        led->brightness_delta = 5;
                    }

                    led->last_update = current_time;
                }
                display_color = scale_color(display_color, led->brightness);
                ws2812_set_pixel(i, display_color);
                break;
            }

            case LED_EFFECT_FADE: {
                // Fade in effect
                if ((current_time - led->last_update) >= 10) {  // Update every 10ms
                    if (led->brightness < 255) {
                        led->brightness += 5;
                        if (led->brightness > 255) led->brightness = 255;
                    }
                    led->last_update = current_time;
                }
                display_color = scale_color(display_color, led->brightness);
                ws2812_set_pixel(i, display_color);
                break;
            }
        }
    }

    // Update the physical LEDs
    ws2812_show();
}

void status_set_system(system_status_t status, led_effect_t effect) {
    if (!status_initialized) {
        return;
    }

    current_system_status = status;
    leds[0].target_color = system_status_colors[status];
    leds[0].effect = effect;
    leds[0].last_update = to_ms_since_boot(get_absolute_time());

    // Reset effect state
    if (effect == LED_EFFECT_PULSE || effect == LED_EFFECT_FADE) {
        leds[0].brightness = (effect == LED_EFFECT_FADE) ? 0 : 128;
        leds[0].brightness_delta = 5;
    } else {
        leds[0].brightness = 255;
        leds[0].state = false;
    }
}

void status_set_weapon(weapon_status_t status, led_effect_t effect) {
    if (!status_initialized) {
        return;
    }

    current_weapon_status = status;
    leds[1].target_color = weapon_status_colors[status];
    leds[1].effect = effect;
    leds[1].last_update = to_ms_since_boot(get_absolute_time());

    // Reset effect state
    if (effect == LED_EFFECT_PULSE || effect == LED_EFFECT_FADE) {
        leds[1].brightness = (effect == LED_EFFECT_FADE) ? 0 : 128;
        leds[1].brightness_delta = 5;
    } else {
        leds[1].brightness = 255;
        leds[1].state = false;
    }
}

void status_set_led_color(uint8_t led_index, uint32_t grb_color, led_effect_t effect) {
    if (!status_initialized || led_index >= NUM_STATUS_LEDS) {
        return;
    }

    leds[led_index].target_color = grb_color;
    leds[led_index].effect = effect;
    leds[led_index].last_update = to_ms_since_boot(get_absolute_time());

    // Reset effect state
    if (effect == LED_EFFECT_PULSE || effect == LED_EFFECT_FADE) {
        leds[led_index].brightness = (effect == LED_EFFECT_FADE) ? 0 : 128;
        leds[led_index].brightness_delta = 5;
    } else {
        leds[led_index].brightness = 255;
        leds[led_index].state = false;
    }
}

void status_emergency_flash(void) {
    if (!status_initialized) {
        return;
    }

    // Flash both LEDs red rapidly
    status_set_led_color(0, LED_COLOR_EMERGENCY, LED_EFFECT_BLINK_FAST);
    status_set_led_color(1, LED_COLOR_WEAPON_ESTOP, LED_EFFECT_BLINK_FAST);
}

void status_test_pattern(void) {
    if (!status_initialized) {
        return;
    }

    static const uint32_t test_colors[] = {
        0x00200000,  // Green (GRB)
        0x00002000,  // Red (GRB)
        0x00000020,  // Blue
        0x00202000,  // Yellow
        0x00200020,  // Cyan
        0x00002020,  // Magenta
        0x00202020   // White
    };

    static uint8_t color_index = 0;

    ws2812_set_pixel(0, test_colors[color_index]);
    ws2812_set_pixel(1, test_colors[(color_index + 3) % 7]);
    ws2812_show();

    color_index = (color_index + 1) % 7;
}

void status_all_off(void) {
    if (!status_initialized) {
        return;
    }

    for (int i = 0; i < NUM_STATUS_LEDS; i++) {
        leds[i].target_color = LED_COLOR_OFF;
        leds[i].effect = LED_EFFECT_SOLID;
    }
    ws2812_clear();
    ws2812_show();
}

system_status_t status_get_system(void) {
    return current_system_status;
}

weapon_status_t status_get_weapon(void) {
    return current_weapon_status;
}
