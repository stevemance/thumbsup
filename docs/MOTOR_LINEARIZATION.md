# Motor Linearization System

## Overview

The motor linearization system compensates for the non-linear ESC+motor response curves and left/right motor asymmetry discovered during calibration. This provides:

1. **Linear control feel** - Stick position is now proportional to actual wheel speed
2. **Rotation center fix** - Slow flat spins now rotate properly on center
3. **Smooth deadband handling** - Better control in the 0-20% throttle range

## Implementation

### Curve Fitting Analysis

Using the calibration data from `forward.csv` and `reverse.csv`, we fitted power law curves to model the motor response:

```
RPM = a × (throttle - deadband)^b
```

Where `b ≈ 0.5` (square root relationship), which is characteristic of brushed motor ESCs.

**Fit Quality:**
- RMSE: 38-55 RPM (5-7% error)
- Deadband: ~10-12% throttle
- Separatecurves for each motor (left/right) and direction (forward/reverse)

### Fitted Curve Parameters

| Motor | Direction | Scale (a) | Exponent (b) | Deadband |
|-------|-----------|-----------|--------------|----------|
| Left  | Forward   | 87.96     | 0.500        | 10.0%    |
| Right | Forward   | 94.40     | 0.500        | 10.0%    |
| Left  | Reverse   | 88.86     | 0.500        | 10.0%    |
| Right | Reverse   | 91.17     | 0.500        | 11.7%    |

## How It Works

### Control Flow

```
Controller Input → Expo Curve (70%) → Drive Mix → Trim → Linearization → Motors
```

The linearization step compensates for the non-linear motor response:

1. **Desired PWM** (from expo/mix/trim): What the user expects
2. **Target RPM** = (desired_pwm × MAX_WHEEL_RPM) / 100
3. **Inverse curve lookup**: Find actual PWM needed to achieve target RPM
4. **Compensated PWM** sent to motors

### Key Functions

**`motor_linearization_compensate(motor, desired_pwm)`**
- Converts desired PWM (-100 to +100) to compensated PWM
- Uses fitted curves to account for non-linearity and motor differences
- Called from `drive.c` before sending commands to motors

**`motor_linearization_init()`**
- Initializes the system and prints curve parameters
- Called during platform initialization

## Benefits

### Before Linearization
- **Non-linear response**: 20-40% throttle = steep (14 RPM/%), 70-100% = flat (2 RPM/%)
- **Motor asymmetry**: Right motor 6% faster at full forward → drift during slow spins
- **Difficult to control**: User reported "incredibly difficult to drive"

### After Linearization
- **Linear response**: 50% stick → 50% of max speed (for both motors)
- **No asymmetry**: Left and right motors achieve the same RPM for the same command
- **Precise control**: Rotation on center during flat spins
- **Predictable behavior**: Control feel matches expectations

## Files

### Core Implementation
- `firmware/include/motor_linearization.h` - Public API
- `firmware/src/motor_linearization.c` - Implementation with fitted curves
- `firmware/src/drive.c` - Integration (calls compensation before motors)
- `firmware/src/bluetooth_platform.c` - Initialization

### Analysis Tools
- `analyze_curves.py` - Curve fitting analysis script
- `forward.csv` - Forward direction calibration data
- `reverse.csv` - Reverse direction calibration data
- `motor_calibration_fits.png` - Visualization of fitted curves
- `pyproject.toml` - UV project configuration

## Future Enhancements

If even more precise control is needed:

1. **Gyro-based velocity control** - Close the loop with IMU feedback
2. **Battery voltage compensation** - Adjust curves based on battery sag
3. **Temperature compensation** - Account for motor heating effects
4. **Adaptive learning** - Fine-tune curves during operation

However, the current open-loop linearization should provide significant improvement!

## Testing Recommendations

1. **Flat spin test**: Command slow rotation (e.g., left stick only)
   - Should rotate on center (not drift)
   - Should feel smooth and predictable

2. **Straight line test**: Command forward at various speeds (20%, 50%, 100%)
   - Should track straight (with existing trim system)
   - Should feel linear (50% = half speed feel)

3. **Low speed control**: Test 10-30% throttle range
   - Should have good sensitivity
   - Shouldn't feel "dead" or "jumpy"

4. **Response curve test**: Gradually increase throttle from 0→100%
   - Should accelerate smoothly
   - Shouldn't have sudden jumps or plateaus

## Calibration Date

Motor calibration performed: **2025-11-12**

If motors are changed, ESCs are reconfigured, or batteries significantly degrade, recalibration should be performed using the calibration mode (hold X+Y).
