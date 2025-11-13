# Motor Calibration Report

Date: 2025-11-12

## Test Setup
- Robot: ThumbsUp 1lb combat robot
- Motors: 030 brushed with 22.6:1 planetary gearbox
- ESC: Kingmodel SAX2 dual 5Ax2 brushed ESC
- Wheels: LEGO 43.2mm diameter
- Battery: 3S LiPo (nominal 11.1V)
- Measurement: Optical tachometer with reflective tape

## Calibration Data

### Forward Direction
| Throttle | Left RPM | Right RPM | Avg RPM | % of Max |
|----------|----------|-----------|---------|----------|
| 10%      | 0        | 0         | 0       | 0%       |
| 20%      | 250      | 270       | 260     | 32%      |
| 30%      | 422      | 482       | 452     | 56%      |
| 40%      | 540      | 598       | 569     | 71%      |
| 50%      | 610      | 671       | 641     | 80%      |
| 60%      | 664      | 710       | 687     | 85%      |
| 70%      | 702      | 753       | 728     | 90%      |
| 80%      | 728      | 775       | 752     | 93%      |
| 90%      | 748      | 793       | 771     | 96%      |
| 100%     | 758      | 805       | 782     | 97%      |

**Forward Max RPM:** 805 RPM (right motor)

### Reverse Direction
| Throttle | Left RPM | Right RPM | Avg RPM | % of Max |
|----------|----------|-----------|---------|----------|
| 10%      | 0        | 0         | 0       | 0%       |
| 20%      | 240      | 199       | 220     | 28%      |
| 30%      | 422      | 400       | 411     | 53%      |
| 40%      | 538      | 559       | 549     | 70%      |
| 50%      | 615      | 621       | 618     | 79%      |
| 60%      | 669      | 680       | 675     | 86%      |
| 70%      | 700      | 719       | 710     | 91%      |
| 80%      | 732      | 750       | 741     | 95%      |
| 90%      | 762      | 770       | 766     | 98%      |
| 100%     | 781      | 777       | 779     | 100%     |

**Reverse Max RPM:** 781 RPM (left motor)

**Overall Max RPM:** 805 RPM

## Analysis

### 1. Actual vs Theoretical Performance

**Theoretical Max RPM:** 1220 RPM @ 3S (from motor specs)
**Measured Max RPM:** 805 RPM
**Efficiency:** 66% of theoretical

**Possible reasons for lower RPM:**
- Battery voltage sag under load
- Motor/gearbox efficiency losses (~10-15% typical)
- ESC efficiency losses (~5-10%)
- Manufacturer specs may be optimistic (free-run vs loaded)
- Wheel contact resistance during measurement

**Actual max velocity:** 805 RPM × 0.1357m circumference / 60 = **1.82 m/s**
(vs theoretical 2.76 m/s)

### 2. Deadband

**Deadband threshold:** 10% throttle produces no movement
**Motor start:** 20% throttle = ~220-270 RPM

This is typical for brushed ESCs and is already handled well by the 70% expo curve, which provides good sensitivity above the deadband.

### 3. Response Curve (Non-Linearity)

The ESC + motor combination shows typical non-linear response:
- **20-40% throttle:** Steepest part of curve (~14 RPM per 1% throttle)
- **40-70% throttle:** Moderate curve (~6 RPM per 1% throttle)
- **70-100% throttle:** Flattens out (~2 RPM per 1% throttle)

This logarithmic curve is characteristic of brushed motors:
- Low RPM: High torque, rapid acceleration
- High RPM: Lower torque, diminishing returns

The 70% exponential curve helps compensate for this by:
- Making small stick movements → small throttle changes (fine control in steep part)
- Making large stick movements → large throttle changes (using the full range)

### 4. Motor Matching (Left vs Right)

**Forward:**
- At 100%: Left=758 RPM, Right=805 RPM
- Difference: 47 RPM (6.2%)
- Right motor consistently ~5-10% faster

**Reverse:**
- At 100%: Left=781 RPM, Right=777 RPM
- Difference: 4 RPM (0.5%)
- Very well matched!

**Assessment:** Motor matching is good (within 10%). The slight forward asymmetry may cause a small drift to the left, but the trim system can compensate for this.

### 5. Forward vs Reverse Asymmetry

- Forward max: 805 RPM (right)
- Reverse max: 781 RPM (left)
- Difference: ~3%

This small asymmetry is typical and acceptable. Both directions reach similar speeds.

## Recommendations

### 1. Update MAX_WHEEL_RPM in config.h
Change from theoretical 1220 RPM to measured 805 RPM:
```c
#define MAX_WHEEL_RPM       805  // Measured actual max (was 1220 theoretical)
```

This will make velocity calculations accurate.

### 2. Update MAX_VELOCITY
```c
#define MAX_VELOCITY_MS     1.82f  // 805 RPM × 0.1357m / 60s
#define MAX_VELOCITY_KMH    6.5f   // 1.82 m/s × 3.6
```

### 3. Keep Current Expo Curve
The 70% expo curve is working well with this response characteristic. The non-linearity of the ESC+motor is actually beneficial because:
- Low throttle: High sensitivity (good for precise control)
- High throttle: Diminishing returns (prevents over-sensitivity at high speed)

The expo curve amplifies small inputs in the region where the hardware is most responsive.

### 4. No Deadband Compensation Needed
The current system works fine. The 70% expo provides good control above the 20% start threshold.

### 5. Monitor for Drift
The ~6% forward asymmetry between left (758) and right (805) may cause slight left drift. Use the dynamic trim system to compensate during driving.

## Conclusions

**Overall:** The motors and ESCs are performing well!

- Actual performance is 66% of theoretical specs (normal for real-world conditions)
- Motor matching is good (within 6%)
- Response curve is typical for brushed motors
- The 70% expo provides excellent control over the actual response range
- No major issues identified

**Action Item:** Update config.h with actual measured values (805 RPM, 1.82 m/s) for accurate telemetry and calculations.

## Future Enhancements (Optional)

If even better control is desired:

1. **Linearization table:** Create a lookup table to compensate for the non-linear response
2. **Per-motor calibration:** Store individual scaling factors for left/right matching
3. **Deadband compensation:** Add ~15% offset to throttle commands to eliminate deadband
4. **Gyro-based control:** Use IMU for closed-loop velocity/rotation control

However, the current open-loop system with 70% expo is working very well!
