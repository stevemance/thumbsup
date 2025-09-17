# ThumbsUp Hardware Setup Guide

## Complete Pin Configuration

### Raspberry Pi Pico W Pinout Usage

```
                    ┌─────────┐
          (GP0)  1  │●       ●│ 40  VBUS (5V from USB)
          (GP1)  2  │●       ●│ 39  VSYS (5V from BEC) ←── ESC BEC Power
     LEFT PWM ←─ 3  │● GP2   ●│ 38  GND
    RIGHT PWM ←─ 4  │● GP3   ●│ 37  3V3_EN
   WEAPON PWM ←─ 5  │● GP4   ●│ 36  3V3(OUT)
   STATUS LED ←─ 6  │● GP5   ●│ 35  ADC_VREF
    ARMED LED ←─ 7  │● GP6   ●│ 34  GP28 (ADC2)
  BATTERY LED ←─ 8  │● GP7   ●│ 33  AGND
 SAFETY BUTTON ←─ 9  │● GP8   ●│ 32  GP27 (ADC1)
          (GP9) 10  │●       ●│ 31  GP26 (ADC0) ←── Battery Monitor
         (GP10) 11  │●       ●│ 30  RUN
         (GP11) 12  │●       ●│ 29  GP22
         (GP12) 13  │●       ●│ 28  GND
         (GP13) 14  │●       ●│ 27  GP21
            GND 15  │●       ●│ 26  GP20
         (GP14) 16  │●       ●│ 25  GP19
         (GP15) 17  │●       ●│ 24  GP18
         (GP16) 18  │●       ●│ 23  GND
         (GP17) 19  │●       ●│ 22  GP17
            GND 20  │●       ●│ 21  GP16
                    └─────────┘
```

## Pin Assignments Summary

| GPIO | Pin# | Function | Direction | Description | Wire Color (Suggested) |
|------|------|----------|-----------|-------------|----------------------|
| GP2 | 3 | PWM | Output | Left Drive Motor Signal | Yellow |
| GP3 | 4 | PWM | Output | Right Drive Motor Signal | Orange |
| GP4 | 5 | PWM | Output | Weapon Motor Signal (AM32 ESC) | Red |
| GP5 | 6 | Digital | Output | Status LED (Blue) | Blue |
| GP6 | 7 | Digital | Output | Armed LED (Red) | Red |
| GP7 | 8 | Digital | Output | Battery LED (Green/Yellow/Red) | Green |
| GP8 | 9 | Digital | Input (Pull-up) | Safety Button | White |
| GP26 | 31 | ADC0 | Input | Battery Voltage Monitor | Brown |

## Safety Button Configuration

### Physical Button
The safety button (GP8) is **OPTIONAL but HIGHLY RECOMMENDED** for:

1. **Configuration Mode Entry**
   - Hold during power-on to enter AM32 ESC configuration mode
   - Used to configure weapon ESC settings

2. **Diagnostic Mode Entry** (when enabled in build)
   - Hold for 3 seconds during boot to enter WiFi diagnostic mode
   - Provides web dashboard for testing and monitoring

3. **Runtime Safety**
   - Press during operation to immediately disarm weapon
   - Part of the safety violation monitoring system

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

### Status LED (GP5 - Blue)
- **Solid ON**: System operational
- **Slow Blink (1Hz)**: Waiting for controller
- **Fast Blink (5Hz)**: Emergency stop / Failsafe active
- **OFF**: System not ready

### Armed LED (GP6 - Red)
- **Solid ON**: ⚠️ WEAPON ARMED - DANGER ⚠️
- **OFF**: Weapon safe/disarmed

### Battery LED (GP7 - Multi-color or Green)
- **Solid GREEN**: Battery good (>11.1V)
- **Blinking YELLOW**: Battery low (10.5-11.1V)
- **Fast Blinking RED**: Battery critical (<10.5V)
- **OFF**: No power

### WiFi LED (Built-in on Pico W)
- **ON during boot**: Initializing
- **OFF after init**: Normal operation (Competition mode)
- **Blinking**: Bluetooth activity
- **Solid ON**: Diagnostic mode active (WiFi AP)

## Battery Monitoring Circuit

### Voltage Divider for 3S LiPo (12.6V max)
```
Battery + ─────┬───── R1 (10kΩ) ────┬───── GP26 (ADC0)
               │                     │
               │                     ├───── R2 (4.7kΩ) ───── GND
               │                     │
               └─────────────────────┴───── C1 (100nF) ───── GND
```

### Component Values
- **R1**: 10kΩ (1% tolerance recommended)
- **R2**: 4.7kΩ (1% tolerance recommended)
- **C1**: 100nF ceramic (filtering)
- **Divider Ratio**: 4.7/(10+4.7) = 0.32
- **Max Input**: 12.6V × 0.32 = 4.03V (safe for 3.3V ADC)

### Calibration
The firmware uses these constants (in config.h):
```c
#define BATTERY_DIVIDER     3.13  // Voltage divider ratio
#define BATTERY_ADC_SCALE   3.3   // ADC reference voltage
```
Adjust `BATTERY_DIVIDER` if your resistor values differ.

## Power Supply Requirements

### Main Power (3S LiPo)
- **Voltage**: 11.1V nominal (9.0V - 12.6V range)
- **Current**:
  - Drive motors: 2-3A peak each
  - Weapon motor: 10-20A peak
  - Logic: 200mA
- **Total**: 30A+ capability recommended
- **Connector**: XT60 recommended

### Logic Power (5V BEC)
- **Source**: ESC BEC or separate UBEC
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
- **Drive ESCs**: 3-pin servo connectors (0.1" pitch)
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