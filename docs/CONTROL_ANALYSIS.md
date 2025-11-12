# Control System Analysis

## Problem Statement

**User feedback:** "The transition from slow speed to fast speed is way too abrupt and it's difficult to control."

This document analyzes the root causes and proposes solutions.

## Root Cause Analysis

### 1. High Power-to-Weight Ratio

**Robot specifications:**
- Weight: ~1 lb (0.454 kg)
- Max thrust: 122 N (stall torque at wheels)
- **Thrust-to-weight ratio:** 122N / (0.454kg × 9.81) = **27:1**

For comparison:
- Racing drones: 3-8:1 thrust-to-weight
- Combat robots: typically 2-5:1
- **This robot:** 27:1 (theoretical, limited by traction)

**Result:** Even with traction limiting actual acceleration to ~5-10 m/s², the robot can reach max speed (2.76 m/s) in **0.3-0.5 seconds**.

### 2. Insufficient Expo Curve

**Current configuration:**
```c
#define DRIVE_EXPO 30  // 30% cubic, 70% linear
```

**Current response curve:**
```
output = input × 0.7 + input³ × 0.3
```

**Sensitivity at various stick positions:**

| Stick Position | Input | Output | Sensitivity (Δout/Δin) |
|----------------|-------|--------|------------------------|
| Center (0%) | 0.00 | 0.00 | 0.70 |
| Small (10%) | 0.10 | 0.07 | 0.67 |
| Quarter (25%) | 0.25 | 0.18 | 0.61 |
| Half (50%) | 0.50 | 0.39 | 0.48 |
| Three-quarter (75%) | 0.75 | 0.65 | 0.36 |
| Full (100%) | 1.00 | 1.00 | 0.25 |

**Problem:** At center stick (where precision is most needed), sensitivity is still **0.70** - meaning a 10% stick movement causes a 7% speed change. With max speed of 2.76 m/s, this is **0.19 m/s or 0.7 km/h per 10% stick**.

### 3. High Gear Ratio with No Feedback

**Gearbox:** 22.6:1 reduction
- Good: High torque, good control authority
- Bad: No encoder feedback, open-loop control only

**Implication:** We're commanding PWM percentages with no knowledge of actual wheel speed or slip.

### 4. Controller Resolution

**Nintendo Switch Pro Controller:**
- Stick range: -512 to +511 (1024 steps)
- After 15-unit deadzone: ~497 steps each direction
- After scaling to ±127: effective resolution ≈ 254 steps

**At 30% expo, center sensitivity:**
- 1 controller step ≈ 0.28% speed change
- At max speed: 1 step ≈ **0.0077 m/s** (7.7 mm/s)

This seems fine, but the issue is the **rate of change** is too fast due to the expo curve shape.

## Current Control Flow

```
Controller Stick (-512 to +511)
    ↓
Deadzone & Scaling (-127 to +127)
    ↓
Expo Curve (30% cubic)
    ↓
Speed Scaling (MAX_DRIVE_SPEED = 100%)
    ↓
Drive Mixing (left/right differential)
    ↓
PWM Output (1000-2000 μs)
    ↓
ESC (linear voltage control)
    ↓
Motor (approximately linear speed)
    ↓
Wheel Speed (0-1220 RPM, 0-2.76 m/s)
```

**Total gain:** High, especially at low speeds where precision is needed.

## Proposed Solutions

### Solution 1: Increase Expo (Simple, Recommended First Step)

**Change:**
```c
#define DRIVE_EXPO 70  // 70% cubic, 30% linear
```

**New response curve:**
```
output = input × 0.3 + input³ × 0.7
```

**New sensitivity:**

| Stick Position | Input | Output | Sensitivity | Improvement |
|----------------|-------|--------|-------------|-------------|
| Center (0%) | 0.00 | 0.00 | 0.30 | **2.3x better** |
| Quarter (25%) | 0.25 | 0.09 | 0.16 | **3.8x better** |
| Half (50%) | 0.50 | 0.24 | 0.21 | **2.3x better** |
| Three-quarter (75%) | 0.75 | 0.54 | 0.44 | 0.8x (slightly less) |
| Full (100%) | 1.00 | 1.00 | 0.93 | 0.4x (less sensitive) |

**Benefits:**
- Much better low-speed control
- Still reaches full speed at full stick
- Simple one-line change

**Drawbacks:**
- Less sensitive at high speeds (may feel sluggish for quick maneuvers)
- Still no rate limiting

### Solution 2: Dual-Rate System (Good for Combat)

**Concept:** Two expo curves selectable by button/trigger

```c
// Normal mode (combat/fast)
#define DRIVE_EXPO_NORMAL 50

// Precision mode (positioning)
#define DRIVE_EXPO_PRECISION 80
#define MAX_SPEED_PRECISION 40  // Limit to 40% of max speed
```

**Implementation:**
- Hold L2/R2 trigger → precision mode active
- Release → normal mode
- Gives operator choice of control style for different situations

**Benefits:**
- Best of both worlds
- Intuitive for operators familiar with RC systems
- Essential for precision weapon aiming in combat

### Solution 3: Acceleration Limiting (Best Control Quality)

**Concept:** Limit rate of velocity change regardless of stick input

```c
#define MAX_ACCELERATION_MPS2 5.0  // 5 m/s² max acceleration
#define CONTROL_LOOP_HZ 100        // 10ms loop time

// In each control loop:
float desired_velocity = calculate_from_stick();
float max_velocity_change = MAX_ACCELERATION_MPS2 * (1.0 / CONTROL_LOOP_HZ);
current_velocity = ramp_toward(desired_velocity, max_velocity_change);
```

**Effect:** Even with abrupt stick movements, velocity ramps smoothly

**Benefits:**
- Prevents jerky motion
- Reduces wheel slip
- More predictable handling
- Easier for operator to learn

**Drawbacks:**
- Adds complexity
- Slight delay in response (may feel "laggy")
- Need to tune acceleration limit

### Solution 4: Custom S-Curve (Advanced)

Instead of simple cubic, use a piecewise curve optimized for this robot:

```c
// Ultra-sensitive at center, aggressive at edges
if (abs(input) < 0.3) {
    // Low speed: very gradual (quartic or quintic)
    output = input × 0.1 + input^5 × 0.9;
} else if (abs(input) < 0.7) {
    // Mid speed: moderate (cubic)
    output = input × 0.3 + input^3 × 0.7;
} else {
    // High speed: more linear
    output = input × 0.6 + input^3 × 0.4;
}
```

**Benefits:**
- Optimized for exact robot characteristics
- Can tune each speed range independently

**Drawbacks:**
- More complex to implement and tune
- Harder to adjust without testing
- May feel inconsistent to operator

### Solution 5: Velocity-Based Control (Most Sophisticated)

**Concept:** Convert control from PWM percentages to actual velocities

```c
// Define control in real units
#define MAX_VELOCITY_MS 2.76   // m/s (measured max speed)
#define MAX_VELOCITY_RPM 1220  // RPM at wheels

// Controller stick maps to desired velocity
float stick_normalized = apply_expo(stick_input);
float desired_velocity = stick_normalized × MAX_VELOCITY_MS;

// With measured PWM→velocity curve, command appropriate PWM
uint16_t pwm = velocity_to_pwm(desired_velocity);
```

**Benefits:**
- Control in meaningful units (m/s, not arbitrary %)
- Can implement velocity-based acceleration limiting
- Foundation for future closed-loop control (with encoders)
- Easier to reason about and tune

**Drawbacks:**
- Requires calibration (PWM → actual velocity mapping)
- More complex implementation
- Still open-loop without encoders

## Recommended Implementation Strategy

### Phase 1: Immediate (Quick Fix)
1. **Increase expo to 70%** - One line change, test immediately
2. **Add debug logging** for velocity calculations (show m/s instead of %)

### Phase 2: Short Term (Best Bang-for-Buck)
1. **Implement dual-rate system** with precision mode
2. **Add acceleration limiting** (start with 5 m/s² limit)
3. **Convert display/debug to real units** (m/s, RPM)

### Phase 3: Medium Term (Optimal Control)
1. **Calibrate PWM→velocity curve** using optical tachometer
2. **Implement velocity-based control** system
3. **Fine-tune acceleration limits** based on testing

### Phase 4: Future (Closed-Loop)
1. Add wheel encoders for velocity feedback
2. Implement PID velocity control
3. Add slip detection and traction control

## Testing Protocol

### Test 1: Expo Tuning
1. Set expo to 50%, drive around, note control feel
2. Increment by 10% (60%, 70%, 80%)
3. Find sweet spot where:
   - Low speeds are controllable
   - High speeds are still responsive
   - Transitions feel smooth

### Test 2: Acceleration Limiting
1. Start with no limit (current behavior)
2. Add 10 m/s² limit (should feel slightly smoother)
3. Reduce to 5 m/s² (should feel noticeably controlled)
4. Try 2 m/s² (may feel too slow)
5. Find balance between control and responsiveness

### Test 3: Dual-Rate Validation
1. Test normal mode in open space (full speed maneuvers)
2. Test precision mode in confined space (slow positioning)
3. Practice switching between modes during operation
4. Verify smooth transition when changing modes

## Calibration Program Design

For collecting actual motor response data with optical tachometer:

### Test Program Requirements
1. Step through PWM values: 1500μs to 2000μs in 50μs increments
2. Hold each value for 3 seconds (allow motor to stabilize)
3. Display current PWM value on LED or serial
4. User measures RPM with optical tachometer, records data
5. Repeat for reverse direction (1500μs to 1000μs)

### Data Collection
Record in CSV format:
```
PWM_us, Measured_RPM_Left, Measured_RPM_Right
1500, 0, 0
1550, 85, 82
1600, 175, 170
...
2000, 1220, 1190
```

### Analysis
1. Plot PWM vs RPM for each motor
2. Check linearity (should be approximately linear for brushed motor)
3. Note any asymmetry between left/right motors
4. Calculate effective deadband size
5. Determine actual max RPM (may be less than theoretical 1220)

### Integration
Use collected data to create accurate PWM→velocity lookup table or curve fit for velocity-based control.

## Summary

**Root cause:** High power-to-weight ratio + insufficient expo = too sensitive at low speeds

**Quick fix:** Increase DRIVE_EXPO from 30 to 70 (2-3x better low-speed control)

**Best solution:** Combo of higher expo + acceleration limiting + dual-rate modes

**Long-term:** Velocity-based control with calibrated curves, eventually add encoders for closed-loop

**Next steps:**
1. Implement higher expo (70-80%) and test
2. Add real-unit conversions (m/s display)
3. Consider adding precision mode button
4. Create calibration program for optical tach data collection
