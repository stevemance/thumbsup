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
// GP4 is UART1 TX, allowing AM32 config mode and DShot on the same pin
#define PIN_WEAPON_PWM      4    // GP4 - Weapon motor PWM/UART1_TX/DShot

// Addressable Status LEDs (SK6812/WS2812)
#define PIN_STATUS_LEDS     28   // GP28 - SK6812 addressable LEDs data line
#define NUM_STATUS_LEDS     2    // Number of addressable LEDs in chain

// Optional Safety Button
#define PIN_SAFETY_BUTTON   8    // GP8 - Physical safety switch (optional)

// Battery Monitoring
#define PIN_BATTERY_ADC     26   // GP26/ADC0 - Battery voltage divider

// Latency marker: driven high while the last received gamepad report has a
// deflected stick or pressed trigger.  Probed by the HITL logic analyzer; a
// single gpio_put per report, so it is left enabled in competition builds.
#define PIN_LATENCY_MARKER  15   // GP15 - HITL latency marker output

// Bluetooth Classic poll latency requested from the radio (HCI QoS Setup) once
// the controller is ready.  Without it the CYW43 polls the controller at its
// default interval (up to 25 ms), which adds 0-25 ms to every report.
// 0 disables the request.
#ifndef BT_QOS_LATENCY_US
#define BT_QOS_LATENCY_US   1250
#endif

// Ask the controller to take the central role once it is ready.  As central
// it transmits each report as soon as it has one instead of waiting to be
// polled.  The PB Tails Crush rejects every QoS request, and with the robot as
// central ~10% of its reports arrived after 20-45 ms gaps; as peripheral, 0.2%
// (max 27 ms), with ~7.3 ms between reports.
#ifndef BT_PREFER_PERIPHERAL_ROLE
#define BT_PREFER_PERIPHERAL_ROLE 1
#endif

// Report-age failsafe: if the drive or weapon is being commanded and no
// controller report has arrived for this long, command neutral.  The Crush
// streams every ~7 ms (max gap seen 27 ms after the role switch).  Neutral
// commands are unaffected, so a controller that only reports on change is
// safe at rest.
#define REPORT_STALE_TIMEOUT_MS 250

// PWM Configuration
// Drive PWM frame rate.  The counter ticks at 1 MHz, so one count is one
// microsecond of pulse width.
// The Kingmodel SAX2 drive ESC only reacts after ~5 frames, so its latency
// scales with the frame period (HITL, Sep 2026: 50 Hz ~95-115 ms, 100 Hz
// ~50-60 ms, 142 Hz ~40-50 ms).  At >=160 Hz it ignores the signal entirely
// and the drive goes dead, so keep a wide margin below that.
#ifndef PWM_FREQUENCY
#define PWM_FREQUENCY       100
#endif
#define PWM_TICK_HZ         1000000
#define PWM_WRAP_VALUE      (PWM_TICK_HZ / PWM_FREQUENCY)

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
#define MOTOR_FREE_RPM_3S   1220    // Theoretical free speed at 12V (RPM) - see note below
#define MOTOR_STALL_CURRENT_A 2.0f  // Stall current (A)
#define MOTOR_STALL_TORQUE_NM 0.116f // Stall torque (N·m)

// Measured Performance Characteristics (from calibration 2025-11-12)
// Note: Actual max RPM is ~66% of theoretical due to voltage sag, friction, and ESC losses
#define MAX_VELOCITY_MS     1.82f   // MEASURED max velocity (m/s) = 805 RPM × 0.1357m / 60s
#define MAX_VELOCITY_KMH    6.5f    // MEASURED max velocity in km/h
#define MAX_WHEEL_RPM       805     // MEASURED max wheel RPM under load (was 1220 theoretical)

// Turning Performance (Differential Drive)
// When spinning in place (wheels opposite directions):
// Angular velocity ω = (V_right - V_left) / wheelbase
//                    = (1.82 - (-1.82)) / 0.086 = 42.3 rad/s = 2425 deg/s
#define MAX_ANGULAR_VELOCITY_RAD_S 42.3f  // Max rotation speed (rad/s) when spinning in place
#define MAX_ANGULAR_VELOCITY_DEG_S 2425.0f // Max rotation speed (deg/s) = 6.7 rev/s
#define MAX_SPIN_TIME_MS    149     // Time for 360° spin at max speed (ms)

// Control Parameters
#define STICK_DEADZONE      15    // Neutral-guard deadzone (raw -512..511 scale)
#define THROTTLE_DEADZONE   24    // Throttle stick deadzone (raw -512..511 scale)
#define TURN_DEADZONE       32    // Turn stick deadzone (raw scale); absorbs snap-back bounce
#define TRIGGER_THRESHOLD   20    // Minimum trigger value to activate
#define MAX_DRIVE_SPEED     75    // Maximum drive speed percentage (75% of max for better control)
#define MAX_TURN_SPEED      70    // Maximum turn rate percentage (70% turn sensitivity)
#define MAX_WEAPON_SPEED    100   // Maximum weapon speed percentage
#define WEAPON_MOTOR_POLES  14    // Weapon motor pole count
#define WEAPON_POLE_PAIRS   (WEAPON_MOTOR_POLES / 2)

// Exponential Curve Parameters
// NOTE: Increased from 30% to 70% for better low-speed control
// Higher expo = more gradual at center stick, maintains full speed at full stick
// See docs/CONTROL_ANALYSIS.md for detailed explanation
#define DRIVE_EXPO          70    // Throttle exponential curve (0-100, 0=linear)
// Turn gets its own, much flatter curve.  At 70% cubic expo the last 20% of
// stick travel carried most of the turn rate, so a flick-to-aim landed on the
// steepest part of the curve.
#define TURN_EXPO           30    // Turn exponential curve (0-100, 0=linear)

// Split-stick drive: left stick Y = throttle, right stick X = turn.
// 0 restores the original single-left-stick arcade layout.
#ifndef DRIVE_LAYOUT_SPLIT
#define DRIVE_LAYOUT_SPLIT  1
#endif

// Weapon on the triggers: hold ZR = forward spin, hold ZL = reverse spin,
// release = spin down.  First trigger pressed wins while both are held.
#define WEAPON_TRIGGER_SPEED 100  // Weapon speed (%) while a trigger is held
#define WEAPON_TRIGGER_ANALOG_ON 512  // Analog trigger level (0..1023) counted as pressed
#define WEAPON_EXPO         20    // Weapon exponential curve

// Real-Unit Conversion Helpers
// Convert PWM percentage (-100 to +100) to estimated velocity
#define PWM_PERCENT_TO_MS(percent) ((percent) * MAX_VELOCITY_MS / 100.0f)
#define PWM_PERCENT_TO_RPM(percent) ((percent) * MAX_WHEEL_RPM / 100)

// Convert velocity back to PWM percentage (for future closed-loop control)
#define MS_TO_PWM_PERCENT(velocity) ((velocity) * 100.0f / MAX_VELOCITY_MS)
#define RPM_TO_PWM_PERCENT(rpm) ((rpm) * 100 / MAX_WHEEL_RPM)

// Safety Configuration
//
// Hardware safety inputs: set to 0 when the corresponding hardware is not
// wired up.  Floating ADC / GPIO pins cause spurious emergency stops.
#define BATTERY_ADC_ENABLED     0   // Set to 1 when battery voltage divider is wired to GP26
#define SAFETY_BUTTON_ENABLED   0   // Set to 1 when physical e-stop button is wired to GP8
#define WEAPON_ARM_TIMEOUT  2000  // Weapon arm timeout (ms).  Must allow ESC to
                                  // settle after DShot 3D mode setup to avoid
                                  // direction bias on first stick input.
#define FAILSAFE_TIMEOUT    1500  // Connection loss failsafe timeout (ms) - increased for reliability
// Weapon response / ramping
//
// Weapon slew limiting:
//
// We need enough ramping to avoid ESC/motor desync and supply brownouts during
// aggressive throttle changes (especially on bench supplies / long leads).
// Keep this reasonably quick, but prioritize stability over absolute snap.
#define WEAPON_SPINUP_TIME   1500  // Weapon ramp-up time (ms)
#define WEAPON_SPINDOWN_TIME 400   // Weapon ramp-down time (ms)
#define WEAPON_RAMP_STEPS   100   // Higher = smoother ramps (step size ~= 1% for 100)
// Direction-change priming (AM32 ESC 3D mode workaround).
//
// The AM32 sensorless startup fails on the first attempt at a new direction
// because the direction-change code (main.c:1063) sets old_routine=1, which
// skips startMotor() → no initial commutate() → stale BEMF state → motor
// won't spin.  Sending DShot=0 triggers the BEMF timeout (22.5ms) and sets
// running=0.  The next throttle command starts cleanly because the ESC's
// internal direction flag (`forward`) was already flipped on the first
// (failed) attempt.
//
// Phase 1 (PRIME_PULSE): Send new direction's minimum DShot value to flip
//   the ESC's internal direction flag.  The throttle maps to adjusted_input
//   ~46 (below startup threshold), so the motor won't actually spin.
// Phase 2 (PRIME_RESET): Send DShot=0 so the BEMF timeout fires (22.5ms)
//   and resets running=0.
// Phase 3: Normal ramp in new direction — ESC direction already correct,
//   clean startup succeeds.
#define WEAPON_PRIME_PULSE_MS 20    // Send min-DShot in new direction (ms)
#define WEAPON_PRIME_RESET_MS 30    // Send DShot=0 to reset ESC state (ms)
#define WEAPON_DSHOT_UPDATE_MS     2   // Minimum DShot update interval (ms) (500 Hz)
#define WEAPON_DSHOT_BIDIRECTIONAL 1   // 0=standard DShot TX, 1=single-wire bidirectional EDT
#define WEAPON_DSHOT_USE_3D       1   // 1=enable DShot 3D mode, 0=use unidirectional control
#define WEAPON_DSHOT_TELEMETRY_MS  50  // Telemetry request interval (ms)
#define WEAPON_DSHOT_TELEMETRY_BURST 4  // Decode up to N consecutive EDT frames per interval (helps catch RPM/V/I/T cycle)
#define WEAPON_DSHOT_TELEMETRY_MAX_PENDING 8  // Max outstanding telemetry frames to decode (budget / FIFO drain)
#define WEAPON_DSHOT_TELEMETRY_TIMEOUT_MS 20  // Timeout before clearing pending telemetry (ms)
// Telemetry sanity bounds.
//
// Bidirectional DShot telemetry can occasionally decode noise/glitches as "valid"
// frames (CRC matches by chance). Reject mechanically-impossible RPM spikes to keep
// HITL and competition logic stable.
#define WEAPON_TELEM_MAX_RPM 25000  // D2822/17 @ 3S (~14k RPM) -> keep generous headroom
// Telemetry IIR filter: RPM alpha = 2/4 = 0.5 (fast, smooths single-frame spikes 50%)
#define WEAPON_TELEM_RPM_ALPHA_NUM     2
#define WEAPON_TELEM_RPM_ALPHA_DEN     4
// V/I/T alpha = 1/4 = 0.25 (slow, these change on second timescales)
#define WEAPON_TELEM_SLOW_ALPHA_NUM    1
#define WEAPON_TELEM_SLOW_ALPHA_DEN    4
// Max RPM change per frame (rejects noise spikes, generous for real spinup)
// Largest believable change between consecutive accepted RPM readings
// (~2-4 ms apart).  The weapon's spin-up ramp is ~9 rpm/ms, so real steps are
// a few tens of rpm; this only catches corrupted frames.
#define WEAPON_TELEM_MAX_RPM_STEP      2000
// Accept a new level after this many mutually consistent out-of-step
// readings, so the check can never lock telemetry out.
#define WEAPON_TELEM_RPM_RESYNC        3
// The rig's AT32F421 AM32 ESC reports a constant 62 A (0x6 frames, raw 124)
// at rest and at full speed: no working current sensor.  Current telemetry
// is ignored unless this is set for an ESC that measures it.
#define WEAPON_ESC_HAS_CURRENT_SENSE   0
// Range bounds for V/I/T at weapon layer
#define WEAPON_TELEM_MAX_VOLTAGE_CV    2520   // 25.2V (2x nominal 3S)
#define WEAPON_TELEM_MIN_VOLTAGE_CV    500    // 5V minimum
#define WEAPON_TELEM_MAX_CURRENT_CA    2000   // 20A (2x motor max 9.9A)
#define WEAPON_TELEM_MAX_TEMP_C        120    // 120C
#define WEAPON_DSHOT_SETUP_RETRY_MS 500  // Retry interval for DShot setup commands (ms)
#define WEAPON_DSHOT_SETUP_MAX_ATTEMPTS 5  // Max setup retries before arming anyway

#ifndef INTEGRATION_TEST_AUTO
#define INTEGRATION_TEST_AUTO 0
#endif

#if INTEGRATION_TEST_AUTO
#undef WEAPON_DSHOT_UPDATE_MS
#undef WEAPON_DSHOT_TELEMETRY_MS
#define WEAPON_DSHOT_UPDATE_MS     2
#define WEAPON_DSHOT_TELEMETRY_MS  20
#endif

#if SERIAL_GAMEPAD
#undef WEAPON_DSHOT_UPDATE_MS
#undef WEAPON_DSHOT_TELEMETRY_MS
#define WEAPON_DSHOT_UPDATE_MS     2
#define WEAPON_DSHOT_TELEMETRY_MS  4
#endif
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
#define BTN_TRIGGER_L       0x0040  // ZL / LT (digital on Switch-class controllers)
#define BTN_TRIGGER_R       0x0080  // ZR / RT
#define BTN_L3              0x0100
#define BTN_R3              0x0200

// Trim Configuration
#define TRIM_STEP           5      // Trim adjustment step size
#define TRIM_MAX            50     // Maximum trim value
#define TRIM_MIN            -50    // Minimum trim value

// Timing Constants
#define MAIN_LOOP_DELAY     10     // Main loop delay in ms (100Hz update)

#if SERIAL_GAMEPAD
#undef MAIN_LOOP_DELAY
#define MAIN_LOOP_DELAY     2      // Faster loop for HITL telemetry capture
#endif
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
