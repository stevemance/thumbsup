# ThumbsUp Combat Robot - Hardware Bringup Plan
## Comprehensive Testing and Validation Protocol

**Date Created:** 2025-11-18
**Robot:** ThumbsUp (RP2040 Pico W based combat robot)
**Motor:** FingerTech Silver Spark F2822-1100KV (0.125" shaft)
**ESC:** AT32F421-based AM32 ESC
**Test Equipment:** Siglent SDS1202X-E oscilloscope, bench power supply, multimeter

---

## ⚠️ CRITICAL SAFETY WARNINGS

**READ BEFORE STARTING:**

1. **Motor Power Limitations:**
   - Max current: 9.9A (VERY LOW for weapon motor)
   - Max voltage: 11.1V (3S LiPo max)
   - Max power: 102W
   - This is a DRONE MOTOR - not designed for impact loads!

2. **Current Limit CRITICAL:**
   - ESC must be configured to 10A max
   - Exceeding 9.9A will damage motor permanently
   - Monitor current continuously during testing

3. **Thermal Protection:**
   - Motor has limited heat capacity (41g small motor)
   - Stop testing if temperature exceeds 60°C
   - Allow 5+ minutes cool-down between high-power runs

4. **Mechanical Safety:**
   - Remove weapon/spinner before ANY powered testing
   - Secure robot to bench (zip ties, clamps, test stand)
   - Keep hands/tools clear of motor shaft
   - Wear safety glasses

5. **Electrical Safety:**
   - Use current-limited bench supply for initial tests
   - Set bench supply to 3A limit for safety
   - Never exceed 11.1V on motor
   - Disconnect battery when making wiring changes

---

## Test Equipment Setup

### Required Equipment

**Essential:**
- [ ] Siglent SDS1202X-E oscilloscope
- [ ] Bench power supply (0-12V, 3A+ capable)
- [ ] Multimeter (DC voltage, current, resistance)
- [ ] USB cable for parameter adjuster
- [ ] USB cable for RP2040 Pico W programming
- [ ] 3S LiPo battery (11.1V nominal, 1000+ mAh)
- [ ] LiPo safety bag

**Recommended:**
- [ ] Current clamp meter (for non-invasive current monitoring)
- [ ] Infrared thermometer or thermal camera (motor temp monitoring)
- [ ] Oscilloscope probes (10:1 passive probes)
- [ ] Small test stand or vise to secure robot
- [ ] Notebook for recording measurements

**Safety Gear:**
- [ ] Safety glasses
- [ ] Fire extinguisher nearby (for LiPo safety)

### Oscilloscope Configuration

**Siglent SDS1202X-E Settings:**
```
Bandwidth: 200 MHz (more than sufficient for DShot1200)
Sample Rate: Use at least 100 MSa/s for DShot signals
Memory Depth: 14 Mpts available (use Deep memory for long captures)

Recommended probe settings:
- Attenuation: 1X for 3.3V logic signals (or 10X if 1X not available)
- Coupling: DC
- Bandwidth Limit: Off (full 200 MHz)
```

**Triggering for DShot:**
```
Trigger Type: Edge
Trigger Source: Channel measuring GP4
Trigger Level: 1.65V (mid-point of 3.3V logic)
Trigger Slope: Rising edge
Trigger Mode: Normal (to capture packets as they occur)
```

---

## Phase 0: Pre-Flight Checks (30 minutes)

**Objective:** Verify all hardware is safe and ready for testing.

### 0.1: Visual Inspection

- [ ] **Motor:**
  - [ ] Check for physical damage (cracks, dents)
  - [ ] Verify shaft spins freely by hand (no grinding)
  - [ ] Inspect wire insulation (no exposed copper)
  - [ ] Check bullet connectors for corrosion

- [ ] **ESC:**
  - [ ] Inspect for physical damage (blown components, burns)
  - [ ] Verify all solder joints are intact
  - [ ] Check wire insulation
  - [ ] Verify pads are not bridged

- [ ] **RP2040 Pico W:**
  - [ ] Inspect for physical damage
  - [ ] Verify USB connector is intact
  - [ ] Check all GPIO pins for damage

- [ ] **Battery:**
  - [ ] Check voltage: 12.6V (fully charged) or 11.1V nominal
  - [ ] Inspect for swelling/damage (if swollen, DISPOSE SAFELY)
  - [ ] Verify balance connector is intact
  - [ ] Check main connector for damage

### 0.2: Resistance Measurements

**Motor Phase Resistance:**
```
Expected: ~0.19Ω (per spec: 0.192Ω internal resistance)
Acceptable range: 0.15Ω - 0.25Ω

Measure between motor phases (any two wires):
Phase A-B: _______ Ω
Phase B-C: _______ Ω
Phase A-C: _______ Ω

All three should be approximately equal (±10%)
If significantly different → motor winding fault, DO NOT USE
```

**ESC Power Rails:**
```
Measure resistance between ESC V+ and GND:
Expected: >1kΩ (ESC powered off)

R(V+ to GND): _______ Ω

If <100Ω → possible short, investigate before powering
If open (>10MΩ) → normal for unpowered ESC
```

### 0.3: Continuity Checks

- [ ] Verify ESC signal pad 'S' has no short to GND
- [ ] Verify ESC signal pad 'S' has no short to V+
- [ ] Verify RP2040 GP4 has no short to GND
- [ ] Verify RP2040 GP4 has no short to 3V3

### 0.4: Firmware Verification

**Upload latest firmware to RP2040:**

```bash
cd /home/smance/projects/thumbsup/firmware
mkdir -p build && cd build
cmake ..
make -j4

# Upload firmware (hold BOOTSEL, connect USB, release BOOTSEL)
cp thumbsup.uf2 /media/username/RPI-RP2/
```

**Verify version:**
- [ ] Firmware version: 1.0.0 (or later)
- [ ] Current limit configured: 10A (CRITICAL!)
- [ ] Temperature limit: 70°C
- [ ] Motor KV: 1100
- [ ] Check git commit matches: `f4c6422` or later

---

## Phase 1: ESC Configuration (45 minutes)

**Objective:** Configure AM32 ESC with correct motor parameters using parameter adjuster.

### 1.1: Parameter Adjuster Connection

**Wiring:**
```
Parameter Adjuster         ESC
─────────────────         ───
USB        → PC
GND        → G (ground pad)
5V         → (leave disconnected - power from bench supply)
S          → S (signal pad)

Bench Power Supply         ESC
──────────────────         ───
V+ (set to 11.1V)  →      V (power pad)
V- (GND)           →      G (ground pad)
```

**Bench Supply Settings:**
```
Voltage: 11.1V (3S nominal)
Current Limit: 3.0A (safety limit for motor protection)
```

**Safety Check:**
- [ ] Verify motor is NOT connected to ESC yet
- [ ] Verify current limit on bench supply is set to 3A
- [ ] Verify voltage is 11.1V (not higher!)

**Power on sequence:**
1. [ ] Connect parameter adjuster USB to PC
2. [ ] Set bench supply: 11.1V, 3A limit, OUTPUT OFF
3. [ ] Connect bench supply to ESC (double-check polarity!)
4. [ ] Turn on bench supply OUTPUT
5. [ ] Verify ESC powers up (may hear startup beeps)

### 1.2: AM32 Configurator Software

**Download and install:**
- Windows: AM32 Multi Tool from https://github.com/AlkaMotors/AM32_MULTI_GUI
- Linux/Mac: Use AM32 Web Configurator or Windows VM

**Open configurator:**
- [ ] Launch AM32 Multi Tool
- [ ] Select correct COM port (parameter adjuster)
- [ ] Set baud rate: 19200 (for config mode)
- [ ] Click "Connect"

**If connection fails:**
- Check USB drivers installed
- Try different USB port
- Verify ESC is powered (check bench supply showing current draw)
- Try "Detect" or "Auto-connect" button

### 1.3: Read Current ESC Configuration

**Before changing anything:**
- [ ] Click "Read Settings" button
- [ ] Save current configuration to file (backup!)
- [ ] Record firmware version: _____________

**Check firmware version:**
```
Expected: AM32 v2.x or newer
If older firmware, consider updating to latest AM32 release
```

### 1.4: Motor Pole Count Detection

**CRITICAL: Must determine actual pole count!**

**Method 1: Physical Count (Most Accurate)**
1. [ ] Remove motor from ESC (disconnect bullet connectors)
2. [ ] Look inside motor bell (rotating part with magnets)
3. [ ] Count number of magnets around inside perimeter
4. [ ] Pole count = number of magnets
5. [ ] Record pole count: _______ poles

**Typical for 2822 motor: 12 or 14 poles**

**Method 2: Auto-Detection (If Method 1 not possible)**
1. [ ] Connect motor to ESC (bullet connectors)
2. [ ] In AM32 configurator, use "Auto-Detect Motor" feature
3. [ ] Software will spin motor briefly and detect pole count
4. [ ] Verify detected count seems reasonable (12-16 range)
5. [ ] Record pole count: _______ poles

**Method 3: Trial and Error (Last Resort)**
1. [ ] Start with pole count = 14 (common for 2822)
2. [ ] After configuration, test motor and read telemetry RPM
3. [ ] Compare telemetry RPM to calculated RPM
4. [ ] If mismatch, try 12 or 16 poles

### 1.5: Configure Critical Parameters

**CRITICAL SETTINGS (Must be exact):**

```
╔═══════════════════════════════════════════════════════╗
║  CRITICAL PARAMETERS - VERIFY CAREFULLY               ║
╠═══════════════════════════════════════════════════════╣
║  Motor Poles:          [  ] poles (from detection)    ║
║  Motor KV:             1100                           ║
║  Current Limit:        10 A  ◄─ CRITICAL!            ║
║  Temperature Limit:    70 °C                          ║
║  Motor Direction:      Normal (test later, may flip) ║
╚═══════════════════════════════════════════════════════╝
```

**Important Settings:**

```
╔═══════════════════════════════════════════════════════╗
║  BASIC SETTINGS                                       ║
╠═══════════════════════════════════════════════════════╣
║  Bidirectional:        OFF (unidirectional weapon)    ║
║  Brake on Stop:        ON (safety)                    ║
║  Startup Power:        5-6 (medium)                   ║
║  Motor Timing:         15-20° (auto-adjust if needed) ║
╚═══════════════════════════════════════════════════════╝
```

**Protocol Settings:**

```
╔═══════════════════════════════════════════════════════╗
║  PWM/PROTOCOL SETTINGS                                ║
╠═══════════════════════════════════════════════════════╣
║  PWM Frequency:        24 kHz (or 48 kHz)             ║
║  Throttle Min:         1000 μs                        ║
║  Throttle Max:         2000 μs                        ║
║  Sine Mode:            OFF (trapezoidal)              ║
║  Demag Compensation:   High (for sudden loads)        ║
╚═══════════════════════════════════════════════════════╝
```

**Telemetry Settings:**

```
╔═══════════════════════════════════════════════════════╗
║  TELEMETRY (Highly Recommended)                       ║
╠═══════════════════════════════════════════════════════╣
║  DShot Telemetry:      ON                             ║
║  Telemetry Protocol:   EDT (Extended DShot Telemetry) ║
╚═══════════════════════════════════════════════════════╝
```

**Low Voltage Cutoff:**

```
╔═══════════════════════════════════════════════════════╗
║  VOLTAGE PROTECTION                                   ║
╠═══════════════════════════════════════════════════════╣
║  Low Voltage Cutoff:   OFF (robot firmware handles)   ║
║  (Or set to 9.0V if you want ESC protection too)      ║
╚═══════════════════════════════════════════════════════╝
```

### 1.6: Write and Save Configuration

**Write settings to ESC:**
1. [ ] Review all settings carefully (especially current limit = 10A!)
2. [ ] Click "Write Settings" button
3. [ ] Wait for confirmation (ESC may beep)
4. [ ] ESC will automatically save to EEPROM

**Verify settings were saved:**
1. [ ] Power cycle ESC (turn off bench supply, wait 5s, turn on)
2. [ ] Click "Read Settings" again
3. [ ] Verify all values match what you configured
4. [ ] **Especially verify: Current Limit = 10A, Temp Limit = 70°C**

### 1.7: Motor Direction Test (No Load)

**Connect motor to ESC:**
```
Motor Wire      ESC Pad
──────────      ───────
Phase A    →    ESC output A
Phase B    →    ESC output B
Phase C    →    ESC output C

Note: Order doesn't matter yet, we'll verify direction
```

**Test motor spin:**
1. [ ] In AM32 configurator, use "Motor Test" feature
2. [ ] Start at very low throttle (10%)
3. [ ] Observe motor spin direction
4. [ ] Record direction: CW / CCW (circle one)

**If direction is wrong:**
- Option A: Swap any two motor wires (easiest)
- Option B: Change "Motor Direction" setting in configurator to "Reversed"

**Verify correct direction:**
- [ ] Motor spins in desired direction
- [ ] Motor starts smoothly (no stuttering)
- [ ] Motor stops cleanly when throttle = 0

### 1.8: Configuration Checklist - FINAL VERIFICATION

**Before proceeding, verify ALL of these:**

- [ ] ✓ Motor poles: _______ (actual count from detection)
- [ ] ✓ Motor KV: 1100
- [ ] ✓ **Current limit: 10A** (CRITICAL!)
- [ ] ✓ Temperature limit: 70°C
- [ ] ✓ DShot telemetry: ON
- [ ] ✓ Brake on stop: ON
- [ ] ✓ Motor direction: Correct (verified by test)
- [ ] ✓ Settings saved to EEPROM (verified by read-back)
- [ ] ✓ Configuration backup saved to file

**Power off:**
- [ ] Disconnect motor from ESC
- [ ] Turn off bench supply
- [ ] Disconnect parameter adjuster

---

## Phase 2: DShot Signal Verification (60 minutes)

**Objective:** Use oscilloscope to verify DShot timing, packet structure, and protocol correctness.

### 2.1: Test Setup - PWM Loopback (Baseline)

**Before testing weapon motor, verify RP2040 PWM works:**

**Wiring:**
```
Oscilloscope Ch1  →  GP4 (PIN_WEAPON_PWM)
Oscilloscope GND  →  Pico W GND
```

**No motor connected yet!**

**RP2040 Setup:**
1. [ ] Connect RP2040 to PC via USB
2. [ ] Power up Pico W (LED should light)
3. [ ] Verify firmware is loaded

**Oscilloscope Settings:**
```
Channel 1:
- Coupling: DC
- V/div: 1V (to see 3.3V logic clearly)
- Probe: 1X
- Bandwidth: Full (200 MHz)

Timebase:
- Time/div: 500 μs (to see whole PWM period)

Trigger:
- Source: Ch1
- Type: Edge, Rising
- Level: 1.65V
- Mode: Normal
```

**Test PWM output:**
1. [ ] Use robot controller to set weapon to PWM mode
2. [ ] Set weapon speed to 0% (should see 1000μs pulse)
3. [ ] Verify oscilloscope shows clean 50Hz PWM signal
4. [ ] Measure pulse width: _______ μs (should be ~1000μs)

**Verify PWM range:**
```
Weapon Speed    Expected Pulse    Measured Pulse    Status
────────────    ──────────────    ──────────────    ──────
0%              1000 μs           _______ μs        [ ]
50%             1500 μs           _______ μs        [ ]
100%            2000 μs           _______ μs        [ ]
```

**If PWM is incorrect:**
- Check config.h PWM_MIN_PULSE, PWM_MAX_PULSE values
- Verify PWM frequency is 50Hz
- Check for noise/ringing on signal

**PWM Test Complete:**
- [ ] PWM signal is clean (no excessive ringing)
- [ ] Pulse widths match expected values (±10μs)
- [ ] Signal amplitude is 3.3V (±0.2V)

### 2.2: DShot150 Signal Capture and Analysis

**Switch to DShot mode:**
1. [ ] Use robot controller to switch weapon to DShot mode
2. [ ] Verify firmware is in DSHOT_300 mode (check debug output)

**Oscilloscope Settings for DShot:**
```
Channel 1: GP4
- V/div: 1V
- Time/div: 10 μs (to see several bits)
- Probe: 1X

Trigger:
- Source: Ch1
- Type: Edge, Rising
- Level: 1.65V
- Mode: Normal

Acquisition:
- Sample Rate: Set to maximum (100 MSa/s or higher)
- Memory Depth: Use deep memory if available
```

**Capture DShot packet:**
1. [ ] Set weapon speed to 0% (disarmed - should send throttle value 0)
2. [ ] Capture oscilloscope trace
3. [ ] Save screenshot: `dshot300_throttle_0.png`

**Measure DShot300 timing:**

```
Expected for DShot300: 3.33 μs per bit (300 kbit/s)

Bit '1' timing (nominal):
- High: 2.22 μs (2/3 of bit period)
- Low:  1.11 μs (1/3 of bit period)

Bit '0' timing (nominal):
- High: 1.11 μs (1/3 of bit period)
- Low:  2.22 μs (2/3 of bit period)

Measure actual timings:
Bit '1' High: _______ μs (expected: 2.22 μs ±5%)
Bit '1' Low:  _______ μs (expected: 1.11 μs ±5%)
Bit '0' High: _______ μs (expected: 1.11 μs ±5%)
Bit '0' Low:  _______ μs (expected: 2.22 μs ±5%)

Total bit period: _______ μs (expected: 3.33 μs ±5%)
```

**Verify DShot packet structure:**
```
DShot frame: 16 bits total
[15:5] = Throttle value (11 bits)
[4]    = Telemetry request (1 bit)
[3:0]  = CRC (4 bits)

Packet duration: 16 bits × 3.33 μs = 53.3 μs total

Measure packet duration: _______ μs (expected: ~53 μs)
```

**Test different throttle values:**
```
Set weapon to 25% throttle:
Capture screenshot: dshot300_throttle_25.png
Throttle bits should be: ~512 (25% of 2047)

Set weapon to 50% throttle:
Capture screenshot: dshot300_throttle_50.png
Throttle bits should be: ~1024 (50% of 2047)

Set weapon to 100% throttle:
Capture screenshot: dshot300_throttle_100.png
Throttle bits should be: 2047 (maximum)
```

**Signal quality checks:**
- [ ] Rising edge time: < 10ns (scope should show sharp edges)
- [ ] Falling edge time: < 10ns
- [ ] No significant overshoot (< 10% of 3.3V)
- [ ] No ringing lasting more than 100ns
- [ ] Clean logic levels: 0V ±0.2V (low), 3.3V ±0.2V (high)

**If timing is wrong (critical bug):**
```
Check firmware/src/dshot.c line 123:
Should be: cycles_per_bit = 15

Check firmware/src/dshot.pio line 220:
Should document 15 cycles per bit

If incorrect, this is a CRITICAL bug - contact developer
```

### 2.3: DShot Packet Decode Verification

**Use oscilloscope's serial decode feature (if available):**

**SDS1202X-E Serial Decode Setup:**
```
Protocol: UART (approximate - DShot is custom but similar)
Note: DShot decode may not be built-in, manual decode required
```

**Manual Decode Method:**

**Capture single packet at high resolution:**
1. [ ] Set weapon to known throttle (e.g., 50% = throttle value 1024)
2. [ ] Trigger on packet start
3. [ ] Increase timebase to see all 16 bits clearly
4. [ ] Use oscilloscope cursors to measure each bit

**Decode packet bit-by-bit:**
```
Bit position:  15 14 13 12 11 10  9  8  7  6  5  4  3  2  1  0
               ┌──────────────────────────┬──┬──────────┐
               │ Throttle (11 bits)       │T │CRC (4b)  │
               └──────────────────────────┴──┴──────────┘

Example for 50% throttle (1024 decimal = 0x400):
Throttle = 1024 = 0b10000000000 (11 bits)
Telemetry = 0 (not requesting)
CRC = (calculate using polynomial 0x19)

Expected packet: 0b0100000000000[CRC]

Measure from scope:
Bit 15: ___ (MSB of throttle)
Bit 14: ___
Bit 13: ___
Bit 12: ___
Bit 11: ___
Bit 10: ___
Bit  9: ___
Bit  8: ___
Bit  7: ___
Bit  6: ___
Bit  5: ___ (LSB of throttle)
Bit  4: ___ (telemetry request)
Bit  3: ___ (CRC bit 3)
Bit  2: ___ (CRC bit 2)
Bit  1: ___ (CRC bit 1)
Bit  0: ___ (CRC bit 0, LSB)
```

**Verify CRC calculation:**
```
CRC-4 polynomial: 0x19 (x⁴ + x³ + x + 1)

Use online CRC calculator or reference implementation
Input: Throttle (11 bits) + Telemetry (1 bit) = 12 bits
Output: 4-bit CRC

Calculated CRC: _______ (binary)
Measured CRC:   _______ (from scope)

Match? [ ] Yes  [ ] No (if no, this is a bug!)
```

### 2.4: DShot Command Verification

**Test special DShot command:**

**Send beep command:**
```
Command: DSHOT_CMD_BEEP1 = 1
Should be sent 10 times (per DShot spec)
Each command is 16-bit packet with throttle = 0, command in lower bits
```

**Capture beep command sequence:**
1. [ ] Trigger robot to send beep command (use debug console if available)
2. [ ] Capture oscilloscope trace showing multiple command packets
3. [ ] Count number of packets: _______ (expected: 10)
4. [ ] Measure time between packets: _______ ms (expected: ~1ms)

**If ESC beeps:**
- [ ] ✓ DShot commands working correctly
- [ ] ✓ ESC is receiving and decoding DShot properly

**If ESC doesn't beep:**
- Check command packet structure on scope
- Verify CRC is correct
- Check ESC is in correct mode (not in bootloader)

### 2.5: DShot Timing Analysis Summary

**Complete this checklist:**

```
╔═══════════════════════════════════════════════════════════╗
║  DSHOT300 TIMING VERIFICATION                             ║
╠═══════════════════════════════════════════════════════════╣
║  Bit period:           _______ μs  (expect: 3.33 μs ±5%) ║
║  Bit '1' high time:    _______ μs  (expect: 2.22 μs ±5%) ║
║  Bit '1' low time:     _______ μs  (expect: 1.11 μs ±5%) ║
║  Bit '0' high time:    _______ μs  (expect: 1.11 μs ±5%) ║
║  Bit '0' low time:     _______ μs  (expect: 2.22 μs ±5%) ║
║  Packet duration:      _______ μs  (expect: 53.3 μs)     ║
║  Signal amplitude:     _______ V   (expect: 3.3V ±0.2V)  ║
║  Rise time:            _______ ns  (expect: <10ns)       ║
║  Fall time:            _______ ns  (expect: <10ns)       ║
╠═══════════════════════════════════════════════════════════╣
║  Throttle decode:      [ ] Correct  [ ] Incorrect        ║
║  CRC calculation:      [ ] Correct  [ ] Incorrect        ║
║  Command packets:      [ ] Working  [ ] Not working      ║
║  ESC beep response:    [ ] Yes      [ ] No               ║
╚═══════════════════════════════════════════════════════════╝
```

**If any timing is outside ±5% tolerance:**
- This is a CRITICAL issue
- Do NOT proceed to motor testing
- Review firmware DShot implementation
- Check PIO clock divider calculations

**DShot Signal Verification Complete:**
- [ ] All timing measurements within spec (±5%)
- [ ] Packet structure correct
- [ ] CRC calculation verified
- [ ] Commands working (ESC beeps)
- [ ] Screenshots saved for documentation

---

## Phase 3: Motor Integration - Bench Testing (90 minutes)

**Objective:** Connect motor to ESC, verify operation, measure current/temperature, test telemetry.

### 3.1: Wiring and Connection

**Power down everything:**
- [ ] Disconnect bench supply
- [ ] Disconnect USB from RP2040
- [ ] Wait 30 seconds for capacitors to discharge

**Final wiring:**
```
Component           Connection
─────────           ──────────
Bench Supply V+  →  ESC 'V' pad
Bench Supply GND →  ESC 'G' pad
ESC Signal 'S'   →  RP2040 GP4
ESC GND          →  RP2040 GND
Motor Phase A    →  ESC Motor Out A
Motor Phase B    →  ESC Motor Out B
Motor Phase C    →  ESC Motor Out C

Oscilloscope Ch1 →  RP2040 GP4 (DShot signal)
Oscilloscope GND →  RP2040 GND
```

**Current monitoring:**
```
Option A (if using current clamp):
  Clamp around bench supply V+ wire

Option B (bench supply built-in meter):
  Read current from bench supply display

Option C (multimeter in series):
  Bench V+ → Multimeter → ESC V+
  Set multimeter to DC A, 10A range
```

**Bench supply settings:**
```
Voltage: 11.1V (3S nominal)
Current Limit: 3.0A (for initial testing - safety!)
Over-Voltage Protection: 12V
Output: OFF (don't turn on yet)
```

**Safety checks before powering:**
- [ ] All connections tight and insulated
- [ ] No wire strands touching adjacent connections
- [ ] Motor is secured (can't fly off bench)
- [ ] Weapon/spinner is removed (bare motor shaft only)
- [ ] Safety glasses on
- [ ] Fire extinguisher nearby

### 3.2: Power-On Sequence

**Initial power-on:**
1. [ ] Turn on oscilloscope
2. [ ] Connect RP2040 USB to PC (powers Pico W)
3. [ ] Verify RP2040 boots (LED activity)
4. [ ] Verify firmware loads (check serial output if available)
5. [ ] Turn on bench supply OUTPUT
6. [ ] **Watch current draw closely**

**Expected current draw:**
```
ESC + motor (no throttle): 0.05 - 0.2A (idle)

If current draw is:
> 0.5A → Something wrong, turn off immediately
> 1.0A → Short circuit, turn off immediately
< 0.05A → ESC may not be powered, check connections
```

**Initial current draw:** _______ A (record actual)

**ESC startup:**
- [ ] ESC may beep startup tones (normal)
- [ ] Motor should NOT move yet (zero throttle)
- [ ] Current should stabilize at idle level

### 3.3: First Spin Test - 10% Power

**Set robot to DShot mode:**
- [ ] Use controller or debug console to select WEAPON_MODE_DSHOT
- [ ] Verify mode switch successful (check serial output)

**Increase current limit:**
```
Bench Supply Current Limit: 3.0A → 5.0A
(Still well below 9.9A motor max, but allows motor to spin)
```

**Arm weapon system:**
- [ ] Arm weapon (use controller button sequence)
- [ ] Verify weapon state changes to ARMED

**Set throttle to 10%:**
- [ ] Slowly increase weapon throttle to 10%
- [ ] **Watch motor and current closely**

**Observations at 10% throttle:**
```
Motor behavior:
- [ ] Motor starts spinning smoothly
- [ ] Motor spins in correct direction
- [ ] No stuttering or jerking
- [ ] No unusual vibration
- [ ] No unusual noise (whining, grinding)

Electrical measurements:
Current draw: _______ A (expect: 0.5 - 1.5A at 10%)
Voltage sag:  _______ V (bench supply should hold 11.1V)
```

**If motor doesn't start:**
- Check DShot signal on oscilloscope (should show changing throttle)
- Verify ESC is receiving signal (check signal wiring)
- Try increasing throttle slightly (may need >10% to overcome startup)

**If motor direction is wrong:**
- Option A: Swap any two motor wires
- Option B: Use DShot command to reverse direction
- Option C: Change direction setting in ESC config

**Run for 30 seconds:**
- [ ] Monitor current continuously
- [ ] Monitor for any smoke or burning smell
- [ ] Check motor temperature by touch (should be barely warm)

**Shutdown test:**
- [ ] Set throttle to 0%
- [ ] Motor should stop within 1-2 seconds
- [ ] If brake enabled, should stop faster (active braking)

### 3.4: Incremental Power Testing

**Test at increasing power levels:**

**25% Power Test:**
```
Current Limit: 6.0A
Throttle: 25%
Run time: 30 seconds

Current draw: _______ A (expect: 1.5 - 3.0A)
Motor temp (after 30s): _______ °C (use IR thermometer)
Motor behavior: [ ] Smooth [ ] Issues: ___________
```

**Stop and cool down: Wait 2 minutes**

**50% Power Test:**
```
Current Limit: 8.0A
Throttle: 50%
Run time: 20 seconds (shorter due to higher power)

Current draw: _______ A (expect: 3.0 - 6.0A)
Motor temp (after 20s): _______ °C (should be warm but <50°C)
Motor behavior: [ ] Smooth [ ] Issues: ___________
```

**Stop and cool down: Wait 5 minutes**

**75% Power Test:**
```
Current Limit: 10.0A (ESC limit)
Throttle: 75%
Run time: 10 seconds (shorter due to high power)

Current draw: _______ A (expect: 6.0 - 9.0A, MUST be <9.9A)
Motor temp (after 10s): _______ °C (will be hot, <60°C?)
Motor behavior: [ ] Smooth [ ] Issues: ___________

⚠️ If current exceeds 9A, STOP TEST immediately
⚠️ If motor temp exceeds 60°C, STOP TEST immediately
```

**Stop and cool down: Wait 10 minutes**

**100% Power Test (OPTIONAL - only if 75% test was good):**
```
Current Limit: 10.0A (ESC limit)
Throttle: 100%
Run time: 5 seconds MAX (very short burst)

Current draw: _______ A (expect: 7.0 - 9.9A, MUST be <9.9A)
Motor temp (before): _______ °C (should be cool from previous rest)
Motor temp (after 5s): _______ °C (will be hot)
Motor behavior: [ ] Smooth [ ] Issues: ___________

⚠️ CRITICAL: Do NOT run at 100% for more than 5 seconds!
⚠️ This motor is NOT designed for continuous high power!
```

**STOP immediately if:**
- Current exceeds 9.5A
- Motor temperature exceeds 60°C
- Motor makes unusual noise
- You smell burning
- Excessive vibration
- ESC cuts out (over-temp protection)

### 3.5: Current vs. Throttle Characterization

**Create current draw profile:**

```
Throttle    Current Draw    Motor Temp    Notes
────────    ────────────    ──────────    ─────
0%          _______ A       _______ °C    (idle)
10%         _______ A       _______ °C
25%         _______ A       _______ °C
50%         _______ A       _______ °C
75%         _______ A       _______ °C
100%        _______ A       _______ °C    (5s max!)

Max safe continuous throttle: _______ % (where current < 8A)
Max safe burst throttle: _______ % (where current < 9.5A)
```

**Plot current vs. throttle curve:**
```
Expected: Approximately linear (I ∝ throttle%)
Reality: May be non-linear due to motor efficiency curve

Use this data to determine safe operating limits for competition
```

### 3.6: Thermal Testing

**Objective:** Determine thermal limits for continuous operation.

**Continuous run test:**
```
Throttle: 50% (or max safe continuous from above)
Current limit: 10A
Run time: 60 seconds
Measure temperature every 10 seconds

Time    Motor Temp    Current    Notes
────    ──────────    ───────    ─────
0s      _______ °C    _______ A  (start cool)
10s     _______ °C    _______ A
20s     _______ °C    _______ A
30s     _______ °C    _______ A
40s     _______ °C    _______ A
50s     _______ °C    _______ A
60s     _______ °C    _______ A  (final temp)

STOP if temperature exceeds 60°C at any point!
```

**Cool-down profile:**
```
After 60s run at 50%, turn off motor and measure cool-down:

Time    Motor Temp    Notes
────    ──────────    ─────
0s      _______ °C    (motor just stopped)
30s     _______ °C
60s     _______ °C
120s    _______ °C
300s    _______ °C    (should be near ambient)
```

**Thermal limits:**
```
Safe continuous operating temp: _______ °C (recommend <50°C)
Max safe burst temp: _______ °C (recommend <60°C)
Time to reach 50°C at 50% throttle: _______ seconds
Cool-down time from 50°C to 30°C: _______ seconds

Recommended duty cycle for combat:
- Spin up for: _______ seconds
- Cool down for: _______ seconds
```

### 3.7: Emergency Stop Response Time

**Objective:** Verify weapon_emergency_stop() works correctly.

**Test setup:**
1. [ ] Spin motor to 50% throttle
2. [ ] Let stabilize for 5 seconds
3. [ ] Trigger emergency stop (controller button or debug command)
4. [ ] Use oscilloscope to measure stop time

**Measurements:**
```
Scope Ch1: GP4 (DShot signal)
Scope Ch2: Motor phase A (to see motor current decay)

Measure on scope:
Time from E-stop trigger to DShot signal = 0: _______ ms
Time from E-stop trigger to motor stopped: _______ ms

Expected: <50ms total, <10ms ideal

If brake enabled, motor should stop faster than coast
```

**Emergency stop checklist:**
- [ ] DShot signal goes to 0 immediately
- [ ] GPIO forced low (hardware level)
- [ ] Motor stops within 50ms
- [ ] Multiple stop methods attempted (defense in depth)
- [ ] No errors or crashes during emergency stop

### 3.8: Motor Bench Test Summary

**Complete the checklist:**

```
╔═════════════════════════════════════════════════════════╗
║  MOTOR BENCH TEST RESULTS                               ║
╠═════════════════════════════════════════════════════════╣
║  Motor starts smoothly:            [ ] Yes  [ ] No      ║
║  Direction correct:                [ ] Yes  [ ] No      ║
║  No unusual vibration:             [ ] Yes  [ ] No      ║
║  No unusual noise:                 [ ] Yes  [ ] No      ║
║  Current within limits (<9.9A):    [ ] Yes  [ ] No      ║
║  Temperature acceptable (<60°C):   [ ] Yes  [ ] No      ║
║  Emergency stop works (<50ms):     [ ] Yes  [ ] No      ║
║  ESC protection working:           [ ] Yes  [ ] No      ║
╠═════════════════════════════════════════════════════════╣
║  Max safe continuous throttle:     _______ %            ║
║  Max safe burst throttle:          _______ %            ║
║  Max current observed:             _______ A            ║
║  Max temperature observed:         _______ °C           ║
║  Emergency stop time:              _______ ms           ║
╚═════════════════════════════════════════════════════════╝
```

**Issues found:**
```
List any problems encountered:
1. _______________________________________________________
2. _______________________________________________________
3. _______________________________________________________
```

**If all tests pass:**
- [ ] Motor is safe for integration into robot
- [ ] Proceed to Phase 4 (Telemetry Validation)

**If critical issues found:**
- [ ] Do NOT integrate motor until issues resolved
- [ ] Review ESC configuration
- [ ] Check motor/ESC compatibility
- [ ] Consider motor replacement if underpowered

---

## Phase 4: EDT Telemetry Validation (45 minutes)

**Objective:** Verify bidirectional DShot telemetry, validate data accuracy.

### 4.1: Telemetry Signal Capture

**Oscilloscope setup for EDT:**
```
DShot is bidirectional:
1. RP2040 sends DShot packet (GP4 output)
2. ESC receives packet
3. ~30μs later, ESC sends telemetry (GP4 becomes input)
4. RP2040 receives telemetry

Need to capture both TX and RX on same pin!

Scope settings:
Ch1: GP4 (DShot TX and EDT RX)
Timebase: 50 μs/div (to see packet + telemetry)
Trigger: Rising edge on first DShot packet
Acquisition mode: Single shot
```

**Enable telemetry requests:**
```
Modify firmware temporarily or use debug console:
dshot_send_throttle(MOTOR_WEAPON, 1024, true);  // true = request telemetry
```

**Capture EDT frame:**
1. [ ] Set motor to 50% throttle
2. [ ] Enable telemetry request in DShot packets
3. [ ] Trigger oscilloscope on DShot TX packet
4. [ ] Capture both TX packet and RX telemetry response
5. [ ] Save screenshot: `edt_telemetry_capture.png`

**Measure EDT timing:**
```
DShot TX packet duration: _______ μs (should be ~53μs for DShot300)
Gap between TX end and EDT start: _______ μs (expect: ~30μs)
EDT frame duration: _______ μs (21 bits + encoding)
```

### 4.2: EDT Frame Decoding

**EDT frame structure (AM32 variant):**
```
Total: 21 bits transmitted using GCR encoding
- 4 × 5-bit GCR symbols = 20 bits (encodes 16 data bits)
- 1 start bit
- Data encodes: value (12 bits) + CRC (4 bits)
```

**Decode EDT frame manually:**
```
Use oscilloscope cursors to identify each bit:

Start bit: ___ (should be long high pulse)

GCR symbol 1 (bits 4-0): _____ (5 bits)
GCR symbol 2 (bits 4-0): _____ (5 bits)
GCR symbol 3 (bits 4-0): _____ (5 bits)
GCR symbol 4 (bits 4-0): _____ (5 bits)

Convert GCR to data using GCR decode table:
Data nibble 1: ____ (4 bits)
Data nibble 2: ____ (4 bits)
Data nibble 3: ____ (4 bits)
Data nibble 4: ____ (4 bits)

Total data: ____________ (16 bits)
Value (12 bits): ____________
CRC (4 bits): ____________
```

**GCR Decode Table:**
```
GCR Input   →   Data Output
─────────       ───────────
01001 (0x09)  →   0000 (0x0)
01010 (0x0A)  →   0001 (0x1)
01011 (0x0B)  →   0010 (0x2)
01101 (0x0D)  →   0011 (0x3)
01110 (0x0E)  →   0100 (0x4)
01111 (0x0F)  →   0101 (0x5)
10010 (0x12)  →   0110 (0x6)
10011 (0x13)  →   0111 (0x7)
10100 (0x14)  →   1000 (0x8)
10101 (0x15)  →   1001 (0x9)
10110 (0x16)  →   1010 (0xA)
10111 (0x17)  →   1011 (0xB)
11010 (0x1A)  →   1100 (0xC)
11011 (0x1B)  →   1101 (0xD)
11100 (0x1C)  →   1110 (0xE)
11101 (0x1D)  →   1111 (0xF)
```

### 4.3: Telemetry Data Validation

**Read telemetry from firmware:**
```
Use debug console or modify test code:

dshot_telemetry_t telem;
if (dshot_get_telemetry(MOTOR_WEAPON, &telem)) {
    printf("eRPM: %u\n", telem.erpm);
    printf("Voltage: %u cV\n", telem.voltage_cV);
    printf("Current: %u cA\n", telem.current_cA);
    printf("Temp: %u C\n", telem.temperature_C);
}
```

**Record telemetry values:**
```
At 50% throttle, 11.1V bench supply:

Firmware reported values:
eRPM:    _______ (electrical RPM)
Voltage: _______ cV (divide by 100 for volts)
Current: _______ cA (divide by 100 for amps)
Temp:    _______ °C

Calculated mechanical RPM:
eRPM / pole_pairs = _______ / _______ = _______ RPM

Expected mechanical RPM:
(11.1V × 1100 KV) × 50% = _______ RPM

RPM Match? [ ] Yes (±10%)  [ ] No (pole count may be wrong)
```

**Validate against measurements:**
```
Telemetry Voltage vs Multimeter:
Telemetry: _______ V
Multimeter: _______ V (measure at ESC V+ pad)
Difference: _______ V (should be <0.5V)

Telemetry Current vs Ammeter:
Telemetry: _______ A
Ammeter: _______ A (bench supply reading or clamp meter)
Difference: _______ A (should be <0.2A or <10% of reading)

Telemetry Temp vs IR Thermometer:
Telemetry: _______ °C
IR Thermometer: _______ °C (measure motor case)
Difference: _______ °C (should be <10°C)
```

**If RPM doesn't match:**
```
Possible causes:
1. Wrong pole count in ESC config
   - Try 12 poles instead of 14, or vice versa
   - Retest and compare RPM

2. EDT bit extraction positions wrong
   - This is the TODO in firmware/src/dshot.c:246
   - May need to adjust bit positions in parse_edt_telemetry()
   - Try shifting all GCR nibble positions by +1 or -1

3. Motor KV is not actually 1100
   - Verify motor part number
   - Some batches may have different KV

Corrective action:
If telemetry voltage/current/temp are correct, but RPM is wrong:
→ Pole count issue (most likely)
If ALL telemetry is garbage:
→ EDT bit extraction issue (firmware bug)
If no telemetry at all:
→ ESC may not support EDT, or not enabled in config
```

### 4.4: Telemetry Update Rate

**Measure how often telemetry updates:**

```
Method: Add debug prints with timestamps

while (motor_running) {
    if (dshot_get_telemetry(MOTOR_WEAPON, &telem)) {
        printf("%lu: eRPM=%u V=%u I=%u T=%u\n",
               time_ms, telem.erpm, telem.voltage_cV,
               telem.current_cA, telem.temperature_C);
    }
    sleep_ms(10);
}

Observe update rate from timestamps:
Telemetry update period: _______ ms (expect: 10-100ms)
Telemetry update rate: _______ Hz

EDT telemetry is async - ESC sends different values in rotation:
Frame 1: eRPM
Frame 2: Voltage
Frame 3: Current
Frame 4: Temperature
(Pattern may vary by ESC firmware)
```

### 4.5: Telemetry Freshness Check

**Verify telemetry age checking works:**

```
Firmware has 100ms max age check (dshot.c:620)

Test:
1. Spin motor, verify telemetry updating
2. Stop motor (set throttle to 0)
3. Wait 200ms
4. Try to read telemetry

Expected: dshot_get_telemetry() should return false
Actual: [ ] Returned false (correct)  [ ] Returned stale data (bug)

If stale data returned:
→ Check firmware TELEMETRY_MAX_AGE_MS implementation
```

### 4.6: EDT Telemetry Summary

**Complete the checklist:**

```
╔═════════════════════════════════════════════════════════╗
║  EDT TELEMETRY VALIDATION                               ║
╠═════════════════════════════════════════════════════════╣
║  Telemetry frames received:       [ ] Yes  [ ] No      ║
║  GCR decoding correct:             [ ] Yes  [ ] No      ║
║  Voltage accurate (±0.5V):         [ ] Yes  [ ] No      ║
║  Current accurate (±10%):          [ ] Yes  [ ] No      ║
║  Temperature accurate (±10°C):     [ ] Yes  [ ] No      ║
║  RPM calculation correct (±10%):   [ ] Yes  [ ] No      ║
║  Update rate acceptable (>10Hz):   [ ] Yes  [ ] No      ║
║  Freshness check working:          [ ] Yes  [ ] No      ║
╠═════════════════════════════════════════════════════════╣
║  Telemetry update rate:            _______ Hz           ║
║  Max telemetry age observed:       _______ ms           ║
║  Voltage accuracy:                 ± _______ V          ║
║  Current accuracy:                 ± _______ A          ║
║  Temperature accuracy:             ± _______ °C         ║
║  RPM error:                        ± _______ %          ║
╚═════════════════════════════════════════════════════════╝
```

**If telemetry not working:**
- [ ] Verify "DShot Telemetry: ON" in ESC config
- [ ] Check EDT frame timing on oscilloscope
- [ ] Verify RP2040 GPIO is configured as input after TX
- [ ] Check PIO program for bidirectional mode
- [ ] May need firmware debugging

**If telemetry working:**
- [ ] Document which values are accurate
- [ ] Note any offsets or calibration needed
- [ ] Telemetry can be used for monitoring in competition

---

## Phase 5: Battery Operation Testing (30 minutes)

**Objective:** Verify operation on actual 3S LiPo battery (not bench supply).

### 5.1: Battery Preparation

**Battery selection:**
- [ ] 3S LiPo (11.1V nominal, 12.6V fully charged)
- [ ] Capacity: ≥1000mAh (for adequate runtime)
- [ ] Discharge rate: ≥20C (for motor current capacity)
- [ ] Condition: No swelling, no damage
- [ ] Charged to: 12.6V (use balance charger)

**Battery safety:**
- [ ] Inspect for damage before connecting
- [ ] Check voltage with multimeter: _______ V (expect 12.6V charged)
- [ ] Place battery in LiPo safety bag during testing
- [ ] Have fire extinguisher ready
- [ ] Test in well-ventilated area

### 5.2: Battery Connection

**Power down:**
- [ ] Disconnect bench supply
- [ ] Disconnect USB from RP2040
- [ ] Wait 30 seconds

**Battery wiring:**
```
Battery +  →  ESC 'V' pad (use proper connector, XT60 or similar)
Battery -  →  ESC 'G' pad

DO NOT reverse polarity! Double check before connecting!
```

**Current monitoring:**
```
Option A: Current clamp on battery + wire
Option B: Inline current sensor
Option C: Battery with built-in current monitoring
```

**Power-on sequence:**
1. [ ] Verify all connections secure
2. [ ] Verify polarity correct (CRITICAL!)
3. [ ] Connect battery (use connector, don't just touch wires)
4. [ ] Connect RP2040 USB to PC
5. [ ] Verify robot powers up
6. [ ] Check battery voltage under no-load: _______ V

### 5.3: Battery Voltage Sag Test

**Test voltage sag under load:**

```
Battery fully charged: 12.6V
No load voltage: _______ V (should be 12.6V)

At 25% throttle:
Battery voltage: _______ V
Voltage sag: _______ V (expect: 0.1-0.3V)

At 50% throttle:
Battery voltage: _______ V
Voltage sag: _______ V (expect: 0.3-0.8V)

At 75% throttle:
Battery voltage: _______ V
Voltage sag: _______ V (expect: 0.5-1.5V)

If voltage sag >1.5V at 75% throttle:
→ Battery internal resistance too high, or
→ Battery capacity too small, or
→ Battery partially discharged
```

**Compare to bench supply:**
```
Bench supply holds voltage constant (regulated)
Battery voltage sags under load (internal resistance)

This is normal! ESC should handle varying voltage.

Verify motor still spins smoothly despite voltage sag.
Verify telemetry reports actual battery voltage.
```

### 5.4: Performance Comparison: Battery vs Bench Supply

**Run same tests as Phase 3.4, but on battery:**

```
Throttle    Current (Battery)    Voltage Sag    Notes
────────    ────────────────    ───────────    ─────
25%         _______ A            _______ V
50%         _______ A            _______ V
75%         _______ A            _______ V

Compare to bench supply tests:
Current should be similar (±10%)
Performance may be slightly lower due to voltage sag
```

### 5.5: Battery Runtime Estimate

**Calculate runtime:**

```
Battery capacity: _______ mAh
Average current at 50% throttle: _______ A = _______ mA

Runtime estimate: Capacity / Current
Runtime = _______ mAh / _______ mA = _______ hours

Convert to minutes: _______ × 60 = _______ minutes

Derate by 80% (usable capacity): _______ min × 0.8 = _______ min

Typical combat match: 3 minutes
Estimated number of matches per battery charge: _______ matches

Note: Actual runtime will be lower in competition due to:
- High-power bursts during impacts
- Inefficiency at varying loads
- Battery aging
```

### 5.6: Low Voltage Cutoff Test

**Test firmware battery protection:**

```
Firmware config.h:
BATTERY_LOW_VOLTAGE = 9600 mV (3.2V per cell)
BATTERY_CRITICAL = 9000 mV (3.0V per cell)

Test (if safe to discharge battery):
1. Run motor at 50% until battery voltage drops
2. Monitor telemetry voltage
3. Verify firmware warnings at low voltage
4. Verify weapon disables at critical voltage

Or simulate with bench supply:
1. Lower bench supply voltage to 9.6V
2. Verify firmware detects low voltage
3. Lower to 9.0V
4. Verify firmware disables weapon

Critical voltage test voltage: _______ V
Firmware response: [ ] Disabled weapon  [ ] No action (bug)
```

**IMPORTANT:** Don't actually discharge LiPo below 3.0V/cell (9.0V total) - damages battery permanently!

### 5.7: Battery Operation Summary

**Complete the checklist:**

```
╔═════════════════════════════════════════════════════════╗
║  BATTERY OPERATION VALIDATION                           ║
╠═════════════════════════════════════════════════════════╣
║  Robot powers from battery:        [ ] Yes  [ ] No      ║
║  Motor operates correctly:         [ ] Yes  [ ] No      ║
║  Voltage sag acceptable (<1.5V):   [ ] Yes  [ ] No      ║
║  Performance matches bench supply: [ ] Yes  [ ] No      ║
║  Telemetry working on battery:     [ ] Yes  [ ] No      ║
║  Low voltage protection working:   [ ] Yes  [ ] No      ║
╠═════════════════════════════════════════════════════════╣
║  Battery voltage (charged):        _______ V            ║
║  Voltage sag at 75% throttle:      _______ V            ║
║  Estimated runtime at 50%:         _______ min          ║
║  Matches per charge (estimate):    _______              ║
╚═════════════════════════════════════════════════════════╝
```

**Battery testing complete:**
- [ ] Robot operates correctly on battery power
- [ ] Ready for final integration testing

---

## Phase 6: Full Robot Integration (60 minutes)

**Objective:** Install weapon system in robot, verify complete integration.

### 6.1: Mechanical Integration

**Install motor in robot:**
- [ ] Secure motor to robot chassis (use anti-vibration mounts if possible)
- [ ] Verify motor mounting is solid (no looseness)
- [ ] Ensure motor shaft is aligned correctly
- [ ] Route motor wires safely (away from wheels, avoid pinch points)

**Install weapon (spinner/blade):**
- [ ] Attach weapon to motor shaft
- [ ] Secure with shaft collar or set screw
- [ ] Verify weapon is balanced (spin by hand, check for wobble)
- [ ] Verify weapon does not hit robot chassis
- [ ] Verify weapon has adequate clearance

**ESC mounting:**
- [ ] Mount ESC securely (zip tie, double-sided tape, or screws)
- [ ] Ensure good airflow over ESC (for cooling)
- [ ] Route signal wire to RP2040
- [ ] Route power wires to battery connector
- [ ] Secure all connections with heat shrink or tape

**Cable management:**
- [ ] Route all wires neatly
- [ ] Use zip ties to prevent wire movement
- [ ] Ensure no wires can get caught in weapon
- [ ] Label wires if needed (for future troubleshooting)

### 6.2: Electrical Integration Check

**Final wiring verification:**
```
RP2040 GP4  →  ESC Signal 'S'     [ ] Connected
RP2040 GND  →  ESC GND 'G'        [ ] Connected
ESC 'V'     →  Battery +          [ ] Connected
ESC 'G'     →  Battery -          [ ] Connected
Motor A/B/C →  ESC Motor outputs  [ ] Connected

Verify no shorts:
Signal to GND: [ ] No short (>1kΩ)
V+ to GND: [ ] No short (>1kΩ)
```

**Power-on test (weapon removed):**
1. [ ] Remove weapon temporarily
2. [ ] Connect battery
3. [ ] Power on RP2040
4. [ ] Verify all systems boot correctly
5. [ ] Test motor spin briefly (10% throttle, 2 seconds)
6. [ ] Verify no interference with other systems (drive motors, LEDs, etc.)

### 6.3: Weight and Balance

**Measure robot weight:**
```
Robot weight (without battery): _______ g
Robot weight (with battery): _______ g

Weight class limit (if applicable): _______ g
Margin remaining: _______ g

Is robot underweight? [ ] Yes [ ] No
If yes, consider adding weight for better traction/stability
```

**Check center of gravity:**
- [ ] Balance robot on finger - should be near geometric center
- [ ] Weapon should not make robot front-heavy
- [ ] If unbalanced, add weight to opposite end

**Verify clearance:**
- [ ] Weapon clears ground (check on flat surface)
- [ ] Weapon clears chassis at full speed
- [ ] Wheels have adequate ground contact
- [ ] Robot sits level (not tilted forward/back)

### 6.4: Integrated System Test

**Test sequence with weapon installed:**

**Safety setup:**
- [ ] Put robot in test box or secure test area
- [ ] Ensure no people/objects near robot
- [ ] Have remote kill switch ready (if equipped)
- [ ] Be ready to trigger emergency stop

**Test 1: Low power weapon spin (25%)**
```
1. Place robot on non-slip surface
2. Arm weapon system
3. Spin weapon to 25% throttle
4. Run for 10 seconds
5. Verify:
   - [ ] Weapon spins smoothly
   - [ ] No excessive vibration
   - [ ] Robot doesn't tip over
   - [ ] No electrical interference (drive motors still respond)
   - [ ] LEDs still working
   - [ ] Controller maintains connection
```

**Test 2: Medium power weapon spin (50%)**
```
1. Spin weapon to 50% throttle
2. Run for 5 seconds
3. Verify:
   - [ ] Weapon spins faster (proportional to throttle)
   - [ ] Robot remains stable
   - [ ] No unusual vibration or noise
   - [ ] All systems functional
```

**Test 3: Drive while weapon spinning**
```
1. Spin weapon to 25% throttle
2. Drive robot forward/backward/turn
3. Verify:
   - [ ] Drive motors work correctly with weapon spinning
   - [ ] No power delivery issues
   - [ ] Robot drives straight (weapon doesn't cause torque steer)
   - [ ] Weapon doesn't slow down during drive
```

**Test 4: Emergency stop while spinning**
```
1. Spin weapon to 50% throttle
2. Trigger emergency stop (controller button)
3. Measure weapon stop time: _______ seconds
4. Verify:
   - [ ] Weapon stops within 2 seconds
   - [ ] All systems stop (drive + weapon)
   - [ ] Robot is safe to approach
   - [ ] Emergency stop can be cleared
```

### 6.5: Gyroscopic Effect Test

**Spinning weapon creates gyroscopic forces:**

```
Test turning with weapon spinning:

1. Spin weapon to 50% throttle
2. Attempt to turn robot left (drive left stick)
3. Observe behavior:
   - [ ] Robot turns normally
   - [ ] Robot resists turning (gyro effect)
   - [ ] Robot tips when turning
   - [ ] Other: _______________

4. Attempt to turn robot right
5. Observe if behavior differs left vs right

Gyroscopic effect severity:
[ ] Negligible (no noticeable difference)
[ ] Mild (slight resistance to turning)
[ ] Moderate (noticeable, but controllable)
[ ] Severe (difficult to turn, tips easily)

If severe:
→ Weapon spinning too fast for robot mass
→ Consider reducing max weapon speed
→ Or add weight to robot (increases rotational inertia)
```

### 6.6: Telemetry Monitoring During Operation

**Monitor weapon during integrated testing:**

```
While weapon spinning at 50%:
eRPM: _______ (mechanical RPM: _______ )
Voltage: _______ V
Current: _______ A
Temperature: _______ °C

After 30 seconds continuous:
eRPM: _______ (should be stable)
Voltage: _______ V (may sag slightly)
Current: _______ A (should be stable)
Temperature: _______ °C (will increase)

Verify telemetry updates during operation
Verify values make sense and are stable
```

### 6.7: Full Integration Summary

**Complete the checklist:**

```
╔═════════════════════════════════════════════════════════╗
║  FULL ROBOT INTEGRATION                                 ║
╠═════════════════════════════════════════════════════════╣
║  Mechanical installation secure:   [ ] Yes  [ ] No      ║
║  Weapon balanced:                  [ ] Yes  [ ] No      ║
║  Electrical connections secure:    [ ] Yes  [ ] No      ║
║  All systems functional:           [ ] Yes  [ ] No      ║
║  Weapon spins smoothly:            [ ] Yes  [ ] No      ║
║  Drive works with weapon spinning: [ ] Yes  [ ] No      ║
║  Emergency stop working:           [ ] Yes  [ ] No      ║
║  No electrical interference:       [ ] Yes  [ ] No      ║
║  Gyro effect manageable:           [ ] Yes  [ ] No      ║
║  Telemetry monitoring working:     [ ] Yes  [ ] No      ║
╠═════════════════════════════════════════════════════════╣
║  Weapon stop time:                 _______ seconds      ║
║  Max safe weapon speed:            _______ %            ║
║  Recommended combat speed:         _______ %            ║
╚═════════════════════════════════════════════════════════╝
```

**Integration complete:**
- [ ] All mechanical integration complete
- [ ] All electrical integration verified
- [ ] All systems tested and functional
- [ ] Robot ready for operational testing

---

## Phase 7: Final Validation and Competition Prep (30 minutes)

**Objective:** Verify robot is competition-ready.

### 7.1: Pre-Competition Checklist

**Mechanical:**
- [ ] All screws tight (check with hex key)
- [ ] Weapon secure (shaft collar tight)
- [ ] Wheels secure (no wobble)
- [ ] Battery secure (won't shift during impact)
- [ ] All wires secured (zip ties, no loose wires)
- [ ] No sharp edges (safety requirement)
- [ ] Weight within class limit

**Electrical:**
- [ ] All connections secure (bullet connectors, signal wires)
- [ ] No exposed wiring (cover with heat shrink)
- [ ] Battery connector secure (won't disconnect on impact)
- [ ] ESC secure (won't move)
- [ ] RP2040 secure (protect from impacts)

**Software:**
- [ ] Latest firmware uploaded
- [ ] Current limit = 10A (verify in code)
- [ ] Temperature limit = 70°C
- [ ] Emergency stop tested and working
- [ ] Failsafe tested (disconnect controller → robot stops)
- [ ] Arming sequence working
- [ ] Battery monitoring working

**Controller:**
- [ ] Controller paired to robot
- [ ] Controller fully charged
- [ ] Failsafe distance tested (how far before disconnect?)
- [ ] Emergency stop button identified
- [ ] Weapon arm sequence memorized
- [ ] Practice driving with weapon spinning

### 7.2: Safety Validation

**Emergency procedures:**
- [ ] Team knows emergency stop procedure
- [ ] Team knows how to disconnect battery quickly
- [ ] Fire extinguisher available (for LiPo fires)
- [ ] Safety glasses available
- [ ] Clear communication plan ("STOP!" means STOP)

**Robot safety features:**
- [ ] Weapon arming requires deliberate action (not accidental)
- [ ] Emergency stop works reliably (<2s weapon stop)
- [ ] Failsafe engages if controller disconnect
- [ ] Low battery warning visible (LED)
- [ ] Robot won't arm with low battery

### 7.3: Performance Envelope Summary

**Document safe operating limits:**

```
╔═════════════════════════════════════════════════════════╗
║  SAFE OPERATING LIMITS                                  ║
╠═════════════════════════════════════════════════════════╣
║  Max continuous throttle:          _______ %            ║
║  Max burst throttle:               _______ %            ║
║  Max continuous time at max:       _______ seconds      ║
║  Minimum cool-down time:           _______ seconds      ║
║  Max current allowed:              9.9 A (HARD LIMIT)   ║
║  Max temperature allowed:          70°C (ESC limit)     ║
║  Emergency stop time:              _______ seconds      ║
║  Battery low voltage:              9.6V                 ║
║  Battery critical voltage:         9.0V                 ║
╚═════════════════════════════════════════════════════════╝
```

**Competition strategy recommendations:**

```
Based on testing, recommended weapon usage:
1. Spin-up time to max speed: _______ seconds
2. Max continuous spin time: _______ seconds (thermal limit)
3. Cool-down time needed: _______ seconds

Recommended combat strategy:
- Spin weapon to _______ % for initial engagement
- Limit continuous spin to _______ seconds
- Monitor telemetry for current/temperature
- Be ready for emergency stop if >9A current or >60°C temp

Driving with weapon spinning:
- Gyro effect: [ ] Negligible [ ] Moderate [ ] Severe
- Compensate for gyro when turning: [ ] Not needed [ ] Needed
- Recommended weapon speed while driving: _______ %
```

### 7.4: Lessons Learned and Improvements

**Document what you learned:**

```
What worked well:
1. _______________________________________________________
2. _______________________________________________________
3. _______________________________________________________

Issues encountered:
1. _______________________________________________________
2. _______________________________________________________
3. _______________________________________________________

Future improvements:
1. _______________________________________________________
2. _______________________________________________________
3. _______________________________________________________

Competition notes:
1. _______________________________________________________
2. _______________________________________________________
3. _______________________________________________________
```

### 7.5: Final Sign-Off

**Bringup complete! Sign off when ready:**

```
Completed by: _____________________ Date: ___/___/_____

Hardware validated:
- [ ] ESC configured correctly (current limit = 10A)
- [ ] DShot protocol verified with oscilloscope
- [ ] Motor operation tested (all power levels)
- [ ] Telemetry validated (voltage, current, temp, RPM)
- [ ] Battery operation confirmed
- [ ] Full robot integration successful

Safety validated:
- [ ] Emergency stop working (<2s)
- [ ] Failsafe tested
- [ ] Current limit enforced
- [ ] Temperature limit enforced
- [ ] Low battery protection working

Robot status:
[ ] READY FOR COMPETITION
[ ] NEEDS ADDITIONAL WORK (specify): ___________________

Notes:
_________________________________________________________
_________________________________________________________
_________________________________________________________
```

---

## Appendix A: Troubleshooting Guide

### Issue: Motor won't start

**Symptoms:** Motor doesn't spin when throttle applied

**Possible causes:**
1. ESC not receiving signal
   - Check: Oscilloscope shows DShot signal on GP4?
   - Fix: Verify wiring, check firmware mode

2. ESC not powered
   - Check: Multimeter shows voltage at ESC V+ pad?
   - Fix: Check battery connection, verify polarity

3. Motor not connected
   - Check: Continuity between ESC outputs and motor wires?
   - Fix: Check bullet connectors, verify phase connections

4. ESC in wrong mode
   - Check: ESC configured for DShot (not PWM-only mode)?
   - Fix: Reconfigure ESC with parameter adjuster

5. Throttle below arming threshold
   - Check: DShot throttle value >48 (minimum armed value)?
   - Fix: Increase throttle, verify firmware arming logic

### Issue: Motor stutters or jerks

**Symptoms:** Motor doesn't spin smoothly, stutters, or vibrates

**Possible causes:**
1. Wrong motor timing
   - Check: ESC timing setting
   - Fix: Try timing values 15-25° (auto-adjust if available)

2. Wrong pole count
   - Check: Pole count in ESC config
   - Fix: Verify actual pole count, reconfigure

3. Demag compensation too low
   - Check: Demag setting in ESC
   - Fix: Increase to "High" for weapon loads

4. Bad motor or ESC
   - Check: Test motor with different ESC, or ESC with different motor
   - Fix: Replace faulty component

### Issue: Current too high (>9.9A)

**Symptoms:** Current exceeds motor rating

**Possible causes:**
1. ESC current limit not set
   - Check: Read ESC config, verify current limit = 10A
   - Fix: Reconfigure ESC with correct limit

2. Motor stalling or binding
   - Check: Spin motor by hand, should be smooth
   - Fix: Check for bearing damage, replace motor

3. Voltage too high
   - Check: Battery voltage (should be ≤11.1V nominal)
   - Fix: Use correct battery (3S max)

4. Motor overloaded
   - Check: Is weapon too heavy for this motor?
   - Fix: Reduce weapon weight or upgrade motor

### Issue: Motor overheating (>70°C)

**Symptoms:** Motor temperature exceeds safe limit

**Possible causes:**
1. Running too long at high power
   - Fix: Reduce continuous run time, allow cool-down

2. Motor underpowered for application
   - Fix: Reduce weapon weight or upgrade motor

3. Poor cooling
   - Fix: Add ventilation, reduce enclosed space

4. ESC temperature limit too high
   - Check: Verify ESC temp limit = 70°C
   - Fix: Reconfigure ESC

### Issue: Telemetry not working

**Symptoms:** No telemetry data from ESC

**Possible causes:**
1. Telemetry not enabled in ESC
   - Check: ESC config shows "DShot Telemetry: ON"?
   - Fix: Enable telemetry in ESC configuration

2. Firmware not requesting telemetry
   - Check: Code calls dshot_send_throttle(..., true)?
   - Fix: Set telemetry request flag to true

3. GPIO not configured for input
   - Check: PIO program for bidirectional mode
   - Fix: Verify bidirectional config in firmware

4. ESC doesn't support EDT
   - Check: ESC firmware version (AM32 v2.x should support)
   - Fix: Update ESC firmware if needed

### Issue: DShot timing wrong

**Symptoms:** Oscilloscope shows incorrect bit timing

**Possible causes:**
1. Clock divider calculation wrong
   - Check: firmware/src/dshot.c line 123: cycles_per_bit = 15
   - Fix: Verify calculation, check PIO clock settings

2. PIO clock frequency wrong
   - Check: System clock (should be 125MHz for RP2040)
   - Fix: Verify clock initialization in firmware

3. Oscilloscope probe loading
   - Check: Use 10:1 probe (lower capacitance)
   - Fix: Account for probe loading in measurements

### Issue: Emergency stop too slow

**Symptoms:** Weapon takes >2 seconds to stop

**Possible causes:**
1. Brake not enabled
   - Check: ESC config "Brake on Stop: ON"?
   - Fix: Enable brake in ESC configuration

2. Weapon has high inertia
   - Check: Is weapon very heavy?
   - Fix: This is physical limitation, may need stronger brake

3. Emergency stop not sending all stop methods
   - Check: firmware/src/weapon.c:413-448
   - Fix: Verify all three stop methods are attempted

### Issue: Gyroscopic effect too strong

**Symptoms:** Robot tips or resists turning when weapon spinning

**Possible causes:**
1. Weapon spinning too fast for robot mass
   - Fix: Reduce max weapon speed to 50-75%

2. Robot too light
   - Fix: Add weight to robot (increases rotational inertia)

3. Weapon orientation unfavorable
   - Fix: Mount weapon horizontally instead of vertically (if possible)

---

## Appendix B: Measurement Data Sheets

### Motor Characterization Data

```
Motor: FingerTech Silver Spark F2822-1100KV
ESC: AT32F421-based AM32 ESC
Date: ___/___/_____
Operator: _____________________

Throttle  Current  Voltage  Temp   RPM     Power   Notes
(%)       (A)      (V)      (°C)   (RPM)   (W)
────────  ───────  ───────  ─────  ──────  ──────  ─────────
0
10
25
50
75
100

Max safe continuous: _______ % throttle
Max safe burst: _______ % throttle
```

### DShot Timing Measurements

```
DShot Speed: DShot300 (300 kbit/s)
Date: ___/___/_____

Parameter              Measured    Expected    Delta   Status
─────────────────────  ──────────  ──────────  ──────  ──────
Bit period (μs)                    3.33 μs
Bit '1' high (μs)                  2.22 μs
Bit '1' low (μs)                   1.11 μs
Bit '0' high (μs)                  1.11 μs
Bit '0' low (μs)                   2.22 μs
Packet duration (μs)               53.3 μs
Signal amplitude (V)               3.3 V
Rise time (ns)                     <10 ns
Fall time (ns)                     <10 ns

Notes:
_________________________________________________________
```

### Telemetry Validation Data

```
Test conditions: 50% throttle, 11.1V battery
Date: ___/___/_____

Parameter      Telemetry  Measured  Delta   Notes
─────────────  ─────────  ────────  ──────  ─────────────
Voltage (V)
Current (A)
Temp (°C)
RPM

Telemetry update rate: _______ Hz
Max age before stale: _______ ms
```

---

## Appendix C: Reference Formulas

### DShot Timing Calculations

```
DShot bit rate (kbit/s): 150, 300, 600, or 1200
Bit period (μs) = 1000 / bit_rate

For DShot300:
Bit period = 1000 / 300 = 3.33 μs

Bit '1': 2/3 high, 1/3 low
  High time = 3.33 × 2/3 = 2.22 μs
  Low time = 3.33 × 1/3 = 1.11 μs

Bit '0': 1/3 high, 2/3 low
  High time = 3.33 × 1/3 = 1.11 μs
  Low time = 3.33 × 2/3 = 2.22 μs

Packet duration:
  16 bits × 3.33 μs/bit = 53.3 μs total
```

### Motor RPM Calculations

```
Mechanical RPM = Voltage × KV × Throttle%

For F2822-1100KV at 11.1V, 50% throttle:
RPM = 11.1V × 1100 KV × 0.50 = 6105 RPM

Electrical RPM (eRPM) from telemetry:
eRPM = Mechanical RPM × Pole Pairs

For 14-pole motor (7 pole pairs):
eRPM = 6105 × 7 = 42735 eRPM

To convert telemetry eRPM back to mechanical:
Mechanical RPM = eRPM / Pole Pairs
```

### Current and Power Calculations

```
Power (W) = Voltage (V) × Current (A)

For F2822 at max spec:
Power = 11.1V × 9.9A = 110W (approximately 102W rated)

Current from power and voltage:
Current (A) = Power (W) / Voltage (V)

Efficiency consideration:
Motor is ~80% efficient, so:
Mechanical Power ≈ Electrical Power × 0.80
```

### Battery Runtime Calculations

```
Runtime (hours) = Battery Capacity (Ah) / Average Current (A)

Example:
Battery: 2000 mAh = 2.0 Ah
Average current: 5A
Runtime = 2.0 / 5.0 = 0.4 hours = 24 minutes

Derate by 80% for usable capacity:
Usable runtime = 24 min × 0.80 = 19.2 minutes

Number of 3-minute matches:
Matches = 19.2 / 3 = 6.4 ≈ 6 matches per charge
```

---

## Appendix D: Quick Reference - Competition Day Checklist

**Before each match:**

- [ ] Battery fully charged (12.6V)
- [ ] All screws tight
- [ ] Weapon secure
- [ ] Wheels secure
- [ ] Wires secured
- [ ] Controller charged
- [ ] Controller paired
- [ ] Test weapon spin (1-2 seconds)
- [ ] Emergency stop tested
- [ ] Safety glasses on

**After each match:**

- [ ] Disconnect battery immediately
- [ ] Inspect for damage
- [ ] Tighten any loose screws
- [ ] Check wiring
- [ ] Test motor spin (if damaged)
- [ ] Charge battery if needed
- [ ] Check battery voltage
- [ ] Clean debris from robot

**Red flags (don't compete if you see these):**

- [ ] Battery swollen or damaged
- [ ] Weapon loose or wobbling
- [ ] Wires exposed or damaged
- [ ] Motor making unusual noise
- [ ] ESC overheating (>80°C)
- [ ] Emergency stop not working
- [ ] Current exceeded 9.9A in practice

---

**END OF HARDWARE BRINGUP PLAN**

**Document Version:** 1.0
**Last Updated:** 2025-11-18
**Status:** Ready for use

Good luck with your combat robot! 🤖⚔️
