#include <stdio.h>
#include <pico/stdlib.h>
#include <hardware/gpio.h>
#include "config.h"
#include "am32_config.h"
#include "dshot.h"

#define ESC_PIN PIN_WEAPON_PWM  // GP4

// Stub functions for motor_control dependencies
bool system_failsafe_active(void) {
    return false;  // No failsafe in test mode
}

bool system_is_armed(void) {
    return true;  // Always armed in test mode
}

void system_set_armed(bool armed) {
    // Stub - not needed for test
}

void system_set_failsafe(bool active) {
    // Stub - not needed for test
}

int main() {
    // Initialize stdio for serial output
    stdio_init_all();
    sleep_ms(2000);  // Wait for USB serial connection

    printf("\n\n");
    printf("========================================\n");
    printf("  ESC Communication Test\n");
    printf("  Testing AM32 and DShot on GP%d\n", ESC_PIN);
    printf("========================================\n\n");

    // ========================================
    // TEST 1: AM32 UART Communication
    // ========================================
    printf("\n=== TEST 1: AM32 UART Communication ===\n");
    printf("Initializing AM32...\n");

    if (!am32_init()) {
        printf("✗ FAILED: AM32 initialization failed\n");
    } else {
        printf("✓ AM32 initialized\n");
    }

    sleep_ms(100);

    printf("\nAttempting to enter config mode...\n");
    if (am32_enter_config_mode()) {
        printf("✓ Entered config mode successfully!\n");

        // Try to read ESC info
        printf("\nReading ESC info...\n");
        am32_info_t info = {0};
        if (am32_get_info(&info)) {
            printf("✓ ESC Info received:\n");
            printf("  Firmware: v%d.%d.%d\n",
                   info.firmware_version[0],
                   info.firmware_version[1],
                   info.firmware_version[2]);
            printf("  Name: %s\n", info.firmware_name);
            printf("  MCU Type: %d\n", info.mcu_type);
            printf("  Flash: %d KB\n", info.flash_size);
        } else {
            printf("✗ Failed to read ESC info\n");
        }

        // Try to read settings
        printf("\nReading ESC settings...\n");
        am32_config_t config = {0};
        if (am32_read_settings(&config)) {
            printf("✓ ESC Settings received:\n");
            printf("  Motor Poles: %d (pole pairs: %d)\n",
                   config.motor_poles, config.motor_poles / 2);
            printf("  Direction: %d (0=normal, 1=reversed)\n", config.motor_direction);
            printf("  Current Limit: %dA\n", config.current_limit);
            printf("  Temp Limit: %d°C\n", config.temperature_limit);
            printf("  Brake on Stop: %s\n", config.brake_on_stop ? "Yes" : "No");
            printf("  Bidirectional: %s\n", config.bidirectional ? "Yes" : "No");
            printf("  Telemetry: %s\n", config.telemetry ? "Yes" : "No");
            printf("  Startup Power: %d\n", config.startup_power);
        } else {
            printf("✗ Failed to read ESC settings\n");
        }

        printf("\nExiting config mode...\n");
        am32_exit_config_mode();
        printf("✓ Exited config mode\n");

    } else {
        printf("✗ FAILED: Cannot enter config mode\n");
        printf("  Possible causes:\n");
        printf("  - ESC not powered (check battery)\n");
        printf("  - Wrong wire on GP4/S pad\n");
        printf("  - ESC doesn't support AM32 protocol\n");
        printf("  - UART not working on GP4\n");
    }

    sleep_ms(500);

    // ========================================
    // TEST 2: DShot Signal Generation
    // ========================================
    printf("\n\n=== TEST 2: DShot Signal Generation ===\n");
    printf("Initializing DShot300 on GP%d...\n", ESC_PIN);

    dshot_config_t dshot_config = {
        .gpio_pin = ESC_PIN,
        .speed = DSHOT_SPEED_300,
        .bidirectional = true,
        .pole_pairs = 7  // 14 poles
    };

    if (dshot_init(MOTOR_WEAPON, &dshot_config)) {
        printf("✓ DShot initialized successfully\n");

        printf("\nSending DShot test sequence...\n");
        printf("(Motor should beep/spin if connected and configured)\n\n");

        // Send stop command
        printf("1. Sending STOP (throttle=0)...\n");
        dshot_send_throttle(MOTOR_WEAPON, 0, false);
        sleep_ms(1000);

        // Send low throttle
        printf("2. Sending LOW throttle (throttle=100)...\n");
        dshot_send_throttle(MOTOR_WEAPON, 100, false);
        sleep_ms(2000);

        // Send medium throttle
        printf("3. Sending MEDIUM throttle (throttle=500)...\n");
        dshot_send_throttle(MOTOR_WEAPON, 500, false);
        sleep_ms(2000);

        // Send high throttle
        printf("4. Sending HIGH throttle (throttle=1000)...\n");
        dshot_send_throttle(MOTOR_WEAPON, 1000, false);
        sleep_ms(2000);

        // Send stop command
        printf("5. Sending STOP (throttle=0)...\n");
        dshot_send_throttle(MOTOR_WEAPON, 0, false);
        sleep_ms(1000);

        printf("\n✓ DShot test sequence complete\n");

        // Test with telemetry request
        printf("\n6. Testing DShot with telemetry request...\n");
        for (int i = 0; i < 10; i++) {
            dshot_send_throttle(MOTOR_WEAPON, 0, true);  // Request telemetry
            sleep_ms(100);
        }
        printf("✓ Telemetry requests sent\n");

        dshot_deinit(MOTOR_WEAPON);
        printf("\n✓ DShot deinitialized\n");

    } else {
        printf("✗ FAILED: DShot initialization failed\n");
        printf("  Check PIO/DMA resources\n");
    }

    // ========================================
    // TEST SUMMARY
    // ========================================
    printf("\n\n========================================\n");
    printf("  ESC Test Complete\n");
    printf("========================================\n");
    printf("\nResults:\n");
    printf("- If AM32 config mode worked: ESC supports UART\n");
    printf("- If DShot initialized: PIO/DMA working\n");
    printf("- If motor responded: DShot wiring correct\n");
    printf("\nNext steps:\n");
    printf("- If AM32 failed: Use USB parameter adjuster\n");
    printf("- If motor didn't respond: Check ESC configuration\n");
    printf("  (motor poles, direction, current limit)\n");
    printf("\nTest will repeat every 15 seconds...\n");
    printf("Press Ctrl+C to exit.\n\n");

    // Setup LED for status indication
    const uint LED_PIN = 25;
    gpio_init(LED_PIN);
    gpio_set_dir(LED_PIN, GPIO_OUT);

    int test_count = 1;

    // Loop forever, repeating the test
    while (true) {
        printf("\n\n");
        printf("=====================================\n");
        printf("  Waiting 15 seconds before test #%d\n", test_count + 1);
        printf("=====================================\n");

        // Wait 15 seconds with LED blinking
        for (int i = 0; i < 15; i++) {
            gpio_put(LED_PIN, 1);
            sleep_ms(500);
            gpio_put(LED_PIN, 0);
            sleep_ms(500);
        }

        test_count++;

        printf("\n\n");
        printf("========================================\n");
        printf("  ESC Communication Test #%d\n", test_count);
        printf("  Testing AM32 and DShot on GP%d\n", ESC_PIN);
        printf("========================================\n\n");

        // ========================================
        // TEST 1: AM32 UART Communication
        // ========================================
        printf("\n=== TEST 1: AM32 UART Communication ===\n");
        printf("Initializing AM32...\n");

        if (!am32_init()) {
            printf("✗ FAILED: AM32 initialization failed\n");
        } else {
            printf("✓ AM32 initialized\n");
        }

        sleep_ms(100);

        printf("\nAttempting to enter config mode...\n");
        if (am32_enter_config_mode()) {
            printf("✓ Entered config mode successfully!\n");

            // Try to read ESC info
            printf("\nReading ESC info...\n");
            am32_info_t info = {0};
            if (am32_get_info(&info)) {
                printf("✓ ESC Info received:\n");
                printf("  Firmware: v%d.%d.%d\n",
                       info.firmware_version[0],
                       info.firmware_version[1],
                       info.firmware_version[2]);
                printf("  Name: %s\n", info.firmware_name);
                printf("  MCU Type: %d\n", info.mcu_type);
                printf("  Flash: %d KB\n", info.flash_size);
            } else {
                printf("✗ Failed to read ESC info\n");
            }

            // Try to read settings
            printf("\nReading ESC settings...\n");
            am32_config_t config = {0};
            if (am32_read_settings(&config)) {
                printf("✓ ESC Settings received:\n");
                printf("  Motor Poles: %d (pole pairs: %d)\n",
                       config.motor_poles, config.motor_poles / 2);
                printf("  Direction: %d (0=normal, 1=reversed)\n", config.motor_direction);
                printf("  Current Limit: %dA\n", config.current_limit);
                printf("  Temp Limit: %d°C\n", config.temperature_limit);
                printf("  Brake on Stop: %s\n", config.brake_on_stop ? "Yes" : "No");
                printf("  Bidirectional: %s\n", config.bidirectional ? "Yes" : "No");
                printf("  Telemetry: %s\n", config.telemetry ? "Yes" : "No");
                printf("  Startup Power: %d\n", config.startup_power);
            } else {
                printf("✗ Failed to read ESC settings\n");
            }

            printf("\nExiting config mode...\n");
            am32_exit_config_mode();
            printf("✓ Exited config mode\n");

        } else {
            printf("✗ FAILED: Cannot enter config mode\n");
            printf("  Possible causes:\n");
            printf("  - ESC not powered (check battery)\n");
            printf("  - Wrong wire on GP4/S pad\n");
            printf("  - ESC doesn't support AM32 protocol\n");
            printf("  - UART not working on GP4\n");
        }

        sleep_ms(500);

        // ========================================
        // TEST 2: DShot Signal Generation
        // ========================================
        printf("\n\n=== TEST 2: DShot Signal Generation ===\n");
        printf("Initializing DShot300 on GP%d...\n", ESC_PIN);

        dshot_config_t dshot_config = {
            .gpio_pin = ESC_PIN,
            .speed = DSHOT_SPEED_300,
            .bidirectional = true,
            .pole_pairs = 7  // 14 poles
        };

        if (dshot_init(MOTOR_WEAPON, &dshot_config)) {
            printf("✓ DShot initialized successfully\n");

            printf("\nSending DShot test sequence...\n");
            printf("(Motor should beep/spin if connected and configured)\n\n");

            // Send stop command
            printf("1. Sending STOP (throttle=0)...\n");
            dshot_send_throttle(MOTOR_WEAPON, 0, false);
            sleep_ms(1000);

            // Send low throttle
            printf("2. Sending LOW throttle (throttle=100)...\n");
            dshot_send_throttle(MOTOR_WEAPON, 100, false);
            sleep_ms(2000);

            // Send medium throttle
            printf("3. Sending MEDIUM throttle (throttle=500)...\n");
            dshot_send_throttle(MOTOR_WEAPON, 500, false);
            sleep_ms(2000);

            // Send high throttle
            printf("4. Sending HIGH throttle (throttle=1000)...\n");
            dshot_send_throttle(MOTOR_WEAPON, 1000, false);
            sleep_ms(2000);

            // Send stop command
            printf("5. Sending STOP (throttle=0)...\n");
            dshot_send_throttle(MOTOR_WEAPON, 0, false);
            sleep_ms(1000);

            printf("\n✓ DShot test sequence complete\n");

            // Test with telemetry request
            printf("\n6. Testing DShot with telemetry request...\n");
            for (int i = 0; i < 10; i++) {
                dshot_send_throttle(MOTOR_WEAPON, 0, true);  // Request telemetry
                sleep_ms(100);
            }
            printf("✓ Telemetry requests sent\n");

            dshot_deinit(MOTOR_WEAPON);
            printf("\n✓ DShot deinitialized\n");

        } else {
            printf("✗ FAILED: DShot initialization failed\n");
            printf("  Check PIO/DMA resources\n");
        }

        printf("\n\n========================================\n");
        printf("  Test #%d Complete\n", test_count);
        printf("========================================\n");
    }

    return 0;
}
