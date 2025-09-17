# ThumbsUp Robot - Quick Reference Card

## ⚡ EMERGENCY STOP: L1 + R1 (Both Shoulders) ⚡

---

## Controller Layout
```
        [L1]                                [R1]
         ╱                                    ╲
    [L2]                                        [R2]

    ┌─────┐                              (Y)
    │  ↑  │  [SELECT]  [SYSTEM]  [START]  (X)   (B)
    │←   →│                                (A)
    │  ↓  │
    └─────┘                              ┌─────┐
  LEFT STICK                             │  ↑  │
   (DRIVE)                               │←   →│
                                         │  ↓  │
                                         └─────┘
                                       RIGHT STICK
                                     (WEAPON SPEED)
```

---

## Essential Controls

| Button/Stick | Action | Notes |
|-------------|---------|-------|
| **Left Stick** | Drive robot | Forward/back/turn |
| **Right Stick UP** | Spin weapon | Only when armed |
| **B** | Arm/Disarm weapon | Toggle |
| **A (Hold 2s)** | Clear E-stop | After emergency stop |
| **L1 + R1** | EMERGENCY STOP! | Instant shutdown |

---

## LED Status Guide

### 🔵 Blue (Status)
- **Solid**: System ready
- **Slow blink**: No controller
- **Fast blink**: EMERGENCY/FAULT

### 🔴 Red (Armed)
- **ON**: ⚠️ WEAPON ARMED ⚠️
- **OFF**: Weapon safe

### 🟢🟡🔴 Battery
- **Green solid**: Good (>11.1V)
- **Yellow blink**: Low (10.5-11.1V)
- **Red fast blink**: CRITICAL (<10.5V)

---

## Startup Sequence

1. **Power ON** → LEDs flash once
2. **Wait 5-10 seconds** → Safety tests run
3. **Look for:** "ALL SAFETY TESTS PASSED"
4. **Connect controller** → Status LED solid
5. **Test drive** → Small movements
6. **Press B to arm** → Red LED on = DANGER

---

## Safety Test Results

**PASS (✓)**: Continue to next step
**FAIL (✗)**: DO NOT OPERATE - Service required

Tests checked:
1. Motor initialization
2. Weapon safety
3. Failsafe system
4. Battery voltage
5. Emergency stops
6. Overflow protection

---

## Emergency Procedures

### Signal Lost / Failsafe
**Automatic:** Motors stop after 1.5 seconds
**Recovery:** Reconnect → Hold A (2 sec) → Resume

### Low Battery Warning
**Yellow LED:** Return to safe area
**Red LED:** STOP immediately

### E-Stop Active
1. Resolve issue
2. Hold A for 2 seconds
3. Wait for LEDs normal
4. Re-arm if needed (B)

---

## Pre-Match Checklist
- [ ] Safety tests: PASSED
- [ ] Battery: >11.5V
- [ ] Controller: Connected
- [ ] Drive test: OK
- [ ] Weapon: DISARMED
- [ ] Arena: Clear
- [ ] Safety gear: ON

---

## Competition Notes

**Arm weapon:** After referee signal only
**Disarm:** Immediately when match ends
**Tap-out:** L1+R1 for emergency stop
**Battery:** Change every 2-3 matches

---

## ⚠️ SAFETY RULES ⚠️

1. **NEVER** bypass safety systems
2. **ALWAYS** wear safety glasses
3. **MAINTAIN** 10ft minimum distance when armed
4. **DISARM** before approaching
5. **E-STOP** when in doubt

---

## Voltage Reference
- 12.6V = Full charge
- 11.5V = Ready for match
- 11.1V = Low warning
- 10.5V = Critical - STOP
- 10.0V = Damage threshold

---

**Firmware v1.0.0 | Stay Safe, Fight Hard!**