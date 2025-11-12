# Motor Specifications

## Drive Motors

**Model:** Custom wound 030 brushed motor with 22.6:1 planetary gearbox

### Physical Specifications
- Motor type: 030 brushed DC motor
- Gearbox: 16mm, 22.6:1 ratio, all-metal planetary
- Output shaft: 3mm or 4mm "D" profile, extra long
- Weight: 26.5g (3mm shaft) / 27.5g (4mm shaft)
- Mounting: 10.5mm M2 face mount hole pattern

### Electrical Ratings
- Voltage range: 2S-4S (7.4V - 14.8V)
- **Recommended:** 3S (11.1V nominal, 12.6V fully charged)

### Performance Characteristics

#### 3S Operation (12V nominal) - PRIMARY
- **Free speed:** 1220 RPM
- **Stall current:** 2A
- **Stall torque:** 1187 g·cm (0.116 N·m)
- **Max power output:** 3.72W

#### 2S Operation (7.4V)
- **Free speed:** 752 RPM

#### 4S Operation (14.8V)
- **Free speed:** 1504 RPM

### Motor Constant Calculations

Based on 3S operation:
- **Voltage per RPM (Kv):** 12V / 1220 RPM = 0.00984 V/RPM (Kv ≈ 102 RPM/V)
- **Torque constant (Kt):** 0.116 N·m / 2A = 0.058 N·m/A
- **No-load current:** ~0.2A (estimated)
- **Resistance:** ~6Ω (estimated from stall)

### Torque-Speed Curve

The motor follows a linear torque-speed relationship:

```
Speed (RPM) = Free_Speed × (1 - Torque/Stall_Torque)
Speed (RPM) = 1220 × (1 - Current/2A)
```

For approximate PWM to speed mapping (assuming linear ESC):
```
PWM% → Voltage → Speed
100%  → 12.0V   → ~1220 RPM
 75%  → 9.0V    → ~915 RPM
 50%  → 6.0V    → ~610 RPM
 25%  → 3.0V    → ~305 RPM
```

**Note:** Actual speed will be lower under load due to torque requirements.

## Mechanical Drive System

### Wheel Specifications
- **Tire:** LEGO 43.2x22 ZR
- **Diameter:** 43.2mm (0.0432m)
- **Circumference:** π × 43.2mm = **135.7mm (0.1357m)**

### Velocity Calculations (3S)

At various motor speeds:

| Motor RPM | Wheel Speed | Linear Velocity |
|-----------|-------------|-----------------|
| 1220 (100%) | 1220 RPM | 2.76 m/s (9.9 km/h) |
| 915 (75%) | 915 RPM | 2.07 m/s (7.4 km/h) |
| 610 (50%) | 610 RPM | 1.38 m/s (5.0 km/h) |
| 305 (25%) | 305 RPM | 0.69 m/s (2.5 km/h) |

**Max theoretical velocity:** 2.76 m/s (9.9 km/h)

### Torque at Wheel

```
Wheel Torque = Motor Stall Torque × Gear Ratio
Wheel Torque = 1187 g·cm × 22.6 = 26,826 g·cm = 2.63 N·m
```

With 43.2mm diameter wheel:
```
Thrust Force = Torque / Radius = 2.63 N·m / 0.0216m = 122 N (12.4 kg force)
```

**Note:** This is stall torque; actual available thrust decreases with speed.

### Acceleration Capability

Assuming 1lb (0.454kg) robot weight:
```
Max acceleration = Force / Mass = 122 N / 0.454 kg = 269 m/s²
```

**Practical acceleration** (accounting for friction, efficiency ~50%):
- Estimated: **5-10 m/s²**
- 0-max speed time: ~0.3-0.5 seconds

This explains why control feels "too abrupt" - the robot can accelerate to full speed in under half a second!

## Control Implications

### Current Issues
1. **High acceleration:** Robot reaches max speed (2.76 m/s) in ~0.3s
2. **Poor low-speed resolution:** Small stick movements cause large velocity changes
3. **30% expo insufficient:** Still too much sensitivity at low speeds

### Recommended Solutions
1. **Increase expo to 60-80%:** More cubic curve for gentler low-speed control
2. **Add acceleration limiting:** Ramp velocity changes over 100-200ms
3. **Expand deadzone:** Current 15-unit deadzone may be too small
4. **Consider velocity-based control:** Command velocity in m/s rather than PWM percentage
5. **Add "precision mode":** Button-triggered mode that limits max speed to 25-50%

### Precision Mode Concept

Combat robots benefit from two speed modes:
- **Normal mode:** Full speed (2.76 m/s) for combat/mobility
- **Precision mode:** Limited speed (0.5-1.0 m/s) for positioning/aiming

Could be toggled with a button (e.g., L2/R2 trigger held = precision mode).
