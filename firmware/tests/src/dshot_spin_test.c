#include <stdio.h>
#include <pico/stdlib.h>
#include "config.h"
#include "dshot.h"

#define DSHOT_TEST_SPEED DSHOT_SPEED_300

static void send_throttle_for_ms(uint16_t throttle, uint32_t duration_ms) {
    const uint32_t step_ms = 2;  // 500 Hz update rate
    uint32_t steps = duration_ms / step_ms;
    for (uint32_t i = 0; i < steps; i++) {
        dshot_send_throttle(MOTOR_WEAPON, throttle, false);
        sleep_ms(step_ms);
    }
}

static void send_command_repeat(dshot_command_t cmd, const char* label, int repeats) {
    printf("Command: %s (cmd=%u) x%d\n", label, (unsigned)cmd, repeats);
    for (int i = 0; i < repeats; i++) {
        dshot_send_command(MOTOR_WEAPON, cmd);
        send_throttle_for_ms(0, 200);
    }
}

int main() {
    stdio_init_all();
    sleep_ms(2000);

    printf("\n========================================\n");
    printf("  DShot Spin Test\n");
    printf("========================================\n\n");
    printf("Target: DShot%u on GP%d\n", (unsigned)DSHOT_TEST_SPEED, PIN_WEAPON_PWM);
    printf("Sequence: arm -> 3D off -> dir normal -> ramp throttle\n\n");

    dshot_config_t config = {
        .gpio_pin = PIN_WEAPON_PWM,
        .speed = DSHOT_TEST_SPEED,
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

        printf("Arming (throttle=0, 5s)\n");
        send_throttle_for_ms(0, 5000);

        send_command_repeat(DSHOT_CMD_3D_MODE_OFF, "3D_MODE_OFF", 3);
        send_command_repeat(DSHOT_CMD_SPIN_DIRECTION_NORMAL, "SPIN_DIR_NORMAL", 3);

        printf("Throttle ramp (2s per step)\n");
        send_throttle_for_ms(200, 2000);
        send_throttle_for_ms(500, 2000);
        send_throttle_for_ms(1000, 2000);
        send_throttle_for_ms(1500, 2000);
        send_throttle_for_ms(1800, 2000);

        printf("Stop (throttle=0, 4s)\n");
        send_throttle_for_ms(0, 4000);
    }
}
