#ifndef BLUETOOTH_H
#define BLUETOOTH_H

#include <stdint.h>
#include <stdbool.h>

typedef struct {
    bool connected;
    int8_t left_stick_x;
    int8_t left_stick_y;
    int8_t right_stick_x;
    int8_t right_stick_y;
    uint8_t left_trigger;
    uint8_t right_trigger;
    uint16_t buttons;
    bool dpad_up;
    bool dpad_down;
    bool dpad_left;
    bool dpad_right;
    uint32_t last_update;
} gamepad_state_t;

bool bluetooth_init(void);
bool bluetooth_update(gamepad_state_t* gamepad);
bool bluetooth_is_connected(void);
void bluetooth_disconnect(void);
const char* bluetooth_get_device_name(void);

#endif // BLUETOOTH_H