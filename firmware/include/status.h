#ifndef STATUS_H
#define STATUS_H

#include <stdint.h>
#include <stdbool.h>

// System status states (LED 0)
typedef enum {
    SYSTEM_STATUS_BOOT,          // Booting up
    SYSTEM_STATUS_READY,         // Ready, no controller
    SYSTEM_STATUS_CONNECTED,     // Controller connected
    SYSTEM_STATUS_FAILSAFE,      // Connection lost
    SYSTEM_STATUS_LOW_BATTERY,   // Battery low
    SYSTEM_STATUS_CRITICAL_BAT,  // Battery critical
    SYSTEM_STATUS_ERROR,         // Error/safety violation
    SYSTEM_STATUS_EMERGENCY,     // Emergency stop
    SYSTEM_STATUS_TEST_MODE      // Test/calibration mode
} system_status_t;

// Weapon status states (LED 1)
typedef enum {
    WEAPON_STATUS_DISARMED,      // Weapon off
    WEAPON_STATUS_ARMING,        // Arming sequence
    WEAPON_STATUS_ARMED,         // Armed but not spinning
    WEAPON_STATUS_SPINNING,      // Weapon spinning
    WEAPON_STATUS_EMERGENCY      // Emergency stop
} weapon_status_t;

// LED effect modes
typedef enum {
    LED_EFFECT_SOLID,            // Solid color
    LED_EFFECT_BLINK_SLOW,       // Slow blink (500ms)
    LED_EFFECT_BLINK_MEDIUM,     // Medium blink (250ms)
    LED_EFFECT_BLINK_FAST,       // Fast blink (100ms)
    LED_EFFECT_PULSE,            // Smooth breathing effect
    LED_EFFECT_FADE              // Fade in/out
} led_effect_t;

// Initialize the status LED system
// Returns: true on success, false on failure
bool status_init(void);

// Update status LEDs (call this regularly from main loop)
void status_update(void);

// Set system status LED (LED 0)
void status_set_system(system_status_t status, led_effect_t effect);

// Set weapon status LED (LED 1)
void status_set_weapon(weapon_status_t status, led_effect_t effect);

// Set a specific LED to a custom color
// led_index: 0 or 1
// grb_color: Color in GRB format (0x00GGRRBB)
// effect: Visual effect to apply
void status_set_led_color(uint8_t led_index, uint32_t grb_color, led_effect_t effect);

// Emergency mode - flash both LEDs red rapidly
void status_emergency_flash(void);

// Test mode - cycle through colors on both LEDs
void status_test_pattern(void);

// Turn off all LEDs
void status_all_off(void);

// Get current system status
system_status_t status_get_system(void);

// Get current weapon status
weapon_status_t status_get_weapon(void);

#endif // STATUS_H
