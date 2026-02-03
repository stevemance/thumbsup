#include "serial_gamepad.h"

#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "bluetooth_platform.h"
#include "config.h"
#include "system_status.h"
#include "weapon.h"
#include "pico/stdlib.h"

#define SERIAL_LINE_MAX 160

static uni_gamepad_t gp_state = {0};

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

static int32_t clamp_axis(int32_t value) {
    if (value < -512) {
        return -512;
    }
    if (value > 511) {
        return 511;
    }
    return value;
}

static int32_t percent_to_axis(int32_t percent) {
    percent = CLAMP(percent, -100, 100);
    int32_t raw = (percent * 512) / 100;
    return clamp_axis(raw);
}

static int32_t weapon_percent_to_axis(int32_t percent) {
    percent = CLAMP(percent, 0, 100);
    if (percent == 0) {
        return 0;
    }
    int32_t span = 511 - TRIGGER_THRESHOLD;
    return clamp_axis(TRIGGER_THRESHOLD + (percent * span) / 100);
}

static void print_state(void) {
    printf("STATE y=%ld x=%ld ry=%ld rx=%ld buttons=0x%04x dpad=0x%02x\n",
           (long)gp_state.axis_y,
           (long)gp_state.axis_x,
           (long)gp_state.axis_ry,
           (long)gp_state.axis_rx,
           gp_state.buttons,
           gp_state.dpad);
}

static const char* weapon_state_label(weapon_state_t state) {
    switch (state) {
        case WEAPON_STATE_DISARMED:
            return "DISARMED";
        case WEAPON_STATE_ARMING:
            return "ARMING";
        case WEAPON_STATE_ARMED:
            return "ARMED";
        case WEAPON_STATE_SPINNING:
            return "SPINNING";
        case WEAPON_STATE_EMERGENCY_STOP:
            return "ESTOP";
        default:
            return "UNKNOWN";
    }
}

static void print_sys_status(void) {
    uint32_t batt_mv = read_battery_voltage();
    printf("SYS armed=%u failsafe=%u weapon=%s speed=%u batt_mv=%lu dshot_fail=%lu\n",
           system_is_armed() ? 1u : 0u,
           system_failsafe_active() ? 1u : 0u,
           weapon_state_label(weapon_get_state()),
           weapon_get_speed(),
           (unsigned long)batt_mv,
           (unsigned long)weapon_get_dshot_failures());
}

static void print_telemetry(void) {
    weapon_telemetry_t telem;
    uint32_t age = weapon_get_telemetry_age_ms();
    if (weapon_get_telemetry(&telem)) {
        printf("TELEM valid=1 age=%lu erpm=%lu rpm=%lu V=%.2f I=%.2f T=%u\n",
               (unsigned long)age,
               (unsigned long)telem.erpm,
               (unsigned long)telem.rpm,
               telem.voltage_cV / 100.0f,
               telem.current_cA / 100.0f,
               telem.temperature_C);
    } else {
        if (age == UINT32_MAX) {
            printf("TELEM valid=0 age=--\n");
        } else {
            printf("TELEM valid=0 age=%lu\n", (unsigned long)age);
        }
    }
}

static void inject_state(void) {
    bluetooth_platform_inject_gamepad(&gp_state);
}

static bool parse_int(const char* value, int32_t* out) {
    if (value == NULL || out == NULL) {
        return false;
    }
    char* end = NULL;
    long parsed = strtol(value, &end, 0);
    if (end == value || *end != '\0') {
        return false;
    }
    *out = (int32_t)parsed;
    return true;
}

static bool button_mask_from_name(const char* name, uint16_t* mask) {
    if (streq_case(name, "A")) {
        *mask = BTN_A;
    } else if (streq_case(name, "B")) {
        *mask = BTN_B;
    } else if (streq_case(name, "X")) {
        *mask = BTN_X;
    } else if (streq_case(name, "Y")) {
        *mask = BTN_Y;
    } else if (streq_case(name, "L1")) {
        *mask = BTN_L1;
    } else if (streq_case(name, "R1")) {
        *mask = BTN_R1;
    } else if (streq_case(name, "BACK")) {
        *mask = BTN_BACK;
    } else if (streq_case(name, "START")) {
        *mask = BTN_START;
    } else if (streq_case(name, "L3")) {
        *mask = BTN_L3;
    } else if (streq_case(name, "R3")) {
        *mask = BTN_R3;
    } else {
        return false;
    }
    return true;
}

static void press_button_mask(uint16_t mask) {
    gp_state.buttons |= mask;
    inject_state();
    sleep_ms(20);
    gp_state.buttons &= (uint16_t)~mask;
    inject_state();
}

static void clear_emergency_stop(void) {
    gp_state.buttons |= BTN_A;
    inject_state();
    sleep_ms(SAFETY_BUTTON_HOLD_TIME + 20);
    inject_state();
    gp_state.buttons &= (uint16_t)~BTN_A;
    inject_state();
}

static void print_help(void) {
    printf("\nSerial gamepad commands:\n");
    printf("  GP y=<raw> x=<raw> ry=<raw> buttons=0xNNNN\n");
    printf("  GP y_pct=<pct> x_pct=<pct> ry_pct=<pct>\n");
    printf("  THROTTLE <0-100>   (maps to right stick Y)\n");
    printf("  DRIVE <fwd_pct> <turn_pct>\n");
    printf("  BTN <name> <0|1>   (A,B,X,Y,L1,R1,BACK,START,L3,R3)\n");
    printf("  ARM                (toggle weapon via B press)\n");
    printf("  ESTOP              (L1+R1)\n");
    printf("  CLEAR_ESTOP        (hold A to clear)\n");
    printf("  SYS                (system status)\n");
    printf("  TELEM              (latest ESC telemetry)\n");
    printf("  RESET              (zero axes/buttons)\n");
    printf("  STATE              (print current state)\n");
    printf("  HELP\n\n");
}

static bool handle_gp_token(const char* token, bool* updated) {
    const char* eq = strchr(token, '=');
    if (!eq) {
        return false;
    }

    char key[32];
    char val[32];
    size_t key_len = (size_t)(eq - token);
    if (key_len >= sizeof(key)) {
        return false;
    }
    memcpy(key, token, key_len);
    key[key_len] = '\0';

    snprintf(val, sizeof(val), "%s", eq + 1);

    int32_t parsed = 0;
    if (streq_case(key, "y") || streq_case(key, "axis_y")) {
        if (!parse_int(val, &parsed)) {
            return false;
        }
        gp_state.axis_y = clamp_axis(parsed);
        *updated = true;
        return true;
    }
    if (streq_case(key, "x") || streq_case(key, "axis_x")) {
        if (!parse_int(val, &parsed)) {
            return false;
        }
        gp_state.axis_x = clamp_axis(parsed);
        *updated = true;
        return true;
    }
    if (streq_case(key, "ry") || streq_case(key, "axis_ry")) {
        if (!parse_int(val, &parsed)) {
            return false;
        }
        gp_state.axis_ry = clamp_axis(parsed);
        *updated = true;
        return true;
    }
    if (streq_case(key, "rx") || streq_case(key, "axis_rx")) {
        if (!parse_int(val, &parsed)) {
            return false;
        }
        gp_state.axis_rx = clamp_axis(parsed);
        *updated = true;
        return true;
    }
    if (streq_case(key, "y_pct") || streq_case(key, "pct_y")) {
        if (!parse_int(val, &parsed)) {
            return false;
        }
        gp_state.axis_y = percent_to_axis(parsed);
        *updated = true;
        return true;
    }
    if (streq_case(key, "x_pct") || streq_case(key, "pct_x")) {
        if (!parse_int(val, &parsed)) {
            return false;
        }
        gp_state.axis_x = percent_to_axis(parsed);
        *updated = true;
        return true;
    }
    if (streq_case(key, "ry_pct") || streq_case(key, "pct_ry")) {
        if (!parse_int(val, &parsed)) {
            return false;
        }
        gp_state.axis_ry = percent_to_axis(parsed);
        *updated = true;
        return true;
    }
    if (streq_case(key, "buttons")) {
        if (!parse_int(val, &parsed)) {
            return false;
        }
        gp_state.buttons = (uint16_t)parsed;
        *updated = true;
        return true;
    }
    if (streq_case(key, "dpad")) {
        if (!parse_int(val, &parsed)) {
            return false;
        }
        gp_state.dpad = (uint8_t)parsed;
        *updated = true;
        return true;
    }
    return false;
}

static bool handle_line(char* line) {
    char* cursor = line;
    while (*cursor && isspace((unsigned char)*cursor)) {
        cursor++;
    }
    if (*cursor == '\0' || *cursor == '#') {
        return false;
    }

    char* save = NULL;
    char* cmd = strtok_r(cursor, " \t", &save);
    if (cmd == NULL) {
        return false;
    }

    if (streq_case(cmd, "HELP") || streq_case(cmd, "?")) {
        print_help();
        return true;
    }
    if (streq_case(cmd, "STATE")) {
        print_state();
        return true;
    }
    if (streq_case(cmd, "SYS")) {
        print_sys_status();
        return true;
    }
    if (streq_case(cmd, "TELEM")) {
        print_telemetry();
        return true;
    }
    if (streq_case(cmd, "RESET")) {
        memset(&gp_state, 0, sizeof(gp_state));
        inject_state();
        return true;
    }
    if (streq_case(cmd, "ARM")) {
        press_button_mask(BTN_B);
        return true;
    }
    if (streq_case(cmd, "ESTOP")) {
        press_button_mask(BTN_L1 | BTN_R1);
        return true;
    }
    if (streq_case(cmd, "CLEAR_ESTOP")) {
        clear_emergency_stop();
        return true;
    }
    if (streq_case(cmd, "THROTTLE") || streq_case(cmd, "WEAPON")) {
        char* value = strtok_r(NULL, " \t", &save);
        int32_t percent = 0;
        if (value == NULL || !parse_int(value, &percent)) {
            printf("ERR: THROTTLE expects 0-100\n");
            return true;
        }
        gp_state.axis_ry = weapon_percent_to_axis(percent);
        inject_state();
        return true;
    }
    if (streq_case(cmd, "DRIVE")) {
        char* fwd = strtok_r(NULL, " \t", &save);
        char* turn = strtok_r(NULL, " \t", &save);
        int32_t fwd_pct = 0;
        int32_t turn_pct = 0;
        if (fwd == NULL || turn == NULL ||
            !parse_int(fwd, &fwd_pct) || !parse_int(turn, &turn_pct)) {
            printf("ERR: DRIVE expects forward and turn percent\n");
            return true;
        }
        gp_state.axis_y = percent_to_axis(-fwd_pct);
        gp_state.axis_x = percent_to_axis(turn_pct);
        inject_state();
        return true;
    }
    if (streq_case(cmd, "BTN")) {
        char* name = strtok_r(NULL, " \t", &save);
        char* value = strtok_r(NULL, " \t", &save);
        if (name == NULL || value == NULL) {
            printf("ERR: BTN expects name and value\n");
            return true;
        }
        uint16_t mask = 0;
        if (!button_mask_from_name(name, &mask)) {
            printf("ERR: Unknown button '%s'\n", name);
            return true;
        }
        int32_t on = 0;
        if (!parse_int(value, &on)) {
            printf("ERR: BTN value must be 0 or 1\n");
            return true;
        }
        if (on) {
            gp_state.buttons |= mask;
        } else {
            gp_state.buttons &= (uint16_t)~mask;
        }
        inject_state();
        return true;
    }
    if (streq_case(cmd, "GP")) {
        bool updated = false;
        char* token = NULL;
        while ((token = strtok_r(NULL, " \t", &save)) != NULL) {
            handle_gp_token(token, &updated);
        }
        if (updated) {
            inject_state();
        } else {
            printf("ERR: GP expects key=value pairs\n");
        }
        return true;
    }

    printf("ERR: Unknown command '%s' (type HELP)\n", cmd);
    return true;
}

void serial_gamepad_init(void) {
    memset(&gp_state, 0, sizeof(gp_state));
    print_help();
}

bool serial_gamepad_poll(void) {
    static char line[SERIAL_LINE_MAX];
    static size_t len = 0;
    bool handled = false;

    int c = getchar_timeout_us(0);
    while (c != PICO_ERROR_TIMEOUT) {
        if (c == '\r') {
            c = getchar_timeout_us(0);
            continue;
        }
        if (c == '\n') {
            line[len] = '\0';
            handled = handle_line(line) || handled;
            len = 0;
            c = getchar_timeout_us(0);
            continue;
        }
        if (len + 1 < sizeof(line)) {
            line[len++] = (char)c;
        }
        c = getchar_timeout_us(0);
    }

    return handled;
}
