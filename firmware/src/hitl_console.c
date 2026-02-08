#include "hitl_console.h"

#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if HITL_CONSOLE
#include <btstack.h>
#include <uni.h>
#endif

#include "config.h"
#include "hitl_overrides.h"
#include "pico/stdlib.h"
#include "system_status.h"
#include "motor_control.h"
#include "weapon.h"

#define HITL_LINE_MAX 160
#define HITL_STATUS_INTERVAL_MS 100

#if HITL_CONSOLE

static bool controller_connected = false;
static bool controller_ready = false;
static uint32_t last_status_ms = 0;
static uint32_t status_interval_ms = HITL_STATUS_INTERVAL_MS;

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

static void hitl_print_help(void) {
    printf("HITL commands:\n");
    printf("  HITL HELP\n");
    printf("  HITL STATUS\n");
    printf("  HITL STATUSRATE <ms>\n");
    printf("  HITL BTADDR\n");
    printf("  HITL BTKEYS CLEAR\n");
    printf("  HITL BTKEYS LIST\n");
    printf("  HITL TELEM\n");
    printf("  HITL TELEMSTATS\n");
    printf("  HITL BATTERY <mv>\n");
    printf("  HITL BATTERY OFF\n");
}

static void hitl_print_btaddr(void) {
    bd_addr_t addr;
    gap_local_bd_addr(addr);
    printf("HITL BTADDR %s\n", bd_addr_to_str(addr));
}

static void hitl_print_telem(void) {
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

static void hitl_print_telem_stats(void) {
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
    uint32_t decode_ok = (raw >= bad) ? (raw - bad) : 0;
    uint32_t decode_pct = (raw > 0) ? (decode_ok * 100u) / raw : 0;

    if (age == UINT32_MAX) {
        printf("TELEMSTATS mode=%s req=%lu resp=%lu raw=%lu bad=%lu ok=%lu ok_pct=%lu age=-- tx=%lu ok_tx=%lu thr=%u fail=%lu setup_pend=%u setup_done=%u\n",
               weapon_mode_label(mode),
               (unsigned long)req,
               (unsigned long)resp,
               (unsigned long)raw,
               (unsigned long)bad,
               (unsigned long)decode_ok,
               (unsigned long)decode_pct,
               (unsigned long)tx,
               (unsigned long)tx_ok,
               (unsigned)last_thr,
               (unsigned long)weapon_get_dshot_failures(),
               setup_pending ? 1u : 0u,
               setup_done ? 1u : 0u);
    } else {
        printf("TELEMSTATS mode=%s req=%lu resp=%lu raw=%lu bad=%lu ok=%lu ok_pct=%lu age=%lu tx=%lu ok_tx=%lu thr=%u fail=%lu setup_pend=%u setup_done=%u\n",
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
               (unsigned)last_thr,
               (unsigned long)weapon_get_dshot_failures(),
               setup_pending ? 1u : 0u,
               setup_done ? 1u : 0u);
    }
}

static void hitl_print_status(const uni_gamepad_t* gp) {
    uint32_t now_ms = to_ms_since_boot(get_absolute_time());
    uint32_t batt_mv = read_battery_voltage();

    uint16_t dl_us = motor_control_get_pulse(MOTOR_LEFT_DRIVE);
    uint16_t dr_us = motor_control_get_pulse(MOTOR_RIGHT_DRIVE);

    weapon_telemetry_t telem;
    bool telem_ok = weapon_get_telemetry(&telem);
    uint32_t age = weapon_get_telemetry_age_ms();

    printf("HITL STATUS t_ms=%lu conn=%u ready=%u armed=%u failsafe=%u batt_mv=%lu weapon=%s speed=%u target=%u thr=%u mode=%s "
           "x=%d y=%d rx=%d ry=%d buttons=0x%04x dpad=0x%02x dl_us=%u dr_us=%u telem=%u age_ms=",
           (unsigned long)now_ms,
           controller_connected ? 1u : 0u,
           controller_ready ? 1u : 0u,
           system_is_armed() ? 1u : 0u,
           system_failsafe_active() ? 1u : 0u,
           (unsigned long)batt_mv,
           weapon_state_label(weapon_get_state()),
           weapon_get_speed(),
           weapon_get_target_speed(),
           (unsigned)weapon_get_dshot_last_throttle(),
           weapon_mode_label(weapon_get_control_mode()),
           gp ? (int)gp->axis_x : 0,
           gp ? (int)gp->axis_y : 0,
           gp ? (int)gp->axis_rx : 0,
           gp ? (int)gp->axis_ry : 0,
           gp ? (unsigned)gp->buttons : 0u,
           gp ? (unsigned)gp->dpad : 0u,
           (unsigned)dl_us,
           (unsigned)dr_us,
           telem_ok ? 1u : 0u);

    if (age == UINT32_MAX) {
        printf("--");
    } else {
        printf("%lu", (unsigned long)age);
    }

    if (telem_ok) {
        printf(" rpm=%lu erpm=%lu v=%.2f i=%.2f temp=%u\n",
               (unsigned long)telem.rpm,
               (unsigned long)telem.erpm,
               telem.voltage_cV / 100.0f,
               telem.current_cA / 100.0f,
               telem.temperature_C);
    } else {
        printf("\n");
    }
}

static void hitl_handle_command(const char* line, const uni_gamepad_t* last_gp) {
    char copy[HITL_LINE_MAX];
    strncpy(copy, line, sizeof(copy));
    copy[sizeof(copy) - 1] = '\0';

    char* save = NULL;
    char* tok = strtok_r(copy, " \t", &save);
    if (!tok) {
        return;
    }

    if (!streq_case(tok, "HITL")) {
        return;
    }

    char* cmd = strtok_r(NULL, " \t", &save);
    if (!cmd) {
        hitl_print_help();
        return;
    }

    if (streq_case(cmd, "HELP")) {
        hitl_print_help();
        return;
    }

    if (streq_case(cmd, "STATUS")) {
        hitl_print_status(last_gp);
        return;
    }

    if (streq_case(cmd, "STATUSRATE")) {
        char* value = strtok_r(NULL, " \t", &save);
        if (!value) {
            printf("ERR HITL STATUSRATE expects <ms>\n");
            return;
        }
        char* end = NULL;
        unsigned long ms = strtoul(value, &end, 0);
        if (!end || *end != '\0') {
            printf("ERR HITL STATUSRATE invalid: %s\n", value);
            return;
        }
        if (ms < 20) {
            ms = 20;
        }
        if (ms > 2000) {
            ms = 2000;
        }
        status_interval_ms = (uint32_t)ms;
        printf("HITL STATUSRATE ms=%lu\n", ms);
        return;
    }

    if (streq_case(cmd, "BTADDR")) {
        hitl_print_btaddr();
        return;
    }

    if (streq_case(cmd, "BTKEYS")) {
        char* sub = strtok_r(NULL, " \t", &save);
        if (!sub) {
            printf("ERR HITL BTKEYS expects <CLEAR|LIST>\n");
            return;
        }
        if (streq_case(sub, "CLEAR")) {
            uni_bt_del_keys_unsafe();
            printf("HITL BTKEYS cleared\n");
            return;
        }
        if (streq_case(sub, "LIST")) {
            uni_bt_list_keys_unsafe();
            printf("HITL BTKEYS listed\n");
            return;
        }
        printf("ERR HITL BTKEYS unknown: %s\n", sub);
        return;
    }

    if (streq_case(cmd, "TELEM")) {
        hitl_print_telem();
        return;
    }

    if (streq_case(cmd, "TELEMSTATS")) {
        hitl_print_telem_stats();
        return;
    }

    if (streq_case(cmd, "BATTERY")) {
        char* value = strtok_r(NULL, " \t", &save);
        if (!value) {
            printf("ERR HITL BATTERY expects <mv|OFF>\n");
            return;
        }
        if (streq_case(value, "OFF")) {
            hitl_overrides_clear_battery_mv();
            printf("HITL BATTERY off\n");
            return;
        }
        char* end = NULL;
        unsigned long mv = strtoul(value, &end, 0);
        if (!end || *end != '\0') {
            printf("ERR HITL BATTERY invalid: %s\n", value);
            return;
        }
        hitl_overrides_set_battery_mv((uint32_t)mv);
        printf("HITL BATTERY mv=%lu\n", mv);
        return;
    }

    printf("ERR unknown HITL command: %s\n", cmd);
}

static void hitl_poll_serial(const uni_gamepad_t* last_gp) {
    static char line[HITL_LINE_MAX];
    static size_t len = 0;

    int ch = getchar_timeout_us(0);
    while (ch != PICO_ERROR_TIMEOUT) {
        if (ch == '\r' || ch == '\n') {
            if (len > 0) {
                line[len] = '\0';
                hitl_handle_command(line, last_gp);
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

void hitl_console_init(void) {
    hitl_overrides_init();
    controller_connected = false;
    controller_ready = false;
    last_status_ms = 0;
    status_interval_ms = HITL_STATUS_INTERVAL_MS;
    printf("HITL console enabled\n");
    hitl_print_help();
}

void hitl_console_set_controller_connected(bool connected) {
    controller_connected = connected;
    printf("HITL EVENT controller_connected=%u\n", connected ? 1u : 0u);
}

void hitl_console_set_controller_ready(bool ready) {
    controller_ready = ready;
    printf("HITL EVENT controller_ready=%u\n", ready ? 1u : 0u);
}

void hitl_console_on_gamepad(const uni_gamepad_t* gp) {
    uint32_t now_ms = to_ms_since_boot(get_absolute_time());
    hitl_poll_serial(gp);
    if (last_status_ms == 0 || (now_ms - last_status_ms) >= status_interval_ms) {
        hitl_print_status(gp);
        last_status_ms = now_ms;
    }
}

#else

void hitl_console_init(void) {}
void hitl_console_set_controller_connected(bool connected) { (void)connected; }
void hitl_console_set_controller_ready(bool ready) { (void)ready; }
void hitl_console_on_gamepad(const uni_gamepad_t* gp) { (void)gp; }

#endif
