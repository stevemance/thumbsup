#include "battery_monitor.h"

#include <stdio.h>

#include "bluetooth_platform.h"
#include "config.h"
#include "status.h"
#include "weapon.h"

static battery_level_t level = BATTERY_LEVEL_UNKNOWN;
static float filtered_mv = 0.0f;
static uint32_t last_sample_ms = 0;      // receive time of the last voltage used
static uint32_t last_led_check_ms = 0;
static int8_t shown_gauge = -1;          // controller player-LED gauge last sent

// Rumble pattern in progress: pulses_left pulses of pulse_ms, pulse_gap_ms apart.
static uint8_t pulses_left = 0;
static uint16_t pulse_ms = 0;
static uint32_t next_pulse_ms = 0;
static uint32_t last_critical_alert_ms = 0;

static const uint16_t PULSE_GAP_MS = 250;

void battery_monitor_init(void) {
    level = BATTERY_LEVEL_UNKNOWN;
    filtered_mv = 0.0f;
    last_sample_ms = 0;
    shown_gauge = -1;
    pulses_left = 0;
}

void battery_monitor_controller_ready(void) {
    shown_gauge = -1;
}

battery_level_t battery_monitor_level(void) {
    return level;
}

uint32_t battery_monitor_mv(void) {
    return (uint32_t)filtered_mv;
}

const char* battery_monitor_level_name(battery_level_t l) {
    switch (l) {
    case BATTERY_LEVEL_OK:       return "OK";
    case BATTERY_LEVEL_LOW:      return "LOW";
    case BATTERY_LEVEL_CRITICAL: return "CRITICAL";
    default:                     return "UNKNOWN";
    }
}

static void start_rumble(uint8_t pulses, uint16_t duration_ms, uint32_t now_ms) {
    pulses_left = pulses;
    pulse_ms = duration_ms;
    next_pulse_ms = now_ms;
}

static void run_rumble(uint32_t now_ms) {
    if (pulses_left == 0 || (int32_t)(now_ms - next_pulse_ms) < 0) {
        return;
    }
    bluetooth_platform_controller_rumble(pulse_ms, 255, 255);
    pulses_left--;
    next_pulse_ms = now_ms + pulse_ms + PULSE_GAP_MS;
}

// Controller player LEDs as a 4-segment gauge (LED 1 = leftmost).
static int8_t gauge_for(uint32_t mv, battery_level_t l) {
    if (l == BATTERY_LEVEL_CRITICAL) return 0x9;   // outer two: distinct "critical" pattern
    if (l == BATTERY_LEVEL_LOW)      return 0x1;
    if (mv >= BATTERY_GAUGE_FULL_MV) return 0xF;
    if (mv >= BATTERY_GAUGE_MID_MV)  return 0x7;
    return 0x3;
}

static void update_indicators(uint32_t now_ms) {
    int8_t gauge = (level == BATTERY_LEVEL_UNKNOWN) ? -1 : gauge_for((uint32_t)filtered_mv, level);
    if (gauge >= 0 && gauge != shown_gauge &&
        bluetooth_platform_controller_player_leds((uint8_t)gauge)) {
        shown_gauge = gauge;
    }

    // The system LED is shared: only take it over from the normal connected
    // state, and hand it back once the battery recovers.
    if (now_ms - last_led_check_ms < 1000) {
        return;
    }
    last_led_check_ms = now_ms;
    system_status_t sys = status_get_system();
    if (level == BATTERY_LEVEL_LOW &&
        (sys == SYSTEM_STATUS_CONNECTED || sys == SYSTEM_STATUS_CRITICAL_BAT)) {
        status_set_system(SYSTEM_STATUS_LOW_BATTERY, LED_EFFECT_SOLID);
    } else if (level == BATTERY_LEVEL_CRITICAL &&
               (sys == SYSTEM_STATUS_CONNECTED || sys == SYSTEM_STATUS_LOW_BATTERY)) {
        status_set_system(SYSTEM_STATUS_CRITICAL_BAT, LED_EFFECT_BLINK_FAST);
    } else if (level == BATTERY_LEVEL_OK &&
               (sys == SYSTEM_STATUS_LOW_BATTERY || sys == SYSTEM_STATUS_CRITICAL_BAT)) {
        status_set_system(SYSTEM_STATUS_CONNECTED, LED_EFFECT_SOLID);
    }
}

static battery_level_t classify(float mv, battery_level_t current) {
    // Enter a worse level below its threshold; leave it only once the voltage
    // is BATTERY_ALERT_HYSTERESIS_MV above it.
    if (mv < BATTERY_ALERT_CRITICAL_MV) {
        return BATTERY_LEVEL_CRITICAL;
    }
    if (current == BATTERY_LEVEL_CRITICAL && mv < BATTERY_ALERT_CRITICAL_MV + BATTERY_ALERT_HYSTERESIS_MV) {
        return BATTERY_LEVEL_CRITICAL;
    }
    if (mv < BATTERY_ALERT_LOW_MV) {
        return BATTERY_LEVEL_LOW;
    }
    if ((current == BATTERY_LEVEL_LOW || current == BATTERY_LEVEL_CRITICAL) &&
        mv < BATTERY_ALERT_LOW_MV + BATTERY_ALERT_HYSTERESIS_MV) {
        return BATTERY_LEVEL_LOW;
    }
    return BATTERY_LEVEL_OK;
}

void battery_monitor_update(uint32_t now_ms) {
    run_rumble(now_ms);

    weapon_telemetry_t t;
    weapon_get_telemetry_snapshot(&t);
    if (t.voltage_ms != 0 && t.voltage_ms != last_sample_ms && t.voltage_cV > 0) {
        float mv = (float)t.voltage_cV * 10.0f;
        if (filtered_mv <= 0.0f) {
            filtered_mv = mv;
        } else {
            // First-order low-pass with BATTERY_ALERT_FILTER_MS time constant,
            // so a spin-up sag of a second or two does not trip an alert.
            float dt = (float)(t.voltage_ms - last_sample_ms);
            float alpha = dt / ((float)BATTERY_ALERT_FILTER_MS + dt);
            filtered_mv += alpha * (mv - filtered_mv);
        }
        last_sample_ms = t.voltage_ms;

        battery_level_t next = classify(filtered_mv, level);
        if (next != level) {
            printf("BATT level %s -> %s at %lu mV\n", battery_monitor_level_name(level),
                   battery_monitor_level_name(next), (unsigned long)filtered_mv);
            if (next == BATTERY_LEVEL_LOW && level != BATTERY_LEVEL_CRITICAL) {
                start_rumble(2, 200, now_ms);
            } else if (next == BATTERY_LEVEL_CRITICAL) {
                start_rumble(3, 400, now_ms);
                last_critical_alert_ms = now_ms;
            }
            level = next;
        }
    }

    // Keep reminding while critical.
    if (level == BATTERY_LEVEL_CRITICAL && pulses_left == 0 &&
        now_ms - last_critical_alert_ms >= BATTERY_CRITICAL_REPEAT_MS) {
        start_rumble(3, 400, now_ms);
        last_critical_alert_ms = now_ms;
    }

    update_indicators(now_ms);
}
