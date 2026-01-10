/*
 * Phase 4: DShot Telemetry Test
 *
 * Purpose: Read bidirectional DShot telemetry from ESC to diagnose motor issues
 *
 * This test will:
 * - Send throttle commands with telemetry requests
 * - Read and display ESC telemetry (voltage, current, RPM, temperature)
 * - Help diagnose why motor isn't spinning
 *
 * Prerequisites:
 * - ESC configured with bidirectional DShot support
 * - Motor connected and secured
 * - Battery connected
 */

#include <stdio.h>
#include <pico/stdlib.h>
#include "config.h"
#include "dshot.h"

int main() {
    stdio_init_all();
    sleep_ms(2000);

    printf("\n========================================\n");
    printf("  Phase 4: DShot Telemetry Test\n");
    printf("========================================\n\n");

    printf("This test will send throttle commands and read telemetry.\n");
    printf("Telemetry includes: voltage, current, RPM, temperature\n\n");

    // Initialize DShot with bidirectional mode
    printf("Initializing DShot300 with bidirectional telemetry...\n");
    dshot_config_t config = {
        .gpio_pin = PIN_WEAPON_PWM,
        .speed = DSHOT_SPEED_300,
        .bidirectional = true,
        .pole_pairs = 7  // 14 poles / 2 = 7 pole pairs
    };

    if (!dshot_init(MOTOR_WEAPON, &config)) {
        printf("✗ DShot init failed!\n");
        while (1) sleep_ms(1000);
    }
    printf("✓ DShot initialized with bidirectional mode\n\n");

    // Setup LED for status
    const uint LED_PIN = 25;
    gpio_init(LED_PIN);
    gpio_set_dir(LED_PIN, GPIO_OUT);

    printf("========================================\n");
    printf("  Starting Telemetry Test\n");
    printf("========================================\n\n");

    printf("Test sequence:\n");
    printf("  1. Arm ESC (throttle=0, 3s)\n");
    printf("  2. Test throttle=500 (5s)\n");
    printf("  3. Test throttle=1000 (5s)\n");
    printf("  4. Test throttle=1500 (5s)\n");
    printf("  5. Stop (throttle=0, 3s)\n");
    printf("  6. Repeat\n\n");

    int test_num = 1;
    uint32_t telemetry_count = 0;
    uint32_t telemetry_errors = 0;

    while (true) {
        printf("\n=== Telemetry Test Run #%d ===\n", test_num);

        // Step 1: Arm ESC
        printf("\n[1/5] ARMING ESC (throttle = 0, 3s)...\n");
        gpio_put(LED_PIN, 1);

        for (int i = 0; i < 1500; i++) {  // 3 seconds @ 2ms
            dshot_send_throttle(MOTOR_WEAPON, 0, true);  // Request telemetry

            // Try to read telemetry
            dshot_telemetry_t telem;
            if (dshot_read_telemetry(MOTOR_WEAPON, &telem)) {
                telemetry_count++;
                printf("  TELEM: eRPM=%u, Volt=%u.%02uV, Curr=%u.%02uA, Temp=%uC\n",
                       telem.erpm,
                       telem.voltage_cV / 100, telem.voltage_cV % 100,
                       telem.current_cA / 100, telem.current_cA % 100,
                       telem.temperature_C);
            }

            sleep_ms(2);
        }
        gpio_put(LED_PIN, 0);
        printf("  Telemetry packets received: %u\n", telemetry_count);
        sleep_ms(500);

        // Step 2: Throttle 500
        printf("\n[2/5] THROTTLE = 500 (5s)...\n");
        gpio_put(LED_PIN, 1);
        uint32_t telem_start = telemetry_count;

        for (int i = 0; i < 2500; i++) {  // 5 seconds @ 2ms
            dshot_send_throttle(MOTOR_WEAPON, 500, true);  // Request telemetry

            dshot_telemetry_t telem;
            if (dshot_read_telemetry(MOTOR_WEAPON, &telem)) {
                telemetry_count++;
                // Print every 100ms
                if (i % 50 == 0) {
                    printf("  TELEM: eRPM=%u, Volt=%u.%02uV, Curr=%u.%02uA, Temp=%uC\n",
                           telem.erpm,
                           telem.voltage_cV / 100, telem.voltage_cV % 100,
                           telem.current_cA / 100, telem.current_cA % 100,
                           telem.temperature_C);
                }
            }

            sleep_ms(2);
        }
        gpio_put(LED_PIN, 0);
        printf("  Telemetry packets this step: %u\n", telemetry_count - telem_start);
        sleep_ms(500);

        // Step 3: Throttle 1000
        printf("\n[3/5] THROTTLE = 1000 (5s)...\n");
        gpio_put(LED_PIN, 1);
        telem_start = telemetry_count;

        for (int i = 0; i < 2500; i++) {  // 5 seconds @ 2ms
            dshot_send_throttle(MOTOR_WEAPON, 1000, true);  // Request telemetry

            dshot_telemetry_t telem;
            if (dshot_read_telemetry(MOTOR_WEAPON, &telem)) {
                telemetry_count++;
                if (i % 50 == 0) {
                    printf("  TELEM: eRPM=%u, Volt=%u.%02uV, Curr=%u.%02uA, Temp=%uC\n",
                           telem.erpm,
                           telem.voltage_cV / 100, telem.voltage_cV % 100,
                           telem.current_cA / 100, telem.current_cA % 100,
                           telem.temperature_C);
                }
            }

            sleep_ms(2);
        }
        gpio_put(LED_PIN, 0);
        printf("  Telemetry packets this step: %u\n", telemetry_count - telem_start);
        sleep_ms(500);

        // Step 4: Throttle 1500
        printf("\n[4/5] THROTTLE = 1500 (5s)...\n");
        printf("      ⚠️  MONITOR MOTOR!\n");
        gpio_put(LED_PIN, 1);
        telem_start = telemetry_count;

        for (int i = 0; i < 2500; i++) {  // 5 seconds @ 2ms
            dshot_send_throttle(MOTOR_WEAPON, 1500, true);  // Request telemetry

            dshot_telemetry_t telem;
            if (dshot_read_telemetry(MOTOR_WEAPON, &telem)) {
                telemetry_count++;
                if (i % 50 == 0) {
                    printf("  TELEM: eRPM=%u, Volt=%u.%02uV, Curr=%u.%02uA, Temp=%uC\n",
                           telem.erpm,
                           telem.voltage_cV / 100, telem.voltage_cV % 100,
                           telem.current_cA / 100, telem.current_cA % 100,
                           telem.temperature_C);
                }
            }

            sleep_ms(2);
        }
        gpio_put(LED_PIN, 0);
        printf("  Telemetry packets this step: %u\n", telemetry_count - telem_start);
        sleep_ms(500);

        // Step 5: Stop
        printf("\n[5/5] STOPPING (throttle = 0, 3s)...\n");
        gpio_put(LED_PIN, 1);
        telem_start = telemetry_count;

        for (int i = 0; i < 1500; i++) {  // 3 seconds @ 2ms
            dshot_send_throttle(MOTOR_WEAPON, 0, true);  // Request telemetry

            dshot_telemetry_t telem;
            if (dshot_read_telemetry(MOTOR_WEAPON, &telem)) {
                telemetry_count++;
                if (i % 50 == 0) {
                    printf("  TELEM: eRPM=%u, Volt=%u.%02uV, Curr=%u.%02uA, Temp=%uC\n",
                           telem.erpm,
                           telem.voltage_cV / 100, telem.voltage_cV % 100,
                           telem.current_cA / 100, telem.current_cA % 100,
                           telem.temperature_C);
                }
            }

            sleep_ms(2);
        }
        gpio_put(LED_PIN, 0);
        printf("  Telemetry packets this step: %u\n", telemetry_count - telem_start);

        printf("\n✓ Test run #%d complete\n", test_num);
        printf("  Total telemetry packets received: %u\n", telemetry_count);
        printf("  Telemetry errors: %u\n", telemetry_errors);

        printf("\nWaiting 10 seconds before next test...\n");
        printf("(Press Ctrl+C to stop)\n");

        // Wait 10 seconds with LED blinking
        for (int i = 0; i < 10; i++) {
            gpio_put(LED_PIN, 1);
            sleep_ms(500);
            gpio_put(LED_PIN, 0);
            sleep_ms(500);
        }

        test_num++;
    }

    return 0;
}
