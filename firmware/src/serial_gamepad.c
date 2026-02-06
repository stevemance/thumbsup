#include "serial_gamepad.h"

#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "bluetooth_platform.h"
#include "config.h"
#include "dshot.h"
#include "motor_control.h"
#include "system_status.h"
#include "weapon.h"
#include "pico/stdlib.h"
#include "hardware/gpio.h"
#if SERIAL_GAMEPAD
#include "tusb.h"
#endif

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

static const char* weapon_mode_label(weapon_control_mode_t mode) {
    switch (mode) {
        case WEAPON_MODE_PWM:
            return "PWM";
        case WEAPON_MODE_DSHOT:
            return "DSHOT";
        case WEAPON_MODE_CONFIG:
            return "CONFIG";
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

static void print_telem_stats(void) {
    static uint32_t last_stats_ms = 0;
    static uint32_t last_tx = 0;
    static uint32_t last_req = 0;
    static uint32_t last_resp = 0;
    uint32_t req = 0;
    uint32_t resp = 0;
    uint32_t raw = 0;
    uint32_t bad = 0;
    uint32_t tx = 0;
    uint32_t tx_ok = 0;
    uint16_t last_thr = 0;
    bool setup_pending = false;
    bool setup_done = false;
    weapon_get_dshot_telemetry_counts(&req, &resp);
    weapon_get_dshot_telemetry_debug(&raw, &bad);
    weapon_get_dshot_send_counts(&tx, &tx_ok);
    last_thr = weapon_get_dshot_last_throttle();
    weapon_get_dshot_setup_state(&setup_pending, &setup_done);
    weapon_control_mode_t mode = weapon_get_control_mode();
    uint32_t age = weapon_get_telemetry_age_ms();
    uint32_t now_ms = to_ms_since_boot(get_absolute_time());
    uint32_t dt_ms = (last_stats_ms == 0) ? 0 : (now_ms - last_stats_ms);
    uint32_t tx_rate = (dt_ms > 0) ? ((tx - last_tx) * 1000u) / dt_ms : 0;
    uint32_t req_rate = (dt_ms > 0) ? ((req - last_req) * 1000u) / dt_ms : 0;
    uint32_t resp_rate = (dt_ms > 0) ? ((resp - last_resp) * 1000u) / dt_ms : 0;
    uint32_t decode_ok = (raw >= bad) ? (raw - bad) : 0;
    uint32_t decode_pct = (raw > 0) ? (decode_ok * 100u) / raw : 0;
    gpio_function_t fn = gpio_get_function(PIN_WEAPON_PWM);
    if (age == UINT32_MAX) {
        printf("TELEMSTATS mode=%s req=%lu resp=%lu raw=%lu bad=%lu ok=%lu ok_pct=%lu age=-- tx=%lu ok_tx=%lu tx_rate=%lu req_rate=%lu resp_rate=%lu thr=%u fail=%lu gpio_fn=%d setup_pend=%u setup_done=%u\n",
               weapon_mode_label(mode),
               (unsigned long)req,
               (unsigned long)resp,
               (unsigned long)raw,
               (unsigned long)bad,
               (unsigned long)decode_ok,
               (unsigned long)decode_pct,
               (unsigned long)tx,
               (unsigned long)tx_ok,
               (unsigned long)tx_rate,
               (unsigned long)req_rate,
               (unsigned long)resp_rate,
               (unsigned)last_thr,
               (unsigned long)weapon_get_dshot_failures(),
               (int)fn,
               setup_pending ? 1u : 0u,
               setup_done ? 1u : 0u);
    } else {
        printf("TELEMSTATS mode=%s req=%lu resp=%lu raw=%lu bad=%lu ok=%lu ok_pct=%lu age=%lu tx=%lu ok_tx=%lu tx_rate=%lu req_rate=%lu resp_rate=%lu thr=%u fail=%lu gpio_fn=%d setup_pend=%u setup_done=%u\n",
               weapon_mode_label(mode),
               (unsigned long)req,
               (unsigned long)resp,
               (unsigned long)raw,
               (unsigned long)bad,
               (unsigned long)decode_ok,
               (unsigned long)decode_pct,
               (unsigned long)age,
               (unsigned long)tx,
               (unsigned long)tx_ok,
               (unsigned long)tx_rate,
               (unsigned long)req_rate,
               (unsigned long)resp_rate,
               (unsigned)last_thr,
               (unsigned long)weapon_get_dshot_failures(),
               (int)fn,
               setup_pending ? 1u : 0u,
               setup_done ? 1u : 0u);
    }

    last_stats_ms = now_ms;
    last_tx = tx;
    last_req = req;
    last_resp = resp;
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

static void print_telemetry_debug(void) {
    dshot_telemetry_t telem;
    bool ext = dshot_extended_telemetry_active(MOTOR_WEAPON);
    bool ext_seen = dshot_extended_telemetry_seen(MOTOR_WEAPON);
    if (dshot_get_telemetry(MOTOR_WEAPON, &telem)) {
        printf("TELEMDBG valid=1 ext=%u seen=%u type=0x%x value=0x%03x erpm=%lu V=%.2f I=%.2f T=%u\n",
               ext ? 1u : 0u,
               ext_seen ? 1u : 0u,
               telem.type,
               telem.value,
               (unsigned long)telem.erpm,
               telem.voltage_cV / 100.0f,
               telem.current_cA / 100.0f,
               telem.temperature_C);
    } else {
        printf("TELEMDBG valid=0 ext=%u seen=%u\n",
               ext ? 1u : 0u,
               ext_seen ? 1u : 0u);
    }
}

static void print_telem_raw(int count) {
    if (count <= 0) {
        count = 10;
    }

    int seen = 0;
    absolute_time_t start = get_absolute_time();
    while (seen < count && absolute_time_diff_us(start, get_absolute_time()) < 500000) {
        uint64_t raw = 0;
        if (dshot_read_telemetry_raw(MOTOR_WEAPON, &raw)) {
            printf("EDT raw=0x%010llx\n", (unsigned long long)raw);
            seen++;
        } else {
            sleep_ms(1);
        }
    }

    printf("TELEMRAW done=%d\n", seen);
}

static void dshot_spin_for_ms(uint16_t throttle, uint32_t duration_ms, bool request_telemetry) {
    const uint32_t step_ms = 2;
    uint32_t steps = duration_ms / step_ms;
    if (steps == 0) {
        steps = 1;
    }

    for (uint32_t i = 0; i < steps; i++) {
        dshot_send_throttle(MOTOR_WEAPON, throttle, request_telemetry);
        sleep_ms(step_ms);
    }
}

static bool weapon_wait_for_armed(uint32_t timeout_ms) {
    uint32_t start = to_ms_since_boot(get_absolute_time());
    while (to_ms_since_boot(get_absolute_time()) - start < timeout_ms) {
        weapon_update();
        if (weapon_get_state() == WEAPON_STATE_ARMED ||
            weapon_get_state() == WEAPON_STATE_SPINNING) {
            return true;
        }
        sleep_ms(MAIN_LOOP_DELAY);
    }
    return false;
}

static void weapon_hold_for_ms(uint8_t percent, uint32_t duration_ms) {
    if (!weapon_is_armed()) {
        if (!weapon_arm()) {
            printf("WEAPON_HOLD arm failed\n");
            return;
        }
        system_set_armed(true);
    }
    uint32_t arm_timeout = WEAPON_ARM_TIMEOUT +
                           (WEAPON_DSHOT_SETUP_MAX_ATTEMPTS * WEAPON_DSHOT_SETUP_RETRY_MS) +
                           1000;
    if (!weapon_wait_for_armed(arm_timeout)) {
        printf("WEAPON_HOLD arm timeout\n");
        return;
    }

    if (!weapon_set_speed(percent)) {
        printf("WEAPON_HOLD set speed failed\n");
        return;
    }

    uint32_t start = to_ms_since_boot(get_absolute_time());
    uint32_t next_log = start + 1000;
    while (to_ms_since_boot(get_absolute_time()) - start < duration_ms) {
        weapon_update();
        uint32_t now = to_ms_since_boot(get_absolute_time());
        if (now >= next_log) {
            printf("WEAPON_HOLD status speed=%u state=%s gpio_fn=%d sm_en=%u\n",
                   weapon_get_speed(),
                   weapon_state_label(weapon_get_state()),
                   (int)gpio_get_function(PIN_WEAPON_PWM),
                   dshot_sm_is_enabled(MOTOR_WEAPON) ? 1u : 0u);
            next_log += 1000;
        }
        sleep_ms(MAIN_LOOP_DELAY);
    }

    weapon_set_speed(0);
    weapon_update();
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
    for (uint32_t elapsed = 0; elapsed < (SAFETY_BUTTON_HOLD_TIME + 50); elapsed += 50) {
        inject_state();
        sleep_ms(50);
    }
    gp_state.buttons &= (uint16_t)~BTN_A;
    inject_state();
}

static void print_help(void) {
    printf("\nSerial gamepad commands:\n");
    printf("  GP y=<raw> x=<raw> ry=<raw> buttons=0xNNNN\n");
    printf("  GP y_pct=<pct> x_pct=<pct> ry_pct=<pct>\n");
    printf("  THROTTLE <0-100>   (maps to right stick Y)\n");
    printf("  WEAPON_SPEED <0-100> (direct weapon speed)\n");
    printf("  DRIVE <fwd_pct> <turn_pct>\n");
    printf("  BTN <name> <0|1>   (A,B,X,Y,L1,R1,BACK,START,L3,R3)\n");
    printf("  ARM                (toggle weapon via B press)\n");
    printf("  ARM_ON             (direct arm for HITL)\n");
    printf("  ARM_OFF            (direct disarm for HITL)\n");
    printf("  BEEP <1-5>         (DShot beep command)\n");
    printf("  DSHOT_CMD <0-31>   (send raw DShot command)\n");
    printf("  DSHOT_CRC <-1|0|1> (CRC override: -1 auto, 0 normal, 1 inverted)\n");
    printf("  DSHOT_SPIN <thr> <ms> [telem]\n");
    printf("  WEAPON_HOLD <0-100> <ms> (weapon_update loop)\n");
    printf("  ESTOP              (L1+R1)\n");
    printf("  CLEAR_ESTOP        (hold A to clear)\n");
    printf("  SYS                (system status)\n");
    printf("  TELEM              (latest ESC telemetry)\n");
    printf("  TELEMDBG           (raw ESC telemetry fields)\n");
    printf("  TELEMSTATS         (DShot telemetry counters)\n");
    printf("  TELEMRESET         (reset DShot telemetry counters)\n");
    printf("  TELEMRAW [count]   (dump raw EDT frames)\n");
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
    if (streq_case(cmd, "TELEMDBG")) {
        print_telemetry_debug();
        return true;
    }
    if (streq_case(cmd, "TELEMRAW")) {
        int32_t count = 0;
        char* value = strtok_r(NULL, " \t", &save);
        if (value != NULL && !parse_int(value, &count)) {
            printf("ERR: TELEMRAW expects optional count\n");
            return true;
        }
        print_telem_raw((int)count);
        return true;
    }
    if (streq_case(cmd, "TELEMRESET")) {
        weapon_reset_dshot_telemetry_counts();
        printf("TELEMRESET ok\n");
        return true;
    }
    if (streq_case(cmd, "TELEMSTATS")) {
        print_telem_stats();
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
    if (streq_case(cmd, "ARM_ON")) {
        bool ok = weapon_arm();
        if (ok) {
            system_set_armed(true);
        }
        printf("ARM_ON %s\n", ok ? "ok" : "fail");
        return true;
    }
    if (streq_case(cmd, "ARM_OFF")) {
        weapon_disarm();
        system_set_armed(false);
        printf("ARM_OFF ok\n");
        return true;
    }
    if (streq_case(cmd, "BEEP")) {
        char* value = strtok_r(NULL, " \t", &save);
        int32_t index = 0;
        if (value == NULL || !parse_int(value, &index) || index < 1 || index > 5) {
            printf("ERR: BEEP expects 1-5\n");
            return true;
        }
        dshot_command_t cmd_id = (dshot_command_t)(DSHOT_CMD_BEEP1 + (index - 1));
        printf("BEEP %s\n", dshot_send_command(MOTOR_WEAPON, cmd_id) ? "ok" : "fail");
        return true;
    }
    if (streq_case(cmd, "DSHOT_CMD")) {
        char* value = strtok_r(NULL, " \t", &save);
        int32_t raw_cmd = 0;
        if (value == NULL || !parse_int(value, &raw_cmd) || raw_cmd < 0 || raw_cmd > 31) {
            printf("ERR: DSHOT_CMD expects 0-31\n");
            return true;
        }
        printf("DSHOT_CMD %s\n",
               dshot_send_command(MOTOR_WEAPON, (dshot_command_t)raw_cmd) ? "ok" : "fail");
        return true;
    }
    if (streq_case(cmd, "DSHOT_CRC")) {
        char* value = strtok_r(NULL, " \t", &save);
        int32_t mode = 0;
        if (value == NULL || !parse_int(value, &mode) || mode < -1 || mode > 1) {
            printf("ERR: DSHOT_CRC expects -1, 0, or 1\n");
            return true;
        }
        dshot_set_crc_invert_override(MOTOR_WEAPON, (int8_t)mode);
        printf("DSHOT_CRC ok\n");
        return true;
    }
    if (streq_case(cmd, "DSHOT_SPIN")) {
        char* thr = strtok_r(NULL, " \t", &save);
        char* ms = strtok_r(NULL, " \t", &save);
        char* telem = strtok_r(NULL, " \t", &save);
        int32_t throttle = 0;
        int32_t duration = 0;
        int32_t telem_flag = 1;
        if (thr == NULL || ms == NULL ||
            !parse_int(thr, &throttle) || !parse_int(ms, &duration)) {
            printf("ERR: DSHOT_SPIN expects <throttle> <ms> [telem]\n");
            return true;
        }
        if (telem != NULL && !parse_int(telem, &telem_flag)) {
            printf("ERR: DSHOT_SPIN telem must be 0 or 1\n");
            return true;
        }
        throttle = CLAMP(throttle, 0, 2047);
        if (duration < 1) {
            duration = 1;
        }
        printf("DSHOT_SPIN start thr=%ld ms=%ld telem=%ld\n",
               (long)throttle, (long)duration, (long)telem_flag);
        dshot_spin_for_ms((uint16_t)throttle, (uint32_t)duration, telem_flag != 0);
        printf("DSHOT_SPIN done\n");
        return true;
    }
    if (streq_case(cmd, "WEAPON_HOLD")) {
        char* pct = strtok_r(NULL, " \t", &save);
        char* ms = strtok_r(NULL, " \t", &save);
        int32_t percent = 0;
        int32_t duration = 0;
        if (pct == NULL || ms == NULL ||
            !parse_int(pct, &percent) || !parse_int(ms, &duration)) {
            printf("ERR: WEAPON_HOLD expects <0-100> <ms>\n");
            return true;
        }
        percent = CLAMP(percent, 0, 100);
        if (duration < 1) {
            duration = 1;
        }
        printf("WEAPON_HOLD start pct=%ld ms=%ld\n", (long)percent, (long)duration);
        weapon_hold_for_ms((uint8_t)percent, (uint32_t)duration);
        printf("WEAPON_HOLD done\n");
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
    if (streq_case(cmd, "WEAPON_SPEED")) {
        char* value = strtok_r(NULL, " \t", &save);
        int32_t percent = 0;
        if (value == NULL || !parse_int(value, &percent)) {
            printf("ERR: WEAPON_SPEED expects 0-100\n");
            return true;
        }
        percent = CLAMP(percent, 0, 100);
        if (weapon_set_speed((uint8_t)percent)) {
            printf("WEAPON_SPEED ok\n");
        } else {
            printf("WEAPON_SPEED fail\n");
        }
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

#if SERIAL_GAMEPAD
    tud_task();
#endif

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
