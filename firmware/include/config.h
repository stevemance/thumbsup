#ifndef CONFIG_H
#define CONFIG_H

#include "pico/stdlib.h"

// Robot Configuration
#define ROBOT_NAME "ThumbsUp"
#define FIRMWARE_VERSION "1.0.0"

// Pin Definitions
#define PIN_DRIVE_LEFT_PWM  2    // GP2 - Left drive motor PWM
#define PIN_DRIVE_RIGHT_PWM 3    // GP3 - Right drive motor PWM
#define PIN_WEAPON_PWM      4    // GP4 - Weapon motor PWM

// Status LEDs
#define PIN_LED_STATUS      5    // GP5 - Main status LED
#define PIN_LED_ARMED       6    // GP6 - Weapon armed indicator
#define PIN_LED_BATTERY     7    // GP7 - Battery status

// Optional Safety Button
#define PIN_SAFETY_BUTTON   8    // GP8 - Physical safety switch (optional)

// Battery Monitoring
#define PIN_BATTERY_ADC     26   // GP26/ADC0 - Battery voltage divider

// PWM Configuration
#define PWM_FREQUENCY       50   // 50Hz for standard servo/ESC control
#define PWM_WRAP_VALUE      20000 // For 50Hz at 125MHz clock

// PWM Pulse Widths (in microseconds)
#define PWM_MIN_PULSE       1000  // Minimum pulse width (full reverse/stop)
#define PWM_NEUTRAL_PULSE   1500  // Neutral position
#define PWM_MAX_PULSE       2000  // Maximum pulse width (full forward)

// Control Parameters
#define STICK_DEADZONE      15    // Joystick deadzone (0-127 scale)
#define TRIGGER_THRESHOLD   20    // Minimum trigger value to activate
#define MAX_DRIVE_SPEED     100   // Maximum drive speed percentage
#define MAX_WEAPON_SPEED    100   // Maximum weapon speed percentage

// Exponential Curve Parameters
#define DRIVE_EXPO          30    // Drive exponential curve (0-100, 0=linear)
#define WEAPON_EXPO         20    // Weapon exponential curve

// Safety Configuration
#define WEAPON_ARM_TIMEOUT  5000  // Weapon arm timeout in milliseconds
#define FAILSAFE_TIMEOUT    1500  // Connection loss failsafe timeout (ms) - increased for reliability
#define WEAPON_SPINUP_TIME  2000  // Weapon ramp-up time (ms)
#define WEAPON_RAMP_STEPS   50    // Number of steps for smooth ramping
#define SAFETY_CHECK_INTERVAL 10  // Safety check interval (ms)
#define EMERGENCY_STOP_HOLD_TIME 2000  // Time emergency stop must be held to clear (ms)

// Bluetooth Configuration
#define BT_DEVICE_NAME      "ThumbsUp_Robot"
#define BT_MAX_RETRIES      3
#define BT_SCAN_TIMEOUT     10000 // Scanning timeout in ms

// Battery Monitoring
#define BATTERY_LOW_VOLTAGE 9600  // Low battery threshold (mV) for 3S
#define BATTERY_CRITICAL    9000  // Critical battery voltage (mV)
#define BATTERY_MAX_VOLTAGE 12600 // Fully charged 3S (mV)
#define BATTERY_ADC_SCALE   3.3f  // ADC reference voltage
#define BATTERY_DIVIDER     4.0f  // Voltage divider ratio (adjust for your circuit)

// LED Blink Patterns (in ms)
#define LED_BLINK_FAST      100
#define LED_BLINK_MEDIUM    250
#define LED_BLINK_SLOW      500

// Debug Configuration
#ifdef DEBUG_MODE
    #define DEBUG_PRINT(...) printf(__VA_ARGS__)
    #define DEBUG_UPDATE_RATE 100  // Debug output rate in ms
#else
    #define DEBUG_PRINT(...)
#endif

// Control Mapping (Xbox 360 Controller via PB Tails Crush)
// Left Stick: X/Y for drive control
// Right Trigger (R2): Weapon speed control
// X + Y buttons: Arm weapon
// L1 + R1: Emergency disarm
// D-pad: Trim adjustments

// Button Masks for Xbox 360 Controller
#define BUTTON_A            0x0001
#define BUTTON_B            0x0002
#define BUTTON_X            0x0004
#define BUTTON_Y            0x0008
#define BUTTON_L1           0x0010
#define BUTTON_R1           0x0020
#define BUTTON_BACK         0x0040
#define BUTTON_START        0x0080
#define BUTTON_L3           0x0100
#define BUTTON_R3           0x0200

// Trim Configuration
#define TRIM_STEP           5      // Trim adjustment step size
#define TRIM_MAX            50     // Maximum trim value
#define TRIM_MIN            -50    // Minimum trim value

// Timing Constants
#define MAIN_LOOP_DELAY     10     // Main loop delay in ms (100Hz update)
#define PWM_UPDATE_RATE     20     // PWM update rate in ms (50Hz)
#define STATUS_UPDATE_RATE  100    // Status LED update rate

// System Limits
#define MAX_GAMEPAD_AXIS    127    // Maximum gamepad axis value
#define MIN_GAMEPAD_AXIS    -128   // Minimum gamepad axis value

// Common utility macros
#ifndef CLAMP
#define CLAMP(x, min, max) ((x) < (min) ? (min) : ((x) > (max) ? (max) : (x)))
#endif

#ifndef MIN
#define MIN(a, b) ((a) < (b) ? (a) : (b))
#endif

#ifndef MAX
#define MAX(a, b) ((a) > (b) ? (a) : (b))
#endif

// Function declarations
uint32_t read_battery_voltage(void);

// Common constants to replace magic numbers
#define MAX_SAFETY_VIOLATIONS       5     // Maximum violations before emergency stop
#define AM32_CONFIG_RETRIES        3     // Retries for AM32 communication
#define WEB_CONTROL_TIMEOUT_MS     1000  // Web control timeout
#define SAFETY_BUTTON_HOLD_TIME    2000  // Hold time for safety button actions (ms)
#define DIAGNOSTIC_MODE_HOLD_TIME  3000  // Hold time to enter diagnostic mode (ms)
#define DIAGNOSTIC_EXIT_HOLD_TIME  5000  // Hold time to exit diagnostic mode (ms)

#endif // CONFIG_H