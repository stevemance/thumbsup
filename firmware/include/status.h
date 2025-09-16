#ifndef STATUS_H
#define STATUS_H

#include <stdint.h>
#include <stdbool.h>

typedef enum {
    STATUS_LED_OFF,
    STATUS_LED_ON,
    STATUS_LED_BLINK_SLOW,
    STATUS_LED_BLINK_MEDIUM,
    STATUS_LED_BLINK_FAST
} status_led_mode_t;

bool status_init(void);
void status_update(void);
void status_set_led(uint8_t led_pin, status_led_mode_t mode);
void status_set_all_leds(status_led_mode_t mode);

#endif // STATUS_H