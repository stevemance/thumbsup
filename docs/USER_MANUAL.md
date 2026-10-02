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
| Drive Motors | 2x brushed DC gearmotors on Pololu DRV8874 H-bridge carriers |
| Weapon Motor | FingerTech Silver Spark F2822-1100KV (brushless, 14 poles) |
| Weapon ESC | AT32F421-based, running AM32 firmware |
| Weapon Protocol | DShot300 with bidirectional EDT telemetry |
| Controller | Bluetooth gamepad via Bluepad32 (Switch Pro, Xbox, PS4/PS5, etc.) |
| Status LEDs | 2x SK6812 addressable RGB LEDs (GRB format) on GP9 |
| Battery | 3S LiPo (11.1V nominal, 12.6V full) |

### Pin Assignments

| Pin | Function |
|-----|----------|
| GP0 / GP1 | Left DRV8874 IN1 / IN2 (20 kHz PWM) |
| GP2 / GP3 | Right DRV8874 IN1 / IN2 |
| GP4 | Weapon motor (UART1 TX / DShot) |
| GP6 | DRV8874 SLEEP (both) |
| GP7 | DRV8874 FAULT (both, input) |
| GP8 | Safety button (optional, active low with pull-up) |
| GP9 | SK6812 status LEDs (2 LEDs) |
| GP26 / GP27 | Left / right motor current sense (ADC0 / ADC1) |
| GP28 | Battery voltage divider, 100k/20k (ADC2) |

Full wiring: docs/HARDWARE_SETUP.md.

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
| Orange | Solid | **Low Battery** - battery below 10.2V (see Battery) |
| Red | Blinking fast | **Critical Battery** - battery below 9.6V |
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
| Safety Test Failure | Red fast blink | Red fast blink |

### Pico W Onboard LED

The built-in LED on the Pico W turns on during boot initialization and turns off
once Bluetooth is ready. It is not used during normal operation.

---

## Driving

Drive uses **split-stick** arcade mixing: the **left stick** is throttle and the
**right stick** is turn, so a turn can be made without touching the throttle and
vice versa. (Compile-time option `DRIVE_LAYOUT_SPLIT 0` restores single-stick.)

### Stick Mapping

| Stick | Direction | Action |
|-------|-----------|--------|
| Left stick Y | Push forward (up) | Drive forward |
| Left stick Y | Pull backward (down) | Drive backward |
| Right stick X | Push right | Turn right |
| Right stick X | Push left | Turn left |

### Drive Parameters

| Parameter | Value |
|-----------|-------|
| Maximum Drive Speed | 75% of motor maximum |
| Maximum Turn Speed | 70% of motor maximum |
| Deadzones (512 raw range) | Throttle 24, turn 32 |
| Expo Curve | Throttle 70% cubic, turn 30% cubic |
| Drive PWM | 20 kHz, slow decay (drive/brake) |
| Stick to motor output | ~0.2 ms after the controller report arrives |
| Zero stick | Brake (wheels stop in well under 150 ms) |
| Acceleration limit | Off (HITL `DRVACCEL`; ramps speed-ups only) |

### Expo Curve

The throttle uses a 70% expo curve: fine control at low stick deflection, full
power at full throw. Turn uses a much flatter 30% curve, so turn rate is close to
proportional to stick position; with 70% expo most of the turn rate sat in the
last fifth of stick travel, which made flick turns overshoot.

### Arcade Mixing

Throttle (left stick Y) and turn (right stick X) are combined:

- **Left motor** = forward + turn
- **Right motor** = forward - turn

If the combined values exceed 100%, both channels are scaled proportionally to
maintain the turn ratio.

### Braking

Centering the stick brakes the wheels: the H-bridge shorts each motor, so the
robot stops in a fraction of the coast distance (on the HITL rig a free wheel
was at 2% of its speed 150 ms after release, against 37% coasting). The amount is
`DRIVE_DRAG_BRAKE_PERMILLE` (100% by default); lower values mix in coasting.

The drive boards are asleep (outputs off, wheels free) until a controller is
connected and ready, and go back to sleep the moment it disconnects.

### Wheel Speed and Wheel Health

The firmware estimates each wheel's speed from the motor's back-EMF (duty,
battery voltage and the drive board's current sense). On the HITL rig it is
within ~0.5 V of the measured back-EMF across the whole speed range, about 5% of
full speed, including while a wheel is accelerating from rest.

From that, each wheel learns how fast it turns for a given power, separately
per direction and speed band. It learns only while the stick is held steady,
and ignores near-stalled readings (pushing, being pinned), so the arena doesn't
look like damage. If one wheel is clearly slower than the other (below 85%,
for more than a second) - typically a damaged or binding gearbox:

- the controller rumbles once (600 ms) and the serial log prints
  `DRV HEALTH motor=<L|R> level=DEGRADED`;
- **speed matching** slows the faster wheel so both turn at the speed the
  stick asks for, and the robot keeps driving straight and turning evenly. Only
  the faster wheel is ever slowed (nothing is boosted). Differences under 3%
  are left alone, and a wheel is never cut below 60% of its command, so a dead
  motor cannot cripple the good side. Top speed drops to what the weak wheel can
  do.

On the rig, with a genuinely damaged right gearbox, matching took the
straight-line wheel-speed mismatch at full stick from 26% to under 5%. The
learned state resets at power-up. It replaces the old manual trim and
linearization calibration.

## Battery

The Pico measures the battery through a 100k/20k divider on GP28 (within 0.4%
on the HITL rig from 9 V to 15 V). The reading is smoothed (5 s), so the sag of
a weapon spin-up doesn't trip an alert.

| Level | Below | Alerts |
|-------|-------|--------|
| Low | 10.2 V (3.4 V/cell) | Controller rumbles twice; one player LED; system LED orange |
| Critical | 9.6 V (3.2 V/cell) | Rumbles three times, repeated every 30 s; outer two player LEDs; system LED red, blinking fast |

A level clears only 0.3 V above its threshold. The controller's player LEDs
otherwise show a gauge: 4 lit at 11.4 V or more, 3 at 10.8 V or more, else 2.

**These are alerts only.** A low battery never stops or limits the drive or
the weapon mid-match. The one rule is that the weapon will not *arm* below
9.6 V.

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
5. Release both triggers, then hold a trigger to spin (see below). A trigger held
   while arming is ignored until it has been released once.

### Arming Will Be Rejected If

- Emergency stop is active.
- Battery voltage is below the low-battery threshold (9.6V).
- The weapon is already in an emergency stop state (must clear E-stop first, then
  re-arm).

### Weapon Speed Control

| Control | Action |
|---------|--------|
| Hold **ZR** (right trigger) | Spin forward at full speed (ramps up over ~1.5 s) |
| Hold **ZL** (left trigger) | Spin in reverse at full speed (3D mode) |
| Release | Weapon spins down |
| Both held | The trigger pressed first wins; releasing it hands over to the other |

The triggers are on/off. After arming, clearing an e-stop, a reconnect or a
controller-signal stall, both triggers must be released before a press spins the
weapon again.

If the weapon ESC stops answering while armed (for example it reset during a
battery sag), the robot recovers it automatically: the weapon stops for about
2-3 seconds while the ESC restarts and re-arms, then spins back up if a trigger
is still held.

### Weapon Telemetry

When armed, the ESC reports telemetry via Extended DShot Telemetry (EDT):

| Field | Description |
|-------|-------------|
| eRPM | Electrical RPM |
| RPM | Mechanical RPM (eRPM / 7 pole pairs) |
| Voltage | ESC input voltage |
| Current | Not available: this ESC has no working current sensor |
| Temperature | ESC MCU temperature (the ESC limits power above 70°C) |

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

After clearing, the drive stays stopped until both drive sticks have returned to
center, and the weapon must be re-armed with the B button (then release and
press a trigger to spin).

---

## Safety System

The safety system runs continuously every 10 ms.

### Safety Checks

| Check | Threshold | Action |
|-------|-----------|--------|
| Battery | Below 9.6V | Weapon arm rejected (nothing is stopped; see Battery) |
| Connection Loss | No input for 1500 ms | Failsafe: all motors stop |
| Safety Violations | 5 cumulative | Emergency stop triggered |
| Boot Self-Test | On power-up | Validates all subsystems |

### Failsafe (Connection Loss)

If the controller stops sending data for 250 ms while the robot is driving or the
weapon is commanded, drive and weapon go to neutral (the weapon trigger must then
be released and pressed again). If it stops for 1500 ms:

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
| Enter | Hold **Minus + Plus** for 1 second |
| Exit | Hold **Minus + Plus** for 1 second again |

While active:
- System LED turns **purple** (pulsing).
- All stick axes, buttons, D-pad, gyroscope, and accelerometer data are displayed
  at 20 Hz.
- All motor outputs are disabled.

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
| Weapon arms, won't spin | Trigger held while arming, or not held | Release both triggers, then hold ZR or ZL |

### ESC Beep Patterns

| Pattern | Meaning |
|---------|---------|
| Continuous beeping (~3 sec interval) | No DShot signal. Normal while the weapon is disarmed: the robot holds the signal low so the ESC always starts its firmware |
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
- Hold ZR (forward) or ZL (reverse) to spin the weapon; release to spin down.
- Throttle with the left stick, turn with the right stick.
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
|  | ^ | Forward           |   |                 Y                 |
|  |   |                   |< >| Turn         X     A               |
|  | v | Reverse           |   |                 B                 |
|  +---+                   +---+               +---+                |
|                                                                   |
|  CONTROLS:                                                        |
|    B              Arm / Disarm weapon (toggle)                    |
|    ZR (hold)      Weapon forward      ZL (hold)  Weapon reverse   |
|    A (hold 2s)    Clear emergency stop                            |
|    L1 + R1        EMERGENCY STOP (immediate)                     |
|    - + + (hold)   Enter/exit controller test mode                 |
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
|    Critical Battery  Red fast blink        ---                    |
|                                                                   |
|  BATTERY (alerts only, never stops the robot):                    |
|    Full 12.6V   Low < 10.2V (2 rumbles)   Critical < 9.6V (3)     |
|    Weapon will not arm below 9.6V                                 |
|                                                                   |
+-------------------------------------------------------------------+
```

---

*ThumbsUp firmware v1.0.0*
