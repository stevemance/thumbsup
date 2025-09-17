#ifndef MOTOR_CONTROL_H
#define MOTOR_CONTROL_H

#include <stdint.h>
#include <stdbool.h>

typedef enum {
    MOTOR_LEFT_DRIVE,
    MOTOR_RIGHT_DRIVE,
    MOTOR_WEAPON,
    MOTOR_COUNT
} motor_channel_t;

typedef struct {
    uint8_t gpio_pin;
    uint8_t pwm_slice;
    uint8_t pwm_channel;
    uint16_t current_pulse_us;
    uint16_t target_pulse_us;
    bool reversed;
} motor_config_t;

bool motor_control_init(void);
bool motor_control_update(void);
bool motor_control_set_pulse(motor_channel_t channel, uint16_t pulse_us);
bool motor_control_set_speed(motor_channel_t channel, int8_t speed);
void motor_control_stop_all(void);
uint16_t motor_control_get_pulse(motor_channel_t channel);
void motor_control_emergency_stop(void);

// Utility macros moved to config.h

#endif // MOTOR_CONTROL_H