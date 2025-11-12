# ESC Specifications

## Kingmodel SAX2 Dual 5Ax2 PRO Brushed ESC

### General Specifications
- **Model:** KINGMODEL Dual-way 5A×2 PRO Brushed ESC
- **Type:** Dual channel brushed bidirectional ESC
- **Power supply:** 2-6S Lithium battery (7.4V - 22.2V)
- **Output current:** 5A per channel (2 channels)
- **BEC:** 5V @ 1.5A
- **Weight:** 20.3g
- **Dimensions:** 42mm × 26mm
- **Control signal:** PWM (standard RC servo protocol)

### Supported Motors
- Designed for: 380/390 high current brushed motors
- Compatible with: 030 brushed motors (our application)
- Max current per channel: 5A continuous

### Control Modes

#### Mixed Mode (CURRENTLY DISABLED)
- ESC performs differential mixing internally
- One PWM signal controls forward/backward
- Another PWM signal controls left/right turning
- **NOT USED** - We disabled this and do mixing in firmware

#### Independent Mode (CURRENTLY IN USE)
- Each channel controlled independently
- Left motor: Independent PWM signal
- Right motor: Independent PWM signal
- Firmware performs differential drive mixing
- **This is our current configuration**

### PWM Signal Specifications

Standard RC PWM protocol:
- **Frequency:** 50 Hz (20ms period)
- **Pulse width range:** 1000-2000 μs
- **Neutral:** 1500 μs (motor stop)
- **Full reverse:** 1000 μs
- **Full forward:** 2000 μs

### Protections

1. **Over-temperature protection:** 130°C shutdown
2. **Over-current protection:** >5A per channel
3. **Loss of throttle signal:** Failsafe stop after timeout
4. **Thermal management:** Built-in capacitor module for current stability

### LED Indicator
- **Red LED:** Power indicator
- Confirms ESC is receiving battery power
- **Status:** Solid when powered, no signal loss indication

### Signal Processing

The ESC converts PWM input to motor voltage:

```
PWM Input → Voltage Output (assuming linear ESC)
1000 μs   → -12V (full reverse, 3S)
1500 μs   → 0V   (neutral, brake)
2000 μs   → +12V (full forward, 3S)
```

**PWM to Motor Voltage:**
```
Voltage = (PWM_us - 1500) / 500 × Battery_Voltage
```

Examples at 3S (12V):
- 1000 μs: (1000-1500)/500 × 12V = **-12V** (full reverse)
- 1250 μs: (1250-1500)/500 × 12V = **-6V** (half reverse)
- 1500 μs: (1500-1500)/500 × 12V = **0V** (stopped)
- 1750 μs: (1750-1500)/500 × 12V = **+6V** (half forward)
- 2000 μs: (2000-1500)/500 × 12V = **+12V** (full forward)

### ESC Response Characteristics

#### Linearity
Most brushed ESCs are **linear**: PWM percentage directly maps to voltage percentage.

```
50% PWM = 50% voltage = 50% of max RPM (approximately)
```

This is different from brushless ESCs which may have non-linear response curves.

#### Deadband
The ESC likely has a small deadband around 1500 μs where motor is held at zero (brake mode).
- Estimated deadband: **±10-20 μs** around 1500 μs
- Within this range: Motor actively braked (both terminals shorted)
- Outside this range: Motor driven proportionally

#### Update Rate
- PWM input frequency: 50 Hz (20ms updates)
- ESC processing: ~1-2ms typical latency
- Motor response: Limited by motor electrical time constant (~5-10ms)

**Total control loop delay:** ~25-30ms from stick input to motor speed change

### Brake Modes

When PWM = 1500 μs (neutral):
1. **Active brake:** Both motor terminals shorted → fast stop
2. **Coast mode:** Motor terminals open → slow coast to stop

Most brushed ESCs use **active brake** by default, which is appropriate for combat robots (need quick stops).

### Power Consumption

At stall (worst case, both motors):
```
Current draw = 2 motors × 2A stall = 4A total
Voltage = 12V (3S nominal)
Power = 12V × 4A = 48W
```

At typical driving (50% load per motor, estimated 0.5A each):
```
Current draw = 2 × 0.5A = 1A
Power = 12V × 1A = 12W
```

BEC power consumption:
```
BEC output: 5V @ 1.5A max = 7.5W max
Assuming 80% efficiency: ~9-10W from battery
```

### Battery Considerations

**3S LiPo:** 11.1V nominal, 12.6V fully charged, 9.0V cutoff

Recommended capacity for combat robot:
- Light use: 500-1000 mAh
- Competition: 1000-1500 mAh
- Extended operation: 1500-2200 mAh

**Current flight time estimation** (1000 mAh battery):
```
Average current draw: ~2A (including motors + electronics)
Run time = 1000 mAh / 2000 mA = 0.5 hours = 30 minutes
```

Actual combat time will be less due to high peak currents, but 15-20 minutes of active driving is realistic.

### Wiring Configuration

Current setup (independent mode):
```
ESC CH1 (PWM) → Pico GP0 (Left Drive PWM)
ESC CH2 (PWM) → Pico GP1 (Right Drive PWM)
ESC BEC 5V    → Pico VSYS (powers Pico)
ESC GND       → Pico GND (common ground)
```

Motor connections:
- Left motor: ESC CH1 output
- Right motor: ESC CH2 output (reversed polarity or `reversed=true` in firmware)

### Recommendations

1. **Verify linear response:** Use optical tachometer to measure actual RPM vs PWM
2. **Check deadband size:** Determine actual neutral range (may affect low-speed control)
3. **Confirm brake mode:** Test if ESC uses active brake or coast at neutral
4. **Monitor temperature:** ESC rated for 130°C but should stay much cooler
5. **Add voltage monitoring:** Low battery cutoff to protect LiPo (already implemented)

### Known Limitations

1. **No telemetry:** ESC doesn't provide current/temperature feedback
2. **No programmability:** Fixed settings (brake mode, timing, etc.)
3. **5A limit:** Can't upgrade to larger motors without ESC upgrade
4. **PWM only:** No modern digital protocols (DShot, etc.)

These limitations are acceptable for this application, but worth noting for future upgrades.
