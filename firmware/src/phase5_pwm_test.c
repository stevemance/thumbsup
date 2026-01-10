/*
 * Phase 5: PWM Motor Test
 *
 * Purpose: Test motor using standard PWM (not DShot) to isolate the issue
 * If PWM works but DShot doesn't, the issue is in DShot implementation
 * If PWM also doesn't work, the issue is physical/ESC config
 *
 * Uses standard servo PWM: 1000-2000μs pulses at 50Hz
 */

#include <stdio.h>
#include <pico/stdlib.h>
#include "hardware/pwm.h"
#include "config.h"

// PWM parameters for ESC
#define PWM_FREQ_HZ 50       // Standard servo frequency
#define PWM_MIN_US 1000      // Minimum pulse (throttle 0%)
#define PWM_MAX_US 2000      // Maximum pulse (throttle 100%)
#define PWM_ARM_US 1000      // Arming pulse

int main() {
    stdio_init_all();
    sleep_ms(2000);

    printf("\n========================================\n");
    printf("  Phase 5: PWM Motor Test\n");
    printf("========================================\n\n");

    printf("This test uses standard PWM (not DShot) to control the motor.\n");
    printf("ESC should auto-detect PWM mode.\n\n");

    // Setup LED for status
    const uint LED_PIN = 25;
    gpio_init(LED_PIN);
    gpio_set_dir(LED_PIN, GPIO_OUT);

    // Setup PWM on weapon pin
    uint pin = PIN_WEAPON_PWM;
    printf("Initializing PWM on GPIO %d...\n", pin);

    gpio_set_function(pin, GPIO_FUNC_PWM);
    uint slice = pwm_gpio_to_slice_num(pin);
    uint channel = pwm_gpio_to_channel(pin);

    // Configure PWM for 50Hz (20ms period)
    // System clock is 125MHz
    // For 50Hz: period = 20ms = 20000us
    // We want good resolution for 1000-2000us range
    // Use wrap = 20000, divider = 125 -> 1us per count
    pwm_set_clkdiv(slice, 125.0f);
    pwm_set_wrap(slice, 19999);  // 20000 counts = 20ms period
    pwm_set_enabled(slice, true);

    printf("✓ PWM initialized at 50Hz\n\n");

    printf("========================================\n");
    printf("  Test Sequence\n");
    printf("========================================\n\n");

    int test_num = 1;

    while (true) {
        printf("\n=== PWM Test Run #%d ===\n", test_num);

        // Step 1: Arm ESC (1000us = 0% throttle) - LONGER arm period
        printf("[1/5] ARMING ESC (1000us pulse, 5s)...\n");
        printf("      Listen for ESC beeps\n");
        gpio_put(LED_PIN, 1);
        pwm_set_chan_level(slice, channel, 1000);  // 1000us pulse
        sleep_ms(5000);
        gpio_put(LED_PIN, 0);
        sleep_ms(500);

        // Step 2: Very low throttle (1100us = 10%)
        printf("[2/5] VERY LOW throttle (1100us = 10%%, 3s)...\n");
        gpio_put(LED_PIN, 1);
        pwm_set_chan_level(slice, channel, 1100);  // 1100us pulse
        sleep_ms(3000);
        gpio_put(LED_PIN, 0);
        sleep_ms(500);

        // Step 3: Low throttle (1150us = 15%)
        printf("[3/5] LOW throttle (1150us = 15%%, 3s)...\n");
        gpio_put(LED_PIN, 1);
        pwm_set_chan_level(slice, channel, 1150);  // 1150us pulse
        sleep_ms(3000);
        gpio_put(LED_PIN, 0);
        sleep_ms(500);

        // Step 4: Medium-low throttle (1200us = 20%)
        printf("[4/5] MEDIUM-LOW throttle (1200us = 20%%, 3s)...\n");
        printf("      ⚠️  MONITOR MOTOR!\n");
        gpio_put(LED_PIN, 1);
        pwm_set_chan_level(slice, channel, 1200);  // 1200us pulse
        sleep_ms(3000);
        gpio_put(LED_PIN, 0);
        sleep_ms(500);

        // Step 5: Stop (back to 1000us)
        printf("[5/5] STOPPING (1000us, 3s)...\n");
        gpio_put(LED_PIN, 1);
        pwm_set_chan_level(slice, channel, 1000);  // 1000us pulse
        sleep_ms(3000);
        gpio_put(LED_PIN, 0);

        printf("\n✓ PWM Test run #%d complete\n", test_num);
        printf("  Did motor spin? (Y/N)\n");
        printf("  If YES: DShot issue in our code\n");
        printf("  If NO: Physical/ESC config issue\n\n");

        printf("Waiting 10 seconds before next test...\n");

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
