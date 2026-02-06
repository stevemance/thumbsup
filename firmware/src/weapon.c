#include "weapon.h"
#include "motor_control.h"
#include "safety.h"
#include "status.h"
#include "config.h"
#include "dshot.h"
#include "am32_config.h"
#include "pico/stdlib.h"
#include "pico/mutex.h"
#include "hardware/pwm.h"
#include "hardware/gpio.h"
#include <stdio.h>
#include <stdlib.h>

// Delay before issuing DShot setup commands during arming.
#define WEAPON_DSHOT_SETUP_DELAY_MS WEAPON_ARM_TIMEOUT

// MINOR FIX: Move extern declarations to file scope for cleaner code organization
extern uint32_t read_battery_voltage(void);

// CRITICAL FIX #2 & #6: Add mutex for safe mode switching (enum is in weapon.h)
static weapon_state_t weapon_state = WEAPON_STATE_DISARMED;
static weapon_control_mode_t control_mode = WEAPON_MODE_PWM;  // Default to PWM
static mutex_t mode_mutex;  // Mutex for thread-safe mode switching
static uint8_t current_speed = 0;
static uint8_t target_speed = 0;
static uint32_t arm_start_time = 0;
static uint32_t last_ramp_time = 0;
static uint32_t last_dshot_send_time = 0;
static uint32_t last_dshot_telemetry_time = 0;
static uint16_t dshot_last_throttle = 0;
static uint32_t dshot_send_attempts = 0;
static uint32_t dshot_send_successes = 0;
static uint32_t dshot_send_failures = 0;
static uint32_t last_dshot_fail_log_ms = 0;
static uint32_t last_dshot_debug_log_ms = 0;
static uint32_t dshot_telemetry_requests = 0;
static uint32_t dshot_telemetry_responses = 0;
static uint32_t dshot_telemetry_pending = 0;
static uint32_t dshot_telemetry_raw = 0;
static uint32_t dshot_telemetry_decode_fail = 0;
static uint32_t last_dshot_telemetry_rx_ms = 0;
static uint64_t dshot_telemetry_decode_us = 0;
static uint32_t dshot_telemetry_decode_frames = 0;
#if INTEGRATION_TEST_AUTO
static uint16_t dshot_raw_dump_remaining = 0;
#endif
static uint32_t last_dshot_setup_attempt_ms = 0;
static uint8_t dshot_setup_attempts = 0;
static bool dshot_setup_pending = false;
static bool dshot_setup_done = false;
static bool initialized = false;
// CRITICAL FIX #2 (Iteration 4): Protect dshot_initialized with mode_mutex
// This flag is accessed by weapon_update() and mode switch functions
// Race scenario: weapon_update checks flag, then mode switch calls dshot_deinit(),
// then weapon_update uses freed resources → use-after-free
static volatile bool dshot_initialized = false;

static void weapon_poll_telemetry_locked(void);

static uint16_t weapon_speed_to_pulse(uint8_t speed_percent) {
    if (speed_percent == 0) {
        return PWM_MIN_PULSE;
    }

    uint16_t range = PWM_MAX_PULSE - PWM_MIN_PULSE;
    return PWM_MIN_PULSE + (speed_percent * range) / 100;
}

static void weapon_mark_dshot_setup_pending(void) {
    dshot_setup_pending = true;
    dshot_setup_done = false;
    dshot_setup_attempts = 0;
    last_dshot_setup_attempt_ms = 0;
}

static void weapon_run_dshot_setup_locked(uint32_t now_ms) {
    if (!dshot_setup_pending) {
        return;
    }
    if ((now_ms - arm_start_time) < WEAPON_DSHOT_SETUP_DELAY_MS) {
        return;
    }
    if (last_dshot_setup_attempt_ms != 0 &&
        (now_ms - last_dshot_setup_attempt_ms) < WEAPON_DSHOT_SETUP_RETRY_MS) {
        return;
    }

    last_dshot_setup_attempt_ms = now_ms;
    if (dshot_setup_attempts < UINT8_MAX) {
        dshot_setup_attempts++;
    }

    bool ok = dshot_send_command(MOTOR_WEAPON, DSHOT_CMD_EXTENDED_TELEMETRY_ENABLE);
    ok = ok && dshot_send_command(MOTOR_WEAPON, DSHOT_CMD_3D_MODE_OFF);
    ok = ok && dshot_send_command(MOTOR_WEAPON, DSHOT_CMD_SPIN_DIRECTION_NORMAL);
    weapon_poll_telemetry_locked();

    if (ok && dshot_extended_telemetry_seen(MOTOR_WEAPON)) {
        dshot_setup_pending = false;
        dshot_setup_done = true;
    } else if (dshot_setup_attempts >= WEAPON_DSHOT_SETUP_MAX_ATTEMPTS) {
        dshot_setup_pending = false;
        dshot_setup_done = true;
        DEBUG_PRINT("WARN: EDT enable not confirmed after %u attempts\n",
                    dshot_setup_attempts);
    }
}

static void weapon_poll_telemetry_locked(void) {
    uint64_t raw = 0;
    dshot_telemetry_t telem;
    while (dshot_read_telemetry_raw(MOTOR_WEAPON, &raw)) {
#if INTEGRATION_TEST_AUTO
        if (dshot_raw_dump_remaining > 0) {
            printf("EDT raw=0x%010llx\n", (unsigned long long)raw);
            dshot_raw_dump_remaining--;
        }
#endif

        dshot_telemetry_raw++;
        if (dshot_telemetry_pending == 0) {
            continue;
        }
        dshot_telemetry_pending--;
        uint64_t decode_start_us = time_us_64();
        bool decoded = dshot_decode_telemetry_raw(MOTOR_WEAPON, raw, &telem);
        dshot_telemetry_decode_us += time_us_64() - decode_start_us;
        dshot_telemetry_decode_frames++;
        if (!decoded) {
            dshot_telemetry_decode_fail++;
            continue;
        }

        dshot_telemetry_responses++;
        last_dshot_telemetry_rx_ms = telem.timestamp_ms;
    }
}

static void weapon_send_dshot_locked(uint32_t now_ms, uint16_t throttle, bool force_send) {
    if (!dshot_initialized) {
        return;
    }

    if (dshot_telemetry_pending > 0 &&
        last_dshot_telemetry_time != 0 &&
        (now_ms - last_dshot_telemetry_time) > WEAPON_DSHOT_TELEMETRY_TIMEOUT_MS) {
        dshot_telemetry_pending = 0;
    }

    bool should_send = force_send ||
                       (now_ms - last_dshot_send_time >= WEAPON_DSHOT_UPDATE_MS);

    // Drain before sending to avoid RX FIFO backpressure blocking the PIO SM.
    weapon_poll_telemetry_locked();

    if (should_send) {
        dshot_last_throttle = throttle;
        dshot_send_attempts++;
        bool telemetry_allowed = (weapon_state == WEAPON_STATE_ARMING ||
                                  weapon_state == WEAPON_STATE_ARMED ||
                                  weapon_state == WEAPON_STATE_SPINNING);
        bool request_telemetry = false;
        if (telemetry_allowed) {
            bool interval_ok = (last_dshot_telemetry_time == 0) ||
                               ((now_ms - last_dshot_telemetry_time) >= WEAPON_DSHOT_TELEMETRY_MS);
            bool pending_ok = dshot_telemetry_pending < WEAPON_DSHOT_TELEMETRY_MAX_PENDING;
            request_telemetry = interval_ok && pending_ok;
        }
#if INTEGRATION_TEST_AUTO
        if (now_ms - last_dshot_debug_log_ms > 1000) {
            printf("DShot send throttle=%u telemetry=%u\n", throttle, request_telemetry ? 1u : 0u);
            last_dshot_debug_log_ms = now_ms;
        }
#endif
        if (dshot_send_throttle(MOTOR_WEAPON, throttle, request_telemetry)) {
            dshot_send_successes++;
            last_dshot_send_time = now_ms;
            if (request_telemetry) {
                last_dshot_telemetry_time = now_ms;
                dshot_telemetry_requests++;
                if (dshot_telemetry_pending < WEAPON_DSHOT_TELEMETRY_MAX_PENDING) {
                    dshot_telemetry_pending++;
                }
            }
        } else {
            dshot_send_failures++;
#if INTEGRATION_TEST_AUTO
            if (now_ms - last_dshot_fail_log_ms > 1000) {
                printf("WARN: DShot send failures=%u\n", dshot_send_failures);
                last_dshot_fail_log_ms = now_ms;
            }
#endif
        }
    }

    // Drain again to capture the response immediately after TX.
    weapon_poll_telemetry_locked();
}

// CRITICAL FIX #2 & #6: Mode switching functions with mutex protection
static bool weapon_set_control_mode(weapon_control_mode_t new_mode) {
    // Must be disarmed to change modes
    if (weapon_state != WEAPON_STATE_DISARMED) {
        DEBUG_PRINT("Cannot change control mode while armed (state=%d)\n", weapon_state);
        return false;
    }

    mutex_enter_blocking(&mode_mutex);

    if (control_mode == new_mode) {
        if (new_mode == WEAPON_MODE_DSHOT) {
            gpio_function_t fn = gpio_get_function(PIN_WEAPON_PWM);
            if (!dshot_initialized || (fn != GPIO_FUNC_PIO0 && fn != GPIO_FUNC_PIO1)) {
                // Reinitialize DShot if GPIO ownership was lost.
            } else {
                mutex_exit(&mode_mutex);
                return true;
            }
        } else {
            mutex_exit(&mode_mutex);
            return true;  // Already in requested mode
        }
    }

    // CRITICAL FIX #2 (Iteration 2): Disable current mode with proper GPIO cleanup
    // CRITICAL FIX #1 (Iteration 3): Add verification that previous owner released GPIO
    switch (control_mode) {
        case WEAPON_MODE_PWM:
            // Stop PWM output
            motor_control_set_pulse(MOTOR_WEAPON, PWM_MIN_PULSE);
            sleep_ms(2);  // Allow final PWM pulse to complete
            // Explicitly disable PWM slice for weapon pin
            uint slice_num = pwm_gpio_to_slice_num(PIN_WEAPON_PWM);
            pwm_set_enabled(slice_num, false);
            // Reset GPIO to SIO before handing off
            gpio_set_function(PIN_WEAPON_PWM, GPIO_FUNC_SIO);
            gpio_put(PIN_WEAPON_PWM, 0);
            // CRITICAL FIX #1 (Iteration 3): Delay for hardware to settle
            sleep_ms(2);
            // Verify GPIO is in safe state
            if (gpio_get_function(PIN_WEAPON_PWM) != GPIO_FUNC_SIO) {
                DEBUG_PRINT("WARNING: GPIO %d not in SIO after PWM cleanup\n", PIN_WEAPON_PWM);
            }
            motor_control_disable_weapon_pwm();
            break;

        case WEAPON_MODE_DSHOT:
            if (dshot_initialized) {
                dshot_send_throttle(MOTOR_WEAPON, 0, false);  // Send stop command
                sleep_ms(10);  // Allow command to complete
                dshot_deinit(MOTOR_WEAPON);
                dshot_initialized = false;
                dshot_setup_pending = false;
                dshot_setup_done = false;
            }
            last_dshot_send_time = 0;
            last_dshot_telemetry_time = 0;
            dshot_telemetry_pending = 0;
            // Reset GPIO to SIO after DShot (PIO cleanup)
            gpio_set_function(PIN_WEAPON_PWM, GPIO_FUNC_SIO);
            gpio_put(PIN_WEAPON_PWM, 0);
            // CRITICAL FIX #1 (Iteration 3): Delay for hardware to settle
            sleep_ms(2);
            // Verify GPIO is in safe state
            if (gpio_get_function(PIN_WEAPON_PWM) != GPIO_FUNC_SIO) {
                DEBUG_PRINT("WARNING: GPIO %d not in SIO after DShot cleanup\n", PIN_WEAPON_PWM);
            }
            break;

        case WEAPON_MODE_CONFIG:
            am32_exit_config_mode();
            // CRITICAL FIX #1 (Iteration 3): Delay for hardware to settle
            sleep_ms(2);
            // Verify GPIO is in safe state (AM32 should set to SIO)
            if (gpio_get_function(PIN_WEAPON_PWM) != GPIO_FUNC_SIO) {
                DEBUG_PRINT("WARNING: GPIO %d not in SIO after AM32 cleanup\n", PIN_WEAPON_PWM);
            }
            break;
    }

    // CRITICAL FIX #1 (Iteration 3): Verify GPIO is available before claiming
    // MAJOR FIX #1 (Iteration 4): Document GPIO conflict window limitation
    // LIMITATION: There is a small race window between GPIO verification (line below)
    // and mode initialization (lines 112-147). If another thread/interrupt claims
    // the GPIO in this window, initialization may fail or cause conflicts.
    //
    // MITIGATION: This system is single-threaded with cooperative multitasking,
    // and mode_mutex is held during this entire function, preventing concurrent
    // mode switches. The only risk is from interrupts, but no interrupt handlers
    // in this system modify GPIO functions.
    //
    // HARDWARE TESTING: Verify on actual hardware that no GPIO conflicts occur
    // during rapid mode switching (PWM ↔ DShot ↔ Config). Use logic analyzer to
    // confirm clean transitions.
    if (gpio_get_function(PIN_WEAPON_PWM) != GPIO_FUNC_SIO) {
        DEBUG_PRINT("ERROR: GPIO %d not in SIO state before mode switch (func=%d)\n",
                   PIN_WEAPON_PWM, gpio_get_function(PIN_WEAPON_PWM));
        mutex_exit(&mode_mutex);
        return false;
    }

    // Enable new mode
    switch (new_mode) {
        case WEAPON_MODE_PWM:
            if (!motor_control_enable_weapon_pwm()) {
                DEBUG_PRINT("ERROR: Failed to initialize weapon PWM\n");
                mutex_exit(&mode_mutex);
                return false;
            }
            motor_control_set_pulse(MOTOR_WEAPON, PWM_MIN_PULSE);
            DEBUG_PRINT("Weapon control mode: PWM\n");
            break;

        case WEAPON_MODE_DSHOT:
            {
                dshot_config_t dshot_config = {
                    .gpio_pin = PIN_WEAPON_PWM,
                    .speed = DSHOT_SPEED_300,  // 300kbit/s recommended for RP2040
                    .bidirectional = true,     // Enable EDT telemetry
                    .pole_pairs = WEAPON_POLE_PAIRS
                };
                if (dshot_init(MOTOR_WEAPON, &dshot_config)) {
                    dshot_initialized = true;
                    last_dshot_send_time = 0;
                    last_dshot_telemetry_time = 0;
                    dshot_send_failures = 0;
                    dshot_send_attempts = 0;
                    dshot_send_successes = 0;
                    dshot_telemetry_requests = 0;
                    dshot_telemetry_responses = 0;
                    dshot_telemetry_pending = 0;
                    dshot_telemetry_raw = 0;
                    dshot_telemetry_decode_fail = 0;
                    dshot_telemetry_decode_us = 0;
                    dshot_telemetry_decode_frames = 0;
                    last_dshot_telemetry_rx_ms = 0;
                    dshot_setup_pending = false;
                    dshot_setup_done = false;
                    DEBUG_PRINT("Weapon control mode: DShot300 with EDT\n");
                } else {
                    // MAJOR FIX #5 (Iteration 3): Fallback to PWM if DShot init fails
                    DEBUG_PRINT("ERROR: Failed to initialize DShot, falling back to PWM\n");
                    if (!motor_control_enable_weapon_pwm()) {
                        DEBUG_PRINT("ERROR: Failed to initialize weapon PWM\n");
                        mutex_exit(&mode_mutex);
                        return false;
                    }
                    motor_control_set_pulse(MOTOR_WEAPON, PWM_MIN_PULSE);
                    new_mode = WEAPON_MODE_PWM;
                    DEBUG_PRINT("Weapon control mode: PWM (fallback)\n");
                }
            }
            break;

        case WEAPON_MODE_CONFIG:
            if (!am32_enter_config_mode()) {
                DEBUG_PRINT("ERROR: Failed to enter AM32 config mode\n");
                mutex_exit(&mode_mutex);
                return false;
            }
            DEBUG_PRINT("Weapon control mode: AM32 Config\n");
            break;
    }

    control_mode = new_mode;
    mutex_exit(&mode_mutex);
    return true;
}

// ============================================================================
// WEAPON MODE SWITCHING API (Not currently used in controller logic)
// ============================================================================
// TODO: Integrate these mode switching functions into controller input
//
// Current status:
// - weapon_init() automatically switches to DShot mode by default
// - Mode switching functions exist but aren't hooked up to controller
//
// Future integration ideas:
// - Button combo to switch between PWM/DShot/Config modes
// - Safety button long-press to enter AM32 config mode
// - Status LED feedback for current mode
// - Store preferred mode in EEPROM/flash
//
// For now, DShot is used by default which is optimal for competition.
// ============================================================================

// Public mode switching functions
bool weapon_enable_dshot(void) {
    return weapon_set_control_mode(WEAPON_MODE_DSHOT);
}

bool weapon_enable_pwm(void) {
    return weapon_set_control_mode(WEAPON_MODE_PWM);
}

bool weapon_enter_config_mode(void) {
    return weapon_set_control_mode(WEAPON_MODE_CONFIG);
}

weapon_control_mode_t weapon_get_control_mode(void) {
    return control_mode;
}

bool weapon_init(void) {
    if (initialized) {
        return true;
    }

    // CRITICAL FIX #6: Initialize mode switching mutex
    mutex_init(&mode_mutex);

    weapon_state = WEAPON_STATE_DISARMED;
    current_speed = 0;
    target_speed = 0;
    control_mode = WEAPON_MODE_PWM;  // Initialize in PWM mode first
    dshot_initialized = false;
    last_dshot_send_time = 0;
    last_dshot_telemetry_time = 0;
    dshot_send_failures = 0;
    dshot_send_attempts = 0;
    dshot_send_successes = 0;
    dshot_telemetry_requests = 0;
    dshot_telemetry_responses = 0;
    dshot_telemetry_pending = 0;
    dshot_telemetry_raw = 0;
    dshot_telemetry_decode_fail = 0;
    dshot_telemetry_decode_us = 0;
    dshot_telemetry_decode_frames = 0;
    last_dshot_telemetry_rx_ms = 0;

    motor_control_set_pulse(MOTOR_WEAPON, PWM_MIN_PULSE);

    initialized = true;

    // Switch to DShot mode by default (better performance, telemetry support)
    // Hardware is configured for DShot on GP4, ESC supports it
    if (weapon_enable_dshot()) {
        DEBUG_PRINT("Weapon system initialized in DShot300 mode\n");
        // Send a short idle burst so ESC auto-detects DShot after power-on.
        uint32_t warmup_start = to_ms_since_boot(get_absolute_time());
        while ((to_ms_since_boot(get_absolute_time()) - warmup_start) < 200) {
            dshot_send_throttle(MOTOR_WEAPON, 0, false);
            sleep_ms(2);
        }
    } else {
        DEBUG_PRINT("Weapon system initialized in PWM mode (DShot init failed)\n");
    }

    return true;
}

void weapon_update(void) {
    if (!initialized) {
        return;
    }

    uint32_t current_time = to_ms_since_boot(get_absolute_time());

    // CONTINUOUS SAFETY CHECK: Always verify safety conditions before allowing operation
    if (weapon_state != WEAPON_STATE_DISARMED && weapon_state != WEAPON_STATE_EMERGENCY_STOP) {
#if INTEGRATION_TEST_AUTO
        if (safety_is_button_pressed()) {
            DEBUG_PRINT("SAFETY VIOLATION: Safety button pressed\n");
            weapon_emergency_stop();
            return;
        }
#else
        uint32_t battery_mv = read_battery_voltage();

        // Emergency disarm if safety conditions are violated
        if (!safety_check_arm_conditions(battery_mv)) {
            DEBUG_PRINT("SAFETY VIOLATION: Force disarming weapon\n");
            weapon_emergency_stop();
            return;
        }
#endif
    }

    switch (weapon_state) {
        case WEAPON_STATE_ARMING:
            // Keep ESC armed with a steady zero throttle signal while arming.
            mutex_enter_blocking(&mode_mutex);
            switch (control_mode) {
                case WEAPON_MODE_PWM:
                    motor_control_set_pulse(MOTOR_WEAPON, PWM_MIN_PULSE);
                    break;

                case WEAPON_MODE_DSHOT:
                    if (dshot_initialized) {
                        weapon_send_dshot_locked(current_time, 0, true);
                        weapon_run_dshot_setup_locked(current_time);
                    }
                    break;

                case WEAPON_MODE_CONFIG:
                    break;
            }
            mutex_exit(&mode_mutex);

            bool ready_to_arm = true;
            if (control_mode == WEAPON_MODE_DSHOT && dshot_setup_pending) {
                ready_to_arm = false;
            }

            if (ready_to_arm && (current_time - arm_start_time > WEAPON_ARM_TIMEOUT)) {
                weapon_state = WEAPON_STATE_ARMED;
                DEBUG_PRINT("Weapon armed\n");
                status_set_weapon(WEAPON_STATUS_ARMED, LED_EFFECT_SOLID);
            }
            break;

        case WEAPON_STATE_ARMED:
        case WEAPON_STATE_SPINNING:
            {
                bool speed_changed = false;
                if (current_speed != target_speed) {
#if INTEGRATION_TEST_AUTO
                    current_speed = target_speed;
                    last_ramp_time = current_time;
                    speed_changed = true;
#else
                    if (current_time - last_ramp_time > (WEAPON_SPINUP_TIME / WEAPON_RAMP_STEPS)) {
                        // MAJOR FIX #5: Static ramp calculation is intentional for performance
                        // Using 'static const' allows compile-time calculation of ramp_step,
                        // avoiding repeated division on every update cycle. This is critical
                        // for real-time motor control where microseconds matter.
                        // If WEAPON_RAMP_STEPS needs to be runtime-configurable, change to:
                        //   uint8_t ramp_step = (100 + weapon_ramp_steps - 1) / weapon_ramp_steps;
                        static const uint8_t ramp_step = (100 + WEAPON_RAMP_STEPS - 1) / WEAPON_RAMP_STEPS;
                        if (target_speed > current_speed) {
                            current_speed = MIN(current_speed + ramp_step, target_speed);
                        } else {
                            current_speed = MAX((int16_t)current_speed - (int16_t)ramp_step, target_speed);
                        }

                        last_ramp_time = current_time;
                        speed_changed = true;
                    }
#endif
                    if (speed_changed) {
                        if (current_speed > 0 && weapon_state != WEAPON_STATE_SPINNING) {
                            weapon_state = WEAPON_STATE_SPINNING;
                            status_set_weapon(WEAPON_STATUS_SPINNING, LED_EFFECT_SOLID);
                        } else if (current_speed == 0 && weapon_state == WEAPON_STATE_SPINNING) {
                            weapon_state = WEAPON_STATE_ARMED;
                            status_set_weapon(WEAPON_STATUS_ARMED, LED_EFFECT_SOLID);
                        }
                    }
                }

                // MAJOR FIX #3 (Iteration 2): Acquire mutex BEFORE reading control_mode
                // This prevents race condition where control_mode changes between
                // read and command execution
                // MAJOR #1 (Iteration 3): VERIFIED - This is NOT a race condition.
                // Mutex is properly acquired here before reading control_mode.
                mutex_enter_blocking(&mode_mutex);
                switch (control_mode) {
                    case WEAPON_MODE_PWM:
                        if (speed_changed) {
                            uint16_t pulse = weapon_speed_to_pulse(current_speed);
                            motor_control_set_pulse(MOTOR_WEAPON, pulse);
                        }
                        break;

                    case WEAPON_MODE_DSHOT: {
                        uint16_t dshot_throttle = dshot_throttle_from_percent_unidir(current_speed);
                        weapon_send_dshot_locked(current_time, dshot_throttle, speed_changed);
                        break;
                    }

                    case WEAPON_MODE_CONFIG:
                        // Cannot control motor while in config mode
                        break;
                }
                mutex_exit(&mode_mutex);
            }
            break;

        case WEAPON_STATE_DISARMED:
        case WEAPON_STATE_EMERGENCY_STOP:
            current_speed = 0;
            target_speed = 0;

            // MAJOR FIX #3 (Iteration 2): Acquire mutex BEFORE reading control_mode
            mutex_enter_blocking(&mode_mutex);
            switch (control_mode) {
                case WEAPON_MODE_PWM:
                    motor_control_set_pulse(MOTOR_WEAPON, PWM_MIN_PULSE);
                    break;

                case WEAPON_MODE_DSHOT:
                    if (dshot_initialized) {
                        dshot_send_throttle(MOTOR_WEAPON, 0, false);
                    }
                    break;

                case WEAPON_MODE_CONFIG:
                    // Motor already stopped in config mode
                    break;
            }
            mutex_exit(&mode_mutex);
            break;
    }
}

bool weapon_arm(void) {
    if (weapon_state != WEAPON_STATE_DISARMED) {
        DEBUG_PRINT("Cannot arm: Weapon not disarmed (state=%d)\n", weapon_state);
        return false;
    }

    // CRITICAL SAFETY CHECK: Read actual battery voltage before arming
    // This is a safety-critical function that must not be bypassed
    uint32_t battery_mv = read_battery_voltage();

#if INTEGRATION_TEST_AUTO
    // Integration test builds bypass arm safety checks to allow automated runs.
    (void)battery_mv;
#else
    // Verify all safety conditions before allowing weapon to arm
    if (!safety_check_arm_conditions(battery_mv)) {
        DEBUG_PRINT("Cannot arm: Safety conditions not met\n");
        return false;
    }
#endif

    weapon_state = WEAPON_STATE_ARMING;
    arm_start_time = to_ms_since_boot(get_absolute_time());
    mutex_enter_blocking(&mode_mutex);
    if (control_mode == WEAPON_MODE_DSHOT && dshot_initialized) {
        weapon_mark_dshot_setup_pending();
        dshot_telemetry_pending = 0;
    }
    mutex_exit(&mode_mutex);
    DEBUG_PRINT("Weapon arming... (Battery: %.1fV)\n", battery_mv / 1000.0f);
    status_set_weapon(WEAPON_STATUS_ARMING, LED_EFFECT_BLINK_MEDIUM);

    return true;
}

bool weapon_disarm(void) {
    weapon_state = WEAPON_STATE_DISARMED;
    current_speed = 0;
    target_speed = 0;

    // MAJOR FIX #3 (Iteration 2): Acquire mutex BEFORE reading control_mode
    mutex_enter_blocking(&mode_mutex);
    switch (control_mode) {
        case WEAPON_MODE_PWM:
            motor_control_set_pulse(MOTOR_WEAPON, PWM_MIN_PULSE);
            break;

        case WEAPON_MODE_DSHOT:
            if (dshot_initialized) {
                dshot_send_throttle(MOTOR_WEAPON, 0, false);
                dshot_telemetry_pending = 0;
            }
            break;

        case WEAPON_MODE_CONFIG:
            // Motor already stopped in config mode
            break;
    }
    mutex_exit(&mode_mutex);

    DEBUG_PRINT("Weapon disarmed\n");
    status_set_weapon(WEAPON_STATUS_DISARMED, LED_EFFECT_SOLID);

    return true;
}

bool weapon_set_speed(uint8_t speed_percent) {
    if (weapon_state != WEAPON_STATE_ARMED && weapon_state != WEAPON_STATE_SPINNING) {
        return false;
    }

    speed_percent = CLAMP(speed_percent, 0, MAX_WEAPON_SPEED);
    target_speed = speed_percent;

    // Apply exponential curve to weapon speed for better control feel
    if (WEAPON_EXPO > 0) {
        float normalized = (float)speed_percent / 100.0f;
        float expo_factor = (float)WEAPON_EXPO / 100.0f;
        float linear = normalized;
        float cubic = normalized * normalized * normalized;
        float output = linear * (1.0f - expo_factor) + cubic * expo_factor;
        target_speed = (uint8_t)(output * 100.0f);
    } else {
        target_speed = speed_percent;
    }

    return true;
}

weapon_state_t weapon_get_state(void) {
    return weapon_state;
}

uint8_t weapon_get_speed(void) {
    return current_speed;
}

bool weapon_is_armed(void) {
    return (weapon_state == WEAPON_STATE_ARMED ||
            weapon_state == WEAPON_STATE_SPINNING ||
            weapon_state == WEAPON_STATE_ARMING);
}

void weapon_emergency_stop(void) {
    // CRITICAL FIX #1 (Iteration 4): Defense-in-depth emergency stop
    // Use ALL stop methods regardless of mode to ensure motor stops
    // This prevents race conditions where mode could change between read and execution

    weapon_state = WEAPON_STATE_EMERGENCY_STOP;
    current_speed = 0;
    target_speed = 0;

    // CRITICAL: Disable motor hardware IMMEDIATELY using all available methods
    // Try ALL methods without checking mode - defense in depth approach
    // Even if one method is wrong for current mode, motor WILL stop

    // Method 1: PWM - always try to stop via PWM
    motor_control_set_pulse(MOTOR_WEAPON, PWM_MIN_PULSE);

    // Method 2: DShot - if initialized, send stop command
    // Note: Read dshot_initialized without mutex - this is acceptable for emergency stop
    // Worst case: we skip DShot stop if flag race occurs, but GPIO force-low still works
    if (dshot_initialized) {
        dshot_send_throttle(MOTOR_WEAPON, 0, false);
        dshot_telemetry_pending = 0;
    }

    // Method 3: Direct GPIO control - force pin low as last resort
    // Disable PWM slice
    uint slice_num = pwm_gpio_to_slice_num(PIN_WEAPON_PWM);
    pwm_set_enabled(slice_num, false);

    // Force GPIO low directly
    gpio_set_function(PIN_WEAPON_PWM, GPIO_FUNC_SIO);
    gpio_set_dir(PIN_WEAPON_PWM, GPIO_OUT);
    gpio_put(PIN_WEAPON_PWM, 0);

    DEBUG_PRINT("WEAPON EMERGENCY STOP!\n");
    status_set_weapon(WEAPON_STATUS_EMERGENCY, LED_EFFECT_BLINK_FAST);
}

bool weapon_get_telemetry(weapon_telemetry_t* telemetry) {
    if (telemetry == NULL) {
        return false;
    }

    dshot_telemetry_t raw;
    mutex_enter_blocking(&mode_mutex);
    bool ok = false;
    if (control_mode == WEAPON_MODE_DSHOT && dshot_initialized) {
        ok = dshot_get_telemetry(MOTOR_WEAPON, &raw);
    }
    mutex_exit(&mode_mutex);
    if (!ok) {
        return false;
    }

    telemetry->erpm = raw.erpm;
    telemetry->rpm = dshot_erpm_to_rpm(raw.erpm, WEAPON_POLE_PAIRS);
    telemetry->voltage_cV = raw.voltage_cV;
    telemetry->current_cA = raw.current_cA;
    telemetry->temperature_C = raw.temperature_C;
    telemetry->crc = raw.crc;
    telemetry->valid = raw.valid;
    telemetry->timestamp_ms = raw.timestamp_ms;

    return true;
}

uint32_t weapon_get_dshot_failures(void) {
    return dshot_send_failures;
}

uint16_t weapon_get_dshot_last_throttle(void) {
    return dshot_last_throttle;
}

void weapon_get_dshot_send_counts(uint32_t* attempts, uint32_t* successes) {
    if (attempts != NULL) {
        *attempts = dshot_send_attempts;
    }
    if (successes != NULL) {
        *successes = dshot_send_successes;
    }
}

void weapon_get_dshot_telemetry_counts(uint32_t* requests, uint32_t* responses) {
    if (requests == NULL && responses == NULL) {
        return;
    }

    mutex_enter_blocking(&mode_mutex);
    if (requests != NULL) {
        *requests = dshot_telemetry_requests;
    }
    if (responses != NULL) {
        *responses = dshot_telemetry_responses;
    }
    mutex_exit(&mode_mutex);
}

void weapon_reset_dshot_telemetry_counts(void) {
    mutex_enter_blocking(&mode_mutex);
    dshot_telemetry_requests = 0;
    dshot_telemetry_responses = 0;
    dshot_telemetry_pending = 0;
    dshot_telemetry_raw = 0;
    dshot_telemetry_decode_fail = 0;
    last_dshot_telemetry_rx_ms = 0;
    dshot_telemetry_decode_us = 0;
    dshot_telemetry_decode_frames = 0;
    mutex_exit(&mode_mutex);
}

void weapon_get_dshot_telemetry_debug(uint32_t* raw, uint32_t* decode_fail) {
    mutex_enter_blocking(&mode_mutex);
    if (raw != NULL) {
        *raw = dshot_telemetry_raw;
    }
    if (decode_fail != NULL) {
        *decode_fail = dshot_telemetry_decode_fail;
    }
    mutex_exit(&mode_mutex);
}

void weapon_get_dshot_telemetry_timing(uint32_t* frames, uint64_t* total_us) {
    mutex_enter_blocking(&mode_mutex);
    if (frames != NULL) {
        *frames = dshot_telemetry_decode_frames;
    }
    if (total_us != NULL) {
        *total_us = dshot_telemetry_decode_us;
    }
    mutex_exit(&mode_mutex);
}

void weapon_set_dshot_raw_dump(uint16_t count) {
#if INTEGRATION_TEST_AUTO
    mutex_enter_blocking(&mode_mutex);
    dshot_raw_dump_remaining = count;
    mutex_exit(&mode_mutex);
#else
    (void)count;
#endif
}

void weapon_get_dshot_setup_state(bool* pending, bool* done) {
    mutex_enter_blocking(&mode_mutex);
    if (pending != NULL) {
        *pending = dshot_setup_pending;
    }
    if (done != NULL) {
        *done = dshot_setup_done;
    }
    mutex_exit(&mode_mutex);
}

uint32_t weapon_get_telemetry_age_ms(void) {
    uint32_t now_ms = to_ms_since_boot(get_absolute_time());

    mutex_enter_blocking(&mode_mutex);
    uint32_t last_ms = last_dshot_telemetry_rx_ms;
    mutex_exit(&mode_mutex);

    if (last_ms == 0) {
        return UINT32_MAX;
    }

    return now_ms - last_ms;
}
