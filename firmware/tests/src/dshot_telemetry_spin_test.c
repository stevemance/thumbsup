#include <stdio.h>
#include <string.h>
#include <pico/stdlib.h>
#include "config.h"
#include "dshot.h"

#define DSHOT_TEST_SPEED DSHOT_SPEED_300
#define TELEMETRY_LOG_INTERVAL_MS 500
#define MOTOR_POLE_PAIRS 7
#define TELEMETRY_REQUEST_PERIOD 1
#define CRC_OVERRIDE_MODE -1  // -1 = use config, 0 = normal, 1 = inverted

typedef struct {
    dshot_telemetry_t last;
    uint32_t packets;
    uint32_t send_errors;
    uint32_t last_log_ms;
    uint32_t frame_count;
} telemetry_stats_t;

static void telemetry_init(telemetry_stats_t* stats) {
    memset(stats, 0, sizeof(*stats));
    stats->last.valid = false;
    stats->last_log_ms = to_ms_since_boot(get_absolute_time());
}

static bool telemetry_request_due(telemetry_stats_t* stats) {
#if TELEMETRY_REQUEST_PERIOD > 0
    stats->frame_count++;
    return (stats->frame_count % TELEMETRY_REQUEST_PERIOD) == 0;
#else
    (void)stats;
    return false;
#endif
}

static void telemetry_drain(telemetry_stats_t* stats) {
    dshot_telemetry_t telem;
    while (dshot_read_telemetry(MOTOR_WEAPON, &telem)) {
        stats->last = telem;
        stats->packets++;
    }
}

static void telemetry_maybe_log(telemetry_stats_t* stats, uint8_t pole_pairs) {
    uint32_t now = to_ms_since_boot(get_absolute_time());
    if ((now - stats->last_log_ms) < TELEMETRY_LOG_INTERVAL_MS) {
        return;
    }

    stats->last_log_ms = now;
    if (!stats->last.valid) {
        printf("Telemetry: none yet (packets=%lu, send_err=%lu)\n",
               stats->packets, stats->send_errors);
        return;
    }

    uint16_t rpm = dshot_erpm_to_rpm(stats->last.erpm, pole_pairs);
    printf("Telemetry: eRPM=%u (RPM=%u), V=%u.%02uV, I=%u.%02uA, T=%uC "
           "(packets=%lu, send_err=%lu)\n",
           stats->last.erpm, rpm,
           stats->last.voltage_cV / 100, stats->last.voltage_cV % 100,
           stats->last.current_cA / 100, stats->last.current_cA % 100,
           stats->last.temperature_C,
           stats->packets, stats->send_errors);
}

static void send_throttle_for_ms(uint16_t throttle, uint32_t duration_ms,
                                 telemetry_stats_t* stats) {
    const uint32_t step_ms = 2;  // 500 Hz update rate
    uint32_t steps = duration_ms / step_ms;

    for (uint32_t i = 0; i < steps; i++) {
        telemetry_drain(stats);
        bool request = telemetry_request_due(stats);
        if (!dshot_send_throttle(MOTOR_WEAPON, throttle, request)) {
            stats->send_errors++;
        }
        sleep_ms(step_ms);
        telemetry_drain(stats);
        telemetry_maybe_log(stats, MOTOR_POLE_PAIRS);
    }
}

static void send_command_repeat(dshot_command_t cmd, const char* label, int repeats,
                                telemetry_stats_t* stats) {
    printf("Command: %s (cmd=%u) x%d\n", label, (unsigned)cmd, repeats);
    for (int i = 0; i < repeats; i++) {
        telemetry_drain(stats);
        if (!dshot_send_throttle(MOTOR_WEAPON, (uint16_t)cmd, false)) {
            stats->send_errors++;
        }
        sleep_ms(2);
        telemetry_drain(stats);
        telemetry_maybe_log(stats, MOTOR_POLE_PAIRS);
    }
}

int main() {
    stdio_init_all();
    sleep_ms(2000);

    printf("\n========================================\n");
    printf("  DShot Telemetry Spin Test\n");
    printf("========================================\n\n");
    printf("Target: DShot%u on GP%d (bidirectional)\n",
           (unsigned)DSHOT_TEST_SPEED, PIN_WEAPON_PWM);
    printf("Sequence: bidir DShot -> 3D off -> dir normal -> throttle ramp\n");
    printf("Telemetry requests enabled (request bit set every frame)\n\n");

    dshot_config_t config = {
        .gpio_pin = PIN_WEAPON_PWM,
        .speed = DSHOT_TEST_SPEED,
        .bidirectional = true,
        .pole_pairs = MOTOR_POLE_PAIRS
    };

    if (!dshot_init(MOTOR_WEAPON, &config)) {
        printf("ERROR: DShot init failed\n");
        while (1) {
            sleep_ms(1000);
        }
    }
    printf("OK: DShot initialized\n");

    telemetry_stats_t stats;
    telemetry_init(&stats);

    uint32_t cycle = 1;
    while (true) {
        int8_t crc_mode = CRC_OVERRIDE_MODE;
        const char* crc_label = (crc_mode < 0) ? "config" : (crc_mode == 1) ? "inverted" : "normal";
        printf("\n=== Cycle %lu (CRC %s) ===\n", cycle++, crc_label);
        dshot_set_crc_invert_override(MOTOR_WEAPON, crc_mode);

        printf("Arming (throttle=0, 5s)\n");
        send_throttle_for_ms(0, 5000, &stats);

        send_command_repeat(DSHOT_CMD_EXTENDED_TELEMETRY_ENABLE, "EDT_ENABLE", 6, &stats);
        send_command_repeat(DSHOT_CMD_3D_MODE_OFF, "3D_MODE_OFF", 6, &stats);
        send_command_repeat(DSHOT_CMD_SPIN_DIRECTION_NORMAL, "SPIN_DIR_NORMAL", 6, &stats);

        printf("Throttle ramp (2s per step)\n");
        send_throttle_for_ms(200, 2000, &stats);
        send_throttle_for_ms(500, 2000, &stats);
        send_throttle_for_ms(1000, 2000, &stats);
        send_throttle_for_ms(1500, 2000, &stats);
        send_throttle_for_ms(1800, 2000, &stats);

        printf("Stop (throttle=0, 4s)\n");
        send_throttle_for_ms(0, 4000, &stats);
    }
}
