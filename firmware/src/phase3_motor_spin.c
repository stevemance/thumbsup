/*
 * Phase 3: Basic Motor Spin Test
 *
 * Purpose: Verify ESC responds to DShot and motor spins correctly
 *
 * Prerequisites:
 * - ESC must be configured with parameter adjuster (Phase 1 complete)
 * - Motor connected to ESC
 * - Battery connected
 * - Motor secured (remove weapon blade!)
 *
 * SAFETY:
 * - Keep hands clear of motor
 * - Motor should be secured to prevent movement
 * - Watch for excessive current (should stay under 10A)
 * - Monitor temperature
 */

#include <stdio.h>
#include <pico/stdlib.h>
#include "config.h"
#include "dshot.h"

int main() {
    stdio_init_all();
    sleep_ms(2000);

    printf("\n========================================\n");
    printf("  Phase 3: Basic Motor Spin Test\n");
    printf("========================================\n\n");

    printf("⚠️  SAFETY CHECKLIST:\n");
    printf("  [ ] Motor is secured to test stand/bench\n");
    printf("  [ ] Weapon blade REMOVED\n");
    printf("  [ ] Hands/tools clear of motor shaft\n");
    printf("  [ ] Safety glasses ON\n");
    printf("  [ ] Battery connected and charged\n");
    printf("  [ ] ESC configured (Phase 1 complete)\n\n");

    printf("Press Enter to continue (or Ctrl+C to abort)...\n");
    getchar();

    // Initialize DShot
    printf("\nInitializing DShot300...\n");
    dshot_config_t config = {
        .gpio_pin = PIN_WEAPON_PWM,
        .speed = DSHOT_SPEED_300,
        .bidirectional = true,  // Re-enabled to test if this helps
        .pole_pairs = 7  // 14 poles / 2 = 7 pole pairs
    };

    if (!dshot_init(MOTOR_WEAPON, &config)) {
        printf("✗ DShot init failed!\n");
        while (1) sleep_ms(1000);
    }
    printf("✓ DShot initialized\n\n");

    // Setup LED for status
    const uint LED_PIN = 25;
    gpio_init(LED_PIN);
    gpio_set_dir(LED_PIN, GPIO_OUT);

    printf("========================================\n");
    printf("  Test Sequence Starting\n");
    printf("========================================\n\n");

    printf("The motor will:\n");
    printf("  1. Beep/arm (throttle=0, 2s)\n");
    printf("  2. Spin slowly (throttle=100, 3s)\n");
    printf("  3. Spin medium (throttle=300, 3s)\n");
    printf("  4. Spin faster (throttle=500, 3s)\n");
    printf("  5. Stop (throttle=0, 3s)\n");
    printf("  6. Repeat every 20 seconds\n\n");

    printf("WATCH FOR:\n");
    printf("  ✓ Motor starts smoothly (no stuttering)\n");
    printf("  ✓ Speed increases with throttle\n");
    printf("  ✓ Motor stops cleanly\n");
    printf("  ✓ No excessive heat or noise\n");
    printf("  ✗ If motor doesn't spin: Check ESC config\n");
    printf("  ✗ If direction wrong: Swap two motor wires\n\n");

    int test_num = 1;

    while (true) {
        printf("\n=== Test Run #%d ===\n", test_num);

        // Step 1: Arm ESC
        printf("[1/5] Arming ESC (throttle = 0)...\n");
        printf("      Listen for ESC beeps\n");
        gpio_put(LED_PIN, 1);
        for (int i = 0; i < 1000; i++) {  // 2 seconds @ 2ms/packet = 500Hz update rate
            dshot_send_throttle(MOTOR_WEAPON, 0, false);
            sleep_ms(2);
        }
        gpio_put(LED_PIN, 0);
        sleep_ms(500);

        // Step 2: Medium-Low speed
        printf("[2/5] MEDIUM-LOW speed (throttle = 500)...\n");
        printf("      Motor should spin slowly\n");
        gpio_put(LED_PIN, 1);
        for (int i = 0; i < 1500; i++) {  // 3 seconds @ 2ms/packet
            dshot_send_throttle(MOTOR_WEAPON, 500, false);
            sleep_ms(2);
        }
        gpio_put(LED_PIN, 0);
        sleep_ms(500);

        // Step 3: Medium speed
        printf("[3/5] MEDIUM speed (throttle = 1000)...\n");
        printf("      Motor should spin faster\n");
        gpio_put(LED_PIN, 1);
        for (int i = 0; i < 1500; i++) {  // 3 seconds @ 2ms/packet
            dshot_send_throttle(MOTOR_WEAPON, 1000, false);
            sleep_ms(2);
        }
        gpio_put(LED_PIN, 0);
        sleep_ms(500);

        // Step 4: High speed
        printf("[4/5] HIGH speed (throttle = 1500)...\n");
        printf("      Motor should spin significantly faster\n");
        printf("      ⚠️  MONITOR CURRENT AND TEMPERATURE!\n");
        gpio_put(LED_PIN, 1);
        for (int i = 0; i < 1500; i++) {  // 3 seconds @ 2ms/packet
            dshot_send_throttle(MOTOR_WEAPON, 1500, false);
            sleep_ms(2);
        }
        gpio_put(LED_PIN, 0);
        sleep_ms(500);

        // Step 5: Stop
        printf("[5/5] STOPPING motor (throttle = 0)...\n");
        printf("      Motor should brake cleanly\n");
        gpio_put(LED_PIN, 1);
        for (int i = 0; i < 1500; i++) {  // 3 seconds @ 2ms/packet
            dshot_send_throttle(MOTOR_WEAPON, 0, false);
            sleep_ms(2);
        }
        gpio_put(LED_PIN, 0);

        printf("\n✓ Test run #%d complete\n", test_num);
        printf("  Did motor spin? (Y/N): ___\n");
        printf("  Direction correct? (Y/N): ___\n");
        printf("  Smooth operation? (Y/N): ___\n");
        printf("  Temperature OK? (Y/N): ___\n\n");

        printf("Waiting 15 seconds before next test...\n");
        printf("(Press Ctrl+C to stop)\n");

        // Wait 15 seconds with LED blinking
        for (int i = 0; i < 15; i++) {
            gpio_put(LED_PIN, 1);
            sleep_ms(500);
            gpio_put(LED_PIN, 0);
            sleep_ms(500);
        }

        test_num++;
    }

    return 0;
}
