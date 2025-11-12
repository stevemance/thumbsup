# Turning Dynamics Analysis

## Robot Geometry

```
Wheelbase (center-to-center): 86mm
Wheel diameter: 43.2mm
Configuration: Differential drive (tank-style)
Front: Sliding contact (no third wheel)
```

## Differential Drive Turning

### How Differential Drive Works

A two-wheeled differential drive robot turns by varying the speed of left and right wheels:

```
Forward motion:   L=100%  R=100%  →  Straight ahead
Gentle right turn: L=100%  R=50%   →  Arcs to the right
Sharp right turn:  L=100%  R=0%    →  Pivots around right wheel
Spin right:        L=100%  R=-100% →  Spins clockwise in place
```

### Turn Radius Calculation

For a differential drive robot:

```
Turn radius R = (wheelbase / 2) × (V_left + V_right) / (V_right - V_left)
```

Where:
- wheelbase = 86mm = 0.086m
- V_left, V_right = wheel velocities in m/s

**Special cases:**

1. **Pivot turn** (one wheel stopped):
   ```
   If V_right = 0, V_left = 2.76 m/s:
   R = wheelbase / 2 = 43mm (minimum turn radius)
   ```

2. **Spin in place** (wheels opposite):
   ```
   If V_left = 2.76 m/s, V_right = -2.76 m/s:
   R = 0 (pure rotation, no forward motion)
   ```

3. **Gentle turn** (both wheels forward, one slower):
   ```
   If V_left = 2.76 m/s, V_right = 1.38 m/s:
   R = 0.043 × (2.76 + 1.38) / (1.38 - (-2.76))
   R = 0.043 × 4.14 / 4.14 = 0.086m = 86mm
   ```

## Angular Velocity (Rotation Speed)

The robot's rotation rate is determined by the difference in wheel speeds:

```
ω = (V_right - V_left) / wheelbase
```

### Examples:

**Maximum spin (full stick deflection):**
```
V_left = +2.76 m/s (forward)
V_right = -2.76 m/s (reverse)

ω = (-2.76 - 2.76) / 0.086
  = -5.52 / 0.086
  = -64.2 rad/s
  = -3680 deg/s
  = -10.2 revolutions per second
  = -613 RPM (body rotation rate!)
```

**Time for 360° spin at maximum:**
```
Time = 360° / 3680 deg/s = 0.098 seconds = 98 milliseconds
```

**This robot can spin a full circle in less than 0.1 second!**

**Half-speed spin:**
```
V_left = +1.38 m/s
V_right = -1.38 m/s

ω = (-1.38 - 1.38) / 0.086 = -32.1 rad/s = -1840 deg/s
Time for 360° = 196 ms (still very fast!)
```

**Gentle turn (50% turn input while moving forward):**
```
Forward: 100% = 2.76 m/s
Turn: 50% → left gets +50%, right gets -50%

V_left = 2.76 × 1.5 = 4.14 m/s (but clamped to 2.76 m/s)
V_right = 2.76 × 0.5 = 1.38 m/s

ω = (1.38 - 2.76) / 0.086 = -16.0 rad/s = -917 deg/s

Turn radius = 0.086 × (2.76 + 1.38) / (2.76 - 1.38)
            = 0.086 × 4.14 / 1.38
            = 0.258m = 258mm
```

## Comparison to Other Robots

### Combat Robot Turn Rates

| Robot Type | Typical Spin Rate | 360° Time |
|------------|-------------------|-----------|
| ThumbsUp (1lb) | 3680 deg/s | 98 ms |
| Typical 1lb | 1000-2000 deg/s | 180-360 ms |
| Typical 3lb | 800-1500 deg/s | 240-450 ms |
| Brushless spinners | 2000-4000 deg/s | 90-180 ms |

**ThumbsUp is EXTREMELY agile** - faster than most 1lb robots!

This high agility means:
- Can reorient weapon very quickly
- Can dodge/evade rapidly
- High power-to-weight extends to rotational motion
- **Control sensitivity is critical** (hence the 70% expo)

## Control Implications

### Stick Input to Turn Rate

Current mixing algorithm:
```c
left_speed = forward + turn
right_speed = forward - turn
```

With MAX_DRIVE_SPEED = 100% and DRIVE_EXPO = 70%:

| Stick Position | Turn Value | Angular Velocity | 360° Time |
|----------------|------------|------------------|-----------|
| Center (0%) | 0 | 0 rad/s | ∞ |
| Small (10%) | ~3% | 2 rad/s (115 deg/s) | 3.1 s |
| Quarter (25%) | ~9% | 5.8 rad/s (330 deg/s) | 1.1 s |
| Half (50%) | ~24% | 15.4 rad/s (880 deg/s) | 410 ms |
| Full (100%) | ~100% | 64.2 rad/s (3680 deg/s) | 98 ms |

**The 70% expo provides much better turn rate control at low speeds!**

At center stick with 70% expo:
- 10% stick movement → 3% turn value → 115 deg/s rotation
- Gentle enough for weapon aiming

With old 30% expo:
- 10% stick movement → 7% turn value → 268 deg/s rotation
- Too aggressive for precision control

### Turn Rate vs Forward Speed

When both moving forward AND turning, the robot:
1. Follows a curved path
2. Rotation rate depends on speed difference
3. Turn radius depends on average speed

**Example: Forward + turn right**
```
Forward stick: 50% → both wheels ~1.38 m/s baseline
Turn stick: 50% → left +50%, right -50%

After drive mixing:
left = 1.38 + 0.69 = 2.07 m/s
right = 1.38 - 0.69 = 0.69 m/s

Turn radius = 0.086 × (2.07 + 0.69) / (2.07 - 0.69) = 0.172m = 172mm

Angular velocity = (0.69 - 2.07) / 0.086 = -16.0 rad/s = -917 deg/s
```

Robot moves forward at ~1.38 m/s while turning at 917 deg/s.

## Future Control Enhancements

### 1. Coordinated Turn Control

Instead of simple addition, use turn radius as input:

```c
// User commands desired turn radius and forward speed
float desired_radius_m = map_stick_to_radius(turn_stick);
float forward_speed_ms = map_stick_to_velocity(forward_stick);

// Calculate required wheel speeds
float omega = forward_speed_ms / desired_radius_m;
float v_left = forward_speed_ms + (omega × wheelbase / 2);
float v_right = forward_speed_ms - (omega × wheelbase / 2);
```

**Benefits:**
- More intuitive control
- Predictable turn behavior
- Can limit max turn rate independently of forward speed

### 2. Turn Rate Limiting

Limit angular velocity independent of wheel speeds:

```c
#define MAX_ANGULAR_VELOCITY_DEG_S 2000.0f  // Limit to 2000 deg/s

// Calculate commanded angular velocity
float omega_commanded = (v_right - v_left) / wheelbase;

// Limit if too high
if (abs(omega_commanded) > MAX_ANGULAR_VEL_RAD_S) {
    float scale = MAX_ANGULAR_VEL_RAD_S / abs(omega_commanded);
    v_left *= scale;
    v_right *= scale;
}
```

**Benefits:**
- Prevents overly aggressive turns
- Improves controllability
- Can tune separately from forward speed

### 3. Turn Expo Separate from Forward Expo

Apply different expo curves to forward and turn inputs:

```c
#define DRIVE_EXPO    70  // Forward motion expo
#define TURN_EXPO     80  // Turn motion expo (more aggressive curve)
```

**Benefits:**
- Can tune forward and turning independently
- Turning often needs more expo due to high agility
- More professional feel

### 4. Gyro-Assisted Turning

With IMU (future enhancement):
- Measure actual rotation rate
- Closed-loop control of angular velocity
- Compensate for wheel slip in turns
- Maintain desired heading during forward motion

## Practical Tips for Operators

### 1. Use Gentle Turn Inputs

This robot is EXTREMELY agile:
- Small stick movements cause fast rotation
- Practice smooth, gradual turn inputs
- Anticipate turns (lead the stick)

### 2. Combine Forward + Turn

For controlled maneuvers:
- Don't just spin in place
- Combine forward motion with turn input
- Creates predictable arcing motion
- Easier to aim weapon

### 3. Use Full Stick Sparingly

Full stick deflection causes:
- 10+ rotations per second
- Difficult to stop precisely
- Mostly useful for emergency evasion

### 4. Practice "Feel"

The 70% expo helps, but still requires practice:
- Learn the "dead zone" where nothing happens
- Find the "sweet spot" for controlled turns
- Develop muscle memory for specific maneuvers

## Summary

**Key Numbers:**
- Wheelbase: 86mm
- Max rotation rate: 3680 deg/s (10.2 rev/s)
- Full 360° spin: 98 milliseconds
- Min turn radius: 43mm (pivot turn)
- Turn radius at 50% differential: ~172mm

**Control Insight:**
The robot's exceptional agility (10 revolutions per second!) is why the transition felt "way too abrupt" at 30% expo. The 70% expo provides much better control over this high rotation rate while still allowing full agility when needed.

**Future Work:**
Consider adding turn rate limiting, separate turn expo, or coordinated turn control for even better handling. The wheelbase information enables these advanced control modes.
