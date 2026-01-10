/*
 * Phase 2: DShot Signal Verification
 *
 * Purpose: Generate precise DShot signals for oscilloscope verification
 *
 * This firmware sends specific DShot throttle values in a repeating pattern
 * to allow oscilloscope capture and timing analysis per the bringup plan.
 *
 * Connect oscilloscope Channel 1 to GP4, GND to Pico GND.
 *
 * Expected waveform timing for DShot300:
 * - Bit period: 3.33 μs
 * - Logic 0: HIGH for 1.25 μs, LOW for 2.08 μs
 * - Logic 1: HIGH for 2.50 μs, LOW for 0.83 μs
 * - Full packet: 16 bits = 53.33 μs
 */

#include <stdio.h>
#include <pico/stdlib.h>
#include "config.h"
#include "dshot.h"

// Test pattern throttle values
#define TEST_THROTTLE_ZERO    0      // Disarmed
#define TEST_THROTTLE_MIN     48     // Minimum armed throttle
#define TEST_THROTTLE_LOW     200    // Low speed
#define TEST_THROTTLE_MID     500    // Medium speed
#define TEST_THROTTLE_HIGH    1000   // High speed
#define TEST_THROTTLE_MAX     2047   // Maximum throttle

int main() {
    stdio_init_all();
    sleep_ms(2000);

    printf("\n========================================\n");
    printf("  Phase 2: DShot Signal Verification\n");
    printf("  For Oscilloscope Analysis\n");
    printf("========================================\n\n");

    printf("Connect oscilloscope:\n");
    printf("  Ch1 → GP4 (weapon ESC signal)\n");
    printf("  GND → Pico GND\n\n");

    printf("Oscilloscope settings:\n");
    printf("  Timebase: 10 μs/div\n");
    printf("  Voltage: 1 V/div\n");
    printf("  Trigger: Rising edge, 1.65V\n");
    printf("  Sample rate: 100 MSa/s minimum\n\n");

    printf("Expected DShot300 timing:\n");
    printf("  Bit period: 3.33 μs\n");
    printf("  Logic 0: HIGH 1.25μs, LOW 2.08μs\n");
    printf("  Logic 1: HIGH 2.50μs, LOW 0.83μs\n");
    printf("  Packet: 16 bits = 53.33 μs total\n\n");

    // Initialize DShot
    printf("Initializing DShot300 on GP%d...\n", PIN_WEAPON_PWM);
    dshot_config_t config = {
        .gpio_pin = PIN_WEAPON_PWM,
        .speed = DSHOT_SPEED_300,
        .bidirectional = true,
        .pole_pairs = 7  // Assumed, will verify with motor
    };

    if (!dshot_init(MOTOR_WEAPON, &config)) {
        printf("✗ DShot init failed!\n");
        while (1) {
            sleep_ms(1000);
        }
    }
    printf("✓ DShot initialized\n\n");

    printf("========================================\n");
    printf("  Test Pattern Starting\n");
    printf("========================================\n\n");

    printf("Test sequence (repeats every 15 seconds):\n");
    printf("  1. Throttle = 0    (disarmed, 3s hold)\n");
    printf("  2. Throttle = 48   (min armed, 3s hold)\n");
    printf("  3. Throttle = 200  (low speed, 3s hold)\n");
    printf("  4. Throttle = 500  (mid speed, 3s hold)\n");
    printf("  5. Throttle = 1000 (high speed, 3s hold)\n");
    printf("  6. Throttle = 0    (stop, 3s hold)\n\n");

    printf("Capture strategy:\n");
    printf("  - Set scope to Single trigger mode\n");
    printf("  - Trigger on rising edge\n");
    printf("  - Capture when value changes\n");
    printf("  - Verify packet timing and structure\n\n");

    const uint LED_PIN = 25;
    gpio_init(LED_PIN);
    gpio_set_dir(LED_PIN, GPIO_OUT);

    int cycle = 0;

    while (true) {
        cycle++;
        printf("\n=== Cycle %d ===\n", cycle);

        // Step 1: ZERO (disarmed)
        printf("[Step 1/6] Sending throttle = 0 (DISARMED)\n");
        printf("  Packet: 0x0000 (all bits 0)\n");
        printf("  Capture this for baseline timing analysis\n");
        gpio_put(LED_PIN, 1);
        for (int i = 0; i < 30; i++) {  // 3 seconds
            dshot_send_throttle(MOTOR_WEAPON, TEST_THROTTLE_ZERO, false);
            sleep_ms(100);
        }
        gpio_put(LED_PIN, 0);

        // Step 2: MIN (minimum armed throttle)
        printf("[Step 2/6] Sending throttle = 48 (MIN ARMED)\n");
        printf("  Packet: 0x0030 with CRC\n");
        printf("  This is minimum value that should arm ESC\n");
        gpio_put(LED_PIN, 1);
        for (int i = 0; i < 30; i++) {
            dshot_send_throttle(MOTOR_WEAPON, TEST_THROTTLE_MIN, false);
            sleep_ms(100);
        }
        gpio_put(LED_PIN, 0);

        // Step 3: LOW
        printf("[Step 3/6] Sending throttle = 200 (LOW)\n");
        printf("  Packet: 0x00C8 with CRC\n");
        gpio_put(LED_PIN, 1);
        for (int i = 0; i < 30; i++) {
            dshot_send_throttle(MOTOR_WEAPON, TEST_THROTTLE_LOW, false);
            sleep_ms(100);
        }
        gpio_put(LED_PIN, 0);

        // Step 4: MEDIUM
        printf("[Step 4/6] Sending throttle = 500 (MEDIUM)\n");
        printf("  Packet: 0x01F4 with CRC\n");
        gpio_put(LED_PIN, 1);
        for (int i = 0; i < 30; i++) {
            dshot_send_throttle(MOTOR_WEAPON, TEST_THROTTLE_MID, false);
            sleep_ms(100);
        }
        gpio_put(LED_PIN, 0);

        // Step 5: HIGH
        printf("[Step 5/6] Sending throttle = 1000 (HIGH)\n");
        printf("  Packet: 0x03E8 with CRC\n");
        gpio_put(LED_PIN, 1);
        for (int i = 0; i < 30; i++) {
            dshot_send_throttle(MOTOR_WEAPON, TEST_THROTTLE_HIGH, false);
            sleep_ms(100);
        }
        gpio_put(LED_PIN, 0);

        // Step 6: STOP
        printf("[Step 6/6] Sending throttle = 0 (STOP)\n");
        gpio_put(LED_PIN, 1);
        for (int i = 0; i < 30; i++) {
            dshot_send_throttle(MOTOR_WEAPON, TEST_THROTTLE_ZERO, false);
            sleep_ms(100);
        }
        gpio_put(LED_PIN, 0);

        printf("\nCycle %d complete. Waiting 3 seconds before next cycle...\n", cycle);
        sleep_ms(3000);
    }

    return 0;
}
