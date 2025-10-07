// ThumbsUp Robot Bluepad32 Platform Implementation
// Adapted from pico_controller my_platform.c

#include <stddef.h>
#include <string.h>
#include <stdlib.h>

#include <pico/cyw43_arch.h>
#include <pico/time.h>
#include <hardware/watchdog.h>
#include <uni.h>

#include "sdkconfig.h"
#include "config.h"
#include "motor_control.h"
#include "drive.h"
#include "weapon.h"
#include "safety.h"
#include "status.h"
#include "system_status.h"
#include "test_mode.h"

// Sanity check
#ifndef CONFIG_BLUEPAD32_PLATFORM_CUSTOM
#error "Pico W must use BLUEPAD32_PLATFORM_CUSTOM"
#endif

// Robot state tracking
static bool emergency_stop = false;
static bool armed_state = false;
static uint32_t last_controller_input = 0;
static uint32_t emergency_clear_start_time = 0;
static bool emergency_clear_in_progress = false;
static bool watchdog_enabled = false;

// Button debouncing
static uint16_t last_buttons = 0;
static uint32_t last_button_change_time = 0;
#define DEBOUNCE_TIME_MS 100  // Minimum time between button state changes

// Declarations
static void trigger_event_on_gamepad(uni_hid_device_t *d);

//
// Platform Overrides
//
static void my_platform_init(int argc, const char **argv) {
    ARG_UNUSED(argc);
    ARG_UNUSED(argv);

    logi("thumbsup_platform: init()\n");

    // Initialize test mode
    test_mode_init();

    // Initialize thumbsup subsystems
    motor_control_init();
    drive_init();
    weapon_init();
    status_init();
}

static void my_platform_on_init_complete(void) {
    logi("thumbsup_platform: on_init_complete()\n");

    // Safe to call "unsafe" functions since they are called from BT thread

    // Start scanning
    uni_bt_enable_new_connections_unsafe(true);

    // Based on runtime condition, you can delete or list the stored BT keys.
    if (1)
        uni_bt_del_keys_unsafe();
    else
        uni_bt_list_keys_unsafe();

    // Turn off LED once init is done.
    cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, 0);

    uni_property_dump_all();
}

static uni_error_t my_platform_on_device_discovered(bd_addr_t addr,
                                                    const char *name,
                                                    uint16_t cod,
                                                    uint8_t rssi) {
    // Filter out keyboards
    if (((cod & UNI_BT_COD_MINOR_MASK) & UNI_BT_COD_MINOR_KEYBOARD) ==
        UNI_BT_COD_MINOR_KEYBOARD) {
        logi("Ignoring keyboard\n");
        return UNI_ERROR_IGNORE_DEVICE;
    }

    return UNI_ERROR_SUCCESS;
}

static void my_platform_on_device_connected(uni_hid_device_t *d) {
    logi("thumbsup_platform: device connected: %p\n", d);
    // Device connected - update status
}

static void my_platform_on_device_disconnected(uni_hid_device_t *d) {
    logi("thumbsup_platform: device disconnected: %p\n", d);

    // Safety: Stop all motors and disarm weapon on disconnect
    drive_control_t stop_cmd = { .forward = 0, .turn = 0, .enabled = false };
    drive_update(&stop_cmd);
    weapon_disarm();
    armed_state = false;
    emergency_stop = true;
}

static uni_error_t my_platform_on_device_ready(uni_hid_device_t *d) {
    logi("thumbsup_platform: device ready: %p\n", d);

    // Reset emergency stop when controller connects
    emergency_stop = false;

    // Enable watchdog on first controller connection
    if (!watchdog_enabled) {
        logi("First controller connected - enabling watchdog timer\n");
        watchdog_enable(1000, 1);  // 1 second timeout, pause on debug
        watchdog_enabled = true;
    }

    return UNI_ERROR_SUCCESS;
}

static void my_platform_on_controller_data(uni_hid_device_t *d,
                                           uni_controller_t *ctl) {
    static uni_controller_t prev = {0};
    static uint32_t last_watchdog_feed = 0;
    uni_gamepad_t *gp;

    // Update timestamp
    last_controller_input = to_ms_since_boot(get_absolute_time());

    // Feed watchdog periodically (every 500ms) - only if enabled
    if (watchdog_enabled && (last_controller_input - last_watchdog_feed > 500)) {
        watchdog_update();
        last_watchdog_feed = last_controller_input;
    }

    // Used to prevent spamming the log, but should be removed in production.
    if (memcmp(&prev, ctl, sizeof(*ctl)) == 0) {
        return;
    }
    prev = *ctl;

    switch (ctl->klass) {
    case UNI_CONTROLLER_CLASS_GAMEPAD:
        gp = &ctl->gamepad;

        // Check for test mode activation first
        test_mode_check_activation(gp);

        // If in test mode, just update the display and return
        if (test_mode_is_active()) {
            test_mode_update(gp);
            return;
        }

        // Emergency stop (Both shoulder buttons pressed)
        if ((gp->buttons & (BTN_L1 | BTN_R1)) ==
            (BTN_L1 | BTN_R1)) {
            emergency_stop = true;
            armed_state = false;
            drive_control_t stop_cmd = { .forward = 0, .turn = 0, .enabled = false };
            drive_update(&stop_cmd);
            weapon_disarm();
            logi("EMERGENCY STOP TRIGGERED\n");
            break;
        }

        // SAFETY: Clear emergency stop only after holding A button for required time
        if (gp->buttons & BTN_A) {
            if (!emergency_clear_in_progress) {
                emergency_clear_start_time = to_ms_since_boot(get_absolute_time());
                emergency_clear_in_progress = true;
                logi("Hold A button for %dms to clear emergency stop\n", SAFETY_BUTTON_HOLD_TIME);
            } else {
                uint32_t hold_time = to_ms_since_boot(get_absolute_time()) - emergency_clear_start_time;
                if (hold_time >= SAFETY_BUTTON_HOLD_TIME) {
                    emergency_stop = false;
                    emergency_clear_in_progress = false;
                    logi("Emergency stop cleared after %ums hold\n", hold_time);
                }
            }
        } else {
            // Reset if button released before hold time met
            if (emergency_clear_in_progress) {
                emergency_clear_in_progress = false;
                logi("Emergency stop clear cancelled - button released\n");
            }
        }

        // Weapon arm/disarm with B button (only if not emergency stopped)
        // Only trigger on button press transition (not while held)
        uint32_t current_time = to_ms_since_boot(get_absolute_time());
        bool b_pressed = (gp->buttons & BTN_B) && !(last_buttons & BTN_B);

        if (!emergency_stop && b_pressed) {
            // Check debounce timing
            if (current_time - last_button_change_time > DEBOUNCE_TIME_MS) {
                armed_state = !armed_state;
                if (armed_state) {
                    weapon_arm();
                    logi("Weapon ARMED\n");
                } else {
                    weapon_disarm();
                    logi("Weapon DISARMED\n");
                }
                last_button_change_time = current_time;
            }
        }

        // Only process movement if not emergency stopped
        if (!emergency_stop) {
            // Drive control using left stick with proper deadzone handling
            int32_t raw_forward = -gp->axis_y; // Invert Y for forward
            int32_t raw_turn = gp->axis_x;

            // SAFETY: Validate input ranges from controller
            raw_forward = CLAMP(raw_forward, -512, 511);
            raw_turn = CLAMP(raw_turn, -512, 511);

            // Apply deadzone with proper scaling (use configured deadzone from config.h)
            int32_t forward = 0, turn = 0;

            if (abs(raw_forward) > STICK_DEADZONE) {
                // Scale deadzone-adjusted input to full range
                if (raw_forward > 0) {
                    forward = ((raw_forward - STICK_DEADZONE) * 511) / (511 - STICK_DEADZONE);
                } else {
                    forward = ((raw_forward + STICK_DEADZONE) * 512) / (512 - STICK_DEADZONE);
                }
            }
            if (abs(raw_turn) > STICK_DEADZONE) {
                if (raw_turn > 0) {
                    turn = ((raw_turn - STICK_DEADZONE) * 511) / (511 - STICK_DEADZONE);
                } else {
                    turn = ((raw_turn + STICK_DEADZONE) * 512) / (512 - STICK_DEADZONE);
                }
            }

            // Scale to -127/127 with overflow protection
            if (forward != 0) {
                forward = CLAMP((forward * 127) / 512, -127, 127);
            }
            if (turn != 0) {
                turn = CLAMP((turn * 127) / 512, -127, 127);
            }

            drive_control_t drive_cmd = {
                .forward = forward,
                .turn = turn,
                .enabled = true
            };
            drive_update(&drive_cmd);

            // Weapon control with right stick Y-axis (only if armed)
            if (armed_state) {
                int32_t raw_weapon = gp->axis_ry;

                // SAFETY: Validate weapon input range
                raw_weapon = CLAMP(raw_weapon, -512, 511);

                // Apply deadzone for weapon control with proper scaling
                int32_t weapon_speed = 0;
                if (raw_weapon > TRIGGER_THRESHOLD) {
                    // Scale deadzone-adjusted input (safety: only positive values)
                    weapon_speed = ((raw_weapon - TRIGGER_THRESHOLD) * 100) / (511 - TRIGGER_THRESHOLD);
                    weapon_speed = CLAMP(weapon_speed, 0, 100);
                }
                // SAFETY: Negative values are explicitly ignored for weapon control

                weapon_set_speed(weapon_speed);
            } else {
                // SAFETY: Ensure weapon is stopped when not armed
                weapon_set_speed(0);
            }
        }

        // Update last button state for next frame
        last_buttons = gp->buttons;

        // CRITICAL: Update motor PWM outputs and weapon ramping
        motor_control_update();
        weapon_update();

        break;

    case UNI_CONTROLLER_CLASS_BALANCE_BOARD:
        // Do something
        uni_balance_board_dump(&ctl->balance_board);
        break;

    case UNI_CONTROLLER_CLASS_MOUSE:
        // Do something
        uni_mouse_dump(&ctl->mouse);
        break;

    case UNI_CONTROLLER_CLASS_KEYBOARD:
        // Do something
        uni_keyboard_dump(&ctl->keyboard);
        break;

    default:
        loge("Unsupported controller class: %d\n", ctl->klass);
        break;
    }
}

static const uni_property_t *my_platform_get_property(uni_property_idx_t idx) {
    ARG_UNUSED(idx);
    return NULL;
}

static void my_platform_on_oob_event(uni_platform_oob_event_t event,
                                     void *data) {
    switch (event) {
    case UNI_PLATFORM_OOB_GAMEPAD_SYSTEM_BUTTON:
        // Optional: do something when "system" button gets pressed.
        trigger_event_on_gamepad((uni_hid_device_t *)data);
        break;

    case UNI_PLATFORM_OOB_BLUETOOTH_ENABLED:
        // When the "bt scanning" is on / off. Could be triggered by different
        // events Useful to notify the user
        logi("thumbsup_platform_on_oob_event: Bluetooth enabled: %d\n", (bool)(data));
        break;

    default:
        logi("thumbsup_platform_on_oob_event: unsupported event: 0x%04x\n", event);
    }
}

//
// Helpers
//
static void trigger_event_on_gamepad(uni_hid_device_t *d) {
    if (d->report_parser.play_dual_rumble != NULL) {
        d->report_parser.play_dual_rumble(
            d, 0 /* delayed start ms */, 50 /* duration ms */,
            128 /* weak magnitude */, 40 /* strong magnitude */);
    }

    if (d->report_parser.set_player_leds != NULL) {
        static uint8_t led = 0;
        led += 1;
        led &= 0xf;
        d->report_parser.set_player_leds(d, led);
    }

    if (d->report_parser.set_lightbar_color != NULL) {
        static uint8_t red = 0x10;
        static uint8_t green = 0x20;
        static uint8_t blue = 0x40;

        red += 0x10;
        green -= 0x20;
        blue += 0x40;
        d->report_parser.set_lightbar_color(d, red, green, blue);
    }
}

// Function to check for failsafe conditions
bool bluetooth_platform_failsafe_active(void) {
    uint32_t current_time = to_ms_since_boot(get_absolute_time());
    return emergency_stop || (current_time - last_controller_input > FAILSAFE_TIMEOUT);
}

bool bluetooth_platform_is_armed(void) {
    return armed_state && !bluetooth_platform_failsafe_active();
}

// System status interface implementations
bool system_failsafe_active(void) {
    return bluetooth_platform_failsafe_active();
}

bool system_is_armed(void) {
    return bluetooth_platform_is_armed();
}

void system_set_armed(bool armed) {
    armed_state = armed;
}

void system_set_failsafe(bool active) {
    emergency_stop = active;
}

//
// Entry Point
//
struct uni_platform *get_my_platform(void) {
    static struct uni_platform plat = {
        .name = "ThumbsUp Robot Platform",
        .init = my_platform_init,
        .on_init_complete = my_platform_on_init_complete,
        .on_device_discovered = my_platform_on_device_discovered,
        .on_device_connected = my_platform_on_device_connected,
        .on_device_disconnected = my_platform_on_device_disconnected,
        .on_device_ready = my_platform_on_device_ready,
        .on_oob_event = my_platform_on_oob_event,
        .on_controller_data = my_platform_on_controller_data,
        .get_property = my_platform_get_property,
    };

    return &plat;
}