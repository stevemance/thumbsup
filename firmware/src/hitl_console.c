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

// --- Latency tracking state ---
typedef enum {
    LATENCY_IDLE,
    LATENCY_ARMED,           // Waiting for spinup
    LATENCY_TRACKING_UP,     // Tracking spinup events
    LATENCY_TRACKING_DOWN,   // Tracking spindown events
} latency_phase_t;

static latency_phase_t latency_phase = LATENCY_IDLE;
static uint32_t latency_rpm_threshold = 500;

// Spinup timestamps (microseconds, from time_us_64()).
static uint64_t lat_t_ry_nonzero_us = 0;
static uint64_t lat_t_target_set_us = 0;
static uint64_t lat_t_dshot_nonzero_us = 0;
static uint64_t lat_t_rpm_seen_us = 0;
// Spindown timestamps.
static uint64_t lat_t_ry_zero_us = 0;
static uint64_t lat_t_rpm_below_us = 0;

// Track previous RY value to detect 0->nonzero and nonzero->0 edges.
static int32_t lat_prev_ry = 0;

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
    printf("  HITL TELEMRATE <ms>\n");
    printf("  HITL BATTERY <mv>\n");
    printf("  HITL BATTERY OFF\n");
    printf("  HITL LATENCY ARM <rpm_threshold>\n");
    printf("  HITL LATENCY DISARM\n");
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
    uint32_t rx_raw = 0;
    uint32_t rx_discarded = 0;
    uint32_t dec_frames = 0;
    uint64_t dec_us = 0;
    uint32_t bad = 0;
    uint32_t tx = 0;
    uint32_t tx_ok = 0;
    uint16_t last_thr = 0;
    bool setup_pending = false;
    bool setup_done = false;
    weapon_get_dshot_telemetry_counts(&req, &resp);
    weapon_get_dshot_telemetry_rx_counts(&rx_raw, &rx_discarded);
    weapon_get_dshot_telemetry_debug(NULL, &bad);
    weapon_get_dshot_telemetry_timing(&dec_frames, &dec_us);
    weapon_get_dshot_send_counts(&tx, &tx_ok);
    last_thr = weapon_get_dshot_last_throttle();
    weapon_get_dshot_setup_state(&setup_pending, &setup_done);
    weapon_control_mode_t mode = weapon_get_control_mode();
    uint32_t age = weapon_get_telemetry_age_ms();
    uint32_t reqbit = weapon_get_dshot_telemetry_reqbit_tx();
    uint32_t decode_pct = (dec_frames > 0) ? (resp * 100u) / dec_frames : 0;
    uint32_t decode_us_avg = (dec_frames > 0) ? (uint32_t)(dec_us / dec_frames) : 0;

    if (age == UINT32_MAX) {
        printf("TELEMSTATS mode=%s req=%lu resp=%lu reqbit=%lu rx=%lu disc=%lu dec=%lu bad=%lu ok_pct=%lu dec_us=%lu age=-- tx=%lu ok_tx=%lu thr=%u fail=%lu setup_pend=%u setup_done=%u\n",
               weapon_mode_label(mode),
               (unsigned long)req,
               (unsigned long)resp,
               (unsigned long)reqbit,
               (unsigned long)rx_raw,
               (unsigned long)rx_discarded,
               (unsigned long)dec_frames,
               (unsigned long)bad,
               (unsigned long)decode_pct,
               (unsigned long)decode_us_avg,
               (unsigned long)tx,
               (unsigned long)tx_ok,
               (unsigned)last_thr,
               (unsigned long)weapon_get_dshot_failures(),
               setup_pending ? 1u : 0u,
               setup_done ? 1u : 0u);
    } else {
        printf("TELEMSTATS mode=%s req=%lu resp=%lu reqbit=%lu rx=%lu disc=%lu dec=%lu bad=%lu ok_pct=%lu dec_us=%lu age=%lu tx=%lu ok_tx=%lu thr=%u fail=%lu setup_pend=%u setup_done=%u\n",
               weapon_mode_label(mode),
               (unsigned long)req,
               (unsigned long)resp,
               (unsigned long)reqbit,
               (unsigned long)rx_raw,
               (unsigned long)rx_discarded,
               (unsigned long)dec_frames,
               (unsigned long)bad,
               (unsigned long)decode_pct,
               (unsigned long)decode_us_avg,
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
    // Guard: skip this status update if the USB serial TX buffer can't fit the
    // whole message.  CFG_TUD_CDC_TX_BUFSIZE is 512 for HITL builds; a status
    // line is ~350 bytes.  If 350+ bytes are available we can write the full
    // line in one non-blocking shot.  If less is free we skip this interval
    // rather than entering printf's blocking tud_task loop (which stalls the
    // btstack event loop and causes missed BT HID reports).
    extern bool stdio_usb_connected(void);
    extern uint32_t tud_cdc_n_write_available(uint8_t itf);
    if (!stdio_usb_connected() || tud_cdc_n_write_available(0) < 350) {
        return;
    }

    uint32_t now_ms = to_ms_since_boot(get_absolute_time());
    uint32_t batt_mv = read_battery_voltage();

    uint16_t dl_us = motor_control_get_pulse(MOTOR_LEFT_DRIVE);
    uint16_t dr_us = motor_control_get_pulse(MOTOR_RIGHT_DRIVE);

    weapon_telemetry_t telem;
    bool telem_ok = weapon_get_telemetry(&telem);
    uint32_t age = weapon_get_telemetry_age_ms();

    // Derive weapon command from the current gamepad inputs for debugging.
    // This mirrors the competition mapping logic (signed stick + unsigned pedals).
    int32_t w_raw_ry = gp ? CLAMP(gp->axis_ry, -512, 511) : 0;
    int32_t w_stick = 0;
    if (abs(w_raw_ry) > TRIGGER_THRESHOLD) {
        if (w_raw_ry > 0) {
            w_stick = ((w_raw_ry - TRIGGER_THRESHOLD) * 100) / (511 - TRIGGER_THRESHOLD);
        } else {
            w_stick = ((w_raw_ry + TRIGGER_THRESHOLD) * 100) / (512 - TRIGGER_THRESHOLD);
        }
        w_stick = CLAMP(w_stick, -100, 100);
    }
    int32_t w_thr = 0;
    int32_t w_brk = 0;
    if (gp) {
        int32_t raw_thr = CLAMP(gp->throttle, 0, 1023);
        int32_t raw_brk = CLAMP(gp->brake, 0, 1023);
        if (raw_thr > TRIGGER_THRESHOLD) {
            w_thr = (raw_thr * 100) / 1023;
            w_thr = CLAMP(w_thr, 0, 100);
        }
        if (raw_brk > TRIGGER_THRESHOLD) {
            w_brk = (raw_brk * 100) / 1023;
            w_brk = CLAMP(w_brk, 0, 100);
        }
    }
    // Pedals (unsigned) override stick only if their value exceeds stick magnitude.
    int32_t w_cmd = w_stick;
    if (w_thr > abs(w_cmd)) w_cmd = w_thr;
    if (w_brk > abs(w_cmd)) w_cmd = w_brk;

    printf("HITL STATUS t_ms=%lu conn=%u ready=%u armed=%u failsafe=%u batt_mv=%lu weapon=%s speed=%d target=%d thr=%u mode=%s "
           "x=%d y=%d rx=%d ry=%d p_brk=%ld p_thr=%ld w_stick=%ld w_thr=%ld w_brk=%ld w_cmd=%ld buttons=0x%04x dpad=0x%02x dl_us=%u dr_us=%u telem=%u age_ms=",
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
            gp ? (long)gp->brake : 0,
            gp ? (long)gp->throttle : 0,
            (long)w_stick,
            (long)w_thr,
            (long)w_brk,
            (long)w_cmd,
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
        if (ms < 5) {
            ms = 5;
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

    if (streq_case(cmd, "TELEMRATE")) {
        char* value = strtok_r(NULL, " \t", &save);
        if (!value) {
            printf("ERR HITL TELEMRATE expects <ms>\n");
            return;
        }
        char* end = NULL;
        unsigned long ms = strtoul(value, &end, 0);
        if (!end || *end != '\0') {
            printf("ERR HITL TELEMRATE invalid: %s\n", value);
            return;
        }
        if (ms < 2) {
            ms = 2;
        }
        if (ms > 500) {
            ms = 500;
        }
        weapon_set_telemetry_interval_ms((uint32_t)ms);
        printf("HITL TELEMRATE ms=%lu\n", ms);
        return;
    }

    if (streq_case(cmd, "LATENCY")) {
        char* sub = strtok_r(NULL, " \t", &save);
        if (!sub) {
            printf("ERR HITL LATENCY expects ARM <rpm_threshold> or DISARM\n");
            return;
        }
        if (streq_case(sub, "ARM")) {
            char* thr_str = strtok_r(NULL, " \t", &save);
            if (!thr_str) {
                printf("ERR HITL LATENCY ARM expects <rpm_threshold>\n");
                return;
            }
            char* end = NULL;
            unsigned long thr = strtoul(thr_str, &end, 0);
            if (!end || *end != '\0') {
                printf("ERR HITL LATENCY ARM invalid: %s\n", thr_str);
                return;
            }
            latency_rpm_threshold = (uint32_t)thr;
            latency_phase = LATENCY_ARMED;
            lat_t_ry_nonzero_us = 0;
            lat_t_target_set_us = 0;
            lat_t_dshot_nonzero_us = 0;
            lat_t_rpm_seen_us = 0;
            lat_t_ry_zero_us = 0;
            lat_t_rpm_below_us = 0;
            lat_prev_ry = 0;
            printf("HITL LATENCY ARMED rpm_threshold=%lu\n", (unsigned long)latency_rpm_threshold);
            return;
        }
        if (streq_case(sub, "DISARM")) {
            latency_phase = LATENCY_IDLE;
            printf("HITL LATENCY DISARMED\n");
            return;
        }
        printf("ERR HITL LATENCY unknown: %s\n", sub);
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

// --- Latency callback implementations ---

void hitl_latency_on_ry_change(int32_t ry) {
    if (latency_phase == LATENCY_ARMED && lat_prev_ry == 0 && ry != 0) {
        // 0 -> nonzero: start spinup tracking.
        latency_phase = LATENCY_TRACKING_UP;
        lat_t_ry_nonzero_us = time_us_64();
        lat_t_target_set_us = 0;
        lat_t_dshot_nonzero_us = 0;
        lat_t_rpm_seen_us = 0;
        printf("HITL LATENCY EVENT ry_nonzero t_us=%llu ry=%ld\n",
               (unsigned long long)lat_t_ry_nonzero_us, (long)ry);
    } else if (latency_phase == LATENCY_TRACKING_DOWN && lat_prev_ry != 0 && ry == 0) {
        // nonzero -> 0 during spindown tracking: nothing extra needed, we already
        // recorded ry_zero when transitioning to TRACKING_DOWN. But if the caller
        // sends repeated zero commands, just skip.
    } else if (latency_phase == LATENCY_TRACKING_UP && lat_t_ry_nonzero_us != 0 &&
               lat_t_rpm_seen_us != 0 && ry == 0) {
        // Spindown edge while we are still in TRACKING_UP but already got RESULT.
        // This shouldn't normally happen because TRACKING_UP transitions to
        // TRACKING_DOWN after RESULT, but handle gracefully.
    }
    lat_prev_ry = ry;
}

void hitl_latency_on_target_set(uint8_t target) {
    if (latency_phase == LATENCY_TRACKING_UP && lat_t_target_set_us == 0 && target > 0) {
        lat_t_target_set_us = time_us_64();
        printf("HITL LATENCY EVENT target_set t_us=%llu target=%u\n",
               (unsigned long long)lat_t_target_set_us, (unsigned)target);
    }
}

void hitl_latency_on_dshot_sent(uint16_t throttle) {
    if (latency_phase == LATENCY_TRACKING_UP && lat_t_dshot_nonzero_us == 0 && throttle > 0) {
        lat_t_dshot_nonzero_us = time_us_64();
        printf("HITL LATENCY EVENT dshot_nonzero t_us=%llu thr=%u\n",
               (unsigned long long)lat_t_dshot_nonzero_us, (unsigned)throttle);
    }
}

void hitl_latency_on_rpm_update(uint32_t rpm) {
    if (latency_phase == LATENCY_TRACKING_UP && lat_t_rpm_seen_us == 0 &&
        rpm >= latency_rpm_threshold) {
        lat_t_rpm_seen_us = time_us_64();
        printf("HITL LATENCY EVENT rpm_seen t_us=%llu rpm=%lu\n",
               (unsigned long long)lat_t_rpm_seen_us, (unsigned long)rpm);

        // Emit spinup summary.
        uint64_t ry = lat_t_ry_nonzero_us;
        uint64_t tgt = lat_t_target_set_us;
        uint64_t dsh = lat_t_dshot_nonzero_us;
        uint64_t rp = lat_t_rpm_seen_us;
        printf("HITL LATENCY RESULT ry_us=%llu target_us=%llu dshot_us=%llu rpm_us=%llu "
               "ry_to_target_us=%llu target_to_dshot_us=%llu dshot_to_rpm_us=%llu total_us=%llu\n",
               (unsigned long long)ry,
               (unsigned long long)tgt,
               (unsigned long long)dsh,
               (unsigned long long)rp,
               (unsigned long long)(tgt > ry ? tgt - ry : 0),
               (unsigned long long)(dsh > tgt ? dsh - tgt : 0),
               (unsigned long long)(rp > dsh ? rp - dsh : 0),
               (unsigned long long)(rp > ry ? rp - ry : 0));

        // Transition to spindown tracking.
        latency_phase = LATENCY_TRACKING_DOWN;
        lat_t_ry_zero_us = 0;
        lat_t_rpm_below_us = 0;
        // Record the zero edge for spindown if RY is already 0.
        if (lat_prev_ry == 0) {
            lat_t_ry_zero_us = time_us_64();
            printf("HITL LATENCY EVENT ry_zero t_us=%llu\n",
                   (unsigned long long)lat_t_ry_zero_us);
        }
    } else if (latency_phase == LATENCY_TRACKING_DOWN) {
        // Track spindown: detect when RY goes to zero.
        if (lat_t_ry_zero_us == 0 && lat_prev_ry == 0) {
            lat_t_ry_zero_us = time_us_64();
            printf("HITL LATENCY EVENT ry_zero t_us=%llu\n",
                   (unsigned long long)lat_t_ry_zero_us);
        }
        // Detect RPM falling below threshold.
        if (lat_t_rpm_below_us == 0 && lat_t_ry_zero_us != 0 && rpm < latency_rpm_threshold) {
            lat_t_rpm_below_us = time_us_64();
            printf("HITL LATENCY EVENT rpm_below t_us=%llu rpm=%lu\n",
                   (unsigned long long)lat_t_rpm_below_us, (unsigned long)rpm);

            // Emit spindown summary.
            printf("HITL LATENCY DOWN ry_us=%llu rpm_us=%llu total_us=%llu\n",
                   (unsigned long long)lat_t_ry_zero_us,
                   (unsigned long long)lat_t_rpm_below_us,
                   (unsigned long long)(lat_t_rpm_below_us > lat_t_ry_zero_us ?
                                        lat_t_rpm_below_us - lat_t_ry_zero_us : 0));

            // Return to ARMED state, ready for the next cycle.
            latency_phase = LATENCY_ARMED;
        }
    }
}

#else

void hitl_console_init(void) {}
void hitl_console_set_controller_connected(bool connected) { (void)connected; }
void hitl_console_set_controller_ready(bool ready) { (void)ready; }
void hitl_console_on_gamepad(const uni_gamepad_t* gp) { (void)gp; }
void hitl_latency_on_ry_change(int32_t ry) { (void)ry; }
void hitl_latency_on_target_set(uint8_t target) { (void)target; }
void hitl_latency_on_dshot_sent(uint16_t throttle) { (void)throttle; }
void hitl_latency_on_rpm_update(uint32_t rpm) { (void)rpm; }

#endif
