#include "motor_control.h"
#include "config.h"
#include "hardware/pwm.h"
#include "hardware/clocks.h"
#include <stdio.h>
#include <stdlib.h>

static motor_config_t motors[MOTOR_COUNT];
static bool initialized = false;

static uint16_t speed_to_pulse(int8_t speed) {
    // SAFETY: Clamp input to prevent overflow
    speed = CLAMP(speed, -100, 100);

    const int16_t mid_pulse = PWM_NEUTRAL_PULSE;

    if (speed == 0) {
        return mid_pulse;
    }

    // SAFETY: Use 32-bit arithmetic to prevent overflow, then clamp result
    if (speed > 0) {
        int32_t pulse = mid_pulse + ((int32_t)speed * (PWM_MAX_PULSE - mid_pulse)) / 100;
        return (uint16_t)CLAMP(pulse, PWM_MIN_PULSE, PWM_MAX_PULSE);
    } else {
        int32_t pulse = mid_pulse + ((int32_t)speed * (mid_pulse - PWM_MIN_PULSE)) / 100;
        return (uint16_t)CLAMP(pulse, PWM_MIN_PULSE, PWM_MAX_PULSE);
    }
}

static void setup_pwm_pin(uint8_t pin, uint8_t* slice, uint8_t* channel) {
    // SAFETY: Validate pointer parameters
    if (slice == NULL || channel == NULL) {
        DEBUG_PRINT("CRITICAL: NULL pointer passed to setup_pwm_pin\n");
        return;
    }

    gpio_set_function(pin, GPIO_FUNC_PWM);
    *slice = pwm_gpio_to_slice_num(pin);
    *channel = pwm_gpio_to_channel(pin);

    pwm_config cfg = pwm_get_default_config();

    uint32_t clock_freq = 125000000;
    uint32_t divider = clock_freq / (PWM_FREQUENCY * PWM_WRAP_VALUE);
    pwm_config_set_clkdiv(&cfg, divider);
    pwm_config_set_wrap(&cfg, PWM_WRAP_VALUE - 1);

    pwm_init(*slice, &cfg, false);
}

bool motor_control_init(void) {
    if (initialized) {
        return true;
    }

    motors[MOTOR_LEFT_DRIVE].gpio_pin = PIN_DRIVE_LEFT_PWM;
    motors[MOTOR_LEFT_DRIVE].reversed = false;
    setup_pwm_pin(PIN_DRIVE_LEFT_PWM,
                  &motors[MOTOR_LEFT_DRIVE].pwm_slice,
                  &motors[MOTOR_LEFT_DRIVE].pwm_channel);

    motors[MOTOR_RIGHT_DRIVE].gpio_pin = PIN_DRIVE_RIGHT_PWM;
    motors[MOTOR_RIGHT_DRIVE].reversed = true;
    setup_pwm_pin(PIN_DRIVE_RIGHT_PWM,
                  &motors[MOTOR_RIGHT_DRIVE].pwm_slice,
                  &motors[MOTOR_RIGHT_DRIVE].pwm_channel);

    motors[MOTOR_WEAPON].gpio_pin = PIN_WEAPON_PWM;
    motors[MOTOR_WEAPON].reversed = false;
    setup_pwm_pin(PIN_WEAPON_PWM,
                  &motors[MOTOR_WEAPON].pwm_slice,
                  &motors[MOTOR_WEAPON].pwm_channel);

    // CRITICAL SAFETY: Initialize all motors to safe states
    for (int i = 0; i < MOTOR_COUNT; i++) {
        if (i == MOTOR_WEAPON) {
            // Weapon motor MUST start with minimum pulse (off)
            motors[i].current_pulse_us = PWM_MIN_PULSE;
            motors[i].target_pulse_us = PWM_MIN_PULSE;
            uint32_t pulse_cycles = (PWM_MIN_PULSE * PWM_WRAP_VALUE) / 20000;
            pwm_set_chan_level(motors[i].pwm_slice, motors[i].pwm_channel, pulse_cycles);
        } else {
            // Drive motors start at neutral (stopped)
            motors[i].current_pulse_us = PWM_NEUTRAL_PULSE;
            motors[i].target_pulse_us = PWM_NEUTRAL_PULSE;
            uint32_t pulse_cycles = (PWM_NEUTRAL_PULSE * PWM_WRAP_VALUE) / 20000;
            pwm_set_chan_level(motors[i].pwm_slice, motors[i].pwm_channel, pulse_cycles);
        }
        pwm_set_enabled(motors[i].pwm_slice, true);
    }

    initialized = true;
    DEBUG_PRINT("Motor control initialized\n");

    return true;
}

bool motor_control_update(void) {
    if (!initialized) {
        return false;
    }

    for (int i = 0; i < MOTOR_COUNT; i++) {
        if (motors[i].current_pulse_us != motors[i].target_pulse_us) {
            int16_t diff = motors[i].target_pulse_us - motors[i].current_pulse_us;
            int16_t step = 10;

            if (abs(diff) <= step) {
                motors[i].current_pulse_us = motors[i].target_pulse_us;
            } else if (diff > 0) {
                motors[i].current_pulse_us += step;
            } else {
                motors[i].current_pulse_us -= step;
            }

            uint32_t pulse_cycles = (motors[i].current_pulse_us * PWM_WRAP_VALUE) / 20000;
            pwm_set_chan_level(motors[i].pwm_slice, motors[i].pwm_channel, pulse_cycles);
        }
    }

    return true;
}

bool motor_control_set_pulse(motor_channel_t channel, uint16_t pulse_us) {
    if (!initialized || channel >= MOTOR_COUNT) {
        DEBUG_PRINT("Motor control error: invalid channel %d\n", channel);
        return false;
    }

    // SAFETY: Additional validation for weapon motor
    if (channel == MOTOR_WEAPON) {
        // Weapon motor can only receive MIN_PULSE (off) when not properly armed
        extern bool bluetooth_platform_is_armed(void);
        extern bool bluetooth_platform_failsafe_active(void);

        if (bluetooth_platform_failsafe_active() || !bluetooth_platform_is_armed()) {
            if (pulse_us != PWM_MIN_PULSE) {
                DEBUG_PRINT("SAFETY: Weapon pulse blocked - not armed or failsafe active\n");
                pulse_us = PWM_MIN_PULSE;
            }
        }
    }

    // Strict pulse validation with logging
    if (pulse_us < PWM_MIN_PULSE || pulse_us > PWM_MAX_PULSE) {
        DEBUG_PRINT("Motor control error: invalid pulse %d for channel %d\n", pulse_us, channel);
        pulse_us = CLAMP(pulse_us, PWM_MIN_PULSE, PWM_MAX_PULSE);
    }

    motors[channel].target_pulse_us = pulse_us;

    return true;
}

bool motor_control_set_speed(motor_channel_t channel, int8_t speed) {
    if (!initialized || channel >= MOTOR_COUNT) {
        return false;
    }

    speed = CLAMP(speed, -100, 100);

    if (motors[channel].reversed) {
        speed = -speed;
    }

    uint16_t pulse = speed_to_pulse(speed);
    return motor_control_set_pulse(channel, pulse);
}

void motor_control_stop_all(void) {
    if (!initialized) {
        return;
    }

    for (int i = 0; i < MOTOR_COUNT; i++) {
        if (i == MOTOR_WEAPON) {
            motors[i].target_pulse_us = PWM_MIN_PULSE;
            motors[i].current_pulse_us = PWM_MIN_PULSE;
        } else {
            motors[i].target_pulse_us = PWM_NEUTRAL_PULSE;
            motors[i].current_pulse_us = PWM_NEUTRAL_PULSE;
        }

        uint32_t pulse_cycles = (motors[i].current_pulse_us * PWM_WRAP_VALUE) / 20000;
        pwm_set_chan_level(motors[i].pwm_slice, motors[i].pwm_channel, pulse_cycles);
    }
}

uint16_t motor_control_get_pulse(motor_channel_t channel) {
    if (!initialized || channel >= MOTOR_COUNT) {
        return PWM_NEUTRAL_PULSE;
    }

    return motors[channel].current_pulse_us;
}

void motor_control_emergency_stop(void) {
    motor_control_stop_all();

    for (int i = 0; i < MOTOR_COUNT; i++) {
        pwm_set_enabled(motors[i].pwm_slice, false);
    }

    initialized = false;
    DEBUG_PRINT("Emergency stop activated!\n");
}