# ThumbsUp Combat Robot User Manual

## Table of Contents
1. [Safety Warning](#safety-warning)
2. [Controller Layout](#controller-layout)
3. [Startup Procedure](#startup-procedure)
4. [Safety Test Suite](#safety-test-suite)
5. [LED Indicators](#led-indicators)
6. [Operating Procedures](#operating-procedures)
7. [Emergency Procedures](#emergency-procedures)
8. [Troubleshooting](#troubleshooting)
9. [Battery Management](#battery-management)
10. [Competition Checklist](#competition-checklist)

---

## Safety Warning

⚠️ **DANGER: HIGH-SPEED ROTATING WEAPON** ⚠️

This combat robot contains a high-speed spinning weapon capable of causing serious injury or death.

**ALWAYS:**
- Operate in approved combat robot arenas only
- Wear safety glasses
- Maintain safe distance (minimum 10 feet) when armed
- Have emergency stop procedures ready
- Follow all competition safety rules
- Keep weapon pointed away from people

**NEVER:**
- Operate without safety gear
- Bypass safety systems
- Operate with damaged components
- Leave armed robot unattended

---

## Controller Layout

The ThumbsUp robot uses standard Bluetooth gamepads (Xbox, PlayStation, or compatible).

### Control Mappings

| Control | Function | Description |
|---------|----------|-------------|
| **Left Stick Y-axis** | Forward/Reverse | Push forward to drive forward, pull back to reverse |
| **Left Stick X-axis** | Turning | Left/right for tank-style turning |
| **Right Stick Y-axis** | Weapon Speed | Push forward to spin weapon (only when armed) |
| **A Button** | Clear Emergency Stop | Hold for 2 seconds to clear E-stop |
| **B Button** | Arm/Disarm Toggle | Press to arm or disarm weapon |
| **L1 + R1** | Emergency Stop | Press both simultaneously for immediate shutdown |
| **System Button** | Controller Features | Activates rumble and LED test |

### Control Details

#### Drive Controls
- **Deadzone**: 30 units (of 512) - prevents drift
- **Exponential curve**: 30% default - smoother control at low speeds
- **Max speed**: Limited to 80% for safety
- **Mixing**: Tank-style with automatic speed limiting when turning

#### Weapon Control
- **Trigger threshold**: 50 units - prevents accidental activation
- **Ramp-up time**: 2 seconds - gradual acceleration
- **Speed control**: Proportional from 0-100%
- **Safety interlock**: Must be armed first (B button)

#### Emergency Stop
- **Activation**: L1 + R1 pressed together
- **Effect**: Immediate shutdown of all motors
- **Clear procedure**: Hold A button for 2 seconds
- **Visual indication**: All LEDs flash rapidly

---

## Startup Procedure

### 1. Pre-Power Checks
- [ ] Inspect robot for damage
- [ ] Verify weapon is clear of obstructions
- [ ] Check battery voltage (11.1V minimum)
- [ ] Ensure arena is clear
- [ ] Safety gear on all personnel

### 2. Power On Sequence
1. Connect battery
2. Power on robot (main switch)
3. Observe LED sequence:
   - All LEDs flash once (power-on test)
   - Status LED turns on (system booting)
   - WiFi LED blinks (Bluetooth initializing)

### 3. Safety Test Phase
The robot automatically runs safety tests on startup:

```
=================================
  ThumbsUp Safety Test Suite
=================================

Test 1: Motor Initialization Safety...
  ✓ PASSED
Test 2: Weapon Safety Checks...
  ✓ PASSED
Test 3: Failsafe Conditions...
  ✓ PASSED
Test 4: Battery Monitoring...
  ✓ PASSED
Test 5: Emergency Stop Functions...
  ✓ PASSED
Test 6: Integer Overflow Protection...
  ✓ PASSED

=================================
  Test Results: 6/6 passed
  ✓ ALL SAFETY TESTS PASSED
  System is safe for operation
=================================
```

**If any test fails:**
- Robot enters lockout mode
- All LEDs flash rapidly
- **DO NOT OPERATE** - service required

### 4. Controller Connection
1. Turn on Bluetooth gamepad
2. Wait for pairing (Status LED solid)
3. Test connection with small stick movement
4. Verify drive response

---

## Safety Test Suite

The robot runs 6 critical safety tests at startup:

### Test 1: Motor Initialization Safety
**What it tests:**
- Weapon motor starts at minimum (safe) position
- Drive motors start at neutral (stopped)
- PWM signals are within valid range

**Pass criteria:**
- Weapon pulse = 1000μs (motor off)
- Drive pulses = 1500μs (neutral)

**User indication:**
- Serial output shows "✓ PASSED"
- No motor movement during test

### Test 2: Weapon Safety Checks
**What it tests:**
- Weapon starts in DISARMED state
- Low battery prevents arming
- Safety button prevents arming

**Pass criteria:**
- Initial state = WEAPON_STATE_DISARMED
- Arming blocked if battery < 11.1V
- Arming blocked if safety button pressed

**User indication:**
- Armed LED remains OFF
- Weapon does not respond to throttle

### Test 3: Failsafe Conditions
**What it tests:**
- Failsafe system is operational
- Timeout detection works
- Emergency stop accessible

**Pass criteria:**
- Failsafe function exists and compiles
- 1500ms timeout configured
- Emergency stop can be triggered

**User indication:**
- No errors in serial output
- System ready for failsafe monitoring

### Test 4: Battery Monitoring
**What it tests:**
- Battery voltage reading circuit
- Voltage thresholds are sensible
- ADC is functioning

**Pass criteria:**
- Voltage reads between 6V-15V
- Low voltage < Max voltage
- Critical < Low voltage thresholds

**User indication:**
- Battery LED shows appropriate state:
  - Solid GREEN: Good (>11.1V)
  - Blinking YELLOW: Low (10.5-11.1V)
  - Fast blinking RED: Critical (<10.5V)

### Test 5: Emergency Stop Functions
**What it tests:**
- Emergency stop immediately halts motors
- Weapon enters emergency state
- System can be reset properly

**Pass criteria:**
- All motors stop within 10ms
- Weapon state = EMERGENCY_STOP
- Motors can be reinitialized

**User indication:**
- Brief motor initialization test
- No sustained motor movement

### Test 6: Integer Overflow Protection
**What it tests:**
- PWM value clamping works
- Invalid inputs are handled safely
- No calculation overflows

**Pass criteria:**
- Over-range values are clamped
- Under-range values are clamped
- All calculations stay in bounds

**User indication:**
- No erratic motor behavior
- System remains stable

---

## LED Indicators

### Status LED (Blue)
| Pattern | Meaning |
|---------|---------|
| Solid ON | System operational |
| Slow blink (1Hz) | Waiting for controller |
| Fast blink (5Hz) | Emergency stop / Failsafe active |
| OFF | System not ready |

### Armed LED (Red)
| Pattern | Meaning |
|---------|---------|
| Solid ON | Weapon ARMED - DANGER |
| OFF | Weapon safe/disarmed |
| Cannot turn ON | Safety interlock active |

### Battery LED (Green/Yellow/Red)
| Pattern | Meaning | Voltage |
|---------|---------|---------|
| Solid GREEN | Battery good | >11.1V |
| Blinking YELLOW | Battery low | 10.5-11.1V |
| Fast blinking RED | Battery critical | <10.5V |
| OFF | No power | - |

### WiFi/Bluetooth LED (on Pico W)
| Pattern | Meaning |
|---------|---------|
| ON during boot | Initializing |
| OFF after init | Ready for connections |
| Blinking | Activity/pairing |

---

## Operating Procedures

### Normal Operation

1. **Pre-match Setup**
   - Power on robot
   - Wait for safety tests to complete (5-10 seconds)
   - Verify all LEDs show correct state
   - Connect controller
   - Test drive movement (weapon still disarmed)

2. **Entering Arena**
   - Keep weapon DISARMED
   - Use slow movements
   - Position robot
   - Verify clear surroundings

3. **Match Start**
   - Press B button to ARM weapon (red LED on)
   - Use right stick to control weapon speed
   - Drive with left stick
   - Monitor battery LED

4. **Match End**
   - Press B button to DISARM weapon
   - Wait for weapon to stop spinning (up to 30 seconds)
   - Verify Armed LED is OFF
   - Safe to approach

### Advanced Operations

#### Exponential Control Adjustment
The drive controls use 30% exponential curve by default for smoother low-speed control. This cannot be adjusted without recompiling.

#### Weapon Speed Ramping
- Weapon accelerates gradually over 2 seconds
- Prevents current spikes and mechanical shock
- Full speed available after ramp period

#### Tank Mixing Algorithm
- Forward + Turn inputs are mixed
- Automatic speed limiting maintains control
- Turning takes priority over forward speed

---

## Emergency Procedures

### Emergency Stop (E-Stop)

**To Activate:**
1. Press L1 + R1 simultaneously
2. All motors stop immediately
3. All LEDs flash rapidly
4. Robot enters safe mode

**To Clear:**
1. Ensure hazard is resolved
2. Hold A button for 2 seconds
3. Listen for confirmation (serial output)
4. LEDs return to normal
5. Re-arm weapon if needed (B button)

### Controller Signal Loss

**Automatic Response:**
- Failsafe activates after 1.5 seconds
- All motors stop
- Weapon disarms
- Status LED flashes rapidly

**Recovery:**
1. Re-establish controller connection
2. Clear emergency stop (hold A for 2 seconds)
3. Resume operation

### Low Battery

**Warning (11.1V):**
- Battery LED blinks yellow
- Weapon can still be armed
- Return to safe area soon

**Critical (10.5V):**
- Battery LED flashes red rapidly
- Weapon automatically disarms
- Cannot re-arm weapon
- Drive power reduced
- IMMEDIATELY stop operation

### Safety Button

**If pressed during operation:**
- Weapon immediately disarms
- Cannot re-arm until released
- Drive remains operational
- Used for referee safety stops

---

## Troubleshooting

### Robot Won't Start

| Problem | Possible Cause | Solution |
|---------|---------------|----------|
| No LEDs | No power | Check battery connection |
| All LEDs flashing | Failed safety test | Check serial output for specific failure |
| Status LED off | System crash | Power cycle robot |

### Controller Issues

| Problem | Possible Cause | Solution |
|---------|---------------|----------|
| Won't connect | Bluetooth off | Ensure gamepad is in pairing mode |
| No response | Not paired | Delete pairing and reconnect |
| Delayed response | Interference | Move closer, check for 2.4GHz interference |
| Erratic control | Low controller battery | Charge gamepad |

### Weapon Problems

| Problem | Possible Cause | Solution |
|---------|---------------|----------|
| Won't arm | Low battery | Charge battery above 11.1V |
| Won't arm | Safety button pressed | Release safety button |
| Won't arm | In E-stop | Clear E-stop (hold A for 2 seconds) |
| No speed control | Not armed | Press B button to arm first |
| Stops suddenly | Failsafe triggered | Check controller connection |

### Drive Issues

| Problem | Possible Cause | Solution |
|---------|---------------|----------|
| Won't move | E-stop active | Clear E-stop |
| Drifting | Stick calibration | Re-center stick, reconnect controller |
| One side weak | Motor issue | Check motor connections |
| Erratic movement | Low battery | Charge battery |

---

## Battery Management

### Battery Specifications
- **Type**: 3S LiPo (11.1V nominal)
- **Capacity**: 2200mAh minimum recommended
- **Discharge rate**: 25C minimum
- **Connector**: XT60

### Voltage Thresholds
- **Maximum**: 12.6V (fully charged)
- **Nominal**: 11.1V (storage charge)
- **Low Warning**: 11.1V
- **Critical**: 10.5V
- **Cutoff**: 10.0V (permanent damage below)

### Battery Care
1. **Never over-discharge** below 10.0V
2. **Store at 11.4V** (storage charge)
3. **Balance charge** every 10 cycles
4. **Monitor temperature** during use
5. **Replace** if swollen or damaged

### Runtime Estimates
- **Competition match**: 3-5 minutes active combat
- **Testing**: 10-15 minutes light use
- **Standby**: 30+ minutes (weapon off)

---

## Competition Checklist

### Pre-Event (Day Before)
- [ ] Charge all batteries to storage level
- [ ] Test all systems
- [ ] Verify controller pairing
- [ ] Check all mechanical components
- [ ] Review competition rules
- [ ] Prepare spare parts

### At Venue
- [ ] Safety inspection passed
- [ ] Frequency/channel confirmed
- [ ] Weight verified
- [ ] Fully charge batteries
- [ ] Test in practice arena
- [ ] Brief team on safety procedures

### Pre-Match
- [ ] Fresh battery installed
- [ ] Safety tests pass
- [ ] Controller connected
- [ ] Team positions confirmed
- [ ] Safety gear on
- [ ] Weapon guard removed

### Post-Match
- [ ] Weapon disarmed
- [ ] Power off
- [ ] Inspect for damage
- [ ] Note any issues
- [ ] Recharge if needed

### Emergency Contacts
- **Event Safety Officer**: [Get at venue]
- **Medical Emergency**: 911
- **Fire Extinguisher**: [Locate at venue]

---

## Quick Reference Card

### Essential Controls
- **Drive**: Left stick
- **Weapon speed**: Right stick (when armed)
- **Arm/Disarm**: B button
- **EMERGENCY STOP**: L1 + R1
- **Clear E-stop**: Hold A (2 seconds)

### LED Quick Guide
- **Blue solid**: Ready
- **Red solid**: WEAPON ARMED
- **All flashing**: EMERGENCY/FAULT
- **Green**: Battery good
- **Yellow blink**: Battery low

### Safety Priorities
1. **People safety** - Always first
2. **E-stop** - When in doubt, stop
3. **Disarm** - After every match
4. **Battery** - Monitor constantly
5. **Distance** - Stay back when armed

---

## Revision History
- v1.0 - Initial manual (December 2024)
- Firmware version: 1.0.0
- Compatible controllers: Xbox, PlayStation, generic Bluetooth gamepads

---

**Remember: Safety First, Combat Second!**