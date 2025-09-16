#ifndef WEAPON_H
#define WEAPON_H

#include <stdint.h>
#include <stdbool.h>

typedef enum {
    WEAPON_STATE_DISARMED,
    WEAPON_STATE_ARMING,
    WEAPON_STATE_ARMED,
    WEAPON_STATE_SPINNING,
    WEAPON_STATE_EMERGENCY_STOP
} weapon_state_t;

bool weapon_init(void);
void weapon_update(void);
bool weapon_arm(void);
bool weapon_disarm(void);
bool weapon_set_speed(uint8_t speed_percent);
weapon_state_t weapon_get_state(void);
uint8_t weapon_get_speed(void);
bool weapon_is_armed(void);
void weapon_emergency_stop(void);

#endif // WEAPON_H