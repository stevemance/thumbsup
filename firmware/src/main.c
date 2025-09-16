#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "pico/stdlib.h"
#include "pico/cyw43_arch.h"
#include "hardware/gpio.h"
#include "hardware/adc.h"
#include "hardware/watchdog.h"

#include "config.h"
#include "bluetooth.h"
#include "motor_control.h"
#include "drive.h"
#include "weapon.h"
#include "safety.h"
#include "status.h"
#include "am32_config.h"

typedef struct {
    bool connected;
    bool armed;
    bool failsafe_active;
    uint32_t last_packet_time;
    uint32_t battery_voltage_mv;
    int8_t drive_trim_forward;
    int8_t drive_trim_turn;
} robot_state_t;

static robot_state_t robot_state = {
    .connected = false,
    .armed = false,
    .failsafe_active = false,
    .last_packet_time = 0,
    .battery_voltage_mv = 11100,
    .drive_trim_forward = 0,
    .drive_trim_turn = 0
};

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
}

static uint32_t read_battery_voltage(void) {
    uint16_t adc_raw = adc_read();
    float voltage = (adc_raw * BATTERY_ADC_SCALE / 4095.0f) * BATTERY_DIVIDER * 1000.0f;
    return (uint32_t)voltage;
}

static void check_failsafe(void) {
    uint32_t current_time = to_ms_since_boot(get_absolute_time());

    if (robot_state.connected &&
        (current_time - robot_state.last_packet_time) > FAILSAFE_TIMEOUT) {
        robot_state.failsafe_active = true;
        robot_state.armed = false;

        motor_control_stop_all();
        weapon_disarm();

        DEBUG_PRINT("FAILSAFE: Connection lost!\n");
    }
}

static void process_gamepad_input(gamepad_state_t* gamepad) {
    if (!gamepad || !gamepad->connected) {
        robot_state.connected = false;
        return;
    }

    robot_state.connected = true;
    robot_state.last_packet_time = to_ms_since_boot(get_absolute_time());
    robot_state.failsafe_active = false;

    bool arm_combo = (gamepad->buttons & BUTTON_X) && (gamepad->buttons & BUTTON_Y);
    bool disarm_combo = (gamepad->buttons & BUTTON_L1) && (gamepad->buttons & BUTTON_R1);

    if (disarm_combo) {
        robot_state.armed = false;
        weapon_disarm();
        DEBUG_PRINT("Emergency disarm activated\n");
    } else if (arm_combo && !robot_state.armed) {
        if (safety_check_arm_conditions(robot_state.battery_voltage_mv)) {
            robot_state.armed = true;
            weapon_arm();
            DEBUG_PRINT("Weapon armed\n");
        }
    }

    if (gamepad->dpad_up) {
        robot_state.drive_trim_forward = MIN(robot_state.drive_trim_forward + TRIM_STEP, TRIM_MAX);
    } else if (gamepad->dpad_down) {
        robot_state.drive_trim_forward = MAX(robot_state.drive_trim_forward - TRIM_STEP, TRIM_MIN);
    }
    if (gamepad->dpad_left) {
        robot_state.drive_trim_turn = MIN(robot_state.drive_trim_turn + TRIM_STEP, TRIM_MAX);
    } else if (gamepad->dpad_right) {
        robot_state.drive_trim_turn = MAX(robot_state.drive_trim_turn - TRIM_STEP, TRIM_MIN);
    }

    int8_t forward = gamepad->left_stick_y + robot_state.drive_trim_forward;
    int8_t turn = gamepad->left_stick_x + robot_state.drive_trim_turn;
    forward = CLAMP(forward, MIN_GAMEPAD_AXIS, MAX_GAMEPAD_AXIS);
    turn = CLAMP(turn, MIN_GAMEPAD_AXIS, MAX_GAMEPAD_AXIS);

    drive_control_t drive_cmd = {
        .forward = forward,
        .turn = turn,
        .enabled = !robot_state.failsafe_active
    };
    drive_update(&drive_cmd);

    if (robot_state.armed && !robot_state.failsafe_active) {
        uint8_t weapon_speed = 0;
        if (gamepad->right_trigger > TRIGGER_THRESHOLD) {
            weapon_speed = (gamepad->right_trigger * MAX_WEAPON_SPEED) / 255;
        }
        weapon_set_speed(weapon_speed);
    } else {
        weapon_set_speed(0);
    }
}

static void update_status_leds(void) {
    static uint32_t last_blink = 0;
    static bool blink_state = false;
    uint32_t current_time = to_ms_since_boot(get_absolute_time());

    uint32_t blink_rate = LED_BLINK_SLOW;
    if (robot_state.failsafe_active) {
        blink_rate = LED_BLINK_FAST;
    } else if (robot_state.connected) {
        blink_rate = LED_BLINK_MEDIUM;
    }

    if (current_time - last_blink > blink_rate) {
        blink_state = !blink_state;
        last_blink = current_time;
    }

    gpio_put(PIN_LED_STATUS, robot_state.connected && !robot_state.failsafe_active);

    gpio_put(PIN_LED_ARMED, robot_state.armed ? blink_state : false);

    if (robot_state.battery_voltage_mv < BATTERY_CRITICAL) {
        gpio_put(PIN_LED_BATTERY, blink_state);
    } else if (robot_state.battery_voltage_mv < BATTERY_LOW_VOLTAGE) {
        gpio_put(PIN_LED_BATTERY, true);
    } else {
        gpio_put(PIN_LED_BATTERY, false);
    }
}

#ifdef DEBUG_MODE
static void debug_output(gamepad_state_t* gamepad) {
    static uint32_t last_debug = 0;
    uint32_t current_time = to_ms_since_boot(get_absolute_time());

    if (current_time - last_debug > DEBUG_UPDATE_RATE) {
        printf("\r[STATUS] ");
        printf("Conn:%s ", robot_state.connected ? "YES" : "NO ");
        printf("Armed:%s ", robot_state.armed ? "YES" : "NO ");
        printf("Batt:%.1fV ", robot_state.battery_voltage_mv / 1000.0f);

        if (gamepad && gamepad->connected) {
            printf("LX:%4d LY:%4d RT:%3d ",
                   gamepad->left_stick_x,
                   gamepad->left_stick_y,
                   gamepad->right_trigger);
        }

        printf("     ");
        fflush(stdout);
        last_debug = current_time;
    }
}
#endif

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
            case 'd':
                printf("Applying default weapon settings...\n");
                am32_config_t config;
                am32_apply_weapon_defaults(&config);
                if (am32_enter_config_mode()) {
                    am32_write_settings(&config);
                    am32_save_settings();
                    am32_exit_config_mode();
                }
                printf("Defaults applied!\n");
                break;

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

    if (cyw43_arch_init()) {
        printf("Failed to initialize WiFi/Bluetooth\n");
        return -1;
    }

    // Check if we should enter AM32 config mode
    check_config_mode_entry();

    motor_control_init();
    drive_init();
    weapon_init();
    status_init();
    bluetooth_init();
    am32_init();

    printf("System initialized. Starting main loop...\n");

    gamepad_state_t gamepad = {0};
    uint32_t battery_check_time = 0;

    while (true) {
        uint32_t current_time = to_ms_since_boot(get_absolute_time());

        if (current_time - battery_check_time > 1000) {
            robot_state.battery_voltage_mv = read_battery_voltage();
            battery_check_time = current_time;

            if (robot_state.battery_voltage_mv < BATTERY_CRITICAL) {
                robot_state.armed = false;
                weapon_disarm();
                DEBUG_PRINT("Critical battery! Disarming weapon.\n");
            }
        }

        bluetooth_update(&gamepad);

        check_failsafe();

        process_gamepad_input(&gamepad);

        motor_control_update();

        update_status_leds();

        #ifdef DEBUG_MODE
        debug_output(&gamepad);
        #endif

        if (watchdog_caused_reboot()) {
            printf("System recovered from watchdog reset\n");
        }
        watchdog_update();

        sleep_ms(MAIN_LOOP_DELAY);
    }

    return 0;
}