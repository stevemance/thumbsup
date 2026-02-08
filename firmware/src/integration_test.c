#include "integration_test.h"
#include "config.h"
#include "dshot.h"
#include "motor_control.h"
#include "safety.h"
#include "status.h"
#include "system_status.h"
#include "weapon.h"
#include "am32_config.h"
#include "hardware/gpio.h"
#include "hardware/clocks.h"
#include "pico/stdlib.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define INTEGRATION_TRIGGER_CHAR 'I'
#if INTEGRATION_TEST_AUTO
#define INTEGRATION_POLL_INTERVAL_MS 2
#else
#define INTEGRATION_POLL_INTERVAL_MS MAIN_LOOP_DELAY
#endif
#define INTEGRATION_PROMPT_POLL_US 10000
#define INTEGRATION_ARM_WAIT_MS 9000
#define INTEGRATION_STEP_HOLD_MS 60000
#define INTEGRATION_STEP_TRIM_MS 5000
#define INTEGRATION_STEADY_AFTER_MS 500
#define INTEGRATION_COOLDOWN_MS 0
#define INTEGRATION_TELEM_MIN_PCT 80
#define INTEGRATION_MAX_RPM_SAMPLES 1024
#define INTEGRATION_ESC_CONFIG 0

typedef struct {
    uint8_t speed_percent;
    uint32_t hold_ms;
} integration_step_t;

typedef struct {
    uint32_t checks;
    uint32_t samples;
    uint32_t duplicates;
    uint32_t stale;
    uint32_t expected;
    uint32_t last_timestamp_ms;
    uint32_t request_start;
    uint32_t response_start;
    uint32_t request_count;
    uint32_t response_count;
    uint32_t raw_start;
    uint32_t decode_fail_start;
    uint32_t raw_count;
    uint32_t decode_fail_count;
    uint32_t send_attempts_start;
    uint32_t send_successes_start;
    uint32_t send_attempts;
    uint32_t send_successes;
    uint32_t loop_count;
    uint32_t decode_frames_start;
    uint64_t decode_us_start;
    uint32_t decode_frames;
    uint64_t decode_us;
    uint32_t stable_start_ms;
    uint32_t voltage_samples;
    uint32_t current_samples;
    uint32_t temp_samples;
    uint32_t rpm_min;
    uint32_t rpm_max;
    uint32_t rpm_median;
    uint64_t rpm_sum;
    uint64_t voltage_sum;
    uint64_t current_sum;
    uint64_t temp_sum;
    uint32_t type_counts[16];
    uint16_t rpm_samples[INTEGRATION_MAX_RPM_SAMPLES];
    uint16_t rpm_sample_count;
    uint8_t target_speed;
    uint32_t elapsed_ms;
} telemetry_stats_t;

static const integration_step_t k_steps[] = {
    {90, INTEGRATION_STEP_HOLD_MS}
};

#if INTEGRATION_TEST_AUTO
static bool raw_dump_armed = false;
#endif

static const char* weapon_mode_label(weapon_control_mode_t mode) {
    switch (mode) {
        case WEAPON_MODE_PWM:
            return "PWM";
        case WEAPON_MODE_DSHOT:
            return "DSHOT";
        case WEAPON_MODE_CONFIG:
            return "CONFIG";
        default:
            return "UNKNOWN";
    }
}

static int integration_u16_compare(const void* a, const void* b) {
    uint16_t va = *(const uint16_t*)a;
    uint16_t vb = *(const uint16_t*)b;
    return (va > vb) - (va < vb);
}

static uint8_t integration_target_speed(uint8_t speed_percent) {
    speed_percent = CLAMP(speed_percent, 0, MAX_WEAPON_SPEED);
    if (WEAPON_EXPO > 0) {
        float normalized = (float)speed_percent / 100.0f;
        float expo_factor = (float)WEAPON_EXPO / 100.0f;
        float linear = normalized;
        float cubic = normalized * normalized * normalized;
        float output = linear * (1.0f - expo_factor) + cubic * expo_factor;
        return (uint8_t)(output * 100.0f);
    }
    return speed_percent;
}

static void integration_log_dshot_state(const char* label) {
    uint8_t tx_level = 0;
    uint8_t rx_level = 0;
    bool fifo_ok = dshot_get_fifo_levels(MOTOR_WEAPON, &tx_level, &rx_level);
    bool sm_enabled = dshot_sm_is_enabled(MOTOR_WEAPON);
    bool ext_active = dshot_extended_telemetry_active(MOTOR_WEAPON);
    bool ext_seen = dshot_extended_telemetry_seen(MOTOR_WEAPON);

    printf("%s: gpio_func=%d sm=%u fifo_tx=%u fifo_rx=%u ext=%u seen=%u\n",
           label,
           gpio_get_function(PIN_WEAPON_PWM),
           sm_enabled ? 1u : 0u,
           fifo_ok ? tx_level : 0u,
           fifo_ok ? rx_level : 0u,
           ext_active ? 1u : 0u,
           ext_seen ? 1u : 0u);
}

static void integration_tick(void) {
    motor_control_update();
    weapon_update();
    safety_update();
}

static bool integration_prompt(uint32_t timeout_ms) {
    printf("\n=================================\n");
    printf("  Integration Test Trigger\n");
    printf("=================================\n");
    printf("Press '%c' within %u ms to run the integration test.\n",
           INTEGRATION_TRIGGER_CHAR, (unsigned)timeout_ms);
    printf("Any other key continues normal startup.\n\n");

    uint32_t start_ms = to_ms_since_boot(get_absolute_time());
    while ((to_ms_since_boot(get_absolute_time()) - start_ms) < timeout_ms) {
        int c = getchar_timeout_us(INTEGRATION_PROMPT_POLL_US);
        if (c == PICO_ERROR_TIMEOUT) {
            // Keep motors/weapon in their safe idle signaling state while we
            // wait for a serial keypress. Without this, the ESC can interpret
            // the gap as "signal lost" and start beeping.
            integration_tick();
            continue;
        }
        if (c == INTEGRATION_TRIGGER_CHAR || c == (INTEGRATION_TRIGGER_CHAR + 32)) {
            return true;
        }
        return false;
    }
    return false;
}

static void telemetry_stats_init(telemetry_stats_t* stats, uint32_t hold_ms, uint32_t trim_ms,
                                 uint8_t target_speed) {
    memset(stats, 0, sizeof(*stats));
    stats->rpm_min = UINT32_MAX;
    stats->target_speed = target_speed;
    if (hold_ms > trim_ms) {
        stats->expected = (hold_ms - trim_ms) / WEAPON_DSHOT_TELEMETRY_MS;
    }

    dshot_reset_telemetry_type_counts(MOTOR_WEAPON);
    weapon_get_dshot_telemetry_counts(&stats->request_start, &stats->response_start);
    weapon_get_dshot_telemetry_debug(&stats->raw_start, &stats->decode_fail_start);
    weapon_get_dshot_send_counts(&stats->send_attempts_start, &stats->send_successes_start);
    weapon_get_dshot_telemetry_timing(&stats->decode_frames_start, &stats->decode_us_start);
}

static void telemetry_stats_update(telemetry_stats_t* stats, uint32_t now_ms, uint32_t trim_end_ms) {
    stats->checks++;

    dshot_telemetry_t raw;
    if (!dshot_get_telemetry(MOTOR_WEAPON, &raw)) {
        return;
    }

    if (raw.timestamp_ms == stats->last_timestamp_ms) {
        stats->duplicates++;
        return;
    }
    stats->last_timestamp_ms = raw.timestamp_ms;

    if (now_ms < trim_end_ms) {
        return;
    }

    uint8_t current_speed = weapon_get_speed();
    if (weapon_get_state() != WEAPON_STATE_SPINNING ||
        current_speed < stats->target_speed) {
        stats->stable_start_ms = 0;
        return;
    }

    if (stats->stable_start_ms == 0) {
        stats->stable_start_ms = now_ms;
    }

    if (now_ms - stats->stable_start_ms < INTEGRATION_STEADY_AFTER_MS) {
        return;
    }

    if (now_ms - raw.timestamp_ms > (WEAPON_DSHOT_TELEMETRY_MS * 2)) {
        stats->stale++;
    }

    if (raw.type == 0xE) {
        return;
    }

    bool extended_active = dshot_extended_telemetry_active(MOTOR_WEAPON);
    if (extended_active) {
        if (raw.type == 0x4) {
            stats->voltage_sum += raw.voltage_cV;
            stats->voltage_samples++;
            return;
        }
        if (raw.type == 0x6) {
            stats->current_sum += raw.current_cA;
            stats->current_samples++;
            return;
        }
        if (raw.type == 0x2) {
            stats->temp_sum += raw.temperature_C;
            stats->temp_samples++;
            return;
        }
    }

    if (raw.value == 0xFFF) {
        return;
    }

    uint32_t rpm = dshot_erpm_to_rpm(raw.erpm, WEAPON_POLE_PAIRS);
    if (rpm < stats->rpm_min) {
        stats->rpm_min = rpm;
    }
    if (rpm > stats->rpm_max) {
        stats->rpm_max = rpm;
    }

    stats->rpm_sum += rpm;
    stats->samples++;
    if (stats->rpm_sample_count < INTEGRATION_MAX_RPM_SAMPLES) {
        stats->rpm_samples[stats->rpm_sample_count++] = (uint16_t)rpm;
    }
}

static void telemetry_stats_finalize(telemetry_stats_t* stats) {
    uint32_t requests = 0;
    uint32_t responses = 0;

    weapon_get_dshot_telemetry_counts(&requests, &responses);
    if (requests >= stats->request_start) {
        stats->request_count = requests - stats->request_start;
    }
    if (responses >= stats->response_start) {
        stats->response_count = responses - stats->response_start;
    }

    uint32_t raw = 0;
    uint32_t decode_fail = 0;
    weapon_get_dshot_telemetry_debug(&raw, &decode_fail);
    if (raw >= stats->raw_start) {
        stats->raw_count = raw - stats->raw_start;
    }
    if (decode_fail >= stats->decode_fail_start) {
        stats->decode_fail_count = decode_fail - stats->decode_fail_start;
    }

    uint32_t send_attempts = 0;
    uint32_t send_successes = 0;
    weapon_get_dshot_send_counts(&send_attempts, &send_successes);
    if (send_attempts >= stats->send_attempts_start) {
        stats->send_attempts = send_attempts - stats->send_attempts_start;
    }
    if (send_successes >= stats->send_successes_start) {
        stats->send_successes = send_successes - stats->send_successes_start;
    }

    uint32_t decode_frames = 0;
    uint64_t decode_us = 0;
    weapon_get_dshot_telemetry_timing(&decode_frames, &decode_us);
    if (decode_frames >= stats->decode_frames_start) {
        stats->decode_frames = decode_frames - stats->decode_frames_start;
    }
    if (decode_us >= stats->decode_us_start) {
        stats->decode_us = decode_us - stats->decode_us_start;
    }

    dshot_get_telemetry_type_counts(MOTOR_WEAPON, stats->type_counts);

    if (stats->rpm_sample_count == 0) {
        stats->rpm_median = 0;
        return;
    }

    qsort(stats->rpm_samples, stats->rpm_sample_count, sizeof(stats->rpm_samples[0]),
          integration_u16_compare);
    stats->rpm_median = stats->rpm_samples[stats->rpm_sample_count / 2];
}

static bool integration_hold(uint8_t speed_percent, uint32_t hold_ms, uint32_t trim_ms,
                             telemetry_stats_t* stats) {
    uint32_t start_ms = to_ms_since_boot(get_absolute_time());
    uint32_t trim_end_ms = start_ms + trim_ms;
    uint32_t last_reject_log_ms = start_ms;
    uint32_t last_state_log_ms = start_ms;
    uint32_t last_status_log_ms = start_ms;
#if INTEGRATION_TEST_AUTO
    if (!raw_dump_armed) {
        weapon_set_dshot_raw_dump(0);
        raw_dump_armed = true;
    }
#endif
    telemetry_stats_init(stats, hold_ms, trim_ms, integration_target_speed(speed_percent));
    bool set_ok = weapon_set_speed(speed_percent);
    if (!set_ok) {
        printf("WARN: weapon_set_speed rejected (state=%d)\n", weapon_get_state());
    }

    while ((to_ms_since_boot(get_absolute_time()) - start_ms) < hold_ms) {
        bool speed_ok = weapon_set_speed(speed_percent);
        integration_tick();
        uint32_t now_ms = to_ms_since_boot(get_absolute_time());
        stats->loop_count++;
        telemetry_stats_update(stats, now_ms, trim_end_ms);

        if (!speed_ok && (now_ms - last_reject_log_ms) > 1000) {
            printf("WARN: weapon_set_speed rejected (state=%d)\n", weapon_get_state());
            last_reject_log_ms = now_ms;
        }
        if (speed_percent > 0) {
            weapon_state_t state = weapon_get_state();
            if (state != WEAPON_STATE_ARMED && state != WEAPON_STATE_SPINNING &&
                (now_ms - last_state_log_ms) > 1000) {
                printf("WARN: weapon_state=%d during hold\n", state);
                last_state_log_ms = now_ms;
            }
        }
        if (weapon_get_state() == WEAPON_STATE_EMERGENCY_STOP) {
            printf("ABORT: Emergency stop detected\n");
            telemetry_stats_finalize(stats);
            return false;
        }
        if (now_ms - last_status_log_ms >= 1000) {
            uint8_t tx_level = 0;
            uint8_t rx_level = 0;
            bool fifo_ok = dshot_get_fifo_levels(MOTOR_WEAPON, &tx_level, &rx_level);
            printf("HOLD status t=%u speed=%u state=%d throttle=%u sm=%u fifo_tx=%u fifo_rx=%u\n",
                   now_ms - start_ms,
                   weapon_get_speed(),
                   weapon_get_state(),
                   weapon_get_dshot_last_throttle(),
                   dshot_sm_is_enabled(MOTOR_WEAPON) ? 1u : 0u,
                   fifo_ok ? tx_level : 0u,
                   fifo_ok ? rx_level : 0u);
            last_status_log_ms = now_ms;
        }
        sleep_ms(INTEGRATION_POLL_INTERVAL_MS);
    }

    stats->elapsed_ms = to_ms_since_boot(get_absolute_time()) - start_ms;
    telemetry_stats_finalize(stats);
    return true;
}

static void telemetry_stats_log(const telemetry_stats_t* stats, uint8_t speed_percent) {
    uint32_t sample_pct = 0;
    if (stats->expected > 0) {
        sample_pct = (stats->samples * 100) / stats->expected;
    }
    uint32_t response_pct = 0;
    if (stats->request_count > 0) {
        response_pct = (stats->response_count * 100) / stats->request_count;
    }

    uint32_t avg_rpm = 0;
    uint16_t avg_voltage_cV = 0;
    uint16_t avg_current_cA = 0;
    uint8_t avg_temp_C = 0;
    uint32_t send_rate_hz = 0;
    uint32_t loop_rate_hz = 0;
    uint32_t decode_avg_us = 0;
    uint32_t decode_rate_hz = 0;

    if (stats->samples > 0) {
        avg_rpm = (uint32_t)(stats->rpm_sum / stats->samples);
    }
    if (stats->voltage_samples > 0) {
        avg_voltage_cV = (uint16_t)(stats->voltage_sum / stats->voltage_samples);
    }
    if (stats->current_samples > 0) {
        avg_current_cA = (uint16_t)(stats->current_sum / stats->current_samples);
    }
    if (stats->temp_samples > 0) {
        avg_temp_C = (uint8_t)(stats->temp_sum / stats->temp_samples);
    }
    if (stats->elapsed_ms > 0) {
        send_rate_hz = (uint32_t)((stats->send_successes * 1000ULL) / stats->elapsed_ms);
        loop_rate_hz = (uint32_t)((stats->loop_count * 1000ULL) / stats->elapsed_ms);
        decode_rate_hz = (uint32_t)((stats->decode_frames * 1000ULL) / stats->elapsed_ms);
    }
    if (stats->decode_frames > 0) {
        decode_avg_us = (uint32_t)(stats->decode_us / stats->decode_frames);
    }

    printf("Step %u%%: samples=%u/%u (%u%%) req=%u resp=%u (%u%%) dup=%u stale=%u\n",
           speed_percent, stats->samples, stats->expected, sample_pct,
           stats->request_count, stats->response_count, response_pct,
           stats->duplicates, stats->stale);
    printf("  Elapsed=%u ms\n", stats->elapsed_ms);
    printf("  EDT raw=%u decode_fail=%u\n",
           stats->raw_count, stats->decode_fail_count);
    printf("  DShot sends=%u/%u (%u Hz) loop=%u (%u Hz)\n",
           stats->send_successes, stats->send_attempts, send_rate_hz,
           stats->loop_count, loop_rate_hz);
    printf("  Decode frames=%u (%u Hz) avg=%uus\n",
           stats->decode_frames, decode_rate_hz, decode_avg_us);
    printf("  EDT types: evt=%u temp=%u volt=%u curr=%u\n",
           stats->type_counts[0xE],
           stats->type_counts[0x2],
           stats->type_counts[0x4],
           stats->type_counts[0x6]);
    printf("  DShot failures so far: %u\n", weapon_get_dshot_failures());
    if (stats->samples > 0) {
        printf("  RPM avg=%u med=%u min=%u max=%u (steady samples=%u)\n",
               avg_rpm, stats->rpm_median, stats->rpm_min, stats->rpm_max,
               stats->rpm_sample_count);
        printf("  V=%.2fV I=%.2fA T=%uC\n",
               avg_voltage_cV / 100.0f,
               avg_current_cA / 100.0f,
               avg_temp_C);
    }

    dshot_telemetry_t raw = {0};
    bool ext_active = dshot_extended_telemetry_active(MOTOR_WEAPON);
    bool ext_seen = dshot_extended_telemetry_seen(MOTOR_WEAPON);
    if (dshot_get_telemetry(MOTOR_WEAPON, &raw)) {
        printf("  EDT ext=%u seen=%u type=0x%x value=0x%03x\n",
               ext_active ? 1u : 0u,
               ext_seen ? 1u : 0u,
               raw.type,
               raw.value);
    } else {
        printf("  EDT ext=%u seen=%u (no fresh frame)\n",
               ext_active ? 1u : 0u,
               ext_seen ? 1u : 0u);
    }
}

bool integration_test_run_if_requested(uint32_t timeout_ms) {
#if INTEGRATION_TEST_AUTO
    printf("\n=================================\n");
    printf("  Integration Test Auto-Run\n");
    printf("=================================\n");
#else
    if (!integration_prompt(timeout_ms)) {
        return false;
    }
#endif

    printf("\n=================================\n");
    printf("  Running Integration Test\n");
    printf("=================================\n");
    printf("WARNING: Weapon motor will spin.\n\n");
    printf("System clock: %lu Hz\n", (unsigned long)clock_get_hz(clk_sys));

    system_set_failsafe(false);
    system_set_armed(false);
    weapon_disarm();

#if INTEGRATION_ESC_CONFIG
    printf("Checking ESC config...\n");
    if (weapon_enter_config_mode()) {
        am32_config_t cfg = {0};
        if (am32_read_settings(&cfg)) {
            printf("ESC settings: bidirectional=%u telemetry=%u\n",
                   cfg.bidirectional, cfg.telemetry);
            if (cfg.bidirectional == 0 || cfg.telemetry == 0) {
                printf("Updating ESC settings for telemetry...\n");
                cfg.bidirectional = 1;
                cfg.telemetry = 1;
                if (am32_write_settings(&cfg) && am32_save_settings()) {
                    printf("ESC telemetry settings updated.\n");
                } else {
                    printf("WARN: Failed to update ESC telemetry settings\n");
                }
            }
        } else {
            printf("WARN: Failed to read ESC settings\n");
        }
    } else {
        printf("WARN: Failed to enter ESC config mode\n");
    }
#else
    printf("Skipping ESC config check (INTEGRATION_ESC_CONFIG=0)\n");
#endif

    if (!weapon_enable_dshot()) {
        printf("ERROR: Failed to switch to DShot mode\n");
        return true;
    }
    weapon_control_mode_t mode = weapon_get_control_mode();
    printf("Weapon control mode: %s\n", weapon_mode_label(mode));
    if (mode != WEAPON_MODE_DSHOT) {
        printf("ERROR: DShot mode unavailable, aborting test\n");
        return true;
    }
    printf("GPIO %u function: %d\n", PIN_WEAPON_PWM, gpio_get_function(PIN_WEAPON_PWM));
    weapon_reset_dshot_telemetry_counts();
    printf("DShot update interval: %u ms, telemetry interval: %u ms, poll interval: %u ms\n",
           WEAPON_DSHOT_UPDATE_MS, WEAPON_DSHOT_TELEMETRY_MS, INTEGRATION_POLL_INTERVAL_MS);
    integration_log_dshot_state("DShot init");

    printf("Arming weapon...\n");
    system_set_armed(true);
    if (!weapon_arm()) {
        printf("ERROR: Weapon arm failed\n");
        system_set_armed(false);
        return true;
    }
    uint32_t arm_wait_start = to_ms_since_boot(get_absolute_time());
    while ((to_ms_since_boot(get_absolute_time()) - arm_wait_start) < INTEGRATION_ARM_WAIT_MS) {
        integration_tick();
        sleep_ms(INTEGRATION_POLL_INTERVAL_MS);
    }
    printf("Weapon state after arm wait: %d\n", weapon_get_state());
    bool setup_pending = false;
    bool setup_done = false;
    weapon_get_dshot_setup_state(&setup_pending, &setup_done);
    printf("DShot setup: pending=%u done=%u\n",
           setup_pending ? 1u : 0u,
           setup_done ? 1u : 0u);
    integration_log_dshot_state("Post-arm");

    printf("Sending ESC setup commands...\n");
    dshot_send_command(MOTOR_WEAPON, DSHOT_CMD_EXTENDED_TELEMETRY_ENABLE);
    dshot_send_command(MOTOR_WEAPON, DSHOT_CMD_3D_MODE_OFF);
    dshot_send_command(MOTOR_WEAPON, DSHOT_CMD_SPIN_DIRECTION_NORMAL);

    uint16_t prev_avg_rpm = 0;
    bool monotonic_ok = true;
    bool telemetry_ok = true;

    for (size_t i = 0; i < sizeof(k_steps) / sizeof(k_steps[0]); i++) {
        const integration_step_t* step = &k_steps[i];
        telemetry_stats_t stats;

        printf("\nHold %u%% throttle for %u ms (trim %u ms)\n",
               step->speed_percent, step->hold_ms, INTEGRATION_STEP_TRIM_MS);
        integration_log_dshot_state("Hold start");
        if (!integration_hold(step->speed_percent, step->hold_ms,
                              INTEGRATION_STEP_TRIM_MS, &stats)) {
            telemetry_ok = false;
            break;
        }

        telemetry_stats_log(&stats, step->speed_percent);

        if (stats.request_count > 0) {
            uint32_t response_pct = (stats.response_count * 100) / stats.request_count;
            if (response_pct < INTEGRATION_TELEM_MIN_PCT) {
                telemetry_ok = false;
            }
        } else if (stats.expected > 0) {
            uint32_t sample_pct = (stats.samples * 100) / stats.expected;
            if (sample_pct < INTEGRATION_TELEM_MIN_PCT) {
                telemetry_ok = false;
            }
        }

        if (stats.samples > 0) {
            uint16_t sample_rpm = (uint16_t)(stats.rpm_median > 0 ?
                                            stats.rpm_median :
                                            (stats.rpm_sum / stats.samples));
            if (sample_rpm < prev_avg_rpm) {
                monotonic_ok = false;
            }
            prev_avg_rpm = sample_rpm;
        }

        printf("Cooldown (0%%) for %u ms\n", INTEGRATION_COOLDOWN_MS);
        integration_hold(0, INTEGRATION_COOLDOWN_MS, 0, &stats);
    }

    weapon_set_speed(0);
    for (uint32_t elapsed = 0; elapsed < 2000; elapsed += INTEGRATION_POLL_INTERVAL_MS) {
        integration_tick();
        sleep_ms(INTEGRATION_POLL_INTERVAL_MS);
    }
    weapon_disarm();
    system_set_armed(false);

    printf("\n=================================\n");
    printf("Integration Summary:\n");
    printf("  Telemetry rate: %s (min %u%%)\n",
           telemetry_ok ? "PASS" : "FAIL", INTEGRATION_TELEM_MIN_PCT);
    printf("  RPM monotonicity: %s\n", monotonic_ok ? "PASS" : "FAIL");
    printf("  DShot send failures: %u\n", weapon_get_dshot_failures());
    printf("=================================\n\n");

    return true;
}
