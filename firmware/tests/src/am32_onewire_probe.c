#include <stdio.h>
#include <string.h>
#include <pico/stdlib.h>
#include "hardware/gpio.h"
#include "config.h"
#include "am32_config.h"
#include "motor_control.h"

#define ESC_PIN PIN_WEAPON_PWM

// Minimal stub for am32_config dependency.
bool motor_control_set_pulse(motor_channel_t channel, uint16_t pulse_us) {
    (void)channel;
    (void)pulse_us;
    return true;
}

int main() {
    stdio_init_all();
    sleep_ms(2000);

    printf("\n========================================\n");
    printf("  AM32 One-Wire Config Probe\n");
    printf("========================================\n\n");
    printf("Signal: GP%d (one-wire), GND required\n", ESC_PIN);
    printf("Ensure ESC is powered and motor is safe.\n\n");

    gpio_init(ESC_PIN);
    gpio_set_function(ESC_PIN, GPIO_FUNC_SIO);
    gpio_set_dir(ESC_PIN, GPIO_OUT);
    gpio_put(ESC_PIN, 0);

    if (!am32_init()) {
        printf("FAIL: am32_init\n");
        while (1) {
            sleep_ms(1000);
        }
    }

    uint32_t cycle = 1;
    while (true) {
        printf("\n=== Probe %lu ===\n", cycle++);
        printf("Entering config mode...\n");
        if (!am32_enter_config_mode()) {
            printf("FAIL: am32_enter_config_mode\n");
            sleep_ms(3000);
            continue;
        }
        printf("OK: config mode\n\n");
        printf("Line idle: %s\n\n", gpio_get(ESC_PIN) ? "HIGH" : "LOW");

        am32_info_t info = {0};
        uint8_t info_buf[64] = {0};
        uint16_t info_len = sizeof(info_buf);
        if (am32_send_command(AM32_CMD_GET_INFO, NULL, 0) &&
            am32_receive_response(info_buf, &info_len, 300)) {
            if (info_len >= 3) {
                info.firmware_version[0] = info_buf[0];
                info.firmware_version[1] = info_buf[1];
                info.firmware_version[2] = info_buf[2];
                uint8_t name_len = (info_len - 3) < 16 ? (info_len - 3) : 15;
                memcpy(info.firmware_name, &info_buf[3], name_len);
                info.firmware_name[name_len] = '\0';
            }
            printf("ESC Info:\n");
            printf("  Firmware: v%d.%d.%d\n",
                   info.firmware_version[0],
                   info.firmware_version[1],
                   info.firmware_version[2]);
            printf("  Name: %s\n", info.firmware_name);
        } else {
            printf("FAIL: get_info (len=%u)\n", info_len);
        }

        uint8_t settings[256] = {0};
        uint16_t settings_len = sizeof(settings);
        if (am32_send_command(AM32_CMD_GET_SETTINGS, NULL, 0) &&
            am32_receive_response(settings, &settings_len, 400)) {
            printf("\nESC Settings (len=%u):\n", settings_len);
            printf("  Motor poles: %u\n", settings[AM32_ADDR_MOTOR_POLES]);
            printf("  Direction: %u (0=normal,1=reversed)\n", settings[AM32_ADDR_MOTOR_DIRECTION]);
            printf("  Bidirectional: %u\n", settings[AM32_ADDR_BIDIRECTIONAL]);
            printf("  Brake on stop: %u\n", settings[AM32_ADDR_BRAKE_ON_STOP]);
            printf("  PWM freq: %u kHz\n", settings[AM32_ADDR_PWM_FREQUENCY]);
            uint16_t throttle_min = settings[AM32_ADDR_THROTTLE_MIN] |
                                    (settings[AM32_ADDR_THROTTLE_MIN + 1] << 8);
            uint16_t throttle_max = settings[AM32_ADDR_THROTTLE_MAX] |
                                    (settings[AM32_ADDR_THROTTLE_MAX + 1] << 8);
            printf("  Throttle min/max: %u / %u\n", throttle_min, throttle_max);
            printf("  Startup power: %u\n", settings[AM32_ADDR_STARTUP_POWER]);
            printf("  Telemetry: %u\n", settings[AM32_ADDR_TELEMETRY]);
        } else {
            printf("FAIL: get_settings (len=%u)\n", settings_len);
        }

        printf("\nExiting config mode...\n");
        am32_exit_config_mode();
        printf("Done. Waiting 3s...\n");

        sleep_ms(3000);
    }
}
