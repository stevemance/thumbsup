# ThumbsUp Combat Robot - User Manual

**Firmware Version 1.0.0**

---

## Table of Contents

1. [Overview](#overview)
2. [Hardware Summary](#hardware-summary)
3. [Controller Pairing](#controller-pairing)
4. [Status LEDs](#status-leds)
5. [Driving](#driving)
6. [Weapon Control](#weapon-control)
7. [Emergency Stop](#emergency-stop)
8. [Safety System](#safety-system)
9. [Special Modes](#special-modes)
10. [ESC Configuration](#esc-configuration)
11. [Troubleshooting](#troubleshooting)
12. [Competition Checklist](#competition-checklist)
13. [Quick Reference Card](#quick-reference-card)

---

## Overview

ThumbsUp is a Bluetooth-controlled combat robot built on the Raspberry Pi Pico W
(RP2040). It uses a Bluetooth gamepad for control and communicates with its weapon
ESC over the DShot300 digital protocol with bidirectional telemetry.

The robot has two drive motors (left/right, arcade-style mixing) and one brushless
weapon motor controlled through an AM32 ESC.

---

## Hardware Summary

| Component | Detail |
|-----------|--------|
| MCU | Raspberry Pi Pico W (RP2040, dual-core ARM Cortex-M0+) |
| Drive Motors | 2x brushed DC (PWM control) |
| Weapon Motor | FingerTech Silver Spark F2822-1100KV (brushless, 14 poles) |
| Weapon ESC | AT32F421-based, running AM32 firmware |
| Weapon Protocol | DShot300 with bidirectional EDT telemetry |
| Controller | Bluetooth gamepad via Bluepad32 (Switch Pro, Xbox, PS4/PS5, etc.) |
| Status LEDs | 2x SK6812 addressable RGB LEDs (GRB format) on GP28 |
| Battery | 3S LiPo (11.1V nominal, 12.6V full) |

### Pin Assignments

| Pin | Function |
|-----|----------|
| GP0 | Left drive motor PWM |
| GP1 | Right drive motor PWM |
| GP4 | Weapon motor (UART1 TX / DShot) |
| GP28 | SK6812 status LEDs (2 LEDs) |
| GP8 | Safety button (optional, active low with pull-up) |
| GP26 | Battery voltage monitor (ADC0, optional) |

---

## Controller Pairing

ThumbsUp uses the Bluepad32 library and supports most Bluetooth gamepads:

- Nintendo Switch Pro Controller (primary tested controller)
- Xbox Wireless Controller
- PlayStation DualShock 4 / DualSense
- 8BitDo controllers
- Generic Bluetooth HID gamepads

### Pairing Procedure

1. **Power on** the robot. The system LED (LED 0) will pulse **dim blue** during
   boot.
2. The LED changes to **solid green** when the robot is ready and scanning for
   controllers.
3. Put your controller into **pairing mode**:
   - *Switch Pro*: Hold the small button on the back near the USB port.
   - *Xbox*: Hold the pairing button on top.
   - *PS4/PS5*: Hold Share + PS button simultaneously.
4. When connected, the system LED turns **solid cyan** (green-blue).
5. A brief **neutral guard** activates: the robot waits ~500 ms for all sticks to
   be centered before accepting input. This prevents accidental motion from
   transient axis values during pairing.
6. The robot is now ready to drive.

After the first controller connection, the hardware watchdog is enabled. If the
firmware hangs, the watchdog will automatically reboot the system.

---

## Status LEDs

ThumbsUp has two SK6812 addressable LEDs that provide at-a-glance status.

- **LED 0** (System LED): Overall system state.
- **LED 1** (Weapon LED): Weapon state.

### System LED (LED 0)

| Color | Effect | Meaning |
|-------|--------|---------|
| Dim Blue | Pulsing | **Booting** - firmware is initializing |
| Green | Solid | **Ready** - waiting for controller connection |
| Cyan (green-blue) | Solid | **Connected** - controller paired and active |
| Yellow | Blinking fast | **Failsafe** - controller connection lost |
| Orange | Solid | **Low Battery** - battery below 9.6V |
| Red | Solid | **Critical Battery** - battery below 9.0V |
| Red | Solid | **Error** - safety violation detected |
| Red | Blinking fast | **Emergency Stop** - E-stop active |
| Purple | Pulsing | **Test Mode** - controller test mode active |

### Weapon LED (LED 1)

| Color | Effect | Meaning |
|-------|--------|---------|
| Off | - | **Disarmed** - weapon is safe |
| Yellow/Amber | Solid | **Arming** - ESC arm sequence in progress |
| Orange | Solid | **Armed** - weapon ready, not spinning |
| Red | Solid | **Spinning** - weapon motor active |
| Red | Blinking fast | **Emergency Stop** - weapon E-stopped |

### Special Mode LED Patterns

| Mode | LED 0 | LED 1 |
|------|-------|-------|
| Calibration Mode | Purple/Cyan alternating | Purple/Cyan alternating |
| Calibration Complete | Green slow blink | Green slow blink |
| Trim Mode | Teal solid | Teal solid |
| Trim: Sample Captured | Bright green flash (750 ms) | - |
| Trim: Sample Removed | Bright red flash (750 ms) | - |
| Trim: Fitting Curves | Orange pulsing | - |
| Safety Test Failure | Red fast blink | Red fast blink |

### Pico W Onboard LED

The built-in LED on the Pico W turns on during boot initialization and turns off
once Bluetooth is ready. It is not used during normal operation.

---

## Driving

Drive uses **arcade-style mixing** on the **left analog stick**.

### Left Stick Mapping

| Axis | Direction | Action |
|------|-----------|--------|
| Y-axis | Push forward (up) | Drive forward |
| Y-axis | Pull backward (down) | Drive backward |
| X-axis | Push right | Turn right |
| X-axis | Push left | Turn left |
| Diagonal | Any combination | Combined driving and turning |

### Drive Parameters

| Parameter | Value |
|-----------|-------|
| Maximum Drive Speed | 75% of motor maximum |
| Maximum Turn Speed | 70% of motor maximum |
| Stick Deadzone | 15 (out of 512 raw range) |
| Expo Curve | 70% cubic |

### Expo Curve

The 70% expo curve provides fine control at low stick deflections while preserving
full power at the extremes. At 50% stick, the actual output is much lower than 50%,
making precise maneuvering easier. Full-throw still reaches full speed.

### Arcade Mixing

The left stick Y-axis controls forward/backward speed and the X-axis controls
turning. These are combined:

- **Left motor** = forward + turn
- **Right motor** = forward - turn

If the combined values exceed 100%, both channels are scaled proportionally to
maintain the turn ratio.

### Motor Linearization

The firmware includes a motor linearization system that compensates for non-linear
ESC response and left/right motor asymmetry. This uses calibrated power-law curves
(RPM = a * sqrt(throttle - deadband)) to ensure that equal stick input produces
equal wheel speeds on both sides.

---

## Weapon Control

The weapon uses DShot300 digital protocol with bidirectional telemetry to control a
brushless motor through an AM32 ESC.

### Arming and Disarming

| Action | Control |
|--------|---------|
| **Arm weapon** | Press **B** button |
| **Disarm weapon** | Press **B** button again |

### Arming Sequence

1. Press B. The weapon LED turns **yellow/amber** (arming).
2. The firmware sends DShot throttle-zero for ~2 seconds to arm the ESC.
3. A direction-change prime sequence is sent (required for AM32 3D mode startup).
4. The weapon LED turns **orange** (armed, not spinning).
5. Use the right stick to control weapon speed.

### Arming Will Be Rejected If

- Emergency stop is active.
- Battery voltage is below the low-battery threshold (9.6V).
- The weapon is already in an emergency stop state (must clear E-stop first, then
  re-arm).

### Weapon Speed Control

| Control | Action |
|---------|--------|
| Right Stick Y forward (up) | Increase weapon speed (forward spin) |
| Right Stick Y backward (down) | Reverse weapon spin (3D mode) |
| Right Stick centered | Weapon at idle (0% throttle while armed) |

The weapon uses **bidirectional (3D mode)** throttle:

| Stick Position | DShot Range | Direction |
|----------------|-------------|-----------|
| Centered (0%) | 0 (idle) | Stopped |
| Forward +1% to +100% | 1048-2047 | Forward spin |
| Backward -1% to -100% | 48-1047 | Reverse spin |

A deadzone threshold is applied to the right stick to prevent accidental weapon
activation.

### Weapon Telemetry

When armed, the ESC reports telemetry via Extended DShot Telemetry (EDT):

| Field | Description |
|-------|-------------|
| eRPM | Electrical RPM |
| RPM | Mechanical RPM (eRPM / 7 pole pairs) |
| Voltage | ESC input voltage |
| Current | Motor current draw |
| Temperature | ESC temperature |

Telemetry is visible on the USB serial console.

---

## Emergency Stop

### Triggering Emergency Stop

**Press both shoulder buttons simultaneously: L1 + R1.**

When triggered:
- All motors immediately stop (drive and weapon).
- Both LEDs flash **red rapidly**.
- All further motor input is blocked.
- The weapon is disarmed.

### Clearing Emergency Stop

**Press and hold the A button for 2 seconds.**

1. Press and hold A.
2. After 2000 ms of continuous hold, the E-stop clears.
3. System LED returns to **cyan** (connected).
4. Weapon LED returns to **off** (disarmed).
5. If A is released early, the clear is cancelled.

After clearing, the weapon must be re-armed with the B button.

---

## Safety System

The safety system runs continuously every 10 ms.

### Safety Checks

| Check | Threshold | Action |
|-------|-----------|--------|
| Battery Low | Below 9.6V | System LED orange; weapon arm rejected |
| Battery Critical | Below 9.0V | System LED red; weapon disarmed |
| Connection Loss | No input for 1500 ms | Failsafe: all motors stop |
| Safety Violations | 5 cumulative | Emergency stop triggered |
| Boot Self-Test | On power-up | Validates all subsystems |

### Failsafe (Connection Loss)

If the controller stops sending data for 1500 ms:

1. All drive motors stop.
2. The weapon is disarmed.
3. System LED turns **yellow** (blinking fast).
4. When the controller reconnects, the neutral guard reactivates (sticks must be
   centered before motion resumes).

### Boot Safety Test

On power-up, the firmware runs a self-test. If it fails:

- Both LEDs flash **red rapidly**.
- "CRITICAL SAFETY FAILURE - DO NOT OPERATE" is printed to USB serial.
- The system halts permanently. The robot will not respond to any input.
- Power cycle is required after resolving the issue.

---

## Special Modes

### Controller Test Mode

**Purpose:** Displays raw controller input on USB serial for debugging.

| Action | Control |
|--------|---------|
| Enter | Hold both shoulder buttons (L + R) for 1 second |
| Exit | Hold both shoulder buttons (L + R) for 1 second again |

While active:
- System LED turns **purple** (pulsing).
- All stick axes, buttons, D-pad, gyroscope, and accelerometer data are displayed
  at 20 Hz.
- All motor outputs are disabled.

### Trim Calibration Mode

**Purpose:** Captures drive samples to calibrate motor trim correction, fixing the
robot pulling to one side during straight-line driving.

| Action | Control |
|--------|---------|
| Enter | Hold **D-pad Up + D-pad Right** for 2 seconds |
| Exit | Hold **D-pad Up + D-pad Right** for 2 seconds again |
| Capture sample | Press **A** while driving |
| Remove last sample | Press **B** |

While active:
- Both LEDs turn **teal** (solid).
- Full driving is enabled. Drive in a straight line, then press A to capture a
  sample.
- Minimum 5 samples required for a valid calibration.
- On exit, the firmware fits trim correction curves and saves to flash.
- Trim data persists across power cycles.
- Weapon is kept disarmed during trim mode.

### Motor Calibration Mode

**Purpose:** Steps through predefined throttle levels for measuring motor RPM with
an external tachometer.

| Action | Control |
|--------|---------|
| Enter | Hold **X + Y** buttons for 1 second |
| Exit | Hold **X + Y** buttons for 1 second again |
| Next step | Press **A** |
| Repeat step | Press **B** |

While active:
- LEDs alternate **purple** and **cyan** every 500 ms.
- Each step applies a specific PWM percentage to both drive motors.
- Instructions and expected values are printed to USB serial.

**Ensure wheels are elevated and the robot is secured before entering this mode.**

---

## ESC Configuration

The AM32 ESC can be configured at boot via the physical safety button.

### Entering ESC Config Mode

1. Wire the safety button to GP8 (active low, internal pull-up enabled).
2. Hold the safety button while powering on the robot.
3. A menu appears on USB serial:

```
AM32 Configuration Mode

Options:
1. Press 'C' to configure ESC
2. Press 'P' for passthrough mode
3. Press 'T' for throttle calibration
4. Press 'D' to apply defaults
5. Press any other key to exit
```

### Configuration Options

| Key | Function |
|-----|----------|
| **C** | Write weapon-optimized settings to ESC and save |
| **P** | Passthrough: connects USB serial directly to ESC for use with the AM32 web configurator at am32.ca |
| **T** | Runs ESC throttle calibration sequence |
| **D** | Apply and save default weapon settings |
| Other | Exit config mode, continue to normal operation |

### Default Weapon ESC Settings

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Motor Poles | 14 | FingerTech F2822 motor |
| Current Limit | 10A | Motor rated max is 9.9A |
| Temperature Limit | 140 C | AM32 standard |
| Startup Power | 100% | Reliable starts under load |
| 3D Mode | Enabled | Bidirectional weapon spin |
| Stuck Rotor Protection | Off | Avoid false trips in combat |
| Low-Voltage Cutoff | Off | Handled by firmware battery monitor |

---

## Troubleshooting

### LED Diagnostics

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| No LEDs at all | No power | Check USB or battery connection |
| Blue pulsing forever | Boot stalled | Check USB serial for errors |
| Green, never cyan | Controller not pairing | Put controller in pairing mode |
| Yellow blinking | Connection lost | Reconnect controller; check range |
| Orange system LED | Low battery | Charge battery (below 9.6V) |
| Red system LED | Critical battery or error | Charge battery; check serial log |
| Both LEDs red fast blink | Emergency stop | Hold A for 2 sec to clear |
| B press ignored | E-stop active or low battery | Clear E-stop; check battery |
| Weapon arms, won't spin | Right stick not moved | Push right stick forward |

### ESC Beep Patterns

| Pattern | Meaning |
|---------|---------|
| Continuous beeping (~3 sec interval) | No DShot signal or update rate too slow |
| Single tone on power-up | ESC armed successfully |
| Silent during operation | Normal (ESC receiving valid throttle) |
| Beeping during throttle | Error: check DShot wiring or ESC config |

### USB Serial Console

Connect via USB for diagnostic output (USB CDC, auto-detected baud rate). The
firmware prints:

- Boot status and firmware version
- Controller connect/disconnect events
- Drive and weapon commands (logged every 500 ms when active)
- DShot telemetry (RPM, voltage, current, temperature)
- Safety violations and emergency stop events

---

## Competition Checklist

### Pre-Match

- [ ] Battery fully charged (12.6V)
- [ ] Robot powered on, safety tests pass (LEDs not red)
- [ ] Controller paired (system LED cyan)
- [ ] Drive tested (both directions)
- [ ] Weapon arm/disarm tested (B button)
- [ ] Emergency stop tested (L1 + R1, then hold A to clear)
- [ ] Weapon guard removed

### During Match

- Arm weapon with B when match starts.
- Control weapon speed with right stick.
- Drive with left stick.
- Monitor system LED for battery warnings.

### Post-Match

- [ ] Disarm weapon (B button)
- [ ] Wait for weapon to fully stop
- [ ] Verify weapon LED is off
- [ ] Power off robot
- [ ] Install weapon guard
- [ ] Inspect for damage

---

## Quick Reference Card

```
+-------------------------------------------------------------------+
|                   ThumbsUp Controller Map                         |
+-------------------------------------------------------------------+
|                                                                   |
|  Left Stick              Right Stick         Face Buttons         |
|  +---+                   +---+               +---+                |
|  | ^ | Forward           | ^ | Weapon Fwd      Y                 |
|  |< >| Turn              |   |              X     A               |
|  | v | Reverse           | v | Weapon Rev      B                 |
|  +---+                   +---+               +---+                |
|                                                                   |
|  CONTROLS:                                                        |
|    B              Arm / Disarm weapon (toggle)                    |
|    A (hold 2s)    Clear emergency stop                            |
|    L1 + R1        EMERGENCY STOP (immediate)                     |
|    L + R (hold)   Enter/exit controller test mode                 |
|    X + Y (hold)   Enter/exit motor calibration mode               |
|    D-Up+Right     Enter/exit trim mode (hold 2s)                  |
|                                                                   |
|  STATUS LEDs:        System (LED 0)       Weapon (LED 1)          |
|    Boot              Blue pulse            Off                    |
|    Ready             Green solid           Off                    |
|    Connected         Cyan solid            Off                    |
|    Weapon Armed      Cyan solid            Orange solid           |
|    Weapon Spinning   Cyan solid            Red solid              |
|    E-Stop            Red fast blink        Red fast blink         |
|    Failsafe          Yellow blink          Off                    |
|    Low Battery       Orange solid          ---                    |
|                                                                   |
|  BATTERY:                                                         |
|    Full        12.6V    Normal       11.1V                        |
|    Low         9.6V     Critical     9.0V                         |
|                                                                   |
+-------------------------------------------------------------------+
```

---

*ThumbsUp firmware v1.0.0*
