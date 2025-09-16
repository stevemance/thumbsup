# Wiring Guide - ThumbsUp Antweight Robot

## Overview

This guide covers the complete wiring setup for the antweight combat robot control system.

## Component List

### Required Components
- Raspberry Pi Pico W
- 3S LiPo Battery (11.1V, 450-850mAh recommended)
- AM32 40A Weapon ESC
- 2-Channel Brushed Drive ESC with 5V BEC
- 1000μF 25V Low-ESR Capacitor
- 10kΩ and 3.3kΩ resistors (for battery monitor)
- 3x 220Ω resistors (for LEDs)
- 3x LEDs (different colors recommended)
- JST/XT30 connectors
- 20-22 AWG silicone wire
- Heat shrink tubing

## Wiring Diagram

```
                          3S LiPo Battery
                                |
                    +-----------+------------+
                    |                        |
            [1000μF Cap]              [Drive ESC Power]
                    |                        |
           [Weapon ESC Power]           [5V BEC Out]
                    |                        |
              [Weapon Motor]            [Pico VSYS]
                                             |
                                        [Pico W Board]
```

## Detailed Connections

### Power Distribution

1. **Main Power Bus**:
   - Battery positive → Drive ESC positive
   - Battery positive → Weapon ESC positive (with capacitor)
   - Battery negative → Common ground bus

2. **5V Power**:
   - Drive ESC BEC 5V → Pico VSYS (pin 39)
   - Drive ESC BEC GND → Pico GND (pin 38)

3. **Capacitor Installation**:
   - 1000μF capacitor across weapon ESC power terminals
   - Mount close to ESC, short leads
   - Observe polarity!

### Signal Connections

| Pico Pin | Connection | Wire Color (suggested) |
|----------|------------|------------------------|
| GP2 | Drive ESC Ch1 Signal | White |
| GP3 | Drive ESC Ch2 Signal | Yellow |
| GP4 | Weapon ESC Signal | Orange |
| GND | All ESC Grounds | Black |

### LED Connections

| Pico Pin | LED Function | Resistor |
|----------|--------------|----------|
| GP5 | Status (Green) | 220Ω |
| GP6 | Armed (Red) | 220Ω |
| GP7 | Battery (Yellow) | 220Ω |
| GND | LED Cathodes | - |

### Battery Monitor

```
Battery+ ──[10kΩ]──┬──[3.3kΩ]── GND
                   │
                  GP26
```

This creates a voltage divider:
- Input: 0-12.6V (3S fully charged)
- Output: 0-3.15V (safe for Pico ADC)

### Optional Safety Button

| Pico Pin | Connection |
|----------|------------|
| GP8 | Safety button (N.O.) |
| 3.3V | Safety button other terminal |

## Step-by-Step Assembly

### Step 1: Prepare the Pico W

1. Solder header pins or direct wires to required GPIO pins
2. Add pull-up resistor for safety button if used
3. Test power input with 5V supply before connecting ESCs

### Step 2: ESC Preparation

1. **Drive ESC**:
   - Remove any unnecessary connectors
   - Extend signal wires to reach Pico
   - Verify BEC output is 5V with multimeter

2. **Weapon ESC**:
   - Program with AM32 configurator first
   - Add capacitor across power terminals
   - Heat shrink exposed connections

### Step 3: Power Wiring

1. Create main power distribution:
   - Use bus bars or solder joints
   - Keep high-current paths short
   - Use appropriate wire gauge (14-16 AWG for main power)

2. Install XT30/XT60 connector for battery
3. Add power switch in battery positive line (optional but recommended)

### Step 4: Signal Wiring

1. Route signal wires away from power wires
2. Twist signal and ground wires together
3. Keep signal wires under 15cm if possible
4. Use servo wire or shielded cable for longer runs

### Step 5: LED Installation

1. Mount LEDs in visible location on robot
2. Use hot glue or LED holders
3. Connect with resistors inline
4. Heat shrink resistor connections

### Step 6: Final Assembly

1. Secure all components:
   - Double-sided tape for Pico
   - Zip ties for ESCs
   - Hot glue for small components

2. Strain relief all connections
3. Protect against vibration
4. Ensure no shorts possible

## Testing Procedure

### Pre-Power Checks

1. **Continuity Test**:
   - Check no shorts between power and ground
   - Verify ground connections
   - Test signal paths

2. **Visual Inspection**:
   - Check all solder joints
   - Verify polarity on all connections
   - Ensure no exposed conductors

### Power-On Sequence

1. Connect battery with motors disconnected
2. Verify:
   - Pico powers on (onboard LED)
   - Status LEDs respond
   - No components getting hot

3. Check voltages:
   - 5V at Pico VSYS
   - 3.3V at Pico 3V3 OUT
   - Battery voltage at monitor pin (scaled)

### Function Test

1. Flash test firmware (blink program)
2. Test each subsystem:
   - PWM output on scope/servo tester
   - LED control
   - Battery monitor readings

3. Connect motors (weapon last)
4. Test with low battery first
5. Gradually increase to full power

## Common Issues and Solutions

| Problem | Possible Cause | Solution |
|---------|---------------|----------|
| Pico won't power on | No 5V supply | Check BEC output and connections |
| ESCs not responding | No common ground | Connect all grounds together |
| Erratic behavior | Noise/interference | Add ferrite beads, separate power/signal |
| LEDs too dim/bright | Wrong resistor value | Recalculate based on LED specs |
| Battery reading wrong | Incorrect divider | Check resistor values and connections |

## Safety Considerations

⚠️ **Important Safety Rules**:

1. **Always** disconnect weapon motor during setup
2. **Never** work on powered circuits
3. **Use** proper battery charging/storage practices
4. **Install** physical power switch for emergency stop
5. **Test** in controlled environment only

## Wire Management Tips

1. **Cable Routes**:
   - Keep power and signal separate
   - Avoid sharp bends
   - Leave service loops

2. **Protection**:
   - Use cable sleeving or spiral wrap
   - Heat shrink all connections
   - Strain relief at connection points

3. **Maintenance Access**:
   - Label all connectors
   - Use removable mounting
   - Document any changes

## Recommended Tools

- Soldering iron (temperature controlled)
- Wire strippers
- Multimeter
- Heat gun
- Crimping tool (for connectors)
- Cable ties and mounts
- Heat shrink assortment
- Flux and solder (60/40 or 63/37)

## Next Steps

After completing wiring:
1. Review main README for firmware setup
2. Configure AM32 ESC settings
3. Perform full system test
4. Practice safety procedures

---

Remember: Take your time with wiring - a good wiring job prevents many problems later!