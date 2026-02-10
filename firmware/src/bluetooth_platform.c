// ThumbsUp Robot Bluepad32 Platform Implementation
// Adapted from pico_controller my_platform.c

#include <stddef.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>

#include <pico/time.h>
#include <hardware/watchdog.h>
#if !SERIAL_GAMEPAD
#include <pico/cyw43_arch.h>
#include <btstack.h>
#include <btstack_run_loop.h>
#include <uni.h>
#include "sdkconfig.h"
#else
#include <controller/uni_gamepad.h>
#endif
#include "config.h"
#include "motor_control.h"
#include "drive.h"
#include "weapon.h"
#include "safety.h"
#include "status.h"
#include "system_status.h"
#include "test_mode.h"
#include "trim_mode.h"
#include "calibration_mode.h"
#include "motor_linearization.h"
#include "hitl_console.h"

#if SERIAL_GAMEPAD
#undef logi
#undef loge
#define logi(...) ((void)0)
#define loge(...) ((void)0)
#endif

// Sanity check
#if !SERIAL_GAMEPAD
#ifndef CONFIG_BLUEPAD32_PLATFORM_CUSTOM
#error "Pico W must use BLUEPAD32_PLATFORM_CUSTOM"
#endif
#endif

#if !SERIAL_GAMEPAD
// Active BT connection handle (for potential future per-link tuning)
static hci_con_handle_t active_con_handle = HCI_CON_HANDLE_INVALID;
#endif

// Robot state tracking
static bool emergency_stop = false;
static bool armed_state = false;
static uint32_t last_controller_input = 0;
static uint32_t emergency_clear_start_time = 0;
static bool emergency_clear_in_progress = false;
static bool watchdog_enabled = false;
static uint32_t last_watchdog_feed = 0;

// Controller neutral guard
// Some controllers produce non-neutral axis values during pairing / initial reports.
// For safety, require a short stable "all sticks neutral" window before allowing
// any motor commands after a controller becomes ready.
static bool controller_neutral_guard_active = true;
static uint32_t controller_neutral_start_ms = 0;
static uint32_t controller_neutral_last_log_ms = 0;

// Button debouncing
static uint16_t last_buttons = 0;
static uint32_t last_button_change_time = 0;
#define DEBOUNCE_TIME_MS 100  // Minimum time between button state changes

// Previous controller state for edge detection (file-scope so disconnect can clear).
static uni_gamepad_t inject_prev = {0};
static bool inject_prev_valid = false;

// Declarations
#if !SERIAL_GAMEPAD
static uni_controller_t ctl_prev = {0};
static void trigger_event_on_gamepad(uni_hid_device_t *d);

// HITL support: keep printing status / processing commands even when there is no controller input.
static btstack_timer_source_t hitl_timer;
static uni_gamepad_t hitl_last_gp;
static bool hitl_last_gp_valid = false;

static void hitl_timer_handler(btstack_timer_source_t* ts) {
    // Fast keepalive tick:
    // - Keep DShot frames flowing even when there is no controller traffic.
    //   Some ESCs will start beeping if they don't see frequent DShot updates.
    //   We target WEAPON_DSHOT_UPDATE_MS (2ms) for robustness.
    motor_control_update();
    weapon_update();

    // Slow housekeeping tick (avoid expensive work at 500Hz).
    static uint32_t last_slow_ms = 0;
    uint32_t now_ms = to_ms_since_boot(get_absolute_time());
    if (last_slow_ms == 0 || (now_ms - last_slow_ms) >= 20) {
        hitl_console_on_gamepad(hitl_last_gp_valid ? &hitl_last_gp : NULL);
        status_update();
        safety_update();
        last_slow_ms = now_ms;
    }

    // Feed watchdog even when no controller data is arriving (e.g. controller
    // disconnect). This keeps the watchdog focused on detecting actual system
    // hangs, not RF/controller availability.
    if (watchdog_enabled) {
        uint32_t now_ms = to_ms_since_boot(get_absolute_time());
        if (now_ms - last_watchdog_feed > 500) {
            watchdog_update();
            last_watchdog_feed = now_ms;
        }
    }

    btstack_run_loop_set_timer(ts, 2);
    btstack_run_loop_add_timer(ts);
}
#endif

//
// Platform Overrides
//
#if !SERIAL_GAMEPAD
static void my_platform_init(int argc, const char **argv) {
    ARG_UNUSED(argc);
    ARG_UNUSED(argv);

    logi("thumbsup_platform: init()\n");

    // Initialize test mode
    test_mode_init();

    // Initialize trim mode
    trim_mode_init();
    calibration_mode_init();

    // Initialize thumbsup subsystems
    motor_control_init();
    motor_linearization_init();
    drive_init();
    weapon_init();
    status_init();

    hitl_console_init();

    hitl_last_gp_valid = false;
    memset(&hitl_last_gp, 0, sizeof(hitl_last_gp));
    hitl_timer.process = &hitl_timer_handler;
    btstack_run_loop_set_timer(&hitl_timer, 20);
    btstack_run_loop_add_timer(&hitl_timer);
}

static void my_platform_on_init_complete(void) {
    logi("thumbsup_platform: on_init_complete()\n");

    // Safe to call "unsafe" functions since they are called from BT thread

    // Start scanning (autoconnect) unless explicitly disabled.
    //
    // HITL runs with a controller emulator that initiates the connection to us.
    // If we also scan+autoconnect, we can race the incoming connect and hit
    // errors like "ACL Connection Already Exists" / L2CAP failures.
    //
    // Note: HID status/console output (HITL_CONSOLE) is orthogonal to scan/autoconnect.
#if HITL_NO_SCAN
    uni_bt_enable_new_connections_unsafe(false);
#else
    uni_bt_enable_new_connections_unsafe(true);
#endif

    // Based on runtime condition, you can delete or list the stored BT keys.
    // Keep stored keys so HITL pairing can be stable across reboots.
    // If you need to reset pairing, add an explicit action/command instead of
    // wiping keys on every boot.
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
    // Device connected - update status LED
    status_set_system(SYSTEM_STATUS_CONNECTED, LED_EFFECT_SOLID);
    hitl_console_set_controller_connected(true);
}

static void my_platform_on_device_disconnected(uni_hid_device_t *d) {
    logi("thumbsup_platform: device disconnected: %p\n", d);

    active_con_handle = HCI_CON_HANDLE_INVALID;

    // Safety: Stop all motors and disarm weapon on disconnect
    drive_control_t stop_cmd = { .forward = 0, .turn = 0, .enabled = false };
    drive_update(&stop_cmd);
    weapon_disarm();  // This also updates weapon LED status
    armed_state = false;
    emergency_stop = true;

    // CRITICAL: Ensure PWM outputs are driven to a safe state even if we never
    // receive another controller update after the disconnect callback.
    motor_control_stop_all();

    // Update system status LED
    status_set_system(SYSTEM_STATUS_FAILSAFE, LED_EFFECT_BLINK_FAST);

    hitl_console_set_controller_ready(false);
    hitl_console_set_controller_connected(false);

    hitl_last_gp_valid = false;
    memset(&hitl_last_gp, 0, sizeof(hitl_last_gp));

    controller_neutral_guard_active = true;
    controller_neutral_start_ms = 0;
    controller_neutral_last_log_ms = 0;

    // Reset button/controller edge-detection state so the next connection
    // starts clean and doesn't miss the first B-press transition.
    last_buttons = 0;
    last_button_change_time = 0;
    memset(&ctl_prev, 0, sizeof(ctl_prev));
    memset(&inject_prev, 0, sizeof(inject_prev));
    inject_prev_valid = false;
}

static uni_error_t my_platform_on_device_ready(uni_hid_device_t *d) {
    logi("thumbsup_platform: device ready: %p\n", d);

    // Reset emergency stop when controller connects
    emergency_stop = false;

    // Require a neutral-sticks window before allowing motion.
    controller_neutral_guard_active = true;
    controller_neutral_start_ms = 0;
    controller_neutral_last_log_ms = 0;

    // Reset button edge-detection state so the first B-press is always detected.
    last_buttons = 0;
    last_button_change_time = 0;

    // Enable watchdog on first controller connection
    if (!watchdog_enabled) {
        logi("First controller connected - enabling watchdog timer\n");
        watchdog_enable(1000, 1);  // 1 second timeout, pause on debug
        watchdog_enabled = true;
    }

    // Stop periodic inquiry once we have a working controller.
    // Periodic inquiry generates SPI traffic that contends with BT data on CYW43.
    // We only support one controller — no need to keep scanning.
    uni_bt_stop_scanning_unsafe();

    active_con_handle = d->conn.handle;

    hitl_console_set_controller_ready(true);
    return UNI_ERROR_SUCCESS;
}
#endif

static bool controller_axes_neutral(const uni_gamepad_t* gp) {
    if (!gp) {
        return true;
    }
    // Use the same raw-domain deadzones as the rest of the control code.
    return (abs(gp->axis_x)  <= STICK_DEADZONE) &&
           (abs(gp->axis_y)  <= STICK_DEADZONE) &&
           (abs(gp->axis_rx) <= STICK_DEADZONE) &&
           (abs(gp->axis_ry) <= STICK_DEADZONE);
}

static void note_controller_activity(void) {
    last_controller_input = to_ms_since_boot(get_absolute_time());

    // Feed watchdog periodically (every 500ms) - only if enabled
    if (watchdog_enabled && (last_controller_input - last_watchdog_feed > 500)) {
        watchdog_update();
        last_watchdog_feed = last_controller_input;
    }
}

static void process_gamepad_input(uni_gamepad_t* gp, bool state_changed) {
    // Check for mode activations BEFORE state-change handling to allow hold timers to work
    // Check for test mode activation first
    test_mode_check_activation(gp);

    // If in test mode, just update the display and return
    if (test_mode_is_active()) {
        test_mode_update(gp);
        return;
    }

    // Check for calibration mode activation
    calibration_mode_check_activation(gp);

    // If in calibration mode, step through motor test points
    if (calibration_mode_is_active()) {
        calibration_mode_update(gp);
        motor_control_update();  // Update motors with calibration commands
        return;  // Block all other inputs during calibration
    }

    // Check for trim mode activation
    trim_mode_check_activation(gp);

    // Handle exit feedback LED restoration
    trim_mode_handle_exit_feedback();

    // If in trim mode, handle calibration with full driving control
    if (trim_mode_is_active()) {
        // Update trim calibration (handles B button for removing samples)
        trim_mode_update(gp);

        // Keep weapon disarmed during trim mode
        if (armed_state) {
            weapon_disarm();
            armed_state = false;
        }

        // Allow full driving control in trim mode
        // Drive control using left stick with proper deadzone handling
        int32_t raw_forward = gp->axis_y; // Forward stick push is negative
        int32_t raw_turn = gp->axis_x;

        // Validate input ranges
        raw_forward = CLAMP(raw_forward, -512, 511);
        raw_turn = CLAMP(raw_turn, -512, 511);

        // Apply deadzone with proper scaling
        int32_t forward = 0, turn = 0;

        if (abs(raw_forward) > STICK_DEADZONE) {
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

        // Scale to -127/127 range
        if (forward != 0) {
            forward = CLAMP((forward * 127) / 512, -127, 127);
        }
        if (turn != 0) {
            turn = CLAMP((turn * 127) / 512, -127, 127);
        }

        // Convert to percentage for trim sample capture (-100 to +100)
        int8_t forward_percent = (int8_t)((forward * 100) / 127);
        int8_t turn_percent = (int8_t)((turn * 100) / 127);

        // Static variable for A button edge detection
        static bool button_a_prev = false;
        bool button_a = (gp->buttons & BTN_A) != 0;

        // Check for A button press (capture sample)
        if (button_a && !button_a_prev) {
            // Capture current forward speed and turn value as a sample
            trim_mode_capture_sample(forward_percent, turn_percent);
        }
        button_a_prev = button_a;

        // Send drive commands (no trim applied in trim mode)
        drive_control_t trim_cmd = {
            .forward = (int8_t)forward,
            .turn = (int8_t)turn,
            .enabled = true
        };
        drive_update(&trim_cmd);
        motor_control_update();
        return;
    }

    // Emergency stop (Both shoulder buttons pressed)
    if ((gp->buttons & (BTN_L1 | BTN_R1)) ==
        (BTN_L1 | BTN_R1)) {
        bool was_emergency_stop = emergency_stop;
        emergency_stop = true;
        armed_state = false;
        drive_control_t stop_cmd = { .forward = 0, .turn = 0, .enabled = false };
        drive_update(&stop_cmd);
        weapon_disarm();

        // CRITICAL: Ensure motor outputs are driven to a safe state even if the
        // user keeps holding the emergency stop buttons. Without this, we can
        // get stuck in this early-return path and never call motor_control_update(),
        // leaving PWM outputs at the last commanded value.
        motor_control_stop_all();

        if (!was_emergency_stop) {
            logi("EMERGENCY STOP TRIGGERED\n");
        }
        status_set_system(SYSTEM_STATUS_EMERGENCY, LED_EFFECT_BLINK_FAST);
        status_set_weapon(WEAPON_STATUS_EMERGENCY, LED_EFFECT_BLINK_FAST);
        last_buttons = gp->buttons;

        // Keep the rest of the system responsive / observable while e-stop is held.
        motor_control_update();
        weapon_update();
        safety_update();
        return;
    }

    // SAFETY: Clear emergency stop only after holding A button for required time
    // Only process if emergency stop is actually active
    if (emergency_stop && (gp->buttons & BTN_A)) {
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
                status_set_system(SYSTEM_STATUS_CONNECTED, LED_EFFECT_SOLID);
                status_set_weapon(WEAPON_STATUS_DISARMED, LED_EFFECT_SOLID);
            }
        }
    } else {
        // Reset if button released before hold time met
        if (emergency_clear_in_progress) {
            emergency_clear_in_progress = false;
            logi("Emergency stop clear cancelled - button released\n");
        }
    }

    // Startup neutral-axes guard.
    //
    // Keep outputs at a safe idle state until the controller reports a stable
    // neutral position for a short time. This prevents unexpected motion on
    // initial connect due to transient/non-zero axis values.
    if (controller_neutral_guard_active) {
        uint32_t now_ms = to_ms_since_boot(get_absolute_time());
        bool neutral = controller_axes_neutral(gp);
        if (neutral) {
            if (controller_neutral_start_ms == 0) {
                controller_neutral_start_ms = now_ms;
            } else if ((now_ms - controller_neutral_start_ms) >= 500) {
                controller_neutral_guard_active = false;
                controller_neutral_last_log_ms = now_ms;
                printf("SAFETY: Controller neutral guard cleared\n");
            }
        } else {
            controller_neutral_start_ms = 0;
            if (controller_neutral_last_log_ms == 0 ||
                (now_ms - controller_neutral_last_log_ms) >= 1000) {
                printf("SAFETY: Waiting for controller sticks to be neutral...\n");
                controller_neutral_last_log_ms = now_ms;
            }
        }

        // Hold all outputs in a safe idle state while the guard is active.
        drive_control_t stop_cmd = { .forward = 0, .turn = 0, .enabled = false };
        drive_update(&stop_cmd);
        weapon_set_speed(0);
        if (armed_state || weapon_is_armed()) {
            weapon_disarm();
            armed_state = false;
        }

        last_buttons = gp ? gp->buttons : 0;
        motor_control_update();
        weapon_update();
        safety_update();
        return;
    }

    // Now check if controller state changed - skip normal processing if unchanged.
    // Emergency-stop handling (including the hold-to-clear timer above) must run even
    // while inputs are held steady.
    if (!state_changed) {
        last_buttons = gp->buttons;
        motor_control_update();
        weapon_update();
        safety_update();
        return;
    }

    // Weapon arm/disarm with B button (only if not emergency stopped)
    // Only trigger on button press transition (not while held)
    uint32_t current_time = to_ms_since_boot(get_absolute_time());
    bool b_pressed = (gp->buttons & BTN_B) && !(last_buttons & BTN_B);

    if (!emergency_stop && b_pressed) {
        // Check debounce timing
        if (current_time - last_button_change_time > DEBOUNCE_TIME_MS) {
            if (!armed_state) {
                if (weapon_arm()) {
                    armed_state = true;
                    logi("Weapon ARMED\n");
                } else {
                    armed_state = false;
                    logi("Weapon arm rejected (safety)\n");
                }
            } else {
                weapon_disarm();
                armed_state = false;
                logi("Weapon DISARMED\n");
            }
            last_button_change_time = current_time;
        }
    }

    // Only process movement if not emergency stopped
    if (!emergency_stop) {
        // Drive control using left stick with proper deadzone handling
        int32_t raw_forward = gp->axis_y; // Forward stick push is negative
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

        // Sync armed_state with actual weapon state. weapon_update() can
        // internally trigger emergency_stop (safety check), which changes
        // weapon_state without clearing armed_state here.
        if (armed_state && !weapon_is_armed()) {
            armed_state = false;
            logi("Weapon state desync: cleared armed_state\n");
        }

        // Weapon control with right stick Y-axis (only if armed)
        if (armed_state) {
            // Weapon speed can be commanded either by analog pedals (0-1023, forward only)
            // or by right-stick Y (signed: +Y = forward, -Y = reverse).
            // Pedals override stick only when their magnitude exceeds stick magnitude.

            // Signed stick mapping (-100..+100%).
            int32_t stick_speed = 0;
            int32_t raw_weapon = CLAMP(gp->axis_ry, -512, 511);
            if (abs(raw_weapon) > TRIGGER_THRESHOLD) {
                if (raw_weapon > 0) {
                    stick_speed = ((raw_weapon - TRIGGER_THRESHOLD) * 100) / (511 - TRIGGER_THRESHOLD);
                } else {
                    stick_speed = ((raw_weapon + TRIGGER_THRESHOLD) * 100) / (512 - TRIGGER_THRESHOLD);
                }
                stick_speed = CLAMP(stick_speed, -100, 100);
            }

            // Pedal mapping (0-100%, forward-only). We consider both throttle & brake and
            // take the max so whichever control is active wins.
            int32_t pedal_speed = 0;
            int32_t raw_throttle = CLAMP(gp->throttle, 0, 1023);
            if (raw_throttle > TRIGGER_THRESHOLD) {
                pedal_speed = (raw_throttle * 100) / 1023;
                pedal_speed = CLAMP(pedal_speed, 0, 100);
            }

            int32_t brake_speed = 0;
            int32_t raw_brake = CLAMP(gp->brake, 0, 1023);
            if (raw_brake > TRIGGER_THRESHOLD) {
                brake_speed = (raw_brake * 100) / 1023;
                brake_speed = CLAMP(brake_speed, 0, 100);
            }

            // Pedals (unsigned) override stick only if their value exceeds stick magnitude.
            int32_t weapon_speed = stick_speed;
            if (pedal_speed > abs(weapon_speed)) {
                weapon_speed = pedal_speed;
            }
            if (brake_speed > abs(weapon_speed)) {
                weapon_speed = brake_speed;
            }

#if HITL_CONSOLE
            hitl_latency_on_ry_change(raw_weapon);
#endif
            weapon_set_speed((int8_t)weapon_speed);
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

    // CRITICAL: Run continuous safety monitoring (battery, safety button)
    safety_update();
}

#if !SERIAL_GAMEPAD
static void my_platform_on_controller_data(uni_hid_device_t *d,
                                           uni_controller_t *ctl) {
    bool state_changed = true;
    uni_gamepad_t *gp;

    note_controller_activity();

    switch (ctl->klass) {
    case UNI_CONTROLLER_CLASS_GAMEPAD:
        gp = &ctl->gamepad;
        hitl_last_gp = *gp;
        hitl_last_gp_valid = true;

        state_changed = memcmp(&ctl_prev, ctl, sizeof(*ctl)) != 0;
        if (state_changed) {
            ctl_prev = *ctl;
        }

        process_gamepad_input(gp, state_changed);
        break;

    case UNI_CONTROLLER_CLASS_BALANCE_BOARD:
    case UNI_CONTROLLER_CLASS_MOUSE:
    case UNI_CONTROLLER_CLASS_KEYBOARD:
    default:
        // Robot only supports gamepads - ignore other controller types
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
#endif

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

void bluetooth_platform_inject_gamepad(const uni_gamepad_t* gp) {
    if (gp == NULL) {
        return;
    }

    note_controller_activity();

    bool state_changed = true;
    if (inject_prev_valid && memcmp(&inject_prev, gp, sizeof(*gp)) == 0) {
        state_changed = false;
    }
    inject_prev = *gp;
    inject_prev_valid = true;

    process_gamepad_input((uni_gamepad_t*)gp, state_changed);
}

//
// Entry Point
//
#if !SERIAL_GAMEPAD
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
#endif
