# Motor Calibration Program

## Purpose

Collect actual motor RPM data at various PWM values using an optical tachometer to:
1. Verify linear ESC response
2. Measure actual max RPM (may differ from theoretical 1220 RPM)
3. Detect differences between left and right motors
4. Determine ESC deadband size
5. Build accurate PWM→velocity lookup table for closed-loop control

## Equipment Required

- Assembled ThumbsUp robot with motors installed
- Optical/laser tachometer (non-contact RPM meter)
- Reflective tape or mark on wheel
- Power supply (3S LiPo battery, fully charged)
- Serial terminal for monitoring
- Spreadsheet or notepad for recording data

## Safety Precautions

⚠️ **IMPORTANT:**
- Robot will be stationary but motors will spin
- Secure robot so wheels are elevated (not touching ground)
- Keep fingers/objects away from spinning wheels
- Motor may get warm during extended testing
- Have emergency stop ready (disconnect battery)

## Test Procedure

### Setup

1. **Prepare wheels for tachometer:**
   - Apply small piece of reflective tape to each wheel
   - OR make a contrasting mark with marker
   - Position should be visible to tachometer

2. **Mount robot:**
   - Place robot on blocks/stand so wheels spin freely
   - Ensure robot is stable and won't tip over
   - Wheels should not contact any surface

3. **Connect power:**
   - Fully charge 3S battery
   - Note battery voltage (should be ~12.6V fully charged)
   - Connect battery to ESC
   - Connect USB for serial monitoring

4. **Activate calibration mode:**
   - Power on robot
   - Press and hold BOTH joysticks (L3+R3) for 3 seconds
   - LEDs will turn PURPLE to indicate calibration mode active
   - Serial output will display: "MOTOR CALIBRATION MODE ACTIVE"

### Data Collection - Forward Direction

The calibration program will step through PWM values automatically:

```
Step 1: PWM = 1500 μs (0%)   → Measure and record RPM
Wait 3 seconds...
Step 2: PWM = 1550 μs (10%)  → Measure and record RPM
Wait 3 seconds...
Step 3: PWM = 1600 μs (20%)  → Measure and record RPM
...
Step 11: PWM = 2000 μs (100%) → Measure and record RPM
```

**For each step:**
1. Point tachometer at LEFT wheel reflective mark
2. Wait for RPM reading to stabilize (~2 seconds)
3. Record RPM value in spreadsheet
4. Point tachometer at RIGHT wheel
5. Record RPM value
6. Program automatically advances to next step

**Record format:**
```
PWM (μs), PWM (%), Left RPM, Right RPM, Notes
1500, 0,  0, 0, "Neutral - wheels should not spin"
1550, 10, 95, 92, ""
1600, 20, 195, 190, ""
...
2000, 100, 1205, 1198, "Max forward speed"
```

### Data Collection - Reverse Direction

After forward sweep completes, program automatically starts reverse:

```
Step 1: PWM = 1500 μs (0%)   → Should stop (neutral)
Step 2: PWM = 1450 μs (-10%) → Measure reverse RPM
Step 3: PWM = 1400 μs (-20%) → Measure reverse RPM
...
Step 11: PWM = 1000 μs (-100%) → Max reverse RPM
```

Repeat measurement procedure for reverse direction.

**Note:** Optical tachometers show RPM as positive value even in reverse. Direction doesn't matter for calibration, just magnitude.

### Exit Calibration Mode

- Press BOTH joysticks (L3+R3) again to exit
- LEDs return to normal color (cyan)
- Robot returns to normal drive mode

## Data Analysis

### 1. Check Linearity

Plot PWM vs RPM for each motor:
- Should be approximately straight line
- Slope indicates motor constant (RPM per volt)
- Y-intercept shows deadband/starting threshold

**Expected (linear ESC):**
```
RPM = (PWM% / 100) × Max_RPM
```

If non-linear, ESC may have built-in curve.

### 2. Compare Left vs Right

- Plot both motors on same graph
- Check for systematic difference
- Small differences (±5%) are normal
- Large differences (>10%) may indicate:
  - Motor mismatch
  - ESC channel difference
  - Mechanical drag difference

### 3. Determine Deadband

- Find PWM range where RPM = 0
- Typical brushed ESC: ±20-50μs around 1500μs
- Affects low-speed control precision

### 4. Measure Actual Max RPM

- May be less than theoretical 1220 RPM due to:
  - Battery voltage under load
  - Motor internal resistance
  - ESC voltage drop
  - Bearing friction

Typical: 90-95% of theoretical (1100-1150 RPM)

### 5. Calculate Actual Max Velocity

```
Actual_Max_Velocity = (Measured_Max_RPM × Wheel_Circumference) / 60
                    = (Measured_Max_RPM × 0.1357 m) / 60 seconds
```

Example: If measured 1150 RPM:
```
Max_Velocity = 1150 × 0.1357 / 60 = 2.60 m/s
```

Update `MAX_VELOCITY_MS` in config.h with measured value.

## Using Calibration Data

### Option 1: Update Constants (Simple)

If motors are reasonably linear and matched:

1. Update `MAX_WHEEL_RPM` with measured max RPM
2. Update `MAX_VELOCITY_MS` with calculated velocity
3. Recompile firmware

This improves accuracy of debug output and future velocity control.

### Option 2: Lookup Table (Accurate)

For more precise control, create lookup table:

```c
// In motor_control.c or new calibration.c file
const uint16_t pwm_rpm_table[] = {
    // PWM μs, Expected RPM
    {1500, 0},
    {1550, 95},
    {1600, 195},
    ...
    {2000, 1205}
};

int16_t pwm_to_rpm(uint16_t pwm_us) {
    // Linear interpolation between table entries
    ...
}
```

### Option 3: Curve Fit (Advanced)

Fit measured data to equation:

```
RPM = A × PWM + B
```

Where:
- A = slope (RPM per μs)
- B = intercept (deadband offset)

Use least-squares fitting to find A and B.

## Troubleshooting

**Motors don't spin in calibration mode:**
- Check battery voltage (must be >11V)
- Verify ESC connections
- Check if robot thinks failsafe is active
- Try power cycling

**RPM readings unstable:**
- Improve contrast of reflective mark
- Move tachometer closer to wheel
- Reduce ambient light interference
- Check for wheel wobble

**Left and right motors very different:**
- Normal: <10% difference
- Check motor connections (polarity)
- Verify both motors same model
- Check for mechanical binding on one wheel

**Max RPM much lower than expected:**
- Check battery voltage under load
- Motor may be lower Kv than spec
- ESC may have current limiting active
- Check for high friction/binding

## Example Data Template

Copy this into spreadsheet before starting:

```
ThumbsUp Motor Calibration Data
Date: ___________
Battery Voltage: ______ V
Motor Model: 030 brushed w/ 22.6:1 gearbox
ESC Model: Kingmodel SAX2 5Ax2

Forward Direction:
PWM(μs), PWM(%), Left RPM, Right RPM, Left Notes, Right Notes
1500, 0, , , ,
1550, 10, , , ,
1600, 20, , , ,
1650, 30, , , ,
1700, 40, , , ,
1750, 50, , , ,
1800, 60, , , ,
1850, 70, , , ,
1900, 80, , , ,
1950, 90, , , ,
2000, 100, , , ,

Reverse Direction:
PWM(μs), PWM(%), Left RPM, Right RPM, Left Notes, Right Notes
1500, 0, , , ,
1450, -10, , , ,
1400, -20, , , ,
1350, -30, , , ,
1300, -40, , , ,
1250, -50, , , ,
1200, -60, , , ,
1150, -70, , , ,
1100, -80, , , ,
1050, -90, , , ,
1000, -100, , , ,

Observations:
- Deadband size (neutral range): _______ μs
- Max forward RPM (average): _______ RPM
- Max reverse RPM (average): _______ RPM
- Left/Right difference: _______ %
- Calculated max velocity: _______ m/s
- Motor temperature after test: _______ °C (if measured)
```

## Future Enhancements

With calibration data collected, you can implement:

1. **Accurate velocity control:** Command in m/s instead of PWM %
2. **Velocity profiling:** Smooth acceleration curves
3. **Motor matching:** Compensate for left/right differences
4. **Deadband compensation:** Improve low-speed linearity
5. **Temperature derating:** Reduce max speed if motors get hot

This data is the foundation for transitioning from open-loop PWM control to true velocity-based control.
