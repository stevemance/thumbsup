#include <ctype.h>
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "btstack.h"
#include "pico/cyw43_arch.h"
#include "pico/stdlib.h"
#include "tusb.h"

#define REPORT_INTERVAL_MS 10
#define SERIAL_POLL_MS 5
#define SERIAL_LINE_MAX 160
#define HAT_NEUTRAL 8

#define BTN_A_MASK      (1u << 0)
#define BTN_B_MASK      (1u << 1)
#define BTN_X_MASK      (1u << 3)
#define BTN_Y_MASK      (1u << 4)
#define BTN_L1_MASK     (1u << 6)
#define BTN_R1_MASK     (1u << 7)
#define BTN_L2_MASK     (1u << 8)
#define BTN_R2_MASK     (1u << 9)
#define BTN_SELECT_MASK (1u << 10)
#define BTN_START_MASK  (1u << 11)
#define BTN_HOME_MASK   (1u << 12)
#define BTN_L3_MASK     (1u << 13)
#define BTN_R3_MASK     (1u << 14)

static const uint8_t hid_descriptor_gamepad[] = {
    0x05, 0x01,  // Usage Page (Generic Desktop)
    0x09, 0x05,  // Usage (Game Pad)
    0xA1, 0x01,  // Collection (Application)
    0xA1, 0x00,  // Collection (Physical)
    0x05, 0x09,  // Usage Page (Button)
    0x19, 0x01,  // Usage Minimum (Button 1)
    0x29, 0x10,  // Usage Maximum (Button 16)
    0x15, 0x00,  // Logical Minimum (0)
    0x25, 0x01,  // Logical Maximum (1)
    0x95, 0x10,  // Report Count (16)
    0x75, 0x01,  // Report Size (1)
    0x81, 0x02,  // Input (Data,Var,Abs)
    0x05, 0x01,  // Usage Page (Generic Desktop)
    0x09, 0x39,  // Usage (Hat Switch)
    0x15, 0x00,  // Logical Minimum (0)
    0x25, 0x07,  // Logical Maximum (7)
    0x35, 0x00,  // Physical Minimum (0)
    0x46, 0x3B, 0x01,  // Physical Maximum (315)
    0x65, 0x14,  // Unit (Eng Rot:Angular Pos)
    0x75, 0x04,  // Report Size (4)
    0x95, 0x01,  // Report Count (1)
    0x81, 0x02,  // Input (Data,Var,Abs)
    0x75, 0x04,  // Report Size (4)
    0x95, 0x01,  // Report Count (1)
    0x81, 0x03,  // Input (Const,Var,Abs)
    0x05, 0x01,  // Usage Page (Generic Desktop)
    0x09, 0x30,  // Usage (X)
    0x09, 0x31,  // Usage (Y)
    0x09, 0x33,  // Usage (Rx)
    0x09, 0x35,  // Usage (Rz)
    0x15, 0x81,  // Logical Minimum (-127)
    0x25, 0x7F,  // Logical Maximum (127)
    0x75, 0x08,  // Report Size (8)
    0x95, 0x04,  // Report Count (4)
    0x81, 0x02,  // Input (Data,Var,Abs)
    0xC0,        // End Collection
    0xC0         // End Collection
};

typedef struct {
    int8_t lx;
    int8_t ly;
    int8_t rx;
    int8_t ry;
    uint16_t buttons;
    uint8_t hat;
} gamepad_state_t;

static gamepad_state_t gp_state;
static bool state_dirty = true;
static bool send_pending = false;
static uint32_t last_report_ms = 0;
static uint16_t hid_cid = 0;

static btstack_packet_callback_registration_t hci_event_callback_registration;
static btstack_timer_source_t poll_timer;

static uint8_t hid_service_buffer[300];
static uint8_t device_id_sdp_service_buffer[100];
static const char hid_device_name[] = "ThumbsUp HITL Gamepad";

static int32_t clamp_i32(int32_t value, int32_t min, int32_t max) {
    if (value < min) {
        return min;
    }
    if (value > max) {
        return max;
    }
    return value;
}

static bool streq_case(const char* a, const char* b) {
    while (*a && *b) {
        if (tolower((unsigned char)*a) != tolower((unsigned char)*b)) {
            return false;
        }
        a++;
        b++;
    }
    return *a == '\0' && *b == '\0';
}

static bool parse_int(const char* s, int32_t* out) {
    if (s == NULL || *s == '\0') {
        return false;
    }
    char* end = NULL;
    long value = strtol(s, &end, 0);
    if (end == s || *end != '\0') {
        return false;
    }
    if (value < INT32_MIN || value > INT32_MAX) {
        return false;
    }
    *out = (int32_t)value;
    return true;
}

static void gamepad_reset(void) {
    gp_state.lx = 0;
    gp_state.ly = 0;
    gp_state.rx = 0;
    gp_state.ry = 0;
    gp_state.buttons = 0;
    gp_state.hat = HAT_NEUTRAL;
    state_dirty = true;
}

static uint16_t button_mask_from_name(const char* name) {
    if (streq_case(name, "A")) return BTN_A_MASK;
    if (streq_case(name, "B")) return BTN_B_MASK;
    if (streq_case(name, "X")) return BTN_X_MASK;
    if (streq_case(name, "Y")) return BTN_Y_MASK;
    if (streq_case(name, "L1") || streq_case(name, "LB")) return BTN_L1_MASK;
    if (streq_case(name, "R1") || streq_case(name, "RB")) return BTN_R1_MASK;
    if (streq_case(name, "L2") || streq_case(name, "LT")) return BTN_L2_MASK;
    if (streq_case(name, "R2") || streq_case(name, "RT")) return BTN_R2_MASK;
    if (streq_case(name, "SELECT") || streq_case(name, "BACK")) return BTN_SELECT_MASK;
    if (streq_case(name, "START")) return BTN_START_MASK;
    if (streq_case(name, "HOME") || streq_case(name, "SYSTEM")) return BTN_HOME_MASK;
    if (streq_case(name, "L3")) return BTN_L3_MASK;
    if (streq_case(name, "R3")) return BTN_R3_MASK;
    return 0;
}

static bool parse_hat(const char* name, uint8_t* out_hat) {
    if (streq_case(name, "CENTER") || streq_case(name, "NEUTRAL")) {
        *out_hat = HAT_NEUTRAL;
        return true;
    }
    if (streq_case(name, "UP")) {
        *out_hat = 0;
        return true;
    }
    if (streq_case(name, "UP_RIGHT")) {
        *out_hat = 1;
        return true;
    }
    if (streq_case(name, "RIGHT")) {
        *out_hat = 2;
        return true;
    }
    if (streq_case(name, "DOWN_RIGHT")) {
        *out_hat = 3;
        return true;
    }
    if (streq_case(name, "DOWN")) {
        *out_hat = 4;
        return true;
    }
    if (streq_case(name, "DOWN_LEFT")) {
        *out_hat = 5;
        return true;
    }
    if (streq_case(name, "LEFT")) {
        *out_hat = 6;
        return true;
    }
    if (streq_case(name, "UP_LEFT")) {
        *out_hat = 7;
        return true;
    }
    return false;
}

static void set_axis_value(const char* axis, int32_t value) {
    value = clamp_i32(value, -127, 127);
    if (streq_case(axis, "LX")) {
        gp_state.lx = (int8_t)value;
    } else if (streq_case(axis, "LY")) {
        gp_state.ly = (int8_t)value;
    } else if (streq_case(axis, "RX")) {
        gp_state.rx = (int8_t)value;
    } else if (streq_case(axis, "RY")) {
        gp_state.ry = (int8_t)value;
    }
}

static void send_report(void) {
    if (!hid_cid) {
        return;
    }

    uint8_t report[7];
    report[0] = (uint8_t)(gp_state.buttons & 0xFF);
    report[1] = (uint8_t)((gp_state.buttons >> 8) & 0xFF);
    report[2] = (uint8_t)(gp_state.hat & 0x0F);
    report[3] = (uint8_t)gp_state.lx;
    report[4] = (uint8_t)gp_state.ly;
    report[5] = (uint8_t)gp_state.rx;
    report[6] = (uint8_t)gp_state.ry;

    hid_device_send_interrupt_message(hid_cid, report, sizeof(report));
    send_pending = false;
    state_dirty = false;
    last_report_ms = btstack_run_loop_get_time_ms();
}

static void request_send(void) {
    if (!hid_cid || send_pending) {
        return;
    }
    send_pending = true;
    hid_device_request_can_send_now_event(hid_cid);
}

static void print_state(void) {
    printf("STATE buttons=0x%04x hat=%u lx=%d ly=%d rx=%d ry=%d\n",
           gp_state.buttons,
           gp_state.hat,
           gp_state.lx,
           gp_state.ly,
           gp_state.rx,
           gp_state.ry);
}

static void print_help(void) {
    printf("Commands:\n");
    printf("  BTN <name> <0|1>\n");
    printf("  AXIS <LX|LY|RX|RY> <value -127..127>\n");
    printf("  STICK <L|R> <x> <y>\n");
    printf("  DPAD <CENTER|UP|UP_RIGHT|RIGHT|DOWN_RIGHT|DOWN|DOWN_LEFT|LEFT|UP_LEFT>\n");
    printf("  RESET\n");
    printf("  STATE\n");
    printf("  HELP\n");
}

static void handle_line(char* line) {
    char* save = NULL;
    char* cmd = strtok_r(line, " \t", &save);
    if (cmd == NULL) {
        return;
    }

    if (streq_case(cmd, "BTN")) {
        char* name = strtok_r(NULL, " \t", &save);
        char* value = strtok_r(NULL, " \t", &save);
        int32_t pressed = 0;
        uint16_t mask = 0;
        if (name == NULL || value == NULL || !parse_int(value, &pressed)) {
            printf("ERR BTN expects <name> <0|1>\n");
            return;
        }
        mask = button_mask_from_name(name);
        if (mask == 0) {
            printf("ERR BTN unknown: %s\n", name);
            return;
        }
        if (pressed) {
            gp_state.buttons |= mask;
        } else {
            gp_state.buttons &= (uint16_t)~mask;
        }
        state_dirty = true;
        return;
    }

    if (streq_case(cmd, "AXIS")) {
        char* axis = strtok_r(NULL, " \t", &save);
        char* value = strtok_r(NULL, " \t", &save);
        int32_t v = 0;
        if (axis == NULL || value == NULL || !parse_int(value, &v)) {
            printf("ERR AXIS expects <name> <value>\n");
            return;
        }
        set_axis_value(axis, v);
        state_dirty = true;
        return;
    }

    if (streq_case(cmd, "STICK")) {
        char* which = strtok_r(NULL, " \t", &save);
        char* x_str = strtok_r(NULL, " \t", &save);
        char* y_str = strtok_r(NULL, " \t", &save);
        int32_t x = 0;
        int32_t y = 0;
        if (which == NULL || x_str == NULL || y_str == NULL ||
            !parse_int(x_str, &x) || !parse_int(y_str, &y)) {
            printf("ERR STICK expects <L|R> <x> <y>\n");
            return;
        }
        if (streq_case(which, "L")) {
            set_axis_value("LX", x);
            set_axis_value("LY", y);
        } else if (streq_case(which, "R")) {
            set_axis_value("RX", x);
            set_axis_value("RY", y);
        } else {
            printf("ERR STICK expects L or R\n");
            return;
        }
        state_dirty = true;
        return;
    }

    if (streq_case(cmd, "DPAD")) {
        char* value = strtok_r(NULL, " \t", &save);
        uint8_t hat = 0;
        if (value == NULL || !parse_hat(value, &hat)) {
            printf("ERR DPAD expects direction\n");
            return;
        }
        gp_state.hat = hat;
        state_dirty = true;
        return;
    }

    if (streq_case(cmd, "RESET")) {
        gamepad_reset();
        return;
    }

    if (streq_case(cmd, "STATE")) {
        print_state();
        return;
    }

    if (streq_case(cmd, "HELP")) {
        print_help();
        return;
    }

    printf("ERR unknown command: %s\n", cmd);
}

static void serial_poll(void) {
    tud_task();

    static char line[SERIAL_LINE_MAX];
    static size_t len = 0;
    int ch = getchar_timeout_us(0);
    while (ch != PICO_ERROR_TIMEOUT) {
        if (ch == '\r' || ch == '\n') {
            if (len > 0) {
                line[len] = '\0';
                handle_line(line);
                len = 0;
            }
        } else if (len + 1 < sizeof(line)) {
            line[len++] = (char)ch;
        } else {
            len = 0;
        }
        ch = getchar_timeout_us(0);
    }
}

static void poll_timer_handler(btstack_timer_source_t* ts) {
    serial_poll();

    if (hid_cid) {
        uint32_t now = btstack_run_loop_get_time_ms();
        if (state_dirty || (now - last_report_ms) >= REPORT_INTERVAL_MS) {
            request_send();
        }
    }

    btstack_run_loop_set_timer(ts, SERIAL_POLL_MS);
    btstack_run_loop_add_timer(ts);
}

static void packet_handler(uint8_t packet_type, uint16_t channel, uint8_t* packet, uint16_t size) {
    UNUSED(channel);
    UNUSED(size);

    if (packet_type != HCI_EVENT_PACKET) {
        return;
    }

    bd_addr_t event_addr;

    switch (hci_event_packet_get_type(packet)) {
        case HCI_EVENT_PIN_CODE_REQUEST:
            hci_event_pin_code_request_get_bd_addr(packet, event_addr);
            gap_pin_code_response(event_addr, "0000");
            break;
        case HCI_EVENT_USER_CONFIRMATION_REQUEST:
            hci_event_user_confirmation_request_get_bd_addr(packet, event_addr);
            gap_ssp_confirmation_response(event_addr);
            break;
        case HCI_EVENT_HID_META:
            switch (hci_event_hid_meta_get_subevent_code(packet)) {
                case HID_SUBEVENT_CONNECTION_OPENED:
                    if (hid_subevent_connection_opened_get_status(packet) != ERROR_CODE_SUCCESS) {
                        break;
                    }
                    hid_cid = hid_subevent_connection_opened_get_hid_cid(packet);
                    send_pending = false;
                    state_dirty = true;
                    cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, 1);
                    printf("HID connected\n");
                    break;
                case HID_SUBEVENT_CONNECTION_CLOSED:
                    printf("HID disconnected\n");
                    hid_cid = 0;
                    send_pending = false;
                    state_dirty = true;
                    cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, 0);
                    break;
                case HID_SUBEVENT_CAN_SEND_NOW:
                    send_report();
                    break;
                default:
                    break;
            }
            break;
        default:
            break;
    }
}

int btstack_main(int argc, const char* argv[]);
int btstack_main(int argc, const char* argv[]) {
    (void)argc;
    (void)argv;

    stdio_init_all();

    if (cyw43_arch_init()) {
        printf("ERR cyw43 init failed\n");
        return -1;
    }
    cyw43_arch_gpio_put(CYW43_WL_GPIO_LED_PIN, 0);

    gamepad_reset();

    gap_discoverable_control(1);
    gap_set_class_of_device(0x2508);
    gap_set_local_name("ThumbsUp HITL Gamepad 00:00:00:00:00:00");
    gap_set_default_link_policy_settings(LM_LINK_POLICY_ENABLE_ROLE_SWITCH | LM_LINK_POLICY_ENABLE_SNIFF_MODE);
    gap_set_allow_role_switch(true);

    l2cap_init();
    sdp_init();

    uint8_t hid_virtual_cable = 0;
    uint8_t hid_remote_wake = 1;
    uint8_t hid_reconnect_initiate = 1;
    uint8_t hid_normally_connectable = 1;

    hid_sdp_record_t hid_params = {
        0x2508,
        33,
        hid_virtual_cable,
        hid_remote_wake,
        hid_reconnect_initiate,
        hid_normally_connectable,
        0,
        0xFFFF,
        0xFFFF,
        3200,
        hid_descriptor_gamepad,
        sizeof(hid_descriptor_gamepad),
        hid_device_name
    };

    memset(hid_service_buffer, 0, sizeof(hid_service_buffer));
    hid_create_sdp_record(hid_service_buffer, sdp_create_service_record_handle(), &hid_params);
    btstack_assert(de_get_len(hid_service_buffer) <= sizeof(hid_service_buffer));
    sdp_register_service(hid_service_buffer);

    device_id_create_sdp_record(device_id_sdp_service_buffer,
                                sdp_create_service_record_handle(),
                                DEVICE_ID_VENDOR_ID_SOURCE_USB,
                                0x2E8A,
                                0x0001,
                                0x0001);
    btstack_assert(de_get_len(device_id_sdp_service_buffer) <= sizeof(device_id_sdp_service_buffer));
    sdp_register_service(device_id_sdp_service_buffer);

    hid_device_init(0, sizeof(hid_descriptor_gamepad), hid_descriptor_gamepad);

    hci_event_callback_registration.callback = &packet_handler;
    hci_add_event_handler(&hci_event_callback_registration);
    hid_device_register_packet_handler(&packet_handler);

    poll_timer.process = &poll_timer_handler;
    btstack_run_loop_set_timer(&poll_timer, SERIAL_POLL_MS);
    btstack_run_loop_add_timer(&poll_timer);

    hci_power_control(HCI_POWER_ON);

    printf("ThumbsUp HITL Gamepad ready. Type HELP for commands.\n");

    btstack_run_loop_execute();
    return 0;
}

int main(void) {
    return btstack_main(0, NULL);
}
