#ifndef CONFIG_H
#define CONFIG_H

#include "pico/stdlib.h"

// Robot Configuration
#define ROBOT_NAME "ThumbsUp"
#define FIRMWARE_VERSION "1.0.0"

// Safety: Disable actual motor PWM output for testing (set to 1 to disable motors)
#define DISABLE_MOTOR_OUTPUT 0

// Pin Definitions
#define PIN_DRIVE_LEFT_PWM  0    // GP0 - Left drive motor PWM
#define PIN_DRIVE_RIGHT_PWM 1    // GP1 - Right drive motor PWM
#define PIN_WEAPON_PWM      2    // GP2 - Weapon motor PWM

// Addressable Status LEDs (SK6812/WS2812)
#define PIN_STATUS_LEDS     28   // GP28 - SK6812 addressable LEDs data line
#define NUM_STATUS_LEDS     2    // Number of addressable LEDs in chain

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

// Robot Physical Specifications
#define WHEEL_DIAMETER_MM   43.2f   // LEGO 43.2x22 ZR tire diameter (mm)
#define WHEEL_CIRCUMFERENCE_M 0.1357f // π × 43.2mm = 135.7mm = 0.1357m
#define WHEELBASE_MM        86.0f   // Wheel center-to-center distance (mm)
#define WHEELBASE_M         0.086f  // Wheelbase in meters
#define TURN_RADIUS_M       0.043f  // Minimum turn radius (pivot turn) = wheelbase/2
#define GEAR_RATIO          22.6f   // Motor gearbox ratio (22.6:1)

// Motor Specifications (3S / 12V nominal)
#define MOTOR_FREE_RPM_3S   1220    // Free speed at 12V (RPM)
#define MOTOR_STALL_CURRENT_A 2.0f  // Stall current (A)
#define MOTOR_STALL_TORQUE_NM 0.116f // Stall torque (N·m)

// Calculated Performance Characteristics
#define MAX_VELOCITY_MS     2.76f   // Max theoretical velocity (m/s) = 1220 RPM × 0.1357m / 60s
#define MAX_VELOCITY_KMH    9.9f    // Max velocity in km/h
#define MAX_WHEEL_RPM       1220    // Max wheel RPM (same as motor due to direct drive)

// Turning Performance (Differential Drive)
// When spinning in place (wheels opposite directions):
// Angular velocity ω = (V_right - V_left) / wheelbase
//                    = (2.76 - (-2.76)) / 0.086 = 64.2 rad/s = 3680 deg/s
#define MAX_ANGULAR_VELOCITY_RAD_S 64.2f  // Max rotation speed (rad/s) when spinning in place
#define MAX_ANGULAR_VELOCITY_DEG_S 3680.0f // Max rotation speed (deg/s) = 10.2 rev/s!
#define MAX_SPIN_TIME_MS    98      // Time for 360° spin at max speed (ms)

// Control Parameters
#define STICK_DEADZONE      15    // Joystick deadzone (0-127 scale)
#define TRIGGER_THRESHOLD   20    // Minimum trigger value to activate
#define MAX_DRIVE_SPEED     100   // Maximum drive speed percentage
#define MAX_WEAPON_SPEED    100   // Maximum weapon speed percentage

// Exponential Curve Parameters
// NOTE: Increased from 30% to 70% for better low-speed control
// Higher expo = more gradual at center stick, maintains full speed at full stick
// See docs/CONTROL_ANALYSIS.md for detailed explanation
#define DRIVE_EXPO          70    // Drive exponential curve (0-100, 0=linear)
#define WEAPON_EXPO         20    // Weapon exponential curve

// Real-Unit Conversion Helpers
// Convert PWM percentage (-100 to +100) to estimated velocity
#define PWM_PERCENT_TO_MS(percent) ((percent) * MAX_VELOCITY_MS / 100.0f)
#define PWM_PERCENT_TO_RPM(percent) ((percent) * MAX_WHEEL_RPM / 100)

// Convert velocity back to PWM percentage (for future closed-loop control)
#define MS_TO_PWM_PERCENT(velocity) ((velocity) * 100.0f / MAX_VELOCITY_MS)
#define RPM_TO_PWM_PERCENT(rpm) ((rpm) * 100 / MAX_WHEEL_RPM)

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

// Addressable LED Color Definitions (GRB format for SK6812)
// Format: 0x00GGRRBB (Green-Red-Blue)
// LED 0: System Status LED
// LED 1: Weapon Status LED

// System Status Colors (LED 0)
#define LED_COLOR_OFF           0x00000000  // Off
#define LED_COLOR_BOOT          0x00000020  // Dim blue - booting
#define LED_COLOR_READY         0x00200000  // Green - ready, no controller
#define LED_COLOR_CONNECTED     0x00200020  // Green+Blue (cyan) - controller connected
#define LED_COLOR_FAILSAFE      0x00202000  // Yellow - connection lost
#define LED_COLOR_LOW_BATTERY   0x00104000  // Orange - low battery
#define LED_COLOR_CRITICAL_BAT  0x00002000  // Red - critical battery
#define LED_COLOR_ERROR         0x00002000  // Red - error/safety violation
#define LED_COLOR_EMERGENCY     0x00002000  // Red - emergency stop
#define LED_COLOR_TEST_MODE     0x00001020  // Purple - test mode

// Weapon Status Colors (LED 1)
#define LED_COLOR_WEAPON_OFF    0x00000000  // Off - disarmed
#define LED_COLOR_WEAPON_ARMING 0x00404000  // Amber/Yellow - arming
#define LED_COLOR_WEAPON_ARMED  0x00206000  // Orange - armed but not spinning
#define LED_COLOR_WEAPON_SPIN   0x00006000  // Red - spinning
#define LED_COLOR_WEAPON_ESTOP  0x00006000  // Red flashing - emergency stop

// Brightness levels (0-255)
#define LED_BRIGHTNESS_DIM      32
#define LED_BRIGHTNESS_MEDIUM   128
#define LED_BRIGHTNESS_FULL     255

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
// Prefixed with BTN_ to avoid conflicts with Bluepad32
#define BTN_A               0x0001
#define BTN_B               0x0002
#define BTN_X               0x0004
#define BTN_Y               0x0008
#define BTN_L1              0x0010
#define BTN_R1              0x0020
#define BTN_BACK            0x0040
#define BTN_START           0x0080
#define BTN_L3              0x0100
#define BTN_R3              0x0200

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