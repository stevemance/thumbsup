#include <stdio.h>
#include <pico/stdlib.h>
#include "config.h"
#include "dshot.h"

static void send_throttle_for_ms(uint16_t throttle, uint32_t duration_ms) {
    const uint32_t step_ms = 2;  // 500 Hz update rate
    uint32_t steps = duration_ms / step_ms;
    for (uint32_t i = 0; i < steps; i++) {
        dshot_send_throttle(MOTOR_WEAPON, throttle, false);
        sleep_ms(step_ms);
    }
}

static void send_beep(dshot_command_t cmd, const char* label) {
    printf("Beep command: %s (cmd=%u)\n", label, (unsigned)cmd);
    dshot_send_command(MOTOR_WEAPON, cmd);
    // Keep a valid signal so the ESC doesn't fall into signal-loss beeps.
    send_throttle_for_ms(0, 1500);
}

int main() {
    stdio_init_all();
    sleep_ms(2000);

    printf("\n========================================\n");
    printf("  DShot Beep Test\n");
    printf("========================================\n\n");
    printf("Target: DShot300 on GP%d\n", PIN_WEAPON_PWM);
    printf("Sequence: arm -> beep1..beep5 -> repeat\n\n");

    dshot_config_t config = {
        .gpio_pin = PIN_WEAPON_PWM,
        .speed = DSHOT_SPEED_300,
        .bidirectional = false,
        .pole_pairs = 7
    };

    if (!dshot_init(MOTOR_WEAPON, &config)) {
        printf("ERROR: DShot init failed\n");
        while (1) {
            sleep_ms(1000);
        }
    }
    printf("OK: DShot initialized\n");

    uint32_t cycle = 1;
    while (true) {
        printf("\n=== Cycle %lu ===\n", cycle++);

        printf("Arming (throttle=0)\n");
        send_throttle_for_ms(0, 2000);

        send_beep(DSHOT_CMD_BEEP1, "BEEP1");
        send_beep(DSHOT_CMD_BEEP2, "BEEP2");
        send_beep(DSHOT_CMD_BEEP3, "BEEP3");
        send_beep(DSHOT_CMD_BEEP4, "BEEP4");
        send_beep(DSHOT_CMD_BEEP5, "BEEP5");

        printf("Idle...\n");
        send_throttle_for_ms(0, 2000);
    }
}
