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
#include "pico/stdlib.h"
#include <stdio.h>
#include <string.h>

#define INTEGRATION_TRIGGER_CHAR 'I'
#if INTEGRATION_TEST_AUTO
#define INTEGRATION_POLL_INTERVAL_MS 3
#else
#define INTEGRATION_POLL_INTERVAL_MS MAIN_LOOP_DELAY
#endif
#define INTEGRATION_PROMPT_POLL_US 10000
#define INTEGRATION_ARM_WAIT_MS 5000
#define INTEGRATION_STEP_HOLD_MS 20000
#define INTEGRATION_STEP_TRIM_MS 5000
#define INTEGRATION_COOLDOWN_MS 10000
#define INTEGRATION_TELEM_MIN_PCT 80

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
    uint32_t rpm_min;
    uint32_t rpm_max;
    uint64_t rpm_sum;
    uint64_t voltage_sum;
    uint64_t current_sum;
    uint64_t temp_sum;
} telemetry_stats_t;

static const integration_step_t k_steps[] = {
    {25, INTEGRATION_STEP_HOLD_MS},
    {40, INTEGRATION_STEP_HOLD_MS},
    {55, INTEGRATION_STEP_HOLD_MS},
    {65, INTEGRATION_STEP_HOLD_MS},
    {80, INTEGRATION_STEP_HOLD_MS}
};

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
            continue;
        }
        if (c == INTEGRATION_TRIGGER_CHAR || c == (INTEGRATION_TRIGGER_CHAR + 32)) {
            return true;
        }
        return false;
    }
    return false;
}

static void telemetry_stats_init(telemetry_stats_t* stats, uint32_t hold_ms, uint32_t trim_ms) {
    memset(stats, 0, sizeof(*stats));
    stats->rpm_min = UINT32_MAX;
    if (hold_ms > trim_ms) {
        stats->expected = (hold_ms - trim_ms) / WEAPON_DSHOT_TELEMETRY_MS;
    }

    weapon_get_dshot_telemetry_counts(&stats->request_start, &stats->response_start);
}

static void telemetry_stats_update(telemetry_stats_t* stats, uint32_t now_ms, uint32_t trim_end_ms) {
    stats->checks++;

    weapon_telemetry_t telem;
    if (!weapon_get_telemetry(&telem)) {
        return;
    }

    if (now_ms < trim_end_ms) {
        return;
    }

    if (telem.timestamp_ms == stats->last_timestamp_ms) {
        stats->duplicates++;
        return;
    }
    stats->last_timestamp_ms = telem.timestamp_ms;
    stats->samples++;

    if (now_ms - telem.timestamp_ms > (WEAPON_DSHOT_TELEMETRY_MS * 2)) {
        stats->stale++;
    }

    if (telem.rpm < stats->rpm_min) {
        stats->rpm_min = telem.rpm;
    }
    if (telem.rpm > stats->rpm_max) {
        stats->rpm_max = telem.rpm;
    }

    stats->rpm_sum += telem.rpm;
    stats->voltage_sum += telem.voltage_cV;
    stats->current_sum += telem.current_cA;
    stats->temp_sum += telem.temperature_C;
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
}

static bool integration_hold(uint8_t speed_percent, uint32_t hold_ms, uint32_t trim_ms,
                             telemetry_stats_t* stats) {
    uint32_t start_ms = to_ms_since_boot(get_absolute_time());
    uint32_t trim_end_ms = start_ms + trim_ms;
    telemetry_stats_init(stats, hold_ms, trim_ms);
    bool set_ok = weapon_set_speed(speed_percent);
    if (!set_ok) {
        printf("WARN: weapon_set_speed rejected (state=%d)\n", weapon_get_state());
    }

    while ((to_ms_since_boot(get_absolute_time()) - start_ms) < hold_ms) {
        weapon_set_speed(speed_percent);
        integration_tick();
        uint32_t now_ms = to_ms_since_boot(get_absolute_time());
        telemetry_stats_update(stats, now_ms, trim_end_ms);

        if (weapon_get_state() == WEAPON_STATE_EMERGENCY_STOP) {
            printf("ABORT: Emergency stop detected\n");
            telemetry_stats_finalize(stats);
            return false;
        }
        sleep_ms(INTEGRATION_POLL_INTERVAL_MS);
    }

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

    if (stats->samples > 0) {
        avg_rpm = (uint32_t)(stats->rpm_sum / stats->samples);
        avg_voltage_cV = (uint16_t)(stats->voltage_sum / stats->samples);
        avg_current_cA = (uint16_t)(stats->current_sum / stats->samples);
        avg_temp_C = (uint8_t)(stats->temp_sum / stats->samples);
    }

    printf("Step %u%%: samples=%u/%u (%u%%) req=%u resp=%u (%u%%) dup=%u stale=%u\n",
           speed_percent, stats->samples, stats->expected, sample_pct,
           stats->request_count, stats->response_count, response_pct,
           stats->duplicates, stats->stale);
    printf("  DShot failures so far: %u\n", weapon_get_dshot_failures());
    if (stats->samples > 0) {
        printf("  RPM avg=%u min=%u max=%u\n", avg_rpm, stats->rpm_min, stats->rpm_max);
        printf("  V=%.2fV I=%.2fA T=%uC\n",
               avg_voltage_cV / 100.0f,
               avg_current_cA / 100.0f,
               avg_temp_C);
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

    system_set_failsafe(false);
    system_set_armed(false);
    weapon_disarm();

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

    printf("Arming weapon...\n");
    system_set_armed(true);
    if (!weapon_arm()) {
        printf("ERROR: Weapon arm failed\n");
        system_set_armed(false);
        return true;
    }
    for (uint32_t elapsed = 0; elapsed < INTEGRATION_ARM_WAIT_MS; elapsed += INTEGRATION_POLL_INTERVAL_MS) {
        integration_tick();
        sleep_ms(INTEGRATION_POLL_INTERVAL_MS);
    }
    printf("Weapon state after arm wait: %d\n", weapon_get_state());

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
            uint16_t avg_rpm = (uint16_t)(stats.rpm_sum / stats.samples);
            if (avg_rpm < prev_avg_rpm) {
                monotonic_ok = false;
            }
            prev_avg_rpm = avg_rpm;
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
