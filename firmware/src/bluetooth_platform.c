// ThumbsUp Robot Bluepad32 Platform Implementation
// Adapted from pico_controller my_platform.c

#include <stddef.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>

#include <pico/time.h>
#include <hardware/watchdog.h>
#include <hardware/gpio.h>
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
#include "hitl_overrides.h"
#include "battery_monitor.h"
#include "drive_hbridge.h"
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
static uni_hid_device_t* active_device = NULL;   // set while a controller is ready
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

// Bluetooth inquiry policy.
//
// Inquiry (periodic BR/EDR scan + autoconnect) is stopped once a controller is
// ready because it generates CYW43 SPI traffic that contends with BT data.  It
// MUST be restarted on disconnect: a controller that drops into pairing mode
// waits to be *discovered*, and without inquiry the robot can never find it
// again (only a controller that pages us on its own would reconnect).
//
// HITL builds default this off because the emulator initiates connections and
// a concurrent robot-side autoconnect races it.  The HITL console can turn it
// on at runtime (HITL AUTOSCAN 1) so the disconnect/re-pair path is testable.
#if HITL_NO_SCAN
static bool bt_autoscan_enabled = false;
#else
static bool bt_autoscan_enabled = true;
#endif

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

static void require_weapon_trigger_release(void);

// Stops the drive and weapon if they are being commanded but controller
// reports have stopped arriving (link stalled without a disconnect).
static void check_report_staleness(uint32_t now_ms) {
    if (last_controller_input == 0 || now_ms - last_controller_input <= REPORT_STALE_TIMEOUT_MS) {
        return;
    }
    bool driving = motor_control_get_target_pulse(MOTOR_LEFT_DRIVE) != PWM_NEUTRAL_PULSE ||
                   motor_control_get_target_pulse(MOTOR_RIGHT_DRIVE) != PWM_NEUTRAL_PULSE;
    if (!driving && weapon_get_target_speed() == 0) {
        return;
    }
    printf("SAFETY: no controller report for %lu ms - outputs to neutral\n",
           (unsigned long)(now_ms - last_controller_input));
    drive_stop();
    weapon_set_speed(0);
    require_weapon_trigger_release();
    // Make the next report go through full processing even if unchanged.
    memset(&ctl_prev, 0, sizeof(ctl_prev));
}

static void hitl_timer_handler(btstack_timer_source_t* ts) {
    // Fast keepalive tick:
    // - Keep DShot frames flowing even when there is no controller traffic.
    //   Some ESCs will start beeping if they don't see frequent DShot updates.
    //   We target WEAPON_DSHOT_UPDATE_MS (2ms) for robustness.
    uint32_t now_ms = to_ms_since_boot(get_absolute_time());
    check_report_staleness(now_ms);

    motor_control_update();
    weapon_update();

    // Slow housekeeping tick (avoid expensive work at 500Hz).
    static uint32_t last_slow_ms = 0;
    if (last_slow_ms == 0 || (now_ms - last_slow_ms) >= 20) {
        hitl_console_on_gamepad(hitl_last_gp_valid ? &hitl_last_gp : NULL);
        battery_monitor_update(now_ms);
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
static btstack_packet_callback_registration_t link_event_registration;

// Poll-latency negotiation.  Some controllers (the PB Tails Crush) reject a
// Guaranteed QoS request, so fall back to Best Effort, then to an HCI Flow
// Specification for the incoming direction.
enum { LINK_QOS_GUARANTEED, LINK_QOS_BEST_EFFORT, LINK_QOS_FLOW_SPEC, LINK_QOS_DONE };
static int link_qos_step = LINK_QOS_DONE;
static hci_con_handle_t link_qos_handle = HCI_CON_HANDLE_INVALID;
static btstack_timer_source_t link_qos_timer;

static void link_qos_try_next(btstack_timer_source_t* ts) {
    UNUSED(ts);
#if BT_QOS_LATENCY_US
    if (link_qos_handle == HCI_CON_HANDLE_INVALID) {
        return;
    }
    switch (link_qos_step) {
    case LINK_QOS_GUARANTEED:
        gap_qos_set(link_qos_handle, HCI_SERVICE_TYPE_GUARANTEED, 1000, 0, BT_QOS_LATENCY_US, 0xFFFFFFFF);
        break;
    case LINK_QOS_BEST_EFFORT:
        gap_qos_set(link_qos_handle, HCI_SERVICE_TYPE_BEST_EFFORT, 1000, 0, BT_QOS_LATENCY_US, 0xFFFFFFFF);
        break;
    case LINK_QOS_FLOW_SPEC:
        if (!hci_can_send_command_packet_now()) {
            btstack_run_loop_set_timer(&link_qos_timer, 10);
            btstack_run_loop_add_timer(&link_qos_timer);
            return;
        }
        // flags, flow direction 1 = incoming (controller -> robot), service type,
        // token rate, token bucket size, peak bandwidth, access latency (us).
        hci_send_cmd(&hci_flow_specification, link_qos_handle, 0, 1, HCI_SERVICE_TYPE_BEST_EFFORT,
                     1000, 0, 0, BT_QOS_LATENCY_US);
        break;
    default:
        break;
    }
#endif
}

static void link_qos_start(hci_con_handle_t handle) {
    link_qos_handle = handle;
    link_qos_step = LINK_QOS_GUARANTEED;
    link_qos_timer.process = &link_qos_try_next;
    link_qos_try_next(&link_qos_timer);
}

static void link_qos_result(uint8_t status) {
    if (status == 0 || link_qos_step >= LINK_QOS_FLOW_SPEC) {
        link_qos_step = LINK_QOS_DONE;
        return;
    }
    link_qos_step++;
    btstack_run_loop_set_timer(&link_qos_timer, 10);
    btstack_run_loop_add_timer(&link_qos_timer);
}

// Logs the link-layer state that drives report latency: role, sniff/active
// mode and the QoS (poll latency) the radio actually granted.
static void link_event_handler(uint8_t packet_type, uint16_t channel, uint8_t *packet, uint16_t size) {
    UNUSED(channel);
    if (packet_type != HCI_EVENT_PACKET) {
        return;
    }
    switch (hci_event_packet_get_type(packet)) {
    case HCI_EVENT_ROLE_CHANGE:
        if (size >= 10) {
            printf("BT LINK role_change status=%u role=%s\n", packet[2],
                   packet[9] == 0 ? "central" : "peripheral");
        }
        break;
    case HCI_EVENT_MODE_CHANGE:
        if (size >= 8) {
            printf("BT LINK mode_change status=%u mode=%u interval=%u\n",
                   packet[2], packet[5], little_endian_read_16(packet, 6));
        }
        break;
    case HCI_EVENT_QOS_SETUP_COMPLETE:
        if (size >= 23) {
            printf("BT LINK qos status=%u service=%u latency_us=%lu\n", packet[2], packet[6],
                   (unsigned long)little_endian_read_32(packet, 15));
            link_qos_result(packet[2]);
        }
        break;
    case HCI_EVENT_FLOW_SPECIFICATION_COMPLETE:
        if (size >= 24) {
            printf("BT LINK flow_spec status=%u dir=%u service=%u latency_us=%lu\n", packet[2],
                   packet[6], packet[7], (unsigned long)little_endian_read_32(packet, 20));
            link_qos_result(packet[2]);
        }
        break;
    case HCI_EVENT_COMMAND_STATUS:
        // QoS/Flow Spec rejected before any complete event arrives.
        if (size >= 6 && packet[2] != 0 && link_qos_step != LINK_QOS_DONE &&
            (little_endian_read_16(packet, 4) == HCI_OPCODE_HCI_QOS_SETUP ||
             little_endian_read_16(packet, 4) == HCI_OPCODE_HCI_FLOW_SPECIFICATION)) {
            printf("BT LINK qos_cmd_status=%u opcode=0x%04x\n", packet[2], little_endian_read_16(packet, 4));
            link_qos_result(packet[2]);
        }
        break;
    default:
        break;
    }
}

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

    hitl_console_init();
    battery_monitor_init();

    link_event_registration.callback = &link_event_handler;
    hci_add_event_handler(&link_event_registration);

    gpio_init(PIN_LATENCY_MARKER);
    gpio_set_dir(PIN_LATENCY_MARKER, GPIO_OUT);
    gpio_put(PIN_LATENCY_MARKER, 0);

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
    if (bt_autoscan_enabled) {
        uni_bt_start_scanning_and_autoconnect_unsafe();
    } else {
        uni_bt_stop_scanning_unsafe();
    }

    // Based on runtime condition, you can delete or list the stored BT keys.
    // Keep stored keys so HITL pairing can be stable across reboots.
    // If you need to reset pairing, add an explicit action/command instead of
    // wiping keys on every boot.
    uni_bt_list_keys_unsafe();

    // Competition firmware should not enforce an allowlist; always clear and
    // disable it at boot so fresh controllers can pair without manual steps.
    uni_bt_allowlist_remove_all();
    uni_bt_allowlist_set_enabled(false);

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

#if !HITL_CONSOLE
    // Competition builds must never bind to the bench's HITL gamepad emulator.
    // It advertises as a generic gamepad and, if it is powered anywhere nearby,
    // autoconnect will grab it, stop scanning, and lock the real controller out.
    if (name && strncmp(name, "ThumbsUp HITL Gamepad", 21) == 0) {
        logi("Ignoring HITL gamepad emulator: %s\n", name);
        return UNI_ERROR_IGNORE_DEVICE;
    }
#endif

    return UNI_ERROR_SUCCESS;
}

static void my_platform_on_device_connected(uni_hid_device_t *d) {
    logi("thumbsup_platform: device connected: %p\n", d);
    // Device connected - update status LED
    status_set_system(SYSTEM_STATUS_CONNECTED, LED_EFFECT_SOLID);
    hitl_console_set_controller_connected(true);
}

static void my_platform_on_device_disconnected(uni_hid_device_t *d) {
    active_device = NULL;
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
#if DRIVE_HBRIDGE
    drive_hb_set_awake(false);
#endif

    // Update system status LED
    status_set_system(SYSTEM_STATUS_FAILSAFE, LED_EFFECT_BLINK_FAST);

    // Resume inquiry so a controller in pairing mode can be discovered again.
    // on_device_ready() stopped it to reduce CYW43 SPI contention while a
    // controller was connected; page scan alone is not enough to re-pair.
    if (bt_autoscan_enabled) {
        logi("thumbsup_platform: restarting BT scan after disconnect\n");
        uni_bt_start_scanning_and_autoconnect_unsafe();
    }

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
    active_device = d;
    battery_monitor_controller_ready();
#if DRIVE_HBRIDGE
    drive_hb_set_awake(true);
#endif

    printf("BT LINK ready role=%s\n",
           gap_get_role(active_con_handle) == HCI_ROLE_MASTER ? "central" : "peripheral");
    link_qos_start(active_con_handle);
#if BT_PREFER_PERIPHERAL_ROLE
    printf("BT LINK requesting role=peripheral status=%u\n", gap_request_role(d->conn.btaddr, HCI_ROLE_SLAVE));
#endif

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
           (abs(gp->axis_ry) <= STICK_DEADZONE) &&
           !(gp->buttons & (BTN_TRIGGER_L | BTN_TRIGGER_R)) &&
           gp->brake < WEAPON_TRIGGER_ANALOG_ON &&
           gp->throttle < WEAPON_TRIGGER_ANALOG_ON;
}

// Maps a raw -512..511 axis to -127..127 with a deadzone rescaled so output
// starts at 0 at the deadzone edge.
static int32_t axis_with_deadzone(int32_t raw, int32_t deadzone) {
    raw = CLAMP(raw, -512, 511);
    if (abs(raw) <= deadzone) {
        return 0;
    }
    int32_t scaled = raw > 0 ? ((raw - deadzone) * 511) / (511 - deadzone)
                             : ((raw + deadzone) * 512) / (512 - deadzone);
    return CLAMP((scaled * 127) / 512, -127, 127);
}

static void read_drive_sticks(const uni_gamepad_t* gp, int32_t* forward, int32_t* turn) {
    // Forward stick push is negative.  Turn is negated so +turn = clockwise
    // with the right motor mounted reversed.
    *forward = axis_with_deadzone(gp->axis_y, THROTTLE_DEADZONE);
#if DRIVE_LAYOUT_SPLIT
    *turn = axis_with_deadzone(-gp->axis_rx, TURN_DEADZONE);
#else
    *turn = axis_with_deadzone(-gp->axis_x, TURN_DEADZONE);
#endif
}

// Trigger weapon state.  +1 = forward (ZR), -1 = reverse (ZL), 0 = off.
// After arming, e-stop, reconnect or the neutral guard, both triggers must be
// seen released before a trigger can spin the weapon again, so a trigger held
// through arming never spins it up on its own.
static int8_t weapon_trigger_dir = 0;
static bool drive_requires_neutral = false;   // set by an e-stop clear
static bool weapon_trigger_release_required = true;

static void require_weapon_trigger_release(void) {
    weapon_trigger_dir = 0;
    weapon_trigger_release_required = true;
}

static int8_t update_weapon_trigger_dir(const uni_gamepad_t* gp) {
    bool fwd = (gp->buttons & BTN_TRIGGER_R) || gp->throttle >= WEAPON_TRIGGER_ANALOG_ON;
    bool rev = (gp->buttons & BTN_TRIGGER_L) || gp->brake >= WEAPON_TRIGGER_ANALOG_ON;

    if (!fwd && !rev) {
        weapon_trigger_release_required = false;
        weapon_trigger_dir = 0;
    } else if (weapon_trigger_release_required) {
        weapon_trigger_dir = 0;
    } else if (weapon_trigger_dir > 0 && !fwd) {
        weapon_trigger_dir = rev ? -1 : 0;
    } else if (weapon_trigger_dir < 0 && !rev) {
        weapon_trigger_dir = fwd ? 1 : 0;
    } else if (weapon_trigger_dir == 0 && fwd != rev) {
        // Both pressed in the same report from idle: neither wins.
        weapon_trigger_dir = fwd ? 1 : -1;
    }
    return weapon_trigger_dir;
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
    // Emergency stop (both shoulder buttons).  Checked before any service-mode
    // dispatch so no mode can swallow it.
    if ((gp->buttons & (BTN_L1 | BTN_R1)) ==
        (BTN_L1 | BTN_R1)) {
        bool was_emergency_stop = emergency_stop;
        emergency_stop = true;
        armed_state = false;
        drive_control_t stop_cmd = { .forward = 0, .turn = 0, .enabled = false };
        drive_update(&stop_cmd);
        weapon_disarm();
        require_weapon_trigger_release();

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

    // Check for mode activations BEFORE state-change handling to allow hold timers to work
    // Check for test mode activation first
    test_mode_check_activation(gp);

    // If in test mode, just update the display and return
    if (test_mode_is_active()) {
        test_mode_update(gp);
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
                require_weapon_trigger_release();
                // A stick held through the e-stop must not move the robot the
                // moment it clears: the drive waits for the sticks to centre.
                drive_requires_neutral = true;
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
        require_weapon_trigger_release();
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
                    require_weapon_trigger_release();
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
        int32_t forward = 0, turn = 0;
        read_drive_sticks(gp, &forward, &turn);
        if (drive_requires_neutral) {
            if (forward == 0 && turn == 0) {
                drive_requires_neutral = false;
            } else {
                forward = 0;
                turn = 0;
            }
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
        // We must also call weapon_disarm() to transition from EMERGENCY_STOP
        // to DISARMED, otherwise weapon_arm() will refuse (requires DISARMED).
        if (armed_state && !weapon_is_armed()) {
            weapon_disarm();
            armed_state = false;
            logi("Weapon state desync: cleared armed_state (disarmed)\n");
        }

        // Weapon on the triggers (only if armed): hold to spin, release to stop.
        int8_t weapon_dir = update_weapon_trigger_dir(gp);
        if (armed_state) {
            int32_t weapon_speed = weapon_dir * WEAPON_TRIGGER_SPEED;
            int8_t override_pct = 0;
            if (hitl_overrides_get_weapon_pct(&override_pct)) {
                weapon_speed = override_pct;
            }
#if HITL_CONSOLE
            hitl_latency_on_ry_change(weapon_speed);
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
// Report inter-arrival statistics, to measure the real controller's report
// period (HITL RXSTATS).
static const uint16_t rx_bin_edges_ms[] = {5, 10, 13, 16, 20, 30, 50, 100};
#define RX_BIN_COUNT (sizeof(rx_bin_edges_ms) / sizeof(rx_bin_edges_ms[0]) + 1)
static uint64_t rx_last_us = 0;
static uint32_t rx_count = 0, rx_min_us = UINT32_MAX, rx_max_us = 0;
static uint64_t rx_sum_us = 0;
static uint32_t rx_bins[RX_BIN_COUNT];

static void note_report_interval(void) {
    uint64_t now = time_us_64();
    if (rx_last_us != 0) {
        uint32_t dt = (uint32_t)(now - rx_last_us);
        rx_count++;
        rx_sum_us += dt;
        if (dt < rx_min_us) rx_min_us = dt;
        if (dt > rx_max_us) rx_max_us = dt;
        size_t b = 0;
        while (b < RX_BIN_COUNT - 1 && dt >= (uint32_t)rx_bin_edges_ms[b] * 1000u) b++;
        rx_bins[b]++;
    }
    rx_last_us = now;
}

void bluetooth_platform_print_rx_stats(bool reset) {
    printf("HITL RXSTATS n=%lu min_us=%lu avg_us=%lu max_us=%lu bins_ms=",
           (unsigned long)rx_count, (unsigned long)(rx_count ? rx_min_us : 0),
           (unsigned long)(rx_count ? rx_sum_us / rx_count : 0), (unsigned long)rx_max_us);
    for (size_t b = 0; b < RX_BIN_COUNT; b++) {
        if (b < RX_BIN_COUNT - 1) {
            printf("<%u:%lu,", rx_bin_edges_ms[b], (unsigned long)rx_bins[b]);
        } else {
            printf(">=%u:%lu\n", rx_bin_edges_ms[b - 1], (unsigned long)rx_bins[b]);
        }
    }
    if (reset) {
        rx_count = 0; rx_sum_us = 0; rx_min_us = UINT32_MAX; rx_max_us = 0;
        memset(rx_bins, 0, sizeof(rx_bins));
    }
}

static bool gamepad_is_deflected(const uni_gamepad_t* gp) {
    const int32_t threshold = 256;  // half of the +/-512 axis range
    return abs(gp->axis_x) > threshold || abs(gp->axis_y) > threshold ||
           abs(gp->axis_rx) > threshold || abs(gp->axis_ry) > threshold ||
           gp->brake > 2 * threshold || gp->throttle > 2 * threshold ||
           (gp->buttons & (BTN_TRIGGER_L | BTN_TRIGGER_R));
}

static void my_platform_on_controller_data(uni_hid_device_t *d,
                                           uni_controller_t *ctl) {
    bool state_changed = true;
    uni_gamepad_t *gp;

    note_controller_activity();

    switch (ctl->klass) {
    case UNI_CONTROLLER_CLASS_GAMEPAD:
        gp = &ctl->gamepad;
        gpio_put(PIN_LATENCY_MARKER, gamepad_is_deflected(gp));
        note_report_interval();
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
bool bluetooth_platform_controller_rumble(uint16_t duration_ms, uint8_t weak, uint8_t strong) {
    uni_hid_device_t* d = active_device;
    if (d == NULL || d->report_parser.play_dual_rumble == NULL) {
        return false;
    }
    d->report_parser.play_dual_rumble(d, 0, duration_ms, weak, strong);
    return true;
}

bool bluetooth_platform_controller_player_leds(uint8_t mask) {
    uni_hid_device_t* d = active_device;
    if (d == NULL || d->report_parser.set_player_leds == NULL) {
        return false;
    }
    d->report_parser.set_player_leds(d, mask);
    return true;
}

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

void bluetooth_platform_set_autoscan(bool enabled) {
    bt_autoscan_enabled = enabled;
}

bool bluetooth_platform_get_autoscan(void) {
    return bt_autoscan_enabled;
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
