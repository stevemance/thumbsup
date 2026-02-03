#include <stdio.h>
#include <pico/stdlib.h>
#include "config.h"
#include "dshot.h"

#define DSHOT_TEST_SPEED DSHOT_SPEED_300
#define TELEMETRY_LOG_INTERVAL_MS 1000
#define MOTOR_POLE_PAIRS 7

#define ARMING_MS 5000
#define SPINUP_RAMP_STEP_MS 1000
#define STEP_SPINUP_MS 3000
#define STEP_MEASURE_MS 12000
#define STEP_COOLDOWN_MS 4000

#define STEP_COUNT 1
static const uint16_t throttle_steps[STEP_COUNT] = { 1000 };
static const uint16_t spinup_ramp_throttles[] = { 200, 500 };
#define SPINUP_RAMP_COUNT (sizeof(spinup_ramp_throttles) / sizeof(spinup_ramp_throttles[0]))

static void drain_telemetry(dshot_telemetry_t* last) {
    dshot_telemetry_t telemetry;
    while (dshot_read_telemetry(MOTOR_WEAPON, &telemetry)) {
        *last = telemetry;
    }
}

static void log_telemetry(uint16_t throttle, const dshot_telemetry_t* telemetry) {
    if (!telemetry->valid) {
        printf("RPM_SAMPLE throttle=%u telemetry=--\n", throttle);
        return;
    }

    uint32_t rpm = dshot_erpm_to_rpm(telemetry->erpm, MOTOR_POLE_PAIRS);
    printf("RPM_SAMPLE throttle=%u erpm=%u rpm=%u V=%u.%02u I=%u.%02u T=%u\n",
           throttle,
           (unsigned)telemetry->erpm,
           (unsigned)rpm,
           telemetry->voltage_cV / 100,
           telemetry->voltage_cV % 100,
           telemetry->current_cA / 100,
           telemetry->current_cA % 100,
           telemetry->temperature_C);
}

static void send_throttle_for_ms(uint16_t throttle, uint32_t duration_ms,
                                 bool request_telemetry, dshot_telemetry_t* last,
                                 bool log_samples) {
    const uint32_t step_ms = 2;
    uint32_t start_ms = to_ms_since_boot(get_absolute_time());
    uint32_t next_log_ms = start_ms;

    while ((to_ms_since_boot(get_absolute_time()) - start_ms) < duration_ms) {
        drain_telemetry(last);
        dshot_send_throttle(MOTOR_WEAPON, throttle, request_telemetry);
        sleep_ms(step_ms);

        if (log_samples) {
            uint32_t now_ms = to_ms_since_boot(get_absolute_time());
            if (now_ms >= next_log_ms) {
                log_telemetry(throttle, last);
                next_log_ms = now_ms + TELEMETRY_LOG_INTERVAL_MS;
            }
        }
    }
}

static void spinup_ramp(uint16_t throttle, dshot_telemetry_t* last) {
    for (uint32_t i = 0; i < SPINUP_RAMP_COUNT; i++) {
        uint16_t ramp_throttle = spinup_ramp_throttles[i];
        printf("  Ramp throttle=%u for %ums\n", ramp_throttle, SPINUP_RAMP_STEP_MS);
        send_throttle_for_ms(ramp_throttle, SPINUP_RAMP_STEP_MS, true, last, false);
    }
    printf("  Ramp throttle=%u for %ums\n", throttle, STEP_SPINUP_MS);
    send_throttle_for_ms(throttle, STEP_SPINUP_MS, true, last, false);
}

static void send_command_repeat(dshot_command_t cmd, const char* label, int repeats) {
    printf("Command: %s (cmd=%u) x%d\n", label, (unsigned)cmd, repeats);
    for (int i = 0; i < repeats; i++) {
        dshot_send_throttle(MOTOR_WEAPON, (uint16_t)cmd, false);
        sleep_ms(2);
    }
}

int main() {
    stdio_init_all();
    sleep_ms(2000);

    printf("\n========================================\n");
    printf("  DShot Single RPM Test (Tach + PSU)\n");
    printf("========================================\n\n");
    printf("Target: DShot%u on GP%d (bidirectional)\n",
           (unsigned)DSHOT_TEST_SPEED, PIN_WEAPON_PWM);
    printf("Steps: %u (spinup=%ums, measure=%ums, cooldown=%ums)\n",
           (unsigned)STEP_COUNT, STEP_SPINUP_MS, STEP_MEASURE_MS, STEP_COOLDOWN_MS);
    printf("Telemetry logs every %ums during measurement window\n\n",
           (unsigned)TELEMETRY_LOG_INTERVAL_MS);

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

    dshot_set_crc_invert_override(MOTOR_WEAPON, -1);

    dshot_telemetry_t last = {0};

    printf("Arming (throttle=0, %ums)\n", ARMING_MS);
    send_throttle_for_ms(0, ARMING_MS, true, &last, false);

    send_command_repeat(DSHOT_CMD_EXTENDED_TELEMETRY_ENABLE, "EDT_ENABLE", 6);
    send_command_repeat(DSHOT_CMD_3D_MODE_OFF, "3D_MODE_OFF", 6);
    send_command_repeat(DSHOT_CMD_SPIN_DIRECTION_NORMAL, "SPIN_DIR_NORMAL", 6);

    for (uint32_t i = 0; i < STEP_COUNT; i++) {
        uint16_t throttle = throttle_steps[i];
        printf("\nSTEP %lu/%u: throttle=%u\n", (unsigned long)(i + 1),
               (unsigned)STEP_COUNT, throttle);
        printf("Spinup ramp to %u\n", throttle);
        spinup_ramp(throttle, &last);

        printf("MEASURE START step=%lu throttle=%u duration=%ums (tach + PSU)\n",
               (unsigned long)(i + 1), throttle, STEP_MEASURE_MS);
        send_throttle_for_ms(throttle, STEP_MEASURE_MS, true, &last, true);
        printf("MEASURE END step=%lu\n", (unsigned long)(i + 1));

        printf("Cooldown %ums...\n", STEP_COOLDOWN_MS);
        send_throttle_for_ms(0, STEP_COOLDOWN_MS, false, &last, false);
    }

    printf("\nDone. Holding throttle=0.\n");
    while (1) {
        send_throttle_for_ms(0, 1000, false, &last, false);
    }
}
