#include "weapon.h"
#include "motor_control.h"
#include "safety.h"
#include "status.h"
#include "config.h"
#include "dshot.h"
#include "am32_config.h"
#include "hitl_console.h"
#include "pico/stdlib.h"
#include "pico/mutex.h"
#include "hardware/pwm.h"
#include "hardware/gpio.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// Delay before issuing DShot setup commands during arming.  The ESC needs a
// short stream of throttle-0 packets before it will accept config commands.
// 500ms is enough for ESC initialisation while keeping total arm time short.
#define WEAPON_DSHOT_SETUP_DELAY_MS 500

extern uint32_t read_battery_voltage(void);

static weapon_state_t weapon_state = WEAPON_STATE_DISARMED;
static weapon_control_mode_t control_mode = WEAPON_MODE_PWM;  // Default to PWM
static mutex_t mode_mutex;  // Mutex for thread-safe mode switching
static int8_t current_speed = 0;
static int8_t target_speed = 0;
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
static uint32_t dshot_telemetry_reqbit_tx = 0;
static uint32_t dshot_telemetry_requests = 0;
static uint32_t dshot_telemetry_responses = 0;
static uint32_t dshot_telemetry_pending = 0;
static uint32_t dshot_telemetry_raw = 0;
static uint32_t dshot_telemetry_decode_fail = 0;
static uint32_t dshot_telemetry_plausibility_reject = 0;
static uint32_t dshot_telemetry_discarded = 0;
static uint32_t last_dshot_telemetry_rx_ms = 0;
static uint64_t dshot_telemetry_decode_us = 0;
static uint32_t dshot_telemetry_decode_frames = 0;
#if INTEGRATION_TEST_AUTO
static uint16_t dshot_raw_dump_remaining = 0;
#endif
static weapon_telemetry_t last_weapon_telem = {0};
static bool last_weapon_telem_valid = false;
static uint32_t filtered_rpm = 0;
static uint16_t filtered_voltage_cV = 0;
static uint16_t filtered_current_cA = 0;
static uint8_t  filtered_temperature_C = 0;
static bool     telem_filter_primed = false;
static uint32_t last_dshot_setup_attempt_ms = 0;
static uint8_t dshot_setup_attempts = 0;
static bool dshot_setup_pending = false;
static bool dshot_setup_done = false;
static uint32_t dshot_telemetry_interval_ms = WEAPON_DSHOT_TELEMETRY_MS;
static bool initialized = false;
// Protected by mode_mutex — accessed by weapon_update() and mode switch functions.
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
    ok = ok && dshot_send_command(MOTOR_WEAPON, DSHOT_CMD_3D_MODE_ON);
    // Note: SPIN_DIRECTION_NORMAL intentionally omitted.  Sending it right
    // before the first throttle command biases the ESC's internal direction
    // state, causing one direction to be rejected until a ~2s zero-hold
    // clears the lockout.  The ESC defaults to normal direction anyway.
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

// Maximum time (µs) to spend draining telemetry per call.  The DP decoder can
// take 200-500µs per frame; capping total drain time prevents the weapon update
// loop from stalling and accumulating latency.
#define WEAPON_TELEM_DRAIN_BUDGET_US 250
// Maximum raw frames to read per drain call (even cheap reads add up).
#define WEAPON_TELEM_DRAIN_MAX_FRAMES 4

static void weapon_poll_telemetry_locked(void) {
    uint64_t raw = 0;
    dshot_telemetry_t telem;
    uint64_t drain_start_us = time_us_64();
    uint32_t frames_read = 0;

    while (dshot_read_telemetry_raw(MOTOR_WEAPON, &raw)) {
        frames_read++;

#if INTEGRATION_TEST_AUTO
        if (dshot_raw_dump_remaining > 0) {
            printf("EDT raw=0x%010llx\n", (unsigned long long)raw);
            dshot_raw_dump_remaining--;
        }
#endif

        dshot_telemetry_raw++;
        bool matched_request = (dshot_telemetry_pending > 0);
        if (matched_request) {
            dshot_telemetry_pending--;
        }
        if (!matched_request) {
            // Drain RX frames to avoid FIFO backpressure, but only spend decode cycles
            // when we intentionally scheduled a decode (bounded rate).
            dshot_telemetry_discarded++;
        } else {
            uint64_t decode_start_us = time_us_64();
            bool decoded = dshot_decode_telemetry_raw(MOTOR_WEAPON, raw, &telem);
            dshot_telemetry_decode_us += time_us_64() - decode_start_us;
            dshot_telemetry_decode_frames++;
            if (!decoded) {
                dshot_telemetry_decode_fail++;
            } else {
                uint32_t rpm = dshot_erpm_to_rpm(telem.erpm, WEAPON_POLE_PAIRS);
                if (rpm > WEAPON_TELEM_MAX_RPM) {
                    dshot_telemetry_plausibility_reject++;
                    dshot_telemetry_decode_fail++;
                } else {
                    // Temporal consistency gate: reject large RPM jumps
                    uint32_t rpm_delta = (rpm > filtered_rpm)
                                         ? (rpm - filtered_rpm)
                                         : (filtered_rpm - rpm);
                    if (telem_filter_primed && rpm_delta > WEAPON_TELEM_MAX_RPM_DELTA) {
                        dshot_telemetry_plausibility_reject++;
                        dshot_telemetry_decode_fail++;
                    } else {
                        dshot_telemetry_responses++;

                        // IIR filter
                        if (!telem_filter_primed) {
                            filtered_rpm = rpm;
                            filtered_voltage_cV = telem.voltage_cV;
                            filtered_current_cA = telem.current_cA;
                            filtered_temperature_C = telem.temperature_C;
                            telem_filter_primed = true;
                        } else {
                            // RPM: alpha = NUM/DEN (fast)
                            filtered_rpm = (uint32_t)((int32_t)filtered_rpm +
                                (WEAPON_TELEM_RPM_ALPHA_NUM *
                                 ((int32_t)rpm - (int32_t)filtered_rpm)) /
                                WEAPON_TELEM_RPM_ALPHA_DEN);
                            // V/I/T: slow alpha with range validation
                            if (telem.voltage_cV >= WEAPON_TELEM_MIN_VOLTAGE_CV &&
                                telem.voltage_cV <= WEAPON_TELEM_MAX_VOLTAGE_CV) {
                                filtered_voltage_cV = (uint16_t)((int32_t)filtered_voltage_cV +
                                    (WEAPON_TELEM_SLOW_ALPHA_NUM *
                                     ((int32_t)telem.voltage_cV - (int32_t)filtered_voltage_cV)) /
                                    WEAPON_TELEM_SLOW_ALPHA_DEN);
                            }
                            if (telem.current_cA <= WEAPON_TELEM_MAX_CURRENT_CA) {
                                filtered_current_cA = (uint16_t)((int32_t)filtered_current_cA +
                                    (WEAPON_TELEM_SLOW_ALPHA_NUM *
                                     ((int32_t)telem.current_cA - (int32_t)filtered_current_cA)) /
                                    WEAPON_TELEM_SLOW_ALPHA_DEN);
                            }
                            if (telem.temperature_C <= WEAPON_TELEM_MAX_TEMP_C) {
                                filtered_temperature_C = (uint8_t)((int32_t)filtered_temperature_C +
                                    (WEAPON_TELEM_SLOW_ALPHA_NUM *
                                     ((int32_t)telem.temperature_C - (int32_t)filtered_temperature_C)) /
                                    WEAPON_TELEM_SLOW_ALPHA_DEN);
                            }
                        }

                        last_weapon_telem.erpm = telem.erpm;
                        last_weapon_telem.rpm = filtered_rpm;
                        last_weapon_telem.voltage_cV = filtered_voltage_cV;
                        last_weapon_telem.current_cA = filtered_current_cA;
                        last_weapon_telem.temperature_C = filtered_temperature_C;
                        last_weapon_telem.crc = telem.crc;
                        last_weapon_telem.valid = telem.valid;
                        last_weapon_telem.timestamp_ms = telem.timestamp_ms;
                        last_weapon_telem_valid = true;
                        last_dshot_telemetry_rx_ms = telem.timestamp_ms;
#if HITL_CONSOLE
                        hitl_latency_on_rpm_update(filtered_rpm);
#endif
                    }
                }
            }
        }

        // Bail if we have exceeded the time or frame budget.
        if (frames_read >= WEAPON_TELEM_DRAIN_MAX_FRAMES ||
            (time_us_64() - drain_start_us) >= WEAPON_TELEM_DRAIN_BUDGET_US) {
            break;
        }
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

    (void)force_send;
    // Keep a stable send cadence (bounded by WEAPON_DSHOT_UPDATE_MS). Bursting
    // packets can destabilize bidirectional turnaround / telemetry capture.
    bool should_send = (last_dshot_send_time == 0) ||
                       (now_ms - last_dshot_send_time >= WEAPON_DSHOT_UPDATE_MS);

    // Drain before sending to avoid RX FIFO backpressure blocking the PIO SM.
    weapon_poll_telemetry_locked();

    if (should_send) {
        dshot_last_throttle = throttle;
        dshot_send_attempts++;
        bool telemetry_allowed = (weapon_state == WEAPON_STATE_ARMING ||
                                  weapon_state == WEAPON_STATE_ARMED ||
                                  weapon_state == WEAPON_STATE_SPINNING);
        // Many ESCs (including AM32-based units) are most reliable if the telemetry
        // request bit is asserted on every packet. We do that while armed, but only
        // decode at a bounded rate (DP decoder is expensive).
        bool tx_request_bit = telemetry_allowed;
        bool decode_due = telemetry_allowed &&
                          (last_dshot_telemetry_time == 0 ||
                           (now_ms - last_dshot_telemetry_time) >= dshot_telemetry_interval_ms);
#if INTEGRATION_TEST_AUTO
        if (now_ms - last_dshot_debug_log_ms > 1000) {
            printf("DShot send throttle=%u tlm_bit=%u tlm_decode=%u\n",
                   throttle, tx_request_bit ? 1u : 0u, decode_due ? 1u : 0u);
            last_dshot_debug_log_ms = now_ms;
        }
#endif
        if (dshot_send_throttle(MOTOR_WEAPON, throttle, tx_request_bit)) {
            dshot_send_successes++;
            last_dshot_send_time = now_ms;
#if HITL_CONSOLE
            if (throttle > 0) {
                hitl_latency_on_dshot_sent(throttle);
            }
#endif
            if (tx_request_bit) {
                dshot_telemetry_reqbit_tx++;
            }
            if (decode_due) {
                last_dshot_telemetry_time = now_ms;
                dshot_telemetry_requests++;
                // EDT cycles through frame types (RPM/V/I/T). Decoding a small burst per
                // interval avoids getting "stuck" sampling only one type, which can leave
                // RPM stale and make HITL latency measurements meaningless.
                uint32_t budget = WEAPON_DSHOT_TELEMETRY_BURST;
                while (budget-- > 0 && dshot_telemetry_pending < WEAPON_DSHOT_TELEMETRY_MAX_PENDING) {
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

    // Disable current mode with proper GPIO cleanup
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
            sleep_ms(2);  // Let hardware settle before verifying
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
            dshot_telemetry_reqbit_tx = 0;
            dshot_telemetry_discarded = 0;
            last_dshot_telemetry_rx_ms = 0;
            last_weapon_telem_valid = false;
            memset(&last_weapon_telem, 0, sizeof(last_weapon_telem));
            filtered_rpm = 0;
            filtered_voltage_cV = 0;
            filtered_current_cA = 0;
            filtered_temperature_C = 0;
            telem_filter_primed = false;
            // Reset GPIO to SIO after DShot (PIO cleanup)
            gpio_set_function(PIN_WEAPON_PWM, GPIO_FUNC_SIO);
            gpio_put(PIN_WEAPON_PWM, 0);
            sleep_ms(2);  // Let hardware settle before verifying
            if (gpio_get_function(PIN_WEAPON_PWM) != GPIO_FUNC_SIO) {
                DEBUG_PRINT("WARNING: GPIO %d not in SIO after DShot cleanup\n", PIN_WEAPON_PWM);
            }
            break;

        case WEAPON_MODE_CONFIG:
            am32_exit_config_mode();
            sleep_ms(2);  // Let hardware settle before verifying
            if (gpio_get_function(PIN_WEAPON_PWM) != GPIO_FUNC_SIO) {
                DEBUG_PRINT("WARNING: GPIO %d not in SIO after AM32 cleanup\n", PIN_WEAPON_PWM);
            }
            break;
    }

    // Verify GPIO is in SIO before claiming for the new mode.
    // Safe: mode_mutex is held and no ISR modifies GPIO functions.
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
                    // Bidirectional mode is required for DShot telemetry (EDT).
                    // Hardware must provide a pull-up on the signal line (external resistor).
                    .bidirectional = true,
                    .pole_pairs = WEAPON_POLE_PAIRS
                };
                if (dshot_init(MOTOR_WEAPON, &dshot_config)) {
                    dshot_initialized = true;
                    last_dshot_send_time = 0;
                    last_dshot_telemetry_time = 0;
                    dshot_send_failures = 0;
                    dshot_send_attempts = 0;
                    dshot_send_successes = 0;
                    dshot_telemetry_reqbit_tx = 0;
                    dshot_telemetry_requests = 0;
                    dshot_telemetry_responses = 0;
                    dshot_telemetry_pending = 0;
                    dshot_telemetry_raw = 0;
                    dshot_telemetry_decode_fail = 0;
                    dshot_telemetry_plausibility_reject = 0;
                    dshot_telemetry_discarded = 0;
                    dshot_telemetry_decode_us = 0;
                    dshot_telemetry_decode_frames = 0;
                    last_dshot_telemetry_rx_ms = 0;
                    last_weapon_telem_valid = false;
                    memset(&last_weapon_telem, 0, sizeof(last_weapon_telem));
                    filtered_rpm = 0;
                    filtered_voltage_cV = 0;
                    filtered_current_cA = 0;
                    filtered_temperature_C = 0;
                    telem_filter_primed = false;
                    dshot_setup_pending = false;
                    dshot_setup_done = false;
                    DEBUG_PRINT("Weapon control mode: DShot300\n");
                } else {
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
    dshot_telemetry_reqbit_tx = 0;
    dshot_telemetry_requests = 0;
    dshot_telemetry_responses = 0;
    dshot_telemetry_pending = 0;
    dshot_telemetry_raw = 0;
    dshot_telemetry_decode_fail = 0;
    dshot_telemetry_plausibility_reject = 0;
    dshot_telemetry_discarded = 0;
    dshot_telemetry_decode_us = 0;
    dshot_telemetry_decode_frames = 0;
    last_dshot_telemetry_rx_ms = 0;
    last_weapon_telem_valid = false;
    memset(&last_weapon_telem, 0, sizeof(last_weapon_telem));
    filtered_rpm = 0;
    filtered_voltage_cV = 0;
    filtered_current_cA = 0;
    filtered_temperature_C = 0;
    telem_filter_primed = false;

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

        // Configure EDT telemetry and 3D mode during init, before the btstack
        // run loop starts.  Doing this here avoids blocking sleep_ms() calls
        // inside dshot_send_command() from stalling the btstack event loop
        // during the arming phase.  The ESC retains these settings as long as
        // it stays powered, so a single setup at boot is sufficient.
        dshot_send_command(MOTOR_WEAPON, DSHOT_CMD_EXTENDED_TELEMETRY_ENABLE);
        dshot_send_command(MOTOR_WEAPON, DSHOT_CMD_3D_MODE_ON);
        // SPIN_DIRECTION_NORMAL omitted — see arming setup comment.
        dshot_setup_done = true;
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
        // Only check battery voltage in the fast path (runs every 2ms).
        // The safety button is checked separately by safety_update() which
        // uses a violation counter with threshold — a single noise glitch on
        // the floating GP8 pin (no physical button installed) won't trigger
        // an unrecoverable emergency stop.
        uint32_t battery_mv = read_battery_voltage();
        if (!safety_check_battery(battery_mv)) {
            DEBUG_PRINT("SAFETY VIOLATION: Low battery in weapon_update\n");
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
                // Direction reversal tracking.  Persists across ticks.
                static bool reversal_active = false;
                // Prime phase: 0=idle, 1=pulse (new dir min DShot), 2=reset (DShot=0)
                static uint8_t prime_phase = 0;
                static uint32_t prime_start_ms = 0;

                bool speed_changed = false;
                if (current_speed != target_speed) {
#if INTEGRATION_TEST_AUTO
                    current_speed = target_speed;
                    last_ramp_time = current_time;
                    speed_changed = true;
#else
                    // Detect direction reversal: current and target on
                    // opposite sides of zero.
                    if ((current_speed > 0 && target_speed < 0) ||
                        (current_speed < 0 && target_speed > 0)) {
                        reversal_active = true;
                    }

                    // Direction-change prime: trigger on ANY start from
                    // zero, not just during reversals.  This handles:
                    //   - Initial start after arming (ESC may need dir flip)
                    //   - Slow direction change (stop, wait, new direction)
                    //   - Fast reversal through zero (ramp crosses zero)
                    // Phase 1: send min DShot in target direction → ESC
                    //   flips its internal direction flag.
                    // Phase 2: send DShot=0 → BEMF timeout resets running.
                    bool in_prime = false;
                    if (current_speed == 0 && target_speed != 0) {
                        if (prime_phase == 0) {
                            prime_phase = 1;
                            prime_start_ms = current_time;
                        }
                        if (prime_phase == 1) {
                            in_prime = true;
                            if (current_time - prime_start_ms >= WEAPON_PRIME_PULSE_MS) {
                                prime_phase = 2;
                                prime_start_ms = current_time;
                            }
                        } else if (prime_phase == 2) {
                            if (current_time - prime_start_ms >= WEAPON_PRIME_RESET_MS) {
                                // Prime complete — keep reversal_active so
                                // ramp-up uses fast spindown rate.
                                prime_phase = 0;
                                prime_start_ms = 0;
                            } else {
                                in_prime = true;
                            }
                        }
                    }

                    if (!in_prime) {
                        // Signed ramp: use spindown rate when moving toward
                        // zero, spinup rate when moving away.  During an
                        // active reversal both phases use the fast spindown
                        // rate so the full reversal completes in ~690ms
                        // (320ms down + 50ms prime + 320ms up) at ±80%.
                        int8_t step_dir = (target_speed > current_speed) ? +1 : -1;
                        bool moving_toward_zero = (abs(current_speed + step_dir) < abs(current_speed));
                        uint32_t ramp_interval_ms = (moving_toward_zero || reversal_active)
                            ? (WEAPON_SPINDOWN_TIME / WEAPON_RAMP_STEPS)
                            : (WEAPON_SPINUP_TIME / WEAPON_RAMP_STEPS);
                        if (ramp_interval_ms < 1) {
                            ramp_interval_ms = 1;
                        }

                        if (current_time - last_ramp_time >= ramp_interval_ms) {
                            static const int8_t ramp_step = (100 + WEAPON_RAMP_STEPS - 1) / WEAPON_RAMP_STEPS;
                            if (target_speed > current_speed) {
                                int16_t next = (int16_t)current_speed + ramp_step;
                                current_speed = (int8_t)(next > target_speed ? target_speed : next);
                            } else {
                                int16_t next = (int16_t)current_speed - ramp_step;
                                current_speed = (int8_t)(next < target_speed ? target_speed : next);
                            }

                            last_ramp_time = current_time;
                            speed_changed = true;
                        }
                    }
#endif
                    if (speed_changed) {
                        if (current_speed != 0 && weapon_state != WEAPON_STATE_SPINNING) {
                            weapon_state = WEAPON_STATE_SPINNING;
                            status_set_weapon(WEAPON_STATUS_SPINNING, LED_EFFECT_SOLID);
                        } else if (current_speed == 0 && weapon_state == WEAPON_STATE_SPINNING) {
                            weapon_state = WEAPON_STATE_ARMED;
                            status_set_weapon(WEAPON_STATUS_ARMED, LED_EFFECT_SOLID);
                        }
                    }
                }

                // Clear reversal state when ramp reaches its target
                // (placed outside the != block so it actually executes).
                if (current_speed == target_speed) {
                    reversal_active = false;
                    prime_phase = 0;
                    prime_start_ms = 0;
                }

                // DShot 3D mode: minimum throttle values that trigger a
                // direction change in AM32 without actually spinning the
                // motor (adjusted_input ~46, below startup threshold 47).
                #define DSHOT_3D_FWD_MIN 1048
                #define DSHOT_3D_REV_MIN 48

                mutex_enter_blocking(&mode_mutex);
                switch (control_mode) {
                    case WEAPON_MODE_PWM:
                        if (speed_changed) {
                            // PWM mode is unidirectional; use magnitude only.
                            uint16_t pulse = weapon_speed_to_pulse((uint8_t)abs(current_speed));
                            motor_control_set_pulse(MOTOR_WEAPON, pulse);
                        }
                        break;

                    case WEAPON_MODE_DSHOT: {
                        uint16_t dshot_throttle;
                        if (prime_phase == 1) {
                            // Prime pulse: send new direction's min DShot
                            // to trigger ESC direction flip.
                            dshot_throttle = (target_speed > 0)
                                ? DSHOT_3D_FWD_MIN : DSHOT_3D_REV_MIN;
                        } else if (prime_phase == 2) {
                            // Prime reset: DShot=0 triggers BEMF timeout.
                            dshot_throttle = 0;
                        } else {
                            dshot_throttle = dshot_throttle_from_percent_3d(current_speed);
                        }
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
        // Always re-run DShot setup commands (EDT enable, 3D mode, spin
        // direction) during arming.  The boot-time setup in weapon_init()
        // fires after only 200ms of idle — the ESC is often still booting
        // and silently ignores the commands.  By the time the user arms
        // (seconds after power-on), the ESC is guaranteed to be ready.
        // Without 3D mode active, positive-direction throttle values
        // (1048-2047) appear as mid-range throttle to the ESC and it
        // refuses to start the motor from standstill.
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

    mutex_enter_blocking(&mode_mutex);
    bool need_dshot_reinit = false;
    switch (control_mode) {
        case WEAPON_MODE_PWM:
            motor_control_set_pulse(MOTOR_WEAPON, PWM_MIN_PULSE);
            break;

        case WEAPON_MODE_DSHOT:
            if (dshot_initialized) {
                dshot_send_throttle(MOTOR_WEAPON, 0, false);
                dshot_telemetry_pending = 0;
            } else {
                // DShot was destroyed (e.g. by emergency_stop forcing GPIO to SIO).
                // Re-initialize after releasing the mutex.
                need_dshot_reinit = true;
            }
            break;

        case WEAPON_MODE_CONFIG:
            // Motor already stopped in config mode
            break;
    }
    mutex_exit(&mode_mutex);

    // Reinitialize DShot outside the mutex (weapon_set_control_mode acquires it).
    if (need_dshot_reinit) {
        DEBUG_PRINT("Reinitializing DShot after emergency stop\n");
        weapon_set_control_mode(WEAPON_MODE_DSHOT);
    }

    DEBUG_PRINT("Weapon disarmed\n");
    status_set_weapon(WEAPON_STATUS_DISARMED, LED_EFFECT_SOLID);

    return true;
}

bool weapon_set_speed(int8_t speed_percent) {
    // Allow setting the target speed while ARMING so the motor can begin ramping
    // immediately once the arm timeout completes (avoids requiring a second
    // controller "nudge" after arming).
    if (weapon_state != WEAPON_STATE_ARMED &&
        weapon_state != WEAPON_STATE_SPINNING &&
        weapon_state != WEAPON_STATE_ARMING) {
        return false;
    }

    speed_percent = (int8_t)CLAMP(speed_percent, -MAX_WEAPON_SPEED, MAX_WEAPON_SPEED);
    target_speed = speed_percent;

    // Apply exponential curve to weapon speed for better control feel.
    // Cubic preserves sign: (-x)^3 = -(x^3).
    if (WEAPON_EXPO > 0) {
        float normalized = (float)speed_percent / 100.0f;
        float expo_factor = (float)WEAPON_EXPO / 100.0f;
        float linear = normalized;
        float cubic = normalized * normalized * normalized;
        float output = linear * (1.0f - expo_factor) + cubic * expo_factor;
        target_speed = (int8_t)(output * 100.0f);
    } else {
        target_speed = speed_percent;
    }

#if HITL_CONSOLE
    hitl_latency_on_target_set((uint8_t)abs(target_speed));
#endif

    return true;
}

weapon_state_t weapon_get_state(void) {
    return weapon_state;
}

int8_t weapon_get_speed(void) {
    return current_speed;
}

int8_t weapon_get_target_speed(void) {
    return target_speed;
}

bool weapon_is_armed(void) {
    return (weapon_state == WEAPON_STATE_ARMED ||
            weapon_state == WEAPON_STATE_SPINNING ||
            weapon_state == WEAPON_STATE_ARMING);
}

void weapon_emergency_stop(void) {
    weapon_state = WEAPON_STATE_EMERGENCY_STOP;
    current_speed = 0;
    target_speed = 0;

    // Defense in depth: try ALL stop methods regardless of current mode
    // to guarantee motor stops even if mode state is inconsistent.
    motor_control_set_pulse(MOTOR_WEAPON, PWM_MIN_PULSE);

    // Read dshot_initialized without mutex — acceptable for e-stop because
    // the GPIO force-low below guarantees the motor stops regardless.
    if (dshot_initialized) {
        dshot_send_throttle(MOTOR_WEAPON, 0, false);
        dshot_telemetry_pending = 0;
        // Properly release PIO resources so reinit doesn't leak state machines.
        dshot_deinit(MOTOR_WEAPON);
        dshot_initialized = false;
    }

    // Last resort: force GPIO low directly
    uint slice_num = pwm_gpio_to_slice_num(PIN_WEAPON_PWM);
    pwm_set_enabled(slice_num, false);

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

    mutex_enter_blocking(&mode_mutex);
    bool ok = false;
    if (control_mode == WEAPON_MODE_DSHOT && dshot_initialized && last_weapon_telem_valid) {
        // Mirror dshot_get_telemetry() freshness semantics (avoid returning stale data).
        uint32_t age_ms = to_ms_since_boot(get_absolute_time()) - last_weapon_telem.timestamp_ms;
        #define WEAPON_TELEM_MAX_AGE_MS 100
        if (age_ms <= WEAPON_TELEM_MAX_AGE_MS) {
            memcpy(telemetry, &last_weapon_telem, sizeof(*telemetry));
            ok = true;
        }
    }
    mutex_exit(&mode_mutex);
    return ok;
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

uint32_t weapon_get_dshot_telemetry_reqbit_tx(void) {
    mutex_enter_blocking(&mode_mutex);
    uint32_t v = dshot_telemetry_reqbit_tx;
    mutex_exit(&mode_mutex);
    return v;
}

void weapon_get_dshot_telemetry_rx_counts(uint32_t* raw, uint32_t* discarded) {
    mutex_enter_blocking(&mode_mutex);
    if (raw != NULL) {
        *raw = dshot_telemetry_raw;
    }
    if (discarded != NULL) {
        *discarded = dshot_telemetry_discarded;
    }
    mutex_exit(&mode_mutex);
}

void weapon_reset_dshot_telemetry_counts(void) {
    mutex_enter_blocking(&mode_mutex);
    dshot_telemetry_reqbit_tx = 0;
    dshot_telemetry_requests = 0;
    dshot_telemetry_responses = 0;
    dshot_telemetry_pending = 0;
    dshot_telemetry_raw = 0;
    dshot_telemetry_decode_fail = 0;
    dshot_telemetry_plausibility_reject = 0;
    dshot_telemetry_discarded = 0;
    last_dshot_telemetry_rx_ms = 0;
    dshot_telemetry_decode_us = 0;
    dshot_telemetry_decode_frames = 0;
    last_weapon_telem_valid = false;
    memset(&last_weapon_telem, 0, sizeof(last_weapon_telem));
    filtered_rpm = 0;
    filtered_voltage_cV = 0;
    filtered_current_cA = 0;
    filtered_temperature_C = 0;
    telem_filter_primed = false;
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

void weapon_set_telemetry_interval_ms(uint32_t ms) {
    if (ms < 2) {
        ms = 2;
    }
    if (ms > 500) {
        ms = 500;
    }
    mutex_enter_blocking(&mode_mutex);
    dshot_telemetry_interval_ms = ms;
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
