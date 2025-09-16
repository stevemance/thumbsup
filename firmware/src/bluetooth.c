#include "bluetooth.h"
#include "config.h"
#include <stdio.h>
#include <string.h>
#include "pico/stdlib.h"
#include "pico/cyw43_arch.h"
#include "btstack.h"

static btstack_packet_callback_registration_t hci_event_callback_registration;
static gamepad_state_t internal_gamepad_state = {0};
static bd_addr_t target_device_addr;
static bool bluetooth_initialized = false;
static bool scan_active = false;
static uint16_t hid_cid = 0;

static int8_t apply_deadzone(int8_t value, int8_t deadzone) {
    if (abs(value) < deadzone) {
        return 0;
    }
    if (value > 0) {
        return ((value - deadzone) * 127) / (127 - deadzone);
    } else {
        return ((value + deadzone) * 128) / (128 - deadzone);
    }
}

static void parse_xbox_controller_report(uint8_t* report, uint16_t report_len, gamepad_state_t* state) {
    if (report_len < 15) return;

    if (report[0] == 0x00 && report[1] == 0x14) {
        state->buttons = (report[3] << 8) | report[2];

        state->left_trigger = report[4];
        state->right_trigger = report[5];

        int16_t lx = (report[7] << 8) | report[6];
        int16_t ly = (report[9] << 8) | report[8];
        int16_t rx = (report[11] << 8) | report[10];
        int16_t ry = (report[13] << 8) | report[12];

        state->left_stick_x = apply_deadzone(lx >> 8, STICK_DEADZONE);
        state->left_stick_y = apply_deadzone(-(ly >> 8), STICK_DEADZONE);
        state->right_stick_x = apply_deadzone(rx >> 8, STICK_DEADZONE);
        state->right_stick_y = apply_deadzone(-(ry >> 8), STICK_DEADZONE);

        uint8_t dpad = report[2] & 0x0F;
        state->dpad_up = (dpad == 0x01) || (dpad == 0x02) || (dpad == 0x08);
        state->dpad_down = (dpad == 0x05) || (dpad == 0x04) || (dpad == 0x06);
        state->dpad_left = (dpad == 0x07) || (dpad == 0x08) || (dpad == 0x06);
        state->dpad_right = (dpad == 0x03) || (dpad == 0x02) || (dpad == 0x04);

        state->connected = true;
        state->last_update = to_ms_since_boot(get_absolute_time());
    }
}

static void handle_hid_report(uint8_t* report, uint16_t report_len) {
    parse_xbox_controller_report(report, report_len, &internal_gamepad_state);

    DEBUG_PRINT("HID Report: LX=%d LY=%d RT=%d Buttons=0x%04X\n",
                internal_gamepad_state.left_stick_x,
                internal_gamepad_state.left_stick_y,
                internal_gamepad_state.right_trigger,
                internal_gamepad_state.buttons);
}

static void packet_handler(uint8_t packet_type, uint16_t channel, uint8_t* packet, uint16_t size) {
    UNUSED(channel);

    if (packet_type != HCI_EVENT_PACKET) return;

    uint8_t event = hci_event_packet_get_type(packet);

    switch (event) {
        case BTSTACK_EVENT_STATE:
            if (btstack_event_state_get_state(packet) == HCI_STATE_WORKING) {
                if (!scan_active) {
                    gap_start_scan();
                    scan_active = true;
                    DEBUG_PRINT("Bluetooth initialized, starting scan...\n");
                }
            }
            break;

        case GAP_EVENT_ADVERTISING_REPORT: {
            bd_addr_t address;
            gap_event_advertising_report_get_address(packet, address);

            uint8_t* adv_data = gap_event_advertising_report_get_data(packet);
            uint8_t adv_len = gap_event_advertising_report_get_data_length(packet);

            for (int i = 0; i < adv_len - 1; ) {
                uint8_t data_len = adv_data[i];
                uint8_t data_type = adv_data[i + 1];

                if (data_type == 0x09) {
                    char name[32] = {0};
                    memcpy(name, &adv_data[i + 2], MIN(data_len - 1, 31));

                    if (strstr(name, "Xbox") || strstr(name, "Controller") ||
                        strstr(name, "PB Tails") || strstr(name, "Crush")) {
                        memcpy(target_device_addr, address, 6);
                        gap_stop_scan();
                        scan_active = false;

                        DEBUG_PRINT("Found controller: %s\n", name);
                        DEBUG_PRINT("Connecting to %s\n", bd_addr_to_str(target_device_addr));

                        hid_host_connect(target_device_addr, &hid_cid);
                        break;
                    }
                }
                i += data_len + 1;
            }
            break;
        }

        case HID_SUBEVENT_CONNECTION_OPENED: {
            hid_cid = little_endian_read_16(packet, 3);
            internal_gamepad_state.connected = true;
            DEBUG_PRINT("HID connection opened, cid=0x%04X\n", hid_cid);
            break;
        }

        case HID_SUBEVENT_CONNECTION_CLOSED: {
            internal_gamepad_state.connected = false;
            hid_cid = 0;
            DEBUG_PRINT("HID connection closed\n");

            gap_start_scan();
            scan_active = true;
            break;
        }

        case HID_SUBEVENT_REPORT: {
            uint16_t report_len = little_endian_read_16(packet, 5);
            handle_hid_report(&packet[7], report_len);
            break;
        }

        default:
            break;
    }
}

bool bluetooth_init(void) {
    if (bluetooth_initialized) {
        return true;
    }

    l2cap_init();
    sm_init();

    hid_host_init(packet_handler);

    hci_event_callback_registration.callback = &packet_handler;
    hci_add_event_handler(&hci_event_callback_registration);

    gap_set_scan_parameters(0, 0x0030, 0x0030);

    hci_power_control(HCI_POWER_ON);

    bluetooth_initialized = true;
    DEBUG_PRINT("Bluetooth module initialized\n");

    return true;
}

bool bluetooth_update(gamepad_state_t* gamepad) {
    if (!bluetooth_initialized || !gamepad) {
        return false;
    }

    uint32_t current_time = to_ms_since_boot(get_absolute_time());

    if (internal_gamepad_state.connected &&
        (current_time - internal_gamepad_state.last_update) > BT_SCAN_TIMEOUT) {
        internal_gamepad_state.connected = false;
        if (!scan_active) {
            gap_start_scan();
            scan_active = true;
        }
    }

    memcpy(gamepad, &internal_gamepad_state, sizeof(gamepad_state_t));

    return internal_gamepad_state.connected;
}

bool bluetooth_is_connected(void) {
    return internal_gamepad_state.connected;
}

void bluetooth_disconnect(void) {
    if (hid_cid != 0) {
        hid_host_disconnect(hid_cid);
        hid_cid = 0;
    }
    internal_gamepad_state.connected = false;
}

const char* bluetooth_get_device_name(void) {
    return BT_DEVICE_NAME;
}