#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <btstack_run_loop.h>
#include <pico/cyw43_arch.h>
#include <pico/stdlib.h>
#include <hardware/gpio.h>
#include <hardware/adc.h>
#include <hardware/watchdog.h>
#include <uni.h>

#include "sdkconfig.h"
#include "config.h"
#include "motor_control.h"
#include "drive.h"
#include "weapon.h"
#include "safety.h"
#include "status.h"
#include "am32_config.h"
#include "safety_test.h"

// Sanity check
#ifndef CONFIG_BLUEPAD32_PLATFORM_CUSTOM
#error "Pico W must use BLUEPAD32_PLATFORM_CUSTOM"
#endif

// Defined in bluetooth_platform.c
struct uni_platform* get_my_platform(void);

// Robot state is now managed in bluetooth_platform.c

static void init_hardware(void) {
    stdio_init_all();

    adc_init();
    adc_gpio_init(PIN_BATTERY_ADC);
    adc_select_input(0);

    gpio_init(PIN_LED_STATUS);
    gpio_set_dir(PIN_LED_STATUS, GPIO_OUT);
    gpio_init(PIN_LED_ARMED);
    gpio_set_dir(PIN_LED_ARMED, GPIO_OUT);
    gpio_init(PIN_LED_BATTERY);
    gpio_set_dir(PIN_LED_BATTERY, GPIO_OUT);

    gpio_init(PIN_SAFETY_BUTTON);
    gpio_set_dir(PIN_SAFETY_BUTTON, GPIO_IN);
    gpio_pull_up(PIN_SAFETY_BUTTON);

    printf("\n=================================\n");
    printf("  %s Combat Robot\n", ROBOT_NAME);
    printf("  Firmware v%s\n", FIRMWARE_VERSION);
    printf("=================================\n\n");

    // Check for diagnostic mode entry
    printf("Hold safety button for diagnostic mode...\n");
}

uint32_t read_battery_voltage(void) {
    uint16_t adc_raw = adc_read();

    // SAFETY: Validate ADC reading and prevent overflow
    if (adc_raw > 4095) {
        DEBUG_PRINT("WARNING: Invalid ADC reading %u\n", adc_raw);
        adc_raw = 4095;
    }

    // Use double precision to prevent intermediate overflow
    double voltage = ((double)adc_raw * BATTERY_ADC_SCALE / 4095.0) * BATTERY_DIVIDER * 1000.0;

    // SAFETY: Clamp result to reasonable range before converting to int
    if (voltage < 0.0) voltage = 0.0;
    if (voltage > 20000.0) voltage = 20000.0; // Max 20V for safety

    return (uint32_t)voltage;
}

// Battery monitoring and status functions moved to bluetooth_platform.c

static void check_config_mode_entry(void) {
    // Enter config mode if safety button held during boot
    if (!gpio_get(PIN_SAFETY_BUTTON)) {
        printf("\n=================================\n");
        printf("  AM32 Configuration Mode\n");
        printf("=================================\n\n");

        am32_init();

        printf("Options:\n");
        printf("1. Press 'C' to configure ESC\n");
        printf("2. Press 'P' for passthrough mode\n");
        printf("3. Press 'T' for throttle calibration\n");
        printf("4. Press 'D' to apply defaults\n");
        printf("5. Press any other key to exit\n\n");

        int c = getchar();

        switch (c) {
            case 'C':
            case 'c': {
                printf("Configuring AM32 ESC with weapon defaults...\n");
                am32_config_t config;
                am32_apply_weapon_defaults(&config);

                if (am32_enter_config_mode()) {
                    if (am32_write_settings(&config)) {
                        am32_save_settings();
                        printf("Configuration complete!\n");
                    } else {
                        printf("Configuration failed!\n");
                    }
                    am32_exit_config_mode();
                }
                break;
            }

            case 'P':
            case 'p':
                printf("Entering passthrough mode (ESC to exit)...\n");
                am32_passthrough_mode();
                break;

            case 'T':
            case 't':
                printf("Starting throttle calibration...\n");
                if (am32_enter_config_mode()) {
                    am32_calibrate_throttle();
                    am32_exit_config_mode();
                }
                break;

            case 'D':
            case 'd': {
                printf("Applying default weapon settings...\n");
                am32_config_t default_config;
                am32_apply_weapon_defaults(&default_config);
                if (am32_enter_config_mode()) {
                    am32_write_settings(&default_config);
                    am32_save_settings();
                    am32_exit_config_mode();
                }
                printf("Defaults applied!\n");
                break;
            }

            default:
                printf("Exiting config mode...\n");
                break;
        }

        printf("\nContinuing to normal operation...\n\n");
        sleep_ms(1000);
    }
}

int main() {
    init_hardware();

    // initialize CYW43 driver architecture (will enable BT if/because CYW43_ENABLE_BLUETOOTH == 1)
    if (cyw43_arch_init()) {
        loge("failed to initialise cyw43_arch\n");
        return -1;
    }

    // Turn-on LED. Turn it off once init is done.
    cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, 1);

    // Check if we should enter AM32 config mode
    check_config_mode_entry();

    // Initialize AM32 config
    am32_init();

    // SAFETY: Run comprehensive safety tests
    printf("Running safety validation tests...\n");
    if (!run_safety_tests()) {
        printf("\n*** CRITICAL SAFETY FAILURE ***\n");
        printf("Robot safety tests failed!\n");
        printf("DO NOT OPERATE - SYSTEM UNSAFE\n");
        printf("*******************************\n\n");

        // Flash all LEDs rapidly to indicate unsafe condition
        while (true) {
            status_set_all_leds(STATUS_LED_BLINK_FAST);
            status_update();
            sleep_ms(100);
        }
    }
    printf("Safety tests passed - system ready\n");

    // Must be called before uni_init()
    uni_platform_set_custom(get_my_platform());

    // Initialize BP32
    uni_init(0, NULL);

    printf("ThumbsUp robot initialized. Starting Bluepad32...\n");

    // Enable watchdog with 1 second timeout
    // The BTstack run loop will be modified to feed it
    watchdog_enable(1000, true);
    printf("Watchdog enabled (1s timeout)\n");

    // Does not return - BTstack takes over
    btstack_run_loop_execute();

    return 0;
}