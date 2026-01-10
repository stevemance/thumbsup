/*
 * AM32 Config Test - E2E validation of config read/diff/update
 */

#include <stdio.h>
#include <string.h>
#include <pico/stdlib.h>
#include "hardware/gpio.h"
#include "am32_bootloader.h"
#include "am32_config_data.h"

int main() {
    stdio_init_all();
    sleep_ms(3000);

    printf("\n========================================\n");
    printf("  AM32 Config Library E2E Test\n");
    printf("========================================\n\n");

    // Setup LED
    const uint LED_PIN = 25;
    gpio_init(LED_PIN);
    gpio_set_dir(LED_PIN, GPIO_OUT);

    // Initialize bootloader GPIO
    am32_bootloader_init();

    printf("Attempting to enter bootloader mode...\n");
    printf("If ESC not in bootloader, power cycle it now.\n");
    gpio_put(LED_PIN, 1);

    // Enter bootloader - waits ~2.5s for firmware timeout
    int result = am32_bootloader_enter();
    if (result != AM32_OK) {
        printf("FAIL: Could not enter bootloader mode (error %d)\n", result);
        printf("Make sure ESC is powered and connected to GP4\n");
        goto fail;
    }

    printf("SUCCESS: Entered bootloader mode!\n\n");
    gpio_put(LED_PIN, 0);

    printf("\n--- Test 1: Read Current Config ---\n");
    uint8_t current_config[192];
    result = am32_bootloader_read(current_config);

    if (result != AM32_OK) {
        printf("FAIL: Could not read config (error %d)\n", result);
        printf("ESC may not be in bootloader mode.\n");
        goto fail;
    }

    printf("SUCCESS: Read 192 bytes from ESC\n\n");

    printf("--- Current ESC Config ---\n");
    am32_bootloader_print(current_config);

    printf("\n--- Test 2: Diff Against Desired Config ---\n");
    uint8_t diff_mask[192];
    int diff_count = am32_bootloader_diff(current_config, am32_desired_config, diff_mask);

    printf("Differences found: %d bytes\n", diff_count);

    if (diff_count > 0) {
        printf("Differing bytes:\n");
        for (int i = 0; i < 192; i++) {
            if (diff_mask[i]) {
                printf("  [%3d]: ESC=0x%02X  Desired=0x%02X\n",
                       i, current_config[i], am32_desired_config[i]);
            }
        }

        printf("\n--- Test 3: Update Config ---\n");
        result = am32_bootloader_write(am32_desired_config);

        if (result != AM32_OK) {
            printf("FAIL: Could not write config (error %d)\n", result);
            goto fail;
        }

        printf("SUCCESS: Wrote desired config to ESC\n\n");

        printf("--- Test 4: Verify Write ---\n");
        uint8_t verify_config[192];
        result = am32_bootloader_read(verify_config);

        if (result != AM32_OK) {
            printf("FAIL: Could not read back config (error %d)\n", result);
            goto fail;
        }

        if (memcmp(verify_config, am32_desired_config, 192) == 0) {
            printf("SUCCESS: Config verified - matches desired!\n");
        } else {
            printf("FAIL: Config mismatch after write\n");
            int mismatch = am32_bootloader_diff(verify_config, am32_desired_config, diff_mask);
            printf("Mismatched bytes: %d\n", mismatch);
            goto fail;
        }
    } else {
        printf("Config already matches desired - no update needed\n");
    }

    printf("\n--- Final Config ---\n");
    uint8_t final_config[192];
    am32_bootloader_read(final_config);
    am32_bootloader_print(final_config);

    printf("\n========================================\n");
    printf("  ALL TESTS PASSED!\n");
    printf("========================================\n\n");

    // Exit bootloader and run ESC firmware
    printf("Sending RUN command to exit bootloader...\n");
    am32_bootloader_run();

    // Success blink pattern
    while (1) {
        gpio_put(LED_PIN, 1);
        sleep_ms(100);
        gpio_put(LED_PIN, 0);
        sleep_ms(100);
        gpio_put(LED_PIN, 1);
        sleep_ms(100);
        gpio_put(LED_PIN, 0);
        sleep_ms(700);
    }

    return 0;

fail:
    printf("\n========================================\n");
    printf("  TEST FAILED\n");
    printf("========================================\n");

    // Failure blink pattern
    while (1) {
        gpio_put(LED_PIN, 1);
        sleep_ms(100);
        gpio_put(LED_PIN, 0);
        sleep_ms(900);
    }

    return 1;
}
