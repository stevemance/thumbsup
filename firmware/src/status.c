#include "status.h"
#include "config.h"
#include "hardware/gpio.h"
#include "pico/stdlib.h"
#include <stdio.h>

typedef struct {
    uint8_t pin;
    status_led_mode_t mode;
    bool state;
    uint32_t last_toggle;
} led_status_t;

static led_status_t leds[] = {
    {PIN_LED_STATUS, STATUS_LED_OFF, false, 0},
    {PIN_LED_ARMED, STATUS_LED_OFF, false, 0},
    {PIN_LED_BATTERY, STATUS_LED_OFF, false, 0}
};

static const int num_leds = sizeof(leds) / sizeof(led_status_t);
static bool status_initialized = false;

bool status_init(void) {
    if (status_initialized) {
        return true;
    }

    for (int i = 0; i < num_leds; i++) {
        gpio_init(leds[i].pin);
        gpio_set_dir(leds[i].pin, GPIO_OUT);
        gpio_put(leds[i].pin, false);
    }

    status_initialized = true;
    DEBUG_PRINT("Status system initialized\n");

    return true;
}

void status_update(void) {
    if (!status_initialized) {
        return;
    }

    uint32_t current_time = to_ms_since_boot(get_absolute_time());

    for (int i = 0; i < num_leds; i++) {
        uint32_t blink_rate = 0;

        switch (leds[i].mode) {
            case STATUS_LED_OFF:
                gpio_put(leds[i].pin, false);
                continue;

            case STATUS_LED_ON:
                gpio_put(leds[i].pin, true);
                continue;

            case STATUS_LED_BLINK_SLOW:
                blink_rate = LED_BLINK_SLOW;
                break;

            case STATUS_LED_BLINK_MEDIUM:
                blink_rate = LED_BLINK_MEDIUM;
                break;

            case STATUS_LED_BLINK_FAST:
                blink_rate = LED_BLINK_FAST;
                break;
        }

        if (blink_rate > 0 && (current_time - leds[i].last_toggle) >= blink_rate) {
            leds[i].state = !leds[i].state;
            gpio_put(leds[i].pin, leds[i].state);
            leds[i].last_toggle = current_time;
        }
    }
}

void status_set_led(uint8_t led_pin, status_led_mode_t mode) {
    for (int i = 0; i < num_leds; i++) {
        if (leds[i].pin == led_pin) {
            leds[i].mode = mode;
            leds[i].last_toggle = to_ms_since_boot(get_absolute_time());
            break;
        }
    }
}

void status_set_all_leds(status_led_mode_t mode) {
    for (int i = 0; i < num_leds; i++) {
        leds[i].mode = mode;
        leds[i].last_toggle = to_ms_since_boot(get_absolute_time());
    }
}