# Hardware Configuration Analysis
## ThumbsUp Combat Robot - Weapon Motor Configuration

**Date:** 2025-11-18
**Hardware Review:** FingerTech Silver Spark F2822-1100KV + AT32F421-based AM32 ESC

---

## Motor Specifications (Verified)

**FingerTech Silver Spark F2822-1100KV (0.125" shaft)**

| Specification | Value | Source |
|--------------|-------|--------|
| KV Rating | 1100 rpm/V | FingerTech specs ✓ |
| Max Voltage | 11.1V (3S LiPo) | FingerTech specs ✓ |
| Max Current | **9.9A** | FingerTech specs ✓ |
| Max Power | 102W | FingerTech specs ✓ |
| Internal Resistance | 0.192Ω | FingerTech specs ✓ |
| RPM @ 3S | 12,210 RPM | FingerTech specs ✓ |
| Weight | 41g | FingerTech specs ✓ |
| Pole Count | **Unknown** - needs verification | Not documented ❌ |

---

## ESC Specifications (Verified)

**AT32F421K8U7-based AM32 ESC**

| Specification | Value | Notes |
|--------------|-------|-------|
| MCU | AT32F421K8U7 | ARM Cortex-M4 ✓ |
| Flash | 64KB | Adequate for AM32 ✓ |
| RAM | 16KB | Adequate for AM32 ✓ |
| Firmware | AM32 | Standard protocol ✓ |
| Config Interface | Single wire (S pad only) | No RX pad accessible ⚠️ |
| DShot Support | Yes (all speeds) | Tested on AT32F421 ✓ |
| EDT Telemetry | Yes (if enabled) | Needs testing ⚠️ |

---

## Current Firmware Configuration Status

### ✓ CORRECT Settings

| Setting | Location | Current Value | Status |
|---------|----------|---------------|--------|
| KV Rating | `am32_config.c:609` | 1100 | ✓ Matches motor |
| DShot Speed | `weapon.c:139` | DSHOT_300 | ✓ Safe choice |
| Bidirectional | `weapon.c:140` | true | ✓ Telemetry enabled |
| GPIO Pin | `config.h:18` | GP4 | ✓ UART1 TX / DShot |
| Max Voltage | Battery config | 12.6V (3S) | ✓ Within motor range |

### ⚠️ UNKNOWN Settings (Need Verification)

| Setting | Location | Current Value | Issue |
|---------|----------|---------------|-------|
| Motor Poles | `am32_config.c:610` | 14 | **ASSUMPTION - not verified** ⚠️ |
| Pole Pairs | `weapon.c:141` | 7 (14 poles) | **ASSUMPTION - not verified** ⚠️ |

**Impact:** Wrong pole count causes:
- Incorrect RPM calculations in telemetry
- Poor motor timing performance
- Reduced efficiency

**Action Required:**
1. Count motor poles physically (typical: 12, 14, or 16 for 2822 size)
2. Or enable telemetry and measure RPM against known speed
3. Or use AM32 configurator auto-detection

### ❌ INCORRECT Settings (CRITICAL)

| Setting | Location | Current Value | Correct Value | Issue |
|---------|----------|---------------|---------------|-------|
| **Current Limit** | `am32_config.c:615` | **40A** | **10A** | **CRITICAL SAFETY ISSUE** ❌ |

**Severity:** CRITICAL
**Impact:**
- Motor rated for **9.9A max**
- Current setting allows **40A** (4× over spec!)
- **WILL DAMAGE MOTOR** under high load
- Windings will overheat and fail
- Potential fire hazard

**Required Fix:**
```c
// am32_config.c line 615
config->current_limit = 10;  // Changed from 40A to 10A (motor max 9.9A + margin)
```

### ⚠️ RECOMMENDED Settings Changes

| Setting | Location | Current Value | Recommended | Reason |
|---------|----------|---------------|-------------|--------|
| Temperature Limit | `am32_config.c:614` | 80°C | 70°C | Small motor, conservative limit |
| Brake on Stop | `am32_config.c:606` | 0 (off) | 1 (on) | Safety for weapon |
| Startup Power | `am32_config.c:607` | 6 | 5-6 | Reduce stress on small motor |

---

## Hardware Limitations

### ESC Configuration Access

**Current Setup:**
- ESC has only 'S' (signal), 'G' (ground), 'V' (power) pads
- No accessible UART RX pad
- Small pads (3/G/D/C) are SWD debug, not UART

**Implications:**
- ✓ **DShot works perfectly** (single wire protocol)
- ✓ **PWM works perfectly** (single wire protocol)
- ✓ **EDT telemetry may work** (bidirectional DShot on same wire)
- ❌ **AM32 serial config won't work** from robot firmware
- ✓ **Parameter adjuster WILL work** (handles bidirectional internally)

**Recommended Configuration Method:**
1. Use parameter adjuster (USB configurator you purchased)
2. Configure ESC on bench before installing
3. Set all parameters correctly (especially current limit!)
4. Save to EEPROM
5. Install in robot and use DShot control

### Motor Power Limitations

**Important:** This is a **DRONE MOTOR**, not a dedicated weapon motor!

| Characteristic | Value | Combat Robot Suitability |
|----------------|-------|-------------------------|
| Max Current | 9.9A | ⚠️ LOW for weapon (typical weapon: 20-60A) |
| Max Power | 102W | ⚠️ LOW for weapon (typical weapon: 200-500W) |
| Weight | 41g | ✓ Light (good for antweight/beetleweight) |
| Efficiency | Good for drones | ⚠️ Not optimized for impact loads |

**Recommendations:**
1. This motor is suitable for **lightweight robots only** (antweight class, <1 lb)
2. **Avoid heavy impacts** - motor not designed for shock loads
3. **Monitor temperature closely** - small motor heats up quickly
4. **Consider upgrade** to dedicated weapon motor if power is insufficient
5. **Test incrementally** - start at 50% power, increase carefully

---

## Required Code Changes

### CRITICAL FIX: Current Limit

**File:** `firmware/src/am32_config.c`
**Line:** 615

**Current:**
```c
config->current_limit = 40;         // 40A limit
```

**Change to:**
```c
config->current_limit = 10;         // 10A limit (motor max 9.9A)
```

### RECOMMENDED CHANGES

**File:** `firmware/src/am32_config.c`

**Line 606 - Enable brake:**
```c
config->brake_on_stop = 1;          // Enable brake for weapon safety
```

**Line 614 - Lower temperature limit:**
```c
config->temperature_limit = 70;     // 70°C limit (conservative for small motor)
```

**Line 607 - Reduce startup power (optional):**
```c
config->startup_power = 5;          // Gentler startup for small motor
```

---

## Pole Count Determination

**Current Assumption:** 14 poles (7 pole pairs)

**Verification Methods:**

### Method 1: Physical Count (Most Accurate)
1. Look at motor bell (rotating part)
2. Count the magnets on inside of bell
3. Pole count = number of magnets
4. Typical for 2822 size: 12 or 14 poles

### Method 2: Telemetry RPM Check
1. Configure ESC with pole count = 14
2. Enable DShot telemetry
3. Spin motor at known throttle (e.g., 50%)
4. Read eRPM from telemetry
5. Calculate: `Mechanical RPM = eRPM / pole_pairs`
6. Compare to expected RPM: `Expected RPM = (Voltage × KV) × throttle%`
7. If mismatch, try pole count = 12 or 16

### Method 3: AM32 Configurator Auto-Detect
1. Connect via parameter adjuster
2. Use AM32 configurator's auto-detection feature
3. Software measures motor response and determines pole count

**Action:** Verify pole count during initial ESC configuration with parameter adjuster

---

## ESC Configuration Checklist

**Before installing in robot, configure via parameter adjuster:**

### Basic Settings
- [x] Motor Direction: Normal (or reversed if needed)
- [x] Bidirectional: OFF (weapon spins one direction)
- [x] Brake on Stop: ON (safety)

### Motor Settings
- [ ] **Motor Poles:** Verify actual count (12, 14, or 16)
- [x] Motor KV: 1100
- [x] Startup Power: 5-6 (medium)
- [x] Motor Timing: 15-20° (auto-adjust if needed)

### Protection Settings
- [ ] **Current Limit: 10A** (CRITICAL!)
- [x] Temperature Limit: 70°C
- [x] Low Voltage Cutoff: OFF (robot handles this)

### Protocol Settings
- [x] PWM Frequency: 24-48 kHz
- [x] Throttle Min: 1000μs
- [x] Throttle Max: 2000μs
- [x] Demag Compensation: High (for sudden loads)
- [x] Sine Mode: OFF (trapezoidal, more torque)

### Telemetry
- [x] DShot Telemetry: ON (provides voltage/current/temp/RPM feedback)

---

## Testing Protocol

### Phase 1: Bench Testing (No Load)
1. Configure ESC with parameter adjuster
2. Verify current limit is 10A
3. Verify pole count setting
4. Test motor direction
5. Test telemetry reading

### Phase 2: Initial Robot Testing (Light Load)
1. Install in robot
2. Use DShot mode: `weapon_set_control_mode(WEAPON_MODE_DSHOT)`
3. Start at 25% power
4. Monitor current via telemetry
5. Monitor temperature via telemetry
6. Verify current stays below 9A

### Phase 3: Incremental Power Testing
1. Increase power in 10% increments
2. Monitor current at each step
3. Monitor temperature at each step
4. **STOP if current exceeds 9A**
5. **STOP if temperature exceeds 60°C**
6. Find safe maximum power level

### Phase 4: Impact Testing
1. Start with soft impacts (foam targets)
2. Monitor current spikes during impacts
3. Watch for thermal buildup
4. **NEVER exceed 9.9A sustained**
5. Allow cool-down between tests

---

## Safety Warnings

⚠️ **MOTOR POWER LIMITATIONS:**
- This is a **DRONE MOTOR**, not a weapon motor
- Max current 9.9A is **VERY LOW** for combat robotics
- Designed for continuous loads, **NOT shock loads**
- **Will overheat** quickly under weapon loads

⚠️ **CURRENT LIMIT CRITICAL:**
- Firmware default (40A) will **DESTROY THIS MOTOR**
- **MUST change to 10A** before any testing
- ESC may not protect motor if limit too high

⚠️ **THERMAL MANAGEMENT:**
- Small motor has limited heat capacity
- Monitor temperature via telemetry continuously
- Stop operation if temperature exceeds 70°C
- Allow adequate cool-down between runs

⚠️ **MECHANICAL STRESS:**
- 0.125" (3.17mm) shaft is relatively small
- Avoid large weapon loads on this shaft
- Consider 4mm shaft variant for robustness (as manufacturer suggests)

---

## Recommended Upgrades for Combat Use

If this motor proves underpowered or overheats:

**Option 1:** Larger weapon motor (dedicated combat design)
- Typical combat motor: 20-60A continuous
- Designed for shock loads
- Larger shaft (4-5mm)
- Better thermal capacity

**Option 2:** Better cooling for current motor
- Active airflow over motor
- Reduce duty cycle (spin up only when needed)
- Larger heatsinking

**Option 3:** Gear reduction
- Use gearbox to reduce motor load
- Trade speed for torque
- Reduces current draw
- Protects motor from shock

---

## Summary

### CRITICAL ACTION REQUIRED
**Change current limit from 40A to 10A** - this is a safety issue!

### MUST VERIFY
**Motor pole count** - affects performance and telemetry accuracy

### RECOMMENDED
- Enable brake on stop for safety
- Lower temperature limit to 70°C
- Use parameter adjuster for initial config
- Test incrementally with current monitoring

### HARDWARE COMPATIBILITY
✓ Firmware is compatible with AT32F421 ESC
✓ DShot protocol will work perfectly
✓ Telemetry should work (test to confirm)
✓ No code changes needed (except current limit)
⚠️ Motor may be underpowered for weapon use

---

**Created:** 2025-11-18
**Status:** Awaiting pole count verification and current limit fix
