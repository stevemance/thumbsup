#include "hitl_overrides.h"

#include <stdio.h>

#if HITL_CONSOLE

static bool battery_override_active = false;
static uint32_t battery_override_mv = 0;
static bool weapon_override_active = false;
static int8_t weapon_override_pct = 0;

void hitl_overrides_init(void) {
    battery_override_active = false;
    battery_override_mv = 0;
    weapon_override_active = false;
}

void hitl_overrides_set_weapon_pct(int8_t pct) {
    weapon_override_active = true;
    weapon_override_pct = pct;
}

void hitl_overrides_clear_weapon_pct(void) {
    weapon_override_active = false;
}

bool hitl_overrides_get_weapon_pct(int8_t* out_pct) {
    if (!weapon_override_active) {
        return false;
    }
    if (out_pct) {
        *out_pct = weapon_override_pct;
    }
    return true;
}

void hitl_overrides_set_battery_mv(uint32_t mv) {
    battery_override_active = true;
    battery_override_mv = mv;
}

void hitl_overrides_clear_battery_mv(void) {
    battery_override_active = false;
}

bool hitl_overrides_get_battery_mv(uint32_t* out_mv) {
    if (!battery_override_active) {
        return false;
    }
    if (out_mv) {
        *out_mv = battery_override_mv;
    }
    return true;
}

#else

void hitl_overrides_init(void) {}
void hitl_overrides_set_battery_mv(uint32_t mv) { (void)mv; }
void hitl_overrides_clear_battery_mv(void) {}
bool hitl_overrides_get_battery_mv(uint32_t* out_mv) { (void)out_mv; return false; }
void hitl_overrides_set_weapon_pct(int8_t pct) { (void)pct; }
void hitl_overrides_clear_weapon_pct(void) {}
bool hitl_overrides_get_weapon_pct(int8_t* out_pct) { (void)out_pct; return false; }

#endif

