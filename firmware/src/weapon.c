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
static bool     telem_filter_primed = false;
static uint32_t rpm_last_accepted = 0;   // last raw rpm that passed the step check
static uint32_t rpm_last_rejected = 0;
static uint8_t  rpm_consistent_rejects = 0;
static uint32_t last_dshot_setup_attempt_ms = 0;
static uint8_t dshot_setup_attempts = 0;
static bool dshot_setup_pending = false;
static bool dshot_setup_done = false;
static uint8_t dshot_setup_step = 0;     // index into the setup command list
enum { ESC_RECOVERY_NONE, ESC_RECOVERY_LOW, ESC_RECOVERY_REARM };
static uint8_t esc_recovery_phase = ESC_RECOVERY_NONE;
static uint32_t esc_recovery_start_ms = 0;
static uint32_t esc_last_reply_ms = 0;
static uint32_t esc_recoveries = 0;
static bool esc_replied = false;         // a reply since the last (re)arm
static uint32_t esc_first_reply_ms = 0;
static uint32_t esc_link_start_ms = 0;   // when frames last (re)started
static uint8_t dshot_setup_repeat = 0;   // frames of the current command sent
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

// ESC setup (EDT on, 3D off, normal direction, optionally 3D on) is sent as
// ordinary frames on the normal send cadence: each command value repeated
// WEAPON_DSHOT_CMD_REPEAT times (AM32 acts on the 6th identical command).
// This used to call dshot_send_command(), which sleeps 2 ms per frame and
// blocked the Bluetooth/control loop for ~80 ms per attempt.
#define WEAPON_DSHOT_CMD_REPEAT 10
static const uint16_t dshot_setup_cmds[] = {
    DSHOT_CMD_EXTENDED_TELEMETRY_ENABLE,
    DSHOT_CMD_3D_MODE_OFF,
    DSHOT_CMD_SPIN_DIRECTION_NORMAL,
    DSHOT_CMD_3D_MODE_ON,   // only when WEAPON_DSHOT_USE_3D
};
#define DSHOT_SETUP_CMD_COUNT (WEAPON_DSHOT_USE_3D ? 4u : 3u)

static void weapon_mark_dshot_setup_pending(void) {
    dshot_setup_pending = true;
    dshot_setup_done = false;
    dshot_setup_attempts = 0;
    dshot_setup_step = 0;
    dshot_setup_repeat = 0;
    last_dshot_setup_attempt_ms = 0;
}

// Returns the setup command to send in place of the throttle this frame, or
// -1 when no setup frame is due.
static int weapon_dshot_setup_frame_locked(uint32_t now_ms) {
    // AM32 only accepts these commands once it has armed, which it does a
    // while after it first answers (it then plays its arming tone).  The
    // disarmed robot sends no frames, so the ESC starts arming only when we do.
    if (!dshot_setup_pending || !esc_replied ||
        (int32_t)(now_ms - esc_first_reply_ms) < WEAPON_DSHOT_SETUP_AFTER_REPLY_MS) {
        return -1;
    }
    if (dshot_setup_step >= DSHOT_SETUP_CMD_COUNT) {
        return -1;
    }
    if (dshot_setup_step == 0 && dshot_setup_repeat == 0) {
        last_dshot_setup_attempt_ms = now_ms;
        dshot_setup_attempts++;
    }
    return dshot_setup_cmds[dshot_setup_step];
}

static void weapon_dshot_setup_frame_sent_locked(uint32_t now_ms) {
    if (++dshot_setup_repeat < WEAPON_DSHOT_CMD_REPEAT) {
        return;
    }
    dshot_setup_repeat = 0;
    if (++dshot_setup_step < DSHOT_SETUP_CMD_COUNT) {
        return;
    }
    dshot_setup_pending = false;
    dshot_setup_done = true;
    printf("WPN setup done in %lu ms edt_ack=%u edt_seen=%u\n",
           (unsigned long)(now_ms - last_dshot_setup_attempt_ms),
           dshot_extended_telemetry_active(MOTOR_WEAPON) ? 1u : 0u,
           dshot_extended_telemetry_seen(MOTOR_WEAPON) ? 1u : 0u);
}

static void weapon_reset_telemetry_filter_locked(void) {
    telem_filter_primed = false;
    filtered_rpm = 0;
    rpm_last_accepted = 0;
    rpm_consistent_rejects = 0;
    memset(&last_weapon_telem, 0, sizeof(last_weapon_telem));
    last_weapon_telem_valid = false;
}

// RPM step check.  Decoding is now exact (GCR + checksum, no guessing), so
// this is only a backstop against the rare corrupted frame that still passes
// the 4-bit checksum.  It compares against the last *accepted raw* value, not
// the filter output, and accepts WEAPON_TELEM_RPM_RESYNC mutually consistent
// readings in a row, so it can never lock telemetry out (it used to, for
// seconds, after a single bad frame).
static bool weapon_rpm_plausible_locked(uint32_t rpm) {
    if (rpm > WEAPON_TELEM_MAX_RPM) {
        return false;
    }
    if (!telem_filter_primed) {
        return true;
    }
    uint32_t step = rpm > rpm_last_accepted ? rpm - rpm_last_accepted : rpm_last_accepted - rpm;
    if (step <= WEAPON_TELEM_MAX_RPM_STEP) {
        rpm_consistent_rejects = 0;
        return true;
    }
    uint32_t vs_prev = rpm > rpm_last_rejected ? rpm - rpm_last_rejected : rpm_last_rejected - rpm;
    rpm_consistent_rejects = (rpm_consistent_rejects > 0 && vs_prev <= WEAPON_TELEM_MAX_RPM_STEP)
                             ? rpm_consistent_rejects + 1 : 1;
    rpm_last_rejected = rpm;
    if (rpm_consistent_rejects >= WEAPON_TELEM_RPM_RESYNC) {
        rpm_consistent_rejects = 0;
        return true;
    }
    return false;
}

static void weapon_apply_telemetry_locked(const dshot_telemetry_t* t) {
    last_dshot_telemetry_rx_ms = t->timestamp_ms;

    if (t->fresh & DSHOT_FRESH_ERPM) {
        uint32_t rpm = t->stopped ? 0 : dshot_erpm_to_rpm(t->erpm, WEAPON_POLE_PAIRS);
        if (!weapon_rpm_plausible_locked(rpm)) {
            dshot_telemetry_plausibility_reject++;
        } else {
            filtered_rpm = telem_filter_primed
                ? (uint32_t)((int32_t)filtered_rpm +
                             (WEAPON_TELEM_RPM_ALPHA_NUM * ((int32_t)rpm - (int32_t)filtered_rpm)) /
                             WEAPON_TELEM_RPM_ALPHA_DEN)
                : rpm;
            if (rpm == 0) {
                filtered_rpm = 0;
            }
            telem_filter_primed = true;
            rpm_last_accepted = rpm;
            last_weapon_telem.erpm = t->stopped ? 0 : t->erpm;
            last_weapon_telem.rpm = filtered_rpm;
            last_weapon_telem.erpm_ms = t->erpm_ms;
            last_weapon_telem.timestamp_ms = t->erpm_ms;
            last_weapon_telem.valid = true;
            last_weapon_telem_valid = true;
#if HITL_CONSOLE
            hitl_latency_on_rpm_update(filtered_rpm);
#endif
        }
    }
    // AM32 already smooths voltage and temperature; use them as sent.
    if ((t->fresh & DSHOT_FRESH_VOLT) &&
        t->voltage_cV >= WEAPON_TELEM_MIN_VOLTAGE_CV && t->voltage_cV <= WEAPON_TELEM_MAX_VOLTAGE_CV) {
        last_weapon_telem.voltage_cV = t->voltage_cV;
        last_weapon_telem.voltage_ms = t->voltage_ms;
    }
    if ((t->fresh & DSHOT_FRESH_TEMP) && t->temperature_C <= WEAPON_TELEM_MAX_TEMP_C) {
        last_weapon_telem.temperature_C = t->temperature_C;
        last_weapon_telem.temperature_ms = t->temperature_ms;
    }
#if WEAPON_ESC_HAS_CURRENT_SENSE
    if ((t->fresh & DSHOT_FRESH_CURR) && t->current_cA <= WEAPON_TELEM_MAX_CURRENT_CA) {
        last_weapon_telem.current_cA = t->current_cA;
        last_weapon_telem.current_ms = t->current_ms;
    }
#endif
}

// Reads the reply to the previous frame, if one has been captured.  A capture
// fills the whole 4-word RX FIFO, so there is at most one per call.
static void weapon_poll_telemetry_locked(void) {
    uint8_t rx_level = 0;
    if (!dshot_get_fifo_levels(MOTOR_WEAPON, NULL, &rx_level) || rx_level < DSHOT_RX_WORDS) {
        return;
    }
    dshot_telemetry_t t;
    uint64_t start_us = time_us_64();
    bool ok = dshot_read_telemetry(MOTOR_WEAPON, &t);
    dshot_telemetry_decode_us += time_us_64() - start_us;
    dshot_telemetry_decode_frames++;
    dshot_telemetry_raw++;
    if (!ok) {
        dshot_telemetry_decode_fail++;
        return;
    }
    dshot_telemetry_responses++;
    if (!esc_replied) {
        esc_replied = true;
        esc_first_reply_ms = t.timestamp_ms;
        printf("WPN ESC first reply %lu ms after frames started\n",
               (unsigned long)(t.timestamp_ms - esc_link_start_ms));
    }
    esc_last_reply_ms = t.timestamp_ms;
    weapon_apply_telemetry_locked(&t);
}

static void weapon_send_dshot_locked(uint32_t now_ms, uint16_t throttle, bool force_send) {
    if (!dshot_initialized) {
        return;
    }
    (void)force_send;

    // ESC recovery, step 2: after the low pulse, resume frames and re-arm.
    if (esc_recovery_phase == ESC_RECOVERY_LOW) {
        current_speed = 0;
        if ((now_ms - esc_recovery_start_ms) < WEAPON_ESC_RECOVER_LOW_MS) {
            return;
        }
        dshot_set_output_paused(MOTOR_WEAPON, false);
        esc_recovery_phase = ESC_RECOVERY_REARM;
        esc_recovery_start_ms = now_ms;
        esc_link_start_ms = now_ms;
        esc_replied = false;
        arm_start_time = now_ms;
        weapon_mark_dshot_setup_pending();
    }

    // Read the reply to the previous frame first: sending drains the RX FIFO.
    weapon_poll_telemetry_locked();

    // ESC recovery, step 1: the ESC stopped answering (or never started);
    // hold the line low.  Reply timestamps can be a tick newer than now_ms,
    // so ages are signed.
    bool esc_settled = esc_replied &&
                       (int32_t)(now_ms - esc_first_reply_ms) > WEAPON_ESC_SETTLE_MS;
    bool lost;
    int32_t silent_ms;
    if (!esc_replied) {
        silent_ms = (int32_t)(now_ms - esc_link_start_ms);
        lost = silent_ms > WEAPON_ESC_FIRST_REPLY_MS;
    } else {
        silent_ms = (int32_t)(now_ms - esc_last_reply_ms);
        lost = esc_settled && esc_recovery_phase == ESC_RECOVERY_NONE &&
               (weapon_state == WEAPON_STATE_ARMED || weapon_state == WEAPON_STATE_SPINNING) &&
               silent_ms > WEAPON_ESC_LOST_MS;
    }
    if (esc_recovery_phase != ESC_RECOVERY_LOW && lost) {
        esc_recovery_phase = ESC_RECOVERY_LOW;
        esc_recovery_start_ms = now_ms;
        esc_recoveries++;
        current_speed = 0;
        dshot_set_output_paused(MOTOR_WEAPON, true);
        printf("WPN ESC %s for %ld ms: recovery %lu\n", esc_replied ? "stopped replying" : "never replied",
               (long)silent_ms, (unsigned long)esc_recoveries);
        return;
    }
    if (esc_recovery_phase == ESC_RECOVERY_REARM) {
        current_speed = 0;
        throttle = 0;
        if ((now_ms - esc_recovery_start_ms) >= WEAPON_ESC_REARM_MS && !dshot_setup_pending &&
            esc_settled) {
            esc_recovery_phase = ESC_RECOVERY_NONE;
            printf("WPN ESC recovery %lu done, replies %s\n", (unsigned long)esc_recoveries,
                   esc_replied ? "resumed" : "still missing");
        }
    }

    // Keep a stable send cadence (bounded by WEAPON_DSHOT_UPDATE_MS).
    bool should_send = (last_dshot_send_time == 0) ||
                       (now_ms - last_dshot_send_time >= WEAPON_DSHOT_UPDATE_MS);
    if (!should_send) {
        return;
    }

    int setup_cmd = weapon_dshot_setup_frame_locked(now_ms);
    uint16_t frame = setup_cmd >= 0 ? (uint16_t)setup_cmd : throttle;
    bool telemetry_allowed = (weapon_state == WEAPON_STATE_ARMING ||
                              weapon_state == WEAPON_STATE_ARMED ||
                              weapon_state == WEAPON_STATE_SPINNING);
    // Commands go out with the telemetry bit clear, as dshot_send_command()
    // always sent them; throttle frames request telemetry while armed.
    bool tx_request_bit = telemetry_allowed && setup_cmd < 0;

    dshot_last_throttle = frame;
    dshot_send_attempts++;
    if (dshot_send_throttle(MOTOR_WEAPON, frame, tx_request_bit)) {
        dshot_send_successes++;
        last_dshot_send_time = now_ms;
        if (setup_cmd >= 0) {
            weapon_dshot_setup_frame_sent_locked(now_ms);
            // Command frames go out with the telemetry bit clear and the ESC
            // does not answer them: don't count this as the ESC going silent.
            esc_last_reply_ms = now_ms;
            esc_link_start_ms = esc_replied ? esc_link_start_ms : now_ms;
        }
#if HITL_CONSOLE
        if (setup_cmd < 0 && throttle > 0) {
            hitl_latency_on_dshot_sent(throttle);
        }
#endif
        if (tx_request_bit) {
            dshot_telemetry_reqbit_tx++;
            dshot_telemetry_requests++;
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
            weapon_reset_telemetry_filter_locked();
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
                    // Keep this explicit so normal unidirectional AM32 ESCs are stable.
                    // Enable only when the ESC and wiring support single-wire bidirectional EDT.
                    .bidirectional = (WEAPON_DSHOT_BIDIRECTIONAL != 0),
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
                    weapon_reset_telemetry_filter_locked();
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
    weapon_reset_telemetry_filter_locked();

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
        dshot_send_command(MOTOR_WEAPON, DSHOT_CMD_3D_MODE_OFF);
        dshot_send_command(MOTOR_WEAPON, DSHOT_CMD_SPIN_DIRECTION_NORMAL);
        if (WEAPON_DSHOT_USE_3D) {
            dshot_send_command(MOTOR_WEAPON, DSHOT_CMD_3D_MODE_ON);
        }
        dshot_setup_done = true;
        // Disarmed until armed: hold the signal low (see dshot_set_output_paused).
        dshot_set_output_paused(MOTOR_WEAPON, true);
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
                printf("WPN state ARMED (arm took %lu ms)\n", (unsigned long)(current_time - arm_start_time));
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
                int8_t effective_speed = current_speed;
                if (!WEAPON_DSHOT_USE_3D && effective_speed < 0) {
                    effective_speed = 0;
                }

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

                    bool in_prime = false;
                    if (WEAPON_DSHOT_USE_3D) {
                        // Direction-change prime: trigger on ANY start from
                        // zero, not just during reversals.  This handles:
                        //   - Initial start after arming (ESC may need dir flip)
                        //   - Slow direction change (stop, wait, new direction)
                        //   - Fast reversal through zero (ramp crosses zero)
                        // Phase 1: send min DShot in target direction → ESC
                        //   flips its internal direction flag.
                        // Phase 2: send DShot=0 → BEMF timeout resets running.
                        if (effective_speed == 0 && target_speed != 0) {
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
                    } else {
                        prime_phase = 0;
                        prime_start_ms = 0;
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
                        } else if (WEAPON_DSHOT_USE_3D) {
                            dshot_throttle = dshot_throttle_from_percent_3d(effective_speed);
                        } else {
                            dshot_throttle = dshot_throttle_from_percent_unidir((uint8_t)abs(effective_speed));
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
                    // Disarmed: no frames, signal held low, so an ESC that
                    // powers up or resets now always starts its firmware.
                    if (dshot_initialized && !dshot_output_paused(MOTOR_WEAPON)) {
                        dshot_set_output_paused(MOTOR_WEAPON, true);
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
    // Start every arming with fresh telemetry: a filter left over from a
    // previous spin must not gate the new readings.
    weapon_reset_telemetry_filter_locked();
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
        // Frames resume here; the ARMING state then sends zero throttle for
        // WEAPON_ARM_TIMEOUT so the ESC arms.
        dshot_set_output_paused(MOTOR_WEAPON, false);
        esc_recovery_phase = ESC_RECOVERY_NONE;
        esc_link_start_ms = arm_start_time;
        esc_replied = false;
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
                dshot_set_output_paused(MOTOR_WEAPON, true);
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
    if (!WEAPON_DSHOT_USE_3D && speed_percent < 0) {
        speed_percent = 0;
    }
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

uint32_t weapon_get_esc_recoveries(void) {
    return esc_recoveries;
}

bool weapon_get_telemetry_snapshot(weapon_telemetry_t* telemetry) {
    if (telemetry == NULL) {
        return false;
    }
    mutex_enter_blocking(&mode_mutex);
    memcpy(telemetry, &last_weapon_telem, sizeof(*telemetry));
    bool ok = last_weapon_telem_valid;
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
    weapon_reset_telemetry_filter_locked();
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
