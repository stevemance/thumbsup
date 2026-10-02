# ThumbsUp Hardware Setup Guide

## Complete Pin Configuration

The drive motors run from two Pololu DRV8874 single brushed-DC motor driver
carriers driven directly by the Pico (firmware `DRIVE_HBRIDGE 1`, the default).
The older two-RC-ESC (SAX2) servo wiring is still selectable with
`DRIVE_HBRIDGE 0`, with the pins in the git history.

### Raspberry Pi Pico W Pinout Usage

```
                    ┌─────────┐
  LEFT IN1   ←─ 1  │● GP0   ●│ 40  VBUS (5V from USB)
  LEFT IN2   ←─ 2  │● GP1   ●│ 39  VSYS (5V logic supply)
            GND 3  │●       ●│ 38  GND
  RIGHT IN1  ←─ 4  │● GP2   ●│ 37  3V3_EN
  RIGHT IN2  ←─ 5  │● GP3   ●│ 36  3V3(OUT) ──→ DRV8874 PMODE (both)
 WEAPON DSHOT←─ 6  │● GP4   ●│ 35  ADC_VREF
         (GP5)  7  │●       ●│ 34  GP28 (ADC2) ←── Battery divider
            GND 8  │●       ●│ 33  AGND
  DRV SLEEP  ←─ 9  │● GP6   ●│ 32  GP27 (ADC1) ←── RIGHT current sense
  DRV FAULT  ──→10 │● GP7   ●│ 31  GP26 (ADC0) ←── LEFT current sense
 SAFETY BTN  ──→11 │● GP8   ●│ 30  RUN
 STATUS LEDS ←─ 12 │● GP9   ●│ 29  GP22
                   │   ...   │
 LAT. MARKER ←─ 20 │● GP15  ●│
                    └─────────┘
```
(Physical pin numbers: GP0=1, GP1=2, GP2=4, GP3=5, GP4=6, GP6=9, GP7=10, GP8=11,
GP9=12, GP15=20, GP26=31, GP27=32, GP28=34.)

## Pin Assignments Summary

| GPIO | Function | Direction | Description |
|------|----------|-----------|-------------|
| GP0 | PWM slice 0 A | Output | Left DRV8874 IN1 |
| GP1 | PWM slice 0 B | Output | Left DRV8874 IN2 |
| GP2 | PWM slice 1 A | Output | Right DRV8874 IN1 |
| GP3 | PWM slice 1 B | Output | Right DRV8874 IN2 |
| GP4 | PIO / UART1 TX | Output | Weapon ESC signal (AM32, bidirectional DShot300) |
| GP6 | Digital | Output | nSLEEP, both DRV8874s (high = awake) |
| GP7 | Digital | Input (pull-up) | nFAULT, both DRV8874s (open drain, low = fault) |
| GP8 | Digital | Input (pull-up) | Safety button (optional, `SAFETY_BUTTON_ENABLED`) |
| GP9 | PIO | Output | SK6812 status LEDs (2) |
| GP15 | Digital | Output | HITL latency marker (high while a received report is deflected) |
| GP26 | ADC0 | Input | Left DRV8874 IPROPI (current sense) |
| GP27 | ADC1 | Input | Right DRV8874 IPROPI (current sense) |
| GP28 | ADC2 | Input | Battery divider (100 kΩ / 20 kΩ) |

## DRV8874 Drive Boards

Per carrier:

| Carrier pin | Connection | Why |
|-------------|------------|-----|
| VIN / GND | Battery + / − | Motor supply (UVLO 4.35 V) |
| OUT1 / OUT2 | Motor | Swap these, or set `DRIVE_HB_LEFT/RIGHT_INVERT`, if a wheel runs backwards |
| PMODE | 3V3 | PWM (IN/IN) mode, latched at power-up |
| IN1 / IN2 | GP0/GP1 (left), GP2/GP3 (right) | 20 kHz PWM |
| SLEEP | GP6 (shared) | Drivers off until a controller is connected |
| FAULT | GP7 (shared) | Wired-OR of both open-drain fault outputs |
| VREF | SLEEP (3.3 V when awake) | Current limit: 3.3 V / (450 µA/A × 2.49 kΩ) ≈ 2.9 A per motor |
| CS (IPROPI) | GP26 (left), GP27 (right) | 1.12 V/A on the carrier's 2.49 kΩ |

How the firmware drives them:
- **Slow decay (drive/brake):** forward is IN1 high with IN2 PWM'd. The off part
  of each cycle shorts the motor (brake), so speed is nearly linear in duty.
- **Zero stick brakes** (`DRIVE_DRAG_BRAKE_PERMILLE`, default 100%).
- **SLEEP** stays low until a controller is ready, and drops on disconnect.
- **nFAULT** (undervoltage, overcurrent, overtemperature, and current-limit
  chopping) is counted and logged.
- **The ADC** samples both current senses and the battery divider continuously
  (round robin into a DMA ring). From duty, battery voltage and current, the
  firmware estimates each wheel's speed (back-EMF). The winding resistance
  that estimate needs is measured on every start from rest and, more
  accurately, on every drive→brake transition: just before, the motor draws
  (V − EMF)/R; just after, braked, EMF/R; their sum gives V/R. Peak currents are
  used because the current settles with the motor's ~0.4 ms L/R time
  constant. Re-measuring continuously also tracks the winding as it heats.
- **Wheel health:** each wheel learns how fast it turns for a given duty. A wheel
  clearly slower than the other (a damaged gearbox) is reported (console event +
  controller rumble). The faster wheel is then trimmed so the robot still drives
  straight. See docs/USER_MANUAL.md.

## Battery Divider

```
Battery + ──── 100 kΩ ──┬──── GP28 (ADC2)
                        │
                       20 kΩ
                        │
                       GND
```
Ratio 6.0 (`BATTERY_DIVIDER`): 18 V full scale, so 4S fits. Measured on the HITL
rig: within 0.4% from 9 V to 15 V.

## Safety Button Configuration

### Physical Button
The safety button (GP8) is **OPTIONAL but HIGHLY RECOMMENDED** for:

1. **Diagnostic Mode Entry** (requires special build)
   - Build with -DDIAGNOSTIC_MODE=ON
   - Provides WiFi access point with web dashboard
   - For testing and telemetry monitoring

### Button Wiring
```
    GP8 (Pin 9) ──────┬────── Button ────── GND
                      │
                      └── Internal Pull-up (enabled in code)
```
- Button connects GP8 to GND when pressed
- Internal pull-up resistor keeps pin HIGH when not pressed
- Active LOW logic (pressed = 0, released = 1)

### If No Physical Button
If you choose not to install a safety button:
- The pin will always read HIGH (not pressed) due to pull-up
- Configuration modes won't be accessible
- Runtime safety button feature will be inactive
- System will still function normally otherwise

## LED Indicators

The system uses **2 SK6812 addressable RGB LEDs** on GP9:
- **LED 0**: System Status
- **LED 1**: Weapon Status

### System Status LED (LED 0)
- **Dim Blue**: Booting/initializing
- **Green Solid**: Ready, no controller connected
- **Cyan (Green+Blue)**: Controller connected, normal operation
- **Yellow Blinking**: Failsafe - connection lost
- **Orange Solid**: Low battery warning
- **Orange Blinking**: Critical battery
- **Red Solid/Blinking**: Error or emergency stop
- **Purple Pulse**: Test/diagnostic mode

### Weapon Status LED (LED 1)
- **Off**: Weapon disarmed (safe)
- **Amber/Yellow Blinking**: Arming sequence in progress
- **Orange Solid**: Armed but not spinning
- **Red Solid**: ⚠️ WEAPON SPINNING - DANGER ⚠️
- **Red Fast Blinking**: Emergency stop active

### WiFi LED (Built-in on Pico W)
- **ON during boot**: Initializing
- **OFF after init**: Normal operation (Competition mode)
- **Blinking**: Bluetooth activity
- **Solid ON**: Diagnostic mode active (WiFi AP)

## Power Supply Requirements

### Main Power (3S LiPo)
- **Voltage**: 11.1V nominal (9.0V - 12.6V range)
- **Current**:
  - Drive motors: up to ~2.9A each (DRV8874 current limit set by VREF)
  - Weapon motor: 10-20A peak
  - Logic: 200mA
- **Total**: 30A+ capability recommended
- **Connector**: XT60 recommended

### Logic Power (5V BEC)
- **Source**: a BEC/UBEC (the DRV8874 carriers have no BEC; the old SAX2 drive
  ESCs did)
- **Voltage**: 5V ±5%
- **Current**: 500mA minimum
- **Connection**: VSYS pin (39)

## Diagnostic Mode Connections

When diagnostic mode is enabled (requires special build):

### WiFi Access Point
- **SSID**: `ThumbsUp_Diag`
- **Password**: `combat123`
- **IP**: `192.168.4.1`
- **No additional hardware required**

### Serial Debug (USB)
- Built-in USB CDC for debug output
- 115200 baud, 8N1
- View with any serial terminal

## Recommended Connectors

### Motor/ESC Connections
- **Drive motors**: DRV8874 carrier OUT1/OUT2 screw terminals or solder
- **Weapon ESC**: Solder or bullet connectors for high current

### Board Connections
- **LEDs**: JST-XH 2-pin connectors
- **Safety Button**: JST-XH 2-pin or direct solder
- **Battery Monitor**: JST-XH 3-pin (V+, Signal, GND)

## Wiring Best Practices

### Signal Wires
1. Keep PWM wires away from power wires
2. Use twisted pairs for differential signals if possible
3. Keep wires as short as practical
4. Use ferrite beads on motor wires if RF interference occurs

### Power Wiring
1. Use appropriate gauge wire (14-16 AWG for main power)
2. Keep power and ground wires paired
3. Add capacitors near ESCs (typically included)
4. Ensure solid connections (solder + heat shrink)

### Grounding
1. Star ground configuration recommended
2. Single ground point between power and logic
3. Avoid ground loops
4. Keep high-current grounds separate from signal grounds

## Testing Procedure

### Before First Power-On
1. ✓ Check all connections with multimeter
2. ✓ Verify no shorts between power rails
3. ✓ Confirm correct polarity on all connections
4. ✓ Measure battery voltage (should be 11.1-12.6V)
5. ✓ Verify voltage divider output (<3.3V)

### Initial Power-On
1. Connect USB for serial monitoring
2. Apply logic power only (no motors)
3. Verify all LEDs flash once (power-on test)
4. Check serial output for boot messages
5. Run safety tests (automatic on boot)

### Motor Testing
1. Ensure weapon is removed or secured
2. Prop up robot so wheels don't touch ground
3. Connect controller
4. Test each motor individually at low speed
5. Verify correct direction of rotation

## Troubleshooting

### No LEDs Light Up
- Check VSYS power (should be 5V)
- Verify ground connections
- Check for shorts on power rails

### Safety Tests Fail
- Review serial output for specific failure
- Check battery voltage
- Verify ADC reading is valid
- Ensure button not stuck pressed

### Motors Don't Respond
- Verify PWM signals with oscilloscope/logic analyzer
- Check ESC power and arming
- Confirm controller is paired
- Review failsafe status

### Diagnostic Mode Won't Start
- Ensure safety button is properly wired
- Hold button immediately at power-on
- Check serial output for mode detection
- Verify diagnostic mode is enabled in build

## Safety Warnings

⚠️ **DANGER**: Always remove weapon disk/bar during testing
⚠️ **DANGER**: Never bypass safety systems
⚠️ **WARNING**: Always use proper battery charging practices
⚠️ **CAUTION**: Ensure proper ventilation for ESCs

---

For questions or issues, refer to:
- [User Manual](USER_MANUAL.md)
- [Building Guide](building.md)
- [Diagnostic Mode](DIAGNOSTIC_MODE.md)