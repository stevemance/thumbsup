# ThumbsUp motor board — design (rev L, 2026-09-24)

The power half of the two-board stack: battery in, three motor channels out, 5 V down to the
compute board through one header.  This is the brushless variant: **sensorless weapon + two
FOC drive motors with magnetic-encoder feedback**, 4S.  Everything here is meant to be drawn in
KiCad by hand from [`design/motor_board.py`](design/motor_board.py) (the netlist) and built by
JLCPCB.

Rev B applied review round 1, rev C round 2, rev D round 3, rev E round 4, rev F round 5, rev G round 6, rev H round 7, rev I round 8, rev J round 9, rev K round 10, rev L rounds 11–30, then an audited trim of the firmware contract §7–§9 (review/trim_*.md) (rev L adds C19, 1 nF on W_nFAULT); every finding and its fix is in
[`review/CHANGES.md`](review/CHANGES.md).

| File | What it is |
|---|---|
| this file | architecture, circuit blocks and their values, safety, layout rules, firmware contract, bring-up |
| [`design/motor_board.py`](design/motor_board.py) | **the netlist**: every part, pin and net; run it to regenerate the outputs below and re-check |
| [`design/nets.md`](design/nets.md), [`design/netlist.csv`](design/netlist.csv) | generated connection lists (draw from these) |
| [`design/mcu_pinmap.md`](design/mcu_pinmap.md) | STM32G474RET6 pin plan, every alternate function verified against ST's pin database |
| [`design/bom.csv`](design/bom.csv), [`BOM.md`](BOM.md) | JLC-format BOM and the part notes (stock, alternates, what to confirm) |
| [`design/calcs.py`](design/calcs.py) → [`design/calcs.md`](design/calcs.md) | every sizing number in section 4 |
| [`spice/`](spice/) | ngspice checks: power-switch closure with the soft-start switch, dynamic ARM, weapon bridge switching, weapon spin-up |
| [`datasheets/`](datasheets/) | PDFs of every non-generic part, indexed in its README |
| [`review/`](review/) | the adversarial design reviews, round by round |
| [`ref/`](ref/) | ST pin database for the MCU (BSD-3) |

## 1. Requirements this board meets

| Area | Requirement | How |
|---|---|---|
| Battery | 4S LiPo, **4.20 V/cell only** (16.8 V full, 12 V sagged; LiHV would trip the regen limits); survive power-switch closure; survive a reversed pack | High-side back-to-back FET switch (Q7/Q8) under an LM74502 controller: soft-start ~2.2 V/ms (≤ 0.01 V/µs at VM vs the DRV8316's 4 V/µs), reverse-polarity blocking, UVLO; board GND tied to pack− at all times; TVS; 330 µF 35 V polymer bulk |
| Battery monitoring | Pack voltage, current, power, mAh used; **per-cell voltages**; pack over-current and bus over-voltage trip; low-pack warning | INA239 on a 1 mΩ shunt (16-bit); BQ76907 on the balance lead (cell voltages; balancing unused); INA239 ALERT (SOVL, BOVL) kills the weapon PWM; low-cell alarm in firmware.  The buck UVLO (logic off below ~9.2 V = 2.3 V/cell) only keeps the logic sane in a sag: it is **not** pack protection (§7) |
| Weapon | Sensorless BLDC, Repeat 2822 Mk3 1800 KV class, 20 A current limit, ~280 W bursts | DRV8323RH (pin-strapped gate driver) + 6 × 40 V 1.4 mΩ FETs + 3 × 2 mΩ shunts |
| Drive | 2 × FOC BLDC, Repeat Mini Mk4.1 (1106, 3500 KV, 28.5:1) with a magnet on the motor end and an MT6701 encoder (sensorless FOC as the fallback), traction-limited at ~1 A per motor, full telemetry, odometry | 2 × DRV8316C (integrated FETs + current sense) at 48 kHz + protected sensor connectors (also accept Hall sensors) |
| Telemetry | Per-phase currents (9), bus voltage, weapon phase voltages, weapon FET temp, motor temps, speed/position | 16 analog inputs on 5 ADCs + 2 encoder timers on one MCU |
| Compute link | 5 V / ≤ 0.45 A to the compute board, UART, reset + SWD programming, weapon ARM, cell-monitor I²C | 20-pin 1.27 mm header (2 spare) |
| Safety | Weapon cannot be driven unless the compute board is alive and armed; everything off in reset; failsafe on command loss | **Dynamic ARM**: the compute board must keep toggling W_ARM_CLK from software (≥ 500 Hz); a charge pump + Schmitt buffer turns that into the ARM level, which gates every weapon phase enable in hardware (AND on INLx) and disarms ~30–200 ms after the toggling stops (sim: 52–164 ms with nominal parts, 25–85 °C).  Command timeout and a watchdog in firmware.  Pulled-down enables; DRVOFF pulled up |
| Environment | Indoor arena, ambient 0–50 °C | The DRV8316 VM filters (R302/R402 0.1 Ω + ~16 µF) keep the simulated switch-closure, re-close and loaded contact-bounce steps at the DRV8316 VM pins ≤ ~2.3 V/µs with C1 down to 0 °C (~2.8 V/µs only at C1's −40 °C ESR limit), under the 4 V/µs abs max (§5, §7.2).  Not covered: a weapon phase-to-ground short (§7.21) |
| Build | JLCPCB assembly | All parts on LCSC; 199 assembled parts + 6 DNP footprints, 67 BOM lines; **two-sided**: power stage, tall parts, connectors and test pads on top, low-profile passives/logic and J1 on the bottom; J4 THT.  Board area and chassis fit are settled at layout (§6.13 lists the estimate and the levers) |

Not on this board (compute board): Pico/MCU for control, IMU + high-g accel, logging flash,
Bluetooth, status LEDs, the physical ARM link.  All power functions (pack input, protection,
monitoring, regulation) are here.

## 2. Architecture

```
  BAT+ ── Q7 ─┬─ Q8 ── RS4 1mΩ ─┬── D1 TVS ── C1 330u ──┬──────────────┬──────────────┬─────────┐
  (U13 LM74502 soft-start,      │  U7 INA239 (V,I,P)    │              │              │         │
   reverse block, UVLO)         │                  U2 DRV8323RH    U3 DRV8316C    U4 DRV8316C   │
  BAT− ── GND                   │                  gate drv + CSA  drive L        drive R       │
                                │                  + 5 V buck ──┐  (FETs+CSA      (FETs+CSA     │
                                │                  Q1..Q6,RS1..3│   inside)        inside)      │
                                │                  INLx = CHxN  │     │               │         │
                                │                  AND W_ARM_S  │  drive L A/B/C  drive R A/B/C │
                                │                  (U6)         │  J2 sensor      J3 sensor     │
                                │                     +5V ──────┴── U5 LDO ── +3V3 ─────────────┘
                                │                      │                  │
                                │                      │          U1 STM32G474RET6
                                │                      │   TIM1 → U2   TIM8 → U3   TIM20 → U4
                                │                      │   SPI3 → U3,U4,U7   TIM3/TIM2 ← J2/J3 (via Schmitt buffers)
                                │                      │   5 ADCs (9 currents, VBAT, 3 weapon phase V, temps)
                                │                      │
                                └──────── J1 header to the compute board: +5V, GND, UART, W_ARM_CLK (toggled), NRST, SWD, VBAT_SNS_H (via R33), BMS I²C
  J4 balance lead ── U8 BQ76907 (cell voltages) ── I²C on J1 (host = compute board)
```

Design choices (the "why"):

* **One MCU for all three motors.** The G474 has three advanced timers (TIM1/TIM8/TIM20), five
  ADCs and FOC-grade math hardware, and it is what ST's motor SDK, SimpleFOC and moteus-class
  firmware already run on.  One MCU, one firmware image, one programming port.  The motor
  drivers are "dumb" power stages: they turn the MCU's logic-level PWM into motor current and
  report currents and faults back.
* **Integrated drive stages.** The DRV8316C contains the six FETs *and* three current-sense
  amplifiers (no shunts).  Each drive channel is one IC and ~20 passives.
* **3x PWM mode everywhere.** The drivers generate the complementary signals and dead time; the
  MCU needs 3 PWM pins per motor.  That is what makes the pin budget fit on LQFP-64.
* **The weapon driver also makes the 5 V rail.** The DRV8323R's integrated 0.6 A buck powers the
  compute board and the 3.3 V LDO, so there is no separate regulator IC.  The buck is a separate
  die with its own enable (nSHDN, used as the pack UVLO), independent of the driver's ENABLE.
* **Hardware-strapped weapon driver (DRV8323RH).**  Its settings (3x PWM, gate current, VDS
  trip, CSA gain) are resistors, so nothing is lost when it sleeps or browns out, and it needs no
  SPI chip select.  It drives the FET gates with regulated current (IDRIVE), which sets the
  switching speed, so there are **no gate resistors**.
* **The ARM interlock gates the phase enables, not the driver's sleep pin, and ARM is dynamic.**
  In 3x PWM mode a phase with INLx = 0 is Hi-Z regardless of INHx, so INLx = TIM1_CHxN AND W_ARM_S
  means: no ARM → all three weapon phases float (the drum coasts), and the driver stays awake so
  its fault reporting and current sense keep working.  W_ARM only exists while the compute board
  keeps toggling W_ARM_CLK from software, so a hung compute board disarms the weapon by itself.
* **High-side soft-start switch** (Q7/Q8 + LM74502): closing the power switch charges the bus
  at ~0.8 A in ~8 ms instead of a 180–290 A, 4–7 V/µs step; a reversed pack is blocked; the board
  ground stays tied to pack− (a low-side switch floats the ground and drives the cell-monitor
  inputs far below VSS while it ramps).

## 3. Circuit blocks

Reference designators match `design/motor_board.py`; pin numbers are the datasheet's.

### 3.1 Power entry, protection and battery monitoring

Path: **BAT+ (BAT_IN) → Q7 → PSW_S → Q8 → VBAT_SW → RS4 (1 mΩ) → VBAT**; **BAT− = GND**.

| Part | Value | Notes |
|---|---|---|
| J_BAT+ / J_BAT− | plated through-holes (KiCad `SolderWire-1.5sqmm_1x01_D1.7mm_OD3.9mm`: 2.15 mm drill, 3.9 mm pad) | wires pushed through and soldered (SMD pads peel in combat); 16–18 AWG pigtail to an XT30 on the lead (XT30: 15 A cont / 30 A burst; pack peak is 22 A for 0.5 s).  **The external power switch is in the + wire** (see below) |
| U13 | LM74502DDFR (SOT-23-8 thin / DDF, top side next to Q7/Q8) | High-side switch controller: charge pump (C12 220 nF VCAP–VS), 60 µA gate source, 2.4 A gate sink, −65 V reverse rating, 45 µA quiescent.  VS = BAT_IN with C14 100 nF **100 V** 0805 (BAT_IN rings to 40–60 V when the switch opens under load; Q7 avalanches).  OV pin to GND (no over-voltage cut-off: a disconnect during regen would make things worse) |
| Q7, Q8 | 2 × HYG015N04LS1C2 (same as the weapon FETs), common source PSW_S, common gate PSW_G | **Q7** (drain at the pack): body diode blocks the plug-in surge; it is the FET in its linear region during soft-start (16 W peak, 54–57 mJ per closure).  **Q8** (drain at the board): conducts backwards when on; its body diode blocks a reversed pack.  On: 2 × 1.4 mΩ, ~2.0–2.5 W together at 22 A (hot), 0.5 s bursts |
| R1 / D10 / C13 / R32 / D4 | 4.7 k / 1N4148W / 22 nF (Cdvdt) / 1 M / 12 V zener gate–source | Soft-start: VBAT ramps at ~(I_GATE − R32 bleed) / C13 ≈ 2.2 V/ms (sim; ~3.0 V/ms at the 77 µA max gate current), ~0.8 A into ~380 µF.  R1 isolates C13 so turn-off stays fast.  D10 lets C13 only *slow the gate's rise*: with a reversed pack GND is the most positive node and C13 would otherwise push the gate up and turn Q7/Q8 on (sim: 102–147 A without D10 if U13's unpowered gate hold is weak; only the C14 charge spike with it).  R32 resets C13 between power-ups (22 ms); it draws ~20–28 µA of the gate drive, so the ramp is 1.3–3.0 V/ms over the gate-current spread.  After a UVLO trip C13 stays charged for ~20–40 ms (D10 blocks its discharge through the gate); a re-close in that window is not slowed by C13 but is still benign (≤ 0.06 V/µs).  D4 clamps Vgs at 12 V (U13 GATE–SRC abs max 15 V) at full charge-pump voltage and through sag/recovery transients.  |
| R13 / R14 / C18 | 100 k / 15 k / 100 nF on EN/UVLO | Switch off below ~9.0 V (7.7–10.1 V with 1 % resistors and the 0–5 µA EN sink), on above ~9.8 V (worst 10.8 V).  C18 (1.3 ms) filters the weapon's 24 kHz bus ripple so it cannot trip the UVLO early.  Stays below a tired 4S pack under load (~11.5 V average) **provided firmware folds current back at ~12 V** (§8); limits an *unloaded* quick re-close step to ~9 V (under load the bus can fall further before the filtered UVLO opens: §7.2) |
| R15 | 6.8 k 0805 bleeder | After the switch opens the bus decays (τ ≈ 2.3 s with the DC dividers and ~374 µF); the switch UVLO opens the FETs about when the buck stops (~9 V: within ~0.1 s with typical thresholds, ~0.4 s at the minimum threshold), and any re-close after that ramps softly again.  A re-close before that finds the FETs on: at the DRV8316 VM pins (behind R302/R402) 0.06–0.7 V/µs typical, 2.09 V/µs worst (minimum UVLO, C1 at its −40 °C ESR), under 4 V/µs.  A drum still spinning keeps the bus (and the FETs) up longer |
| RS4, U7 | 1 mΩ 2512 + INA239 | **Pack monitor**, after the switch FETs (the INA239 inputs must stay ≥ −0.3 V, so a reversed pack must not reach them).  Kelvin to U7 through R2/R3 10 Ω with C2 100 nF.  VBUS = VBAT.  ±41 A at 1.25 mA/LSB, plus power and die temperature; firmware integrates mAh.  SPI (CS = PA11, R12 100 k pull-up).  ALERT (open drain) is wired onto W_nFAULT → TIM1 break.  **The INA239 has no per-limit mask**: only SOVL (38 A) and BOVL (19 V) are programmed; the rest stay at never-trip reset values (§8).  INA229AIDGSR is pin/footprint compatible but not register compatible (24-bit results, DEVICE_ID 2291h) |
| D1 | SMBJ20A on VBAT | Standoff 20 V > 16.8 V; clamps ≤ 32.4 V, below the DRV8316's 40 V abs max |
| C1 | 330 µF 35 V hybrid polymer (EEHZK1V331P) | Bus bulk and weapon ripple current (2.8 A rms rating); 35 V so it survives the TVS clamp level.  Stake it with adhesive (the vibration-proof EEHZK1V331V is not stocked at JLC) |
| R4 / R5 / C10 | 390 k / 51 k / 100 nF on U2 nSHDN | **Logic brown-out cutoff**: the 5 V buck (and so the MCU and compute board) switches off below ~9.2 V and back on above ~10.4 V (worst-case spread 7.4–10.3 V off).  2.3 V/cell: this keeps the logic sane in a sag; it does not protect the pack (§7.17) |
| D3 / R62 | red LED, 1 k from +5V | **Power LED** = the 5 V rail is up (independent of firmware).  Must be visible from outside the robot.  It also stays lit while a coasting drum back-powers the board with the switch open (§7).  KiCad pad 1 = cathode; the vendor drawing numbers it the other way, so check the cathode mark in the JLC placement preview |

**Cell monitoring (U8 BQ76907 + J4 balance lead).**  The pack's 4S balance lead
(JST-XH 5-pin) plugs into J4.  Each tap goes through a 100 Ω resistor (R6 0603, R7–R10 0402)
with 220 nF 25 V across each cell and from VC0 to VSS (C4–C8): a 22 µs filter per tap (~44 µs cell-to-cell), inside TI's
10–1000 Ω / 0.1 µF min / RC ≤ 200 µs limits.  4S wiring per the BQ76907 datasheet Table 7-1: cells
on VC7–VC6, VC5–VC4, VC3–VC2 and VC1–VC0, with VC6=VC5, VC4=VC3 and VC2=VC1 shorted on the
board.  U8 is powered from the top balance tap through R11 100 Ω 0603 into C9 4.7 µF 50 V X7R
(≥ 1 µF effective at 16.8 V) on BAT and REGSRC; REGOUT (enabled at 3.3 V by OTP default) has
C11 4.7 µF and no load.  Unused functions per TI Table 8-3: SRP/SRN and TS to VSS, CHG/DSG open.
**D5 (B5819W, anode GND, cathode CELL0)** keeps VC0 near VSS when the balance lead is plugged
without the main lead (U8's return current then flows through VC0) and carries the C9 charge at
balance-lead hot plug.  With the main lead in, GND is pack− directly, and VC0 differs from it only
by the main negative lead's I × R (−0.11 V at 22 A; cell 1 then reads tens of mV low under load).
**Plug order: main lead first, balance lead second.**  Coulomb counter and protection FET
drivers are unused: the INA239 measures current and this board must never disconnect the motors
on its own.

The **compute board is the I²C host** (header pins 15–17: SDA, SCL, ALERT; pull-ups on the
compute board, so the lines float on a bench without it).  U8's default cell mode is 7S: the host
must write the 4S cell mode after every power-on reset (check the POR flag) or three of the cells
read 0 V.  Storage = unplug the balance lead (U8 draws ~146 µA in NORMAL; allow SLEEP to cut
that).  The BQ76907 handles 2–7 cells, so the same part serves a 6S variant.

**External power switch (the main power disconnect).**  Off the board, in series with the pack's
+ lead: pack XT30 → screw switch on the chassis wall → BAT+ pad.  FingerTech Mini Power Switch
(40 A continuous / 100 A burst with 16 AWG, 2.15 g) or Repeat Screw Switch (1.5 g; confirm its
current rating).  With it open, nothing is powered except U8 (from the balance lead, µA).  Wait
≥ 2 s after opening before closing again (§3.1 R15); a screw switch cannot do it faster.

### 3.2 Weapon channel — U2 DRV8323RH + Q1–Q6

* **Bridge:** Q1/Q2 (A), Q3/Q4 (B), Q5/Q6 (C), HYG015N04LS1C2 (40 V, 1.4 mΩ typ / 1.7 max @ 10 V,
  PDFN 5×6; leads 1–3 = S, 4 = G, tab = D).  High-side drains on VBAT; U2 VDRAIN (pin 7) Kelvin
  to the drains.  No gate resistors (IDRIVE current-mode gate drive; FET internal RG ~2 Ω).
  One 10 µF 1206 per half-bridge: C25 (A), C26 (B), C31 (C).
* **Shunts:** RS1–RS3 2 mΩ 2512 low-side on a custom footprint (Milliohm's 1–4 mΩ land: 2.0 mm
  terminals).  SPx to the FET-source side (net W_SLx), SNx via net-tie NT1–NT3 to the shunt's
  ground pad.  CSA gain 20 V/V → 40 mV/A, ±35 A linear range, 20 mA/LSB, bidirectional (VREF/2).
  The SOx outputs go to the MCU without an RC filter (within the driver's 60 pF load spec).
* **Strap resistors (hardware variant, SLVSDJ3D Fig. 8-23/8-24 and the EC table):**

  | Pin | Strap | Setting |
  |---|---|---|
  | 29 MODE | R44 47 k → AGND | 3x PWM |
  | 30 IDRIVE | R45 75 k → AGND | 60 mA source / 120 mA sink (faster settings overshoot, §5) |
  | 31 VDS | R46 18 k → AGND | VDS OCP 0.13 V → 62–93 A: a hard-short/shoot-through backstop.  Between 20 A and this trip the MCU limits phase current: the firmware FOC limit, and the comparator fast trip on all three CSAs, which covers one current polarity per phase (low-side over-current, shoot-through and phase-to-phase/-VBAT shorts; ~30–60 A peak depending on the vector angle at a 30 A setting).  The INA239 sees pack current only |
  | 32 GAIN | open (Hi-Z) | CSA 20 V/V |
  | 34 CAL | GND | no auto-trim; firmware measures the CSA offset with the bridge idle after every wake |

  The seven-level pins have only ~±0.27 V of margin between settings: see the layout rule in §6.
* **Fixed H-variant behaviour:** VDS OCP 4 µs deglitch then **4 ms auto-retry**; sense OCP fixed at
  1 V (= 500 A: effectively absent); TDRIVE 4 µs; dead time 100 ns; gate-drive fault is the only
  latched fault (cleared by a short ENABLE pulse).  nFAULT is a single bit shared with U7 ALERT.
* **Charge pump:** C20 47 nF 50 V (CPH–CPL), C21 1 µF 50 V 0603 (VCP–VM).  DVDD C22 1 µF.
  VREF pin 26 = +3V3 with C23 (the CSAs reference the same 3.3 V as the ADC).
* **Control:** INHA/B/C ← TIM1_CH1/2/3 (PC0/PC1/PA10).  INLA/B/C ← U6 (74LVC08) =
  TIM1_CH1N/2N/3N (PA7/PB14/PB15) AND **W_ARM_S** (U14's output, below); R47–R49 100 k keep the MCU side low in reset; the
  fourth gate's inputs are grounded.  ENABLE = W_EN (PA12, R40 100 k pull-down): low = sleep.
  nFAULT → PC13 (TIM1_BKIN, hardware PWM kill) with R42 pull-up and C19 1 nF (analog glitch filter: BKF must be 0 for the comparator trip); U7 ALERT is wire-ORed onto it.
* **Dynamic ARM:** J1 pin 19 W_ARM_CLK (R18 100 k pull-down) → C15 470 nF → D9 BAT54S (clamp to
  GND + rectifier) → W_ARM, held by C16 2.2 µF and bled by R41 47 k → U14 74LVC1G17 Schmitt
  buffer (VT+ ≤ ~2.15 V, VT− ~0.9–1.45 V at 3.3 V; 0.8–1.33 V is the 3.0 V spec) → W_ARM_S (R19 10 k pull-down, in case U14's
  output opens: beats 3 × 5 µA worst-case input leakage) → U6 (all three AND gates) and the MCU (PD2).  `spice/sim_arm.py`
  (`spice/arm.out`), nominal parts, 25 and 85 °C including the BAT54S's hot leakage: toggling at
  250 Hz–10 kHz gives W_ARM = 2.50–2.95 V and arms after 7–10 rising edges (12 ms at 500 Hz: one
  stray edge cannot arm); a stuck-low, stuck-high or floating W_ARM_CLK disarms in 52–164 ms
  (~30–200 ms with part tolerances); a gap in the toggling of ~50 ms is tolerated with nominal parts, ~30 ms worst case.  C15 < C16
  so a clock stuck high cannot hold W_ARM up.
* **Phase voltage sense:** R22–R27 68k/10k dividers + C41–C43 1 nF → PA4/PA5/PA2.  Catches a
  coasting drum (restart after a reset) and six-step BEMF.  The 1 nF also keeps a short (≪ ~9 µs) TVS-level spike
  below the 4 V abs max of PA4/PA5 (TT); PA2 is FT.  A *sustained* D1 clamp is limited by the §8
  regen current limit (≤ ~10 A → ≤ ~3.75 V at the pins: inside the 4.0 V abs max, briefly above the
  VDD + 0.3 V operating limit, §7.4).
* **FET temperature:** TH1 10 k NTC at the FETs, R43 pull-up, C44 100 nF → PA6.
* **5 V buck (inside U2):** VIN pin 47 from VBAT (C27 2.2 µF 50 V X5R); L1 FNR5040S220MT 22 µH,
  Isat 1.6 A guaranteed / 1.8 A typ (−30 % L), which is TI's own 1.6 A recommendation; only a hard
  +5V short (current limit 1.2 A typ / 1.7 A max) reaches soft ferrite roll-off, and the buck's
  thermal shutdown ends that.  D2 SS34 (3 A: survives a shorted +5V); C28 100 nF CB–SW; R20 56 k /
  R21 10 k → 5.05 V; C29/C30 22 µF 25 V.

### 3.3 Drive channels — U3 (left), U4 (right) DRV8316C

**Motor (plan of record):** Repeat Mini Mk4.1 — 1106, 3500 KV, 16 mm planetary 28.5:1, no
sensors; a diametric magnet on the motor end + an MT6701 board on J2/J3 gives true rotor angle.
~6 pole pairs (confirm): 5.9 kHz electrical at 59 k rpm no-load, so the drives run **48 kHz
PWM/FOC** (10–12 updates per electrical cycle at top speed).  Top speed with the drive duty cap (§3.4) ~3.7 m/s at 16.8 V, ~3.1 m/s at 14 V (field weakening only in sensorless mode: the MT6701 is rated 55 k rpm, §8); the tyres slip
at ~0.8–1 A per motor, so the useful current limit is ~1–1.5 A and the drives never approach
their thermal limit (calcs §5, §10).  With the duty cap the motor tops out at ~47 k rpm, inside the MT6701's ~55 k rpm rating.  If the magnet does not work out: sensorless FOC (I/f start +
flux observer), same hardware.

Per channel (U3 values shown; U4 is identical with 4xx designators):

| Pin(s) | Connection |
|---|---|
| VM 9/10/11 | **L_VM** (U4: R_VM), fed from VBAT through **R302 0.1 Ω 1 W 2512** (R402), with C300/C301 100 nF 50 V at the pins + C302/C308/C309/C310 4 × 10 µF 50 V 1206 (~16 µF effective at 16.8 V).  The ~1.6 µs RC isolates the DRV8316's 4 V/µs VM abs max from bus events: loaded contact bounce 3.75 → 2.26 V/µs (≤ 2.33 to ~1.3 ms), worst re-close 3.44 → 2.09 V/µs (spice/hotplug.out), weapon fault-clear kick 9–11 → ~1–2 V/µs (review round 10 sims, not in spice/).  Cost: the RC corner (~99 kHz) is above the 48 kHz PWM, so R302 carries most of the drive's switching ripple too: 0.11 / 0.24 / 0.52 W at 1 / 1.5 / 2 A rms, plus up to ~0.6 W of weapon ripple during a weapon burst (≤ ~1 W for ≤ 0.5 s; ~0.5 W continuous worst; the 1 W part derates to ~0.65 W at 100 °C); 0.8 V drop at an 8 A peak |
| CP 8 / CPH 7 / CPL 6 | C303 1 µF 50 V CP–L_VM; C304 47 nF 50 V CPH–CPL |
| AVDD 25 | C305 1 µF 50 V 0603 (TI wants 0.7–1.3 µF effective at 3.3 V; worst case sits at 0.7: check at bring-up) |
| VREF/ILIM 37 | tied to the chip's own AVDD (pin 25), C306 100 nF.  VREF must stay ≤ AVDD (3.1–3.465 V), so it cannot come from the external LDO.  Consequence: the cycle-by-cycle current-limit modes are **not usable** (they need VREF/ILIM near AVDD/2 and disable SOx); current limiting is done by the MCU's FOC loop |
| SW_BK 5 / FB_BK 3 / GND_BK 4 | **buck unused but must be populated** (SLVSH07 8.3.4.2 / 9.2.1.1.5): R300 22 Ω **1206** SW→FB, C307 22 µF **25 V** 0805 FB→GND (TI: ≥ 10 V); firmware disables it first thing (§8) |
| INHA/B/C 27/29/31 | TIM8_CH1/2/3 = PB6/PC7/PB9 (left); TIM20_CH1/2/3 = PB2/PC2/PC8 (right) |
| INLA/B/C 28/30/32 | +3V3 (3x PWM: INL = phase enable; Hi-Z is done with the shared DRVOFF pin, or per chip with the CTRL4 DRV_OFF bit, §8.1) |
| DRVOFF 21 | shared DRV_OFF net (PC14), R50 10 k pull-**up**: both drive bridges are off until firmware drives it low.  This is the drives' coast path (a timer break brakes: with TIM8/TIM20 OISx = 1 and OSSI = 1 it forces the high sides on in 3x mode, and gives Hi-Z for a chip that has reset into 6x mode, §8.1) |
| nSLEEP 23 | +3V3 (fault clear via SPI CLR_FLT, after unlocking the registers: §8) |
| nFAULT 22 | R301 10 k pull-up to the chip's **own AVDD** (TI: pulled > 2.2 V at power-up or test mode) → PB7 (left, TIM8_BKIN) / PC15 (right, EXTI; no TIM20 break pin exists on LQFP-64).  Over-temperature *warnings* are not routed to nFAULT (polled over SPI) |
| SOA/SOB/SOC 40/39/38 | through R70–R72 330 Ω with C80–C82 22 pF C0G at the MCU (TI §9.2.1.1.6) → left PA8/PA9 (ADC5_IN1/IN2) and PC3 (OPAMP5 follower → ADC5); right (R80–R82, C90–C92) PB12 (ADC4_IN3), PB13 (ADC3_IN5), PB1 (ADC3_IN1).  0.15 V/A → ±8.7–9.9 A over the AVDD range (accuracy specified to 6 A) |
| OUTA/B/C | motor wire holes J_LA..J_LC / J_RA..J_RC (`SolderWire-0.5sqmm…`: 1.15 mm drill; 2 pins each on the IC) |

**Footprint:** the RGF0040E land (EP 3.7 × 5.7 mm) is not in the KiCad library; draw
`thumbsup:TI_RGF0040E_VQFN-40-1EP_5x7mm_P0.5mm_EP3.7x5.7mm` from TI's package drawing.  Keep
AGND/PGND partitioned at the IC per TI §11.1 (the netlist has one GND net; do the partition in
copper: thermal pad + AGND pins + AVDD/VREF/CBK returns on a local island joined to the power
ground at the pad).

**Sensor connectors J2/J3** (SH 1.0 mm 6-pin, XUNPU WAFER-SH1.0-6PWB): 1 VS, 2 GND, 3 S1, 4 S2,
5 S3, 6 motor NTC.

* **Supply:** JP1/JP2 select 3.3 V (default, 1–2 bridged) or 5 V (2–3: 5 V Hall ICs).  Then U11/U12
  TPS22945 (100–200 mA current limit, 5–20 ms blanking, 80 ms auto-retry; OC flag unused) with
  C45/C48 4.7 µF in and C46/C49 1 µF out: a crushed cable (VS to GND) cannot pull the logic
  rails down (dip ≤ 0.5 V for 1–2 µs).
* **Signals:** R54–R59 4.7 k pull-ups to +3V3 at the connector (open-drain Halls), R110–R112 /
  R114–R116 1 k series, C110–C112 / C114–C116 1 nF **DNP** (fit only for Hall sensors; never
  with MT6701 ABZ), into U9/U10 SN74LVC3G17 Schmitt buffers powered from +3V3 (C47/C50).  Their
  inputs tolerate 5.5 V, so 5 V push-pull sensors are safe and the MCU pins (two of them TT,
  3.6 V-only) never see more than 3.3 V; a cable short onto a motor phase kills a buffer, not the
  MCU.  Outputs → TIM3_CH1/2/3 (PC6/PB5/PB0, left) and TIM2_CH1/2/3 (PA15/PB3/PB10, right):
  **MT6701 in ABZ (encoder mode) or UVW mode**, or Hall sensors.  Z (index) is handled with a CH3
  capture interrupt.  The MT6701's EEPROM is programmed off-board (its I²C is not on the
  connector).
* **Motor NTC** (if the motor has one): J pin 6 → R113/R117 2.2 k 0603 series → L_MTEMP/R_MTEMP
  with R52/R53 10 k pull-ups, C72/C73 100 nF and D7/D8 BAV99 clamps to GND/+3V3 → PF0/PF1.  A
  cable chafed onto a motor phase injects ≤ 6 mA into the clamp instead of 16.8 V into the MCU;
  firmware subtracts the known 2.2 k.  The Mk4.1 has no NTC: pin 6 can carry one glued to the
  motor can.
* **Residual:** a motor phase shorted onto the **VS** wire back-feeds the sensor supply (§7).

### 3.4 MCU and logic

* U1 STM32G474RET6 (LQFP-64).  Full pin plan in [`design/mcu_pinmap.md`](design/mcu_pinmap.md).
* VDD × 4: C60–C63 100 nF + C64 4.7 µF 0603.  +3V3A via R60 0 Ω (ferrite option): VDDA pin 29
  C65 100 nF; VREF+ pin 28 C71 100 nF + C66 4.7 µF.  VBAT pin 1 to +3V3 with C74 100 nF.
* NRST: C67 100 nF + R16 10 k pull-up (an RP2040 pin in reset has a ~50 k pull-down, which
  would otherwise hold NRST mid-level).  BOOT0 (PB8) R61 10 k to GND.  No crystal: HSI16 is
  −1.85/+1.55 % at 0–85 °C including initial spread; fine for 2 Mbaud.
* SPI3 (PC10/11/12) shared by U3/U4/U7, all SPI mode 1; chip selects PC9 (L), PB4 (R), PA11 (INA,
  R12 pull-up).  MISO floats between transfers (enable the PC11 internal pull-down).  SCLK ≤
  5.3 MHz (/32).
* USART1 PC4 (TX) / PC5 (RX, TT pin, R17 10 k pull-up; the compute board drives 3.3 V).
* PD2 = W_ARM_S input (FT, EXTI; clean Schmitt edges from U14; R19 10 k pull-down).  PA12 = W_EN.  PC14 = DRV_OFF.
* VBAT_SNS: R63 68 k / R64 10 k / C68 100 nF (0.87 ms) → PA3.  The header gets it only through
  R33 100 k (net VBAT_SNS_H, J1 pin 11), so a compute-board pin in reset cannot drag the MCU reading.
* U5 AP2112K-3.3 from +5V: 3.3 V for the MCU, CSA reference, sensors, logic (~120 mA of 600).
* Test pads TP1–TP12: 3V3, SWDIO, SWCLK, NRST, GND, W_ARM, W_EN, DRV_OFF, W_nFAULT, VBAT, 5V, GND.

**Timers and ADC plan.**  TIM1 (weapon) centre-aligned 24 kHz, ARR = 3542 (even), PWM mode 1:
weapon low sides are on around the TIM1 peak.  TIM8/TIM20 (drives) centre-aligned 48 kHz, ARR =
1771, reset-slaved to TIM1 through ITR0 (URS = 1), **PWM mode 2**: drive low sides are on around
the drive-timer valleys, which coincide with both the TIM1 valley and peak.  ES0430: every
concurrently converting ADC uses the same asynchronous clock, **PLLP = 42.5 MHz, prescaler /1**
(workaround 2), and they start together from one hardware trigger; every ADC gets the same number
of injected ranks with the same sampling time, and ADC1/ADC2 run in **dual simultaneous mode**.
**Injected** groups (all five ADCs) trigger on **TIM8_TRGO2 = OC6REF** at 48 kHz, CCR6 set so the
sample lands ~1 µs after the drive low-side window opens + DLY_TARGET (1.8 µs, §8): CCR6 ≈ 257–264
counts (trim on a scope at bring-up); it is an internal reference signal, so it keeps running when the TIM1
or TIM8 break has cleared MOE.  The weapon uses the samples at the TIM1 peak (its low-side
centre; it uses ranks 1–2 only, which already give A, B and C).  **Regular** groups (ADC1/ADC2 only) trigger on **TIM1_TRGO2 = OC6REF**, once per TIM1
period at a fixed weapon PWM phase placed inside t ∈ [3.34, 13.59] or [24.18, 34.43] µs of the TIM1
period (for CCR6 ≈ 257–264; each window moves by CCR6/170 MHz if CCR6 is trimmed) so they never overlap an injected group.  12.5-cycle sampling for every injected rank
(≥ 200 ns for the OPAMP5 channel, ≤ 680 Ω source behind the 330 Ω filters).  **Duty limits:**
weapon ~86–88 %; drive L ~81 % (three sequential ranks); drive R ~86 % using the rank-2 pair (A on
ADC4, B on ADC3) and C = −(A + B), because the DRV8316's CSA
only reads while its low-side FET is on (not in dead time); use flat-bottom SVPWM to recover line
voltage.  Start sequence: TIM1 MMS = update (TRGO), TIM8/TIM20 combined reset + trigger slave
mode on ITR0, enable the slaves first, then TIM1.

| ADC | Injected ranks 1 / 2 / 3 (simultaneous across ADCs) | Regular ranks 1–4 (same sampling time per rank on ADC1/ADC2) |
|---|---|---|
| ADC1 | W_SOA PA0 / W_SOC PB11 (ADC1_IN14, slow: 12.5 cycles allow ≤ 470 Ω, the CSA output is far lower) / W_SOC PB11 | W_VC PA2 / VBAT_SNS PA3 / L_MTEMP PF0 / VREFINT (247.5 cycles) |
| ADC2 | W_SOB PA1 / W_SOA PA0 (ADC12_IN1) / W_SOB PA1 | W_VA PA4 / W_VB PA5 / W_NTC PA6 / R_MTEMP PF1 (247.5 cycles) |
| ADC3 | R_SOC PB1 / R_SOB PB13 / R_SOC PB1 | — |
| ADC4 | R_SOA PB12 / R_SOA / R_SOA | — |
| ADC5 | L_SOA PA8 / L_SOB PA9 / L_SOC (PC3 → OPAMP5 → ch3) | — |

Weapon: rank 1 gives A+B, rank 2 C+A, rank 3 C+B simultaneously, with a fixed sequence (no
per-sector JSQR rewrites; PA0 is never on both ADCs in the same rank).  Drive R: A is
simultaneous with C and B.  Drive L: sequential (0.59 µs apart).  Regular ranks 1–3 run at
12.5–24.5 cycles; the weapon phase voltages W_VC (ADC1) and W_VA (ADC2) convert together, W_VB
one slot later, at a fixed PWM phase: what six-step BEMF and catch-spin need.  Each regular
group takes ~8.7 µs (with 24.5-cycle ranks), inside the allowed windows.  Enable VREFEN for VREFINT.

### 3.5 Header to the compute board — J1, 2 × 10, 1.27 mm (BOOMELE 1.27-2*10P, C59981)

| Pin | Signal | Pin | Signal |
|---|---|---|---|
| 1 | +5V out | 2 | +5V out |
| 3 | GND | 4 | GND |
| 5 | MB_TX (motor board → compute) | 6 | MB_RX |
| 7 | spare | 8 | NRST (compute can hold the motor MCU in reset) |
| 9 | SWDIO | 10 | SWCLK |
| 11 | VBAT_SNS_H (the ÷7.8 pack divider through R33 100 k; 3.3 V-safe up to 25.7 V) | 12 | GND |
| 13 | +5V out | 14 | GND |
| 15 | BMS_SDA (BQ76907 I²C data) | 16 | BMS_SCL |
| 17 | BMS_ALERT (open drain) | 18 | spare |
| 19 | **W_ARM_CLK** (toggled by the compute board = armed) | 20 | GND |

J1 is on the **bottom** side (it faces the compute board below), with the other low-profile bottom
parts (§6.13); JLC two-sided assembly is therefore required.  Footprint: custom `thumbsup:BOOMELE_1.27-2x10P_SMD` to the vendor land (20 × 1.5 ×
0.74 mm pads at x = ±2.5 mm; odd pins in the left column, pin 1 top-left, seen from the side it
is mounted on).  JLC's second-side assembly adds ~$30 per order (a second stencil and the
two-sided fee).

**Requirements on the compute board** (it is designed separately):

1. Mating 1.27 mm 2 × 10 SMD female socket whose footprint is the **mirror image** of J1: check
   pin 1 with a 3D stack-up before ordering either board.  The two boards are held together by
   4 × M2 **nylon** standoffs through MH1–MH4 (the header carries no mechanical load, and metal
   standoffs would add a second ground path).
2. Its 5 V input must be **isolated from USB VBUS**: a Schottky (or ideal diode) from the header
   +5V into the Pico's VSYS.  The Pico's own VBUS→VSYS Schottky does *not* do this; without the
   extra diode USB back-feeds +5V and VBAT (~4.4 V) through the buck's high-side body diode.
3. I²C pull-ups (3.3 V) for BMS_SDA/SCL and a pull-up for BMS_ALERT.  Read VBAT_SNS_H (behind R33
   100 k) with ~10 nF at its ADC pin and the pad pulls disabled (it sees ~109 kΩ source: a pull-down
   left on reads a third of the value; pin leakage of 1 µA is ~±0.85 V at the pack).  Keep the
   BQ76907's TS protections disabled (TS is tied to VSS; Enabled Protections B defaults to 0x00).
4. **W_ARM_CLK**: a 3.3 V square wave at ≥ 500 Hz with no gap longer than ~20 ms (gaps beyond
   ~30 ms may disarm, ~45–50 ms with nominal parts), toggled **by software** from a timer ISR running from RAM (not a free-running hardware
   PWM, which keeps running when the CPU hangs), gated by a permission the main loop must
   **refresh at least every 50 ms** (the ISR stops toggling when it goes stale, so a hung main loop
   disarms) and grants only while its own weapon-enable **and** the physical ARM link are present,
   the radio link is fresh (**radio loss detected within ≤ 0.5 s**, tested; some Bluetooth
   controllers only send on change, so use a keep-alive or the link-layer supervision set ≤ 0.5 s),
   **and** the motor MCU's heartbeat is seen on the UART (the STM32 ROM bootloader toggles
   some weapon-control pins).  No flash erase/program on the compute board while armed (an RP2040
   sector erase stalls XIP code for up to 400 ms): log to RAM and flush when disarmed.  On a reported weapon latch the compute board stops the ARM toggle (disarms).  Low or Hi-Z
   when disarmed or unpowered.
   * **Boot self-test (timed, run by the compute board, which knows when it stopped toggling; weapon
     command at zero):** (a) give one single edge and expect W_ARM_S to stay low (catches a C15/C16
     swap); (b) toggle for 100 ms and expect W_ARM_S high; (c) hold W_ARM_CLK high and expect the
     heartbeat's "W_ARM_S fell" flag within 20–250 ms (the fastest good board is ~30 ms, an open
     C16 ~0 ms); (d) toggle again, hold low, expect the same.  Uses the heartbeat fields defined in
     §8 (period ≤ 10 ms).  Catches a shorted C15, an open/high R41, an open C16 and a U14 stuck
     high.  On failure: refuse to arm and report it (the drive still works).
   * **Re-arm after a motor-MCU reset:** when the heartbeat reports "ARM edge required" and no
     weapon latch, hold W_ARM_CLK low for ≥ 250 ms, then toggle again; the weapon then waits for
     its command at zero.  A reported latch or hold is shown to the operator and needs an operator
     action to clear (§8.1); the compute board never sends "clear faults" on its own.  Keeping a
     latch across a power cycle is optional (the weapon's first-start checks re-detect a real
     short).
   * **Radio loss** (≤ 0.5 s) must also stop the drives: stop sending drive commands (the motor
     MCU's command timeout then coasts everything), not only the ARM toggle.
   * Hold-up: ~470 µF on the compute board's 5 V input rides through millisecond contact bounce
     at the switch/XT30 under load (otherwise both boards reset and Bluetooth takes seconds to
     reconnect).  Do not drive MB_RX while the motor board is unpowered (a USB-powered Pico would
     back-power the motor MCU through R17).
   * If the motor MCU's heartbeat stops for > 100 ms, stop toggling and pulse NRST (open drain),
     except during an SWD session or flash of the motor MCU; at most 2 such resets within 10 s,
     then stop resetting and report (a broken return line must not reset the motor MCU forever).
5. SWDIO/SWCLK/NRST Hi-Z when not debugging (NRST open-drain only).  MB_RX at 3.3 V.  Firmware
   updates of the motor MCU go over SWD (the ROM UART bootloader is on PA9/PA10, not MB_TX/RX).
6. A Pico W antenna must not sit under the motor board's copper, and its USB connector must stay
   reachable: keep both at the stack's edges (cut-outs in the motor board outline if needed).
7. Mechanics: the standoff length must equal the mated header height (4.9–6.0 mm depending on the
   socket chosen); parts on the compute board's top side under the motor board must fit in that
   gap; mount the stack to the chassis soft (grommets or foam), not hanging on the M2 nylon alone.

## 4. Sizing summary (details in `design/calcs.md`)

| Item | Number |
|---|---|
| Weapon spin-up (2822 1800 KV, 20 A limit) | 25.6 k rpm, 54 m/s tip, 64 J, 0.52 s to 90 % |
| Pack current peak / bus sag | 22 A / 14.1 V (4S, 70 mΩ pack+lead) |
| Weapon FET loss at 20 A | 0.84 W conduction (hot) + ~1.1 W switching (60 mA IDRIVE) per switching FET — 0.5 s bursts |
| Drive motor (Mk4.1, 43.2 mm wheels) | top speed ~3.7 m/s at 16.8 V, ~3.1 m/s at 14 V (duty-capped; 4.7 m/s is the unreachable no-load figure); traction limit ~0.8–1 A per motor; ~10–12 FOC updates per electrical cycle at top speed |
| Drive channel loss (48 kHz, hot RDS, slew 200 V/µs, dead time, quiescent) | typ 0.89 / 1.35 / 1.93 W at 1 / 1.5 / 2 A rms (worst 1.26 / 1.96 / 2.80 W, +72 °C JEDEC at 2 A) → ≤ 2 A continuous; the traction limit keeps it near 1–1.5 A |
| Current sense | drive ±8.7–9.9 A @ 5.4 mA/LSB; weapon ±35 A @ 20 mA/LSB |
| Voltage sense | 68k/10k: 16.8 V → 2.15 V, 6.3 mV/LSB (also reads 6S) |
| 5 V budget | 600 mA buck; MCU side ~120 mA at 3.3 V → **~450 mA available to the compute board** |
| Pack monitor | ±41 A, 1.25 mA/LSB; shunt 0.48 W and Q7+Q8 2.0–2.5 W at 22 A peak |
| Power switch closure | VBAT ~2.2 V/ms (1.3–3.0 over the gate-current spread), ~0.8 A inrush, ≤ 0.01 V/µs at VM; Q7 16 W peak (22.0 W at the max gate current) / 54–57 mJ |
| Logic cutoff / switch UVLO | logic off ~9.2 V / on ~10.4 V (2.3 V/cell: not pack protection); switch FETs off below ~9.0 V (7.7–10.1) |
| Board heat | ~4.4 W average over a match (calcs §11; weapon bursts 5.5 W, drives 2.7 W at 1.5 A + R302/R402 ~0.25 W each (≤ 1 W in weapon bursts), DRV8323 quiescent + gate drive 0.3 W, logic 1 W) |
| Board area (estimate, informational) | top-side courtyards ≈ 1900 mm² + bottom ≈ 700–900 mm², plus connector mating clearance → ~3600–4400 mm² at realistic density; the v1.1 bay is ~3100 mm².  Settled at layout with the levers in §6.13 |
| Board mass (estimate) | 4-layer 1.6 mm ≈ 4 g per 1000 mm² → ~13–16 g laminate + ~6–8 g of parts ≈ 18–23 g (stack ≈ 32–42 g vs the ≤ 40 g target); 1.2 mm laminate saves ~2–3 g.  Weigh at bring-up |
| Odometry | MT6701 1024 PPR on the motor behind 28.5:1: 116 k counts per wheel rev |

## 4a. Cell balancing: not used

The BQ76907 can bleed-balance cells, but the robot is only powered for the minutes around a
fight, so balancing would never accomplish anything; the external charger balances the pack.
Firmware never enables it (the 100 Ω inputs, R6 0603 / R7–R10 0402, are not rated for balance current).  The cell
monitor is kept for pre-match checks and for logging cell sag under load.

## 4b. Telemetry rates

"Measured" is how often the hardware produces a new value; "reported" is the proposed stream on
the UART to the compute board (USART1 at 2 Mbaud ≈ 200 kB/s; a 64-byte fast frame at 1 kHz uses
~64 kB/s, leaving room for commands and a 10 Hz slow frame).

| Quantity | Source | Measured | Reported (proposed) |
|---|---|---|---|
| Drive phase currents (6) | DRV8316C CSAs → ADC | 48 kHz | 1 kHz (per-motor Iq/Id) |
| Weapon phase currents (3) | DRV8323 CSAs → ADC, centre of the low-side-on interval | 24 kHz | 1 kHz |
| Drive rotor angle / wheel position | MT6701 ABZ into TIM3/TIM2 (hardware counting) | continuous; read every FOC cycle | 1 kHz (position counts, velocity) |
| Weapon speed (eRPM) | sensorless observer / BEMF | 24 kHz | 1 kHz |
| Weapon phase voltages | 68k/10k dividers → ADC, at a fixed PWM phase | 24 kHz | on demand (used internally) |
| Bus voltage (fast) | VBAT_SNS divider → ADC | 24 kHz (0.87 ms filter) | 1 kHz |
| Pack voltage, current, power (precise) | INA239, 16-bit | 50 µs–4.1 ms per conversion (here 150 µs shunt + 150 µs bus ≈ 3.3 kHz) | 100 Hz–1 kHz |
| Pack mAh used | firmware integration of INA239 current | every conversion | 10 Hz |
| Cell voltages (4) | BQ76907 | every scan loop (~15 ms for 4 cells) | 10 Hz (compute board reads it over I²C) |
| FET / motor temperatures (NTC), driver OTW | ADC, SPI | any rate | 10 Hz |
| Driver faults | nFAULT → timer break (weapon, drive L) / EXTI (drive R); SPI status (drives) | hardware: < 1 µs PWM shutdown | event + 10 Hz |
| Pack over-current / bus over-voltage | INA239 ALERT (SOVL, BOVL) → weapon timer break | one conversion (set ≤ 150 µs per channel) | event |
| Cell over/under-voltage | BQ76907 ALERT → compute board | per scan loop | event |

## 5. SPICE results (`spice/`)

| Check | Result |
|---|---|
| Power-switch closure (`sim_hotplug.py`, `hotplug.out`) | Behavioural LM74502 + Q7/Q8 model (charge pump, hysteretic EN/UVLO gating the 60 µA gate source and 2 Ω sink, C18, EN sink, D4, D10/C13/R32) with a realistic load (buck as constant power above its UVLO, ~66 kΩ of dividers, R15).  **Closure:** VBAT ramps ~2.2 V/ms (1.3–3.0 V/ms over the 40–77 µA gate current); VM dV/dt 0.002–0.005 V/µs in every case (stiff or 300 nH lead, C1 at 40 or 300 mΩ, 12 V pack) vs the 4 V/µs limit; Q7 16 W peak (22.0 W at max gate current), 54–57 mJ; the 9–23 A peak current is C14 ringing with the lead, upstream of the FETs.  **Reversed pack:** only the 13 A C14 spike with D10, whatever U13's unpowered gate hold; 102–147 A without D10 if that hold is weak.  **Re-close** (at the DRV8316 VM pins): typical thresholds 0.06–0.7 V/µs within ~0.1 s; minimum threshold with C1 at 300 mΩ 1.8–2.09 V/µs up to ~0.4 s; soft (≤ 0.005 V/µs) after that.  **Contact bounce, 20 A load, 0.1–0.8 ms:** 0.8–2.26 V/µs with C1 up to its aged 0 °C bound, 2.66 V/µs at its −40 °C ESR.  Longer bounces to ~1.3 ms (round 27/28 reruns, not in `hotplug.out`): ≤ 2.33 V/µs at 0 °C, 2.82 V/µs at −40 °C.  Without the R302/R402 filters these were up to ~3.75–4.3 V/µs |
| Dynamic ARM (`sim_arm.py`, `arm.out`) | 250 Hz–10 kHz toggling, 25 and 85 °C (BAT54S leakage): armed 2.50–2.95 V vs U14 VT+ ≤ ~2.15 V; 7–10 rising edges to arm; disarm 52–134 ms stuck low, 67–164 ms stuck high (to VT− 1.33 / 0.8 V) |
| Weapon bridge switching (`sim_weapon_bridge.py`) | At IDRIVE 400 mA the high-side VDS rings to 36–44 V and SHx undershoots past −7 V even with a 3 nH loop. At **60 mA** with a **3–6 nH** commutation loop: VDS ≤ 29 V (40 V part), SHx ≥ −4.6 V (−7 V limit).  At 12 nH, SHx reaches −7.3 V: the loop must stay short.  SPx peaks at +3.2 V for a few ns from the shunt ESL (limit ±3 V for 200 ns).  The FET model is calibrated to datasheet capacitances/gate charge, not a vendor model: read it as trends |
| Weapon spin-up (`sim_weapon_spinup.py`) | See §4; 15 A limit → 0.68 s, 25 A → 0.43 s, pack peak 27 A |

## 6. Layout and mechanical rules (what matters, in order)

1. **Weapon commutation loop ≤ 6 nH, target 3 nH:** one 10 µF per half-bridge (C25 A, C26 B,
   C31 C) directly across that half-bridge's drain and shunt ground on the same layer, bridge →
   shunt → cap in the tightest possible loop, solid GND plane on layer 2 directly under it.
   4-layer board, **1 oz inner copper** (JLC's default is 0.5 oz).
2. **Stack-up and pack current path:** L1 (top) power + parts, L2 solid GND, L3 power pours +
   signals, L4 (bottom) small parts + signals (no bare pack-current copper, all under mask).  BAT
   holes → Q7/Q8 → RS4 → C1 → bridges on wide L1/L3 pours with the return on a dedicated
   power-ground region; the 22–27 A return must not flow under the MCU,
   the CSA traces or the header ground pins (20–45 mV of offset = 0.5 A of weapon-current error).
   One solid, unsplit GND plane on L2 (no separate analog/power grounds); keep the high-current
   return confined to its region by placement, with the MCU, CSA filters and header outside it.
3. **Kelvin sense:** SPx/SNx as a pair from the inner edges of each shunt pad (net-ties NT1–NT3);
   VDRAIN Kelvin to the high-side drains.  U7 IN+/IN− from RS4's pad inner edges.
4. **DRV8323 straps:** R44–R46 within ~2 mm of pins 29–31, returned to AGND pin 35 / the DVDD
   capacitor return (quiet island), never to the power ground under the bridge; keep the open
   GAIN pin 32 pad short and away from switching nodes.
5. **DRV8316 thermal pads:** full via array to inner GND planes; copper area around each drive IC
   (RθJA 25.7 °C/W is the JEDEC 4-layer figure).  AGND/PGND partition per §3.3.  The 100 nF VM
   caps at pins 9 and 11 also serve pin 10 (adjacent); keep U11/U12 away from U3/U4 (85 °C parts).
6. **R302/R402** (up to ~1 W in bursts) away from the DRV8316 thermal copper, on their own pour.  Keep the **DRV_OFF** trace (PC14, a 2 MHz / 30 pF pin) short.  **Power entry:** U13, C12, C14, C18 (at U13 pin 1), R1, D10, C13, R32, D4 next to Q7/Q8; the gate trace short.  Feed U3/U4's VM from C1 on their own branch (not through the weapon bridge's copper), so weapon switching ripple at the DRV8316 VM pins stays well under 4 V/µs (check in §9 step 6).  C1 close to the
   switch output *and* the bridges; each DRV8316 gets its 2 × 100 nF + 4 × 10 µF within 2 mm, on the filtered side of R302/R402 (all DRV8316 VM current must pass through the resistor).
7. **Buck:** SW node tiny; L1/D2/C29 loop tight per the LMR16006 layout guide; FB divider at
   pin 1 away from L1; R4/R5/C10 away from SW.
8. **Analog:** CSA outputs and dividers routed away from phase nodes; the 330 Ω / 22 pF and 1 nF
   filters at the MCU pins.  The weapon INH traces (PC0/PC1) run beside analog pins: keep them
   away from PA0, PA1, PB11 (weapon CSA inputs), PC3 (drive L CSA) and PA2.  Place U2 toward the MCU's left/bottom edge.  Keep W_ARM_CLK/C15/D9
   away from MB_TX and switching nodes.
9. **Connectors:** J4 near the pack side, silkscreen "B−" at pin 1 and "B4+" at pin 5; cell-input
   R/C and D5 at U8; tap traces thin.  J2/J3 at the board edge near the drive ICs with U9–U12,
   R110–R117, D7/D8 beside them; silkscreen "VS" and "T" at the pin-1 and pin-6 ends (the clone's
   drawing does not number its pins: confirm pin 1 against a mating SHR-06V-S cable before the
   footprint is final; both mounting tabs = pad "MP").  Battery and weapon wires in 2.15 mm-drill
   plated holes, drive wires in 1.15 mm holes, pads joined to the pours with wide thermal spokes
   (≥ 4 × 1 mm), strain relief (tie or glue) near the board.  The wire joints protrude on the bottom:
   place them outside the compute board's outline (or keep a matching clear zone on it) and cover
   them (Kapton/conformal coat).  D3 where it can be seen from outside the robot.  Test pads
   TP1–TP12 on the **top** side (they must be reachable with the compute board mounted).
10. **Mechanical:** 4 × M2 NPTH holes (MH1–MH4) near the corners for nylon standoffs clamping the
    stack; J1 on the bottom side; no exposed pack-current copper on the bottom layer facing the
    compute board (keep the high-current pours on top/inner layers, solder mask everywhere);
    C1 staked with adhesive by hand after assembly (JLC does not stake); 1206/2512 parts and C14 (across the unswitched pack) oriented parallel to
    the nearest board edge/standoff line and kept ≥ 3 mm from the holes (flex cracks across the
    bus are shorts on an unfused LiPo); keep the Pico W antenna area of the compute board clear.
11. U8 uses KiCad's QFN-20 EP 2.0 mm land (TI's RGR0020A is 2.05 mm): acceptable; paste per KiCad.
12. **Custom footprints to draw** (`thumbsup.pretty`): TI_RGF0040E… (U3/U4, TI RGF0040E
    drawing), R_2512_HoLR_1-4mR (RS1–RS3, Milliohm HoLR datasheet land), BOOMELE_1.27-2x10P_SMD
    (J1, BOOMELE drawing), SH1.0-6P_RA_XUNPU_WAFER-SH1.0-6PWB (J2/J3, XUNPU drawing: tab pads
    1.2 × 2.5 mm).  RS4 uses JIERR's small-electrode land (2.1 × 4.0 pads, 4.1 mm gap, datasheet p.5): R_2512_JIERR_RE_small_electrode.
13. **Area and placement (settled at layout).**  Estimate: top-side courtyards ≈ 1900 mm², bottom
    ≈ 700–900 mm², plus mating clearance for J2–J4 → ~3600–4400 mm² at realistic density, vs a
    ~3100 mm² v1.1 bay.  Assembly is two-sided anyway (J1).  **Top:** Q1–Q8, RS1–RS4, C1,
    C25/C26/C31, U1–U4, U13 and the power-entry parts (BAT_IN must not appear on the bottom face),
    L1, D1/D2, J2–J4, the wire holes, D3, the test pads, and every part taller than ~1.1 mm (U5,
    C9, the SOD-123 diodes).  **Bottom** (low-profile, inside the stack gap minus the compute
    board's own top-side parts): 0402/0603 passives that are not loop-critical, the SC-70/SOT-23/
    VSSOP/TSSOP logic and monitor ICs.  Loop-critical parts (bridge caps, CSA filters, DRV
    decoupling, gate network, buck loop) stay on the same side as their IC.  Levers if it does not
    fit: move the cell monitor (U8, J4 and its network) to the compute board (its I²C host), 3.3 ×
    3.3 FETs for the weapon/switch (§7.3), drop the sensor-line protection, or enlarge the bay.

## 7. Decisions, residual risks and caveats

1. **Reversed main pack:** Q8's body diode blocks; U13 withstands −65 V; the INA239 sits after
   the switch.  **With the balance lead also plugged**, GND sits at pack+ and D5 conducts ~160 mA
   through R6 (2.7 W): R6 and U8 are damaged.  Only a mis-wired pigtail can do this (both
   connectors are keyed); plug the main lead first, the balance lead last.
2. **Re-closing the power switch early, or a contact bounce under load, is not soft-started.**
   Re-closing within ~0.1 s (typical thresholds) to ~0.4 s (minimum threshold, unloaded) of
   opening finds Q7/Q8 still on.  A bounce of ~0.1–1.3 ms at the XT30/switch while the weapon draws
   20 A collapses the bus faster than the C18-filtered UVLO reacts (~1–2 ms), so the switch
   re-closes hard onto a bus at ~4–10 V.  That is below the DRV8316 UVLO: the drives reset and come
   back through "drives resume" (§8.1).  At the DRV8316 VM pins, behind R302/R402:
   * re-close ≤ 2.1 V/µs;
   * loaded bounce ≤ ~2.3 V/µs with C1 at its aged 0 °C bound (~100 mΩ);
   * ~2.7–2.8 V/µs only at C1's −40 °C ESR limit, outside the environment;
   * all vs the 4 V/µs abs max.  Sources: `spice/hotplug.out` for 0.1–0.8 ms, round 27/28 reruns
     to 1.3 ms.

   The weapon bridge and U2 see the unfiltered step (no ramp limit on them).  No C18 value closes
   the window without bringing back the ripple trip (review/round8_c18_sweep.md).  §9 step 6
   scopes a real bounce.
3. **Weapon FET package:** 5×6 HYG015N04LS1C2 (proven, in stock).  A 3.3×3.3 40 V ≤ 5 mΩ FET
   would save ~40 % of the bridge area.
4. **Regen with the pack disconnected:** a spinning drum can pump VBAT up (64 J vs a 600 W TVS).
   The INA239 BOVL (19 V) trips the weapon break (coast) within ~0.3–0.45 ms; firmware also coasts
   above 18.5 V, never brakes the drum hard, and limits combined regen to a **current** of ~10 A
   (§8 Power budget).  Until the coast acts, D1 clamps: ~28.7 V at 10 A (SMBJ20A linear clamp
   model).  That puts the 68 k/10 k sense pins PA3–PA5 at ~3.7 V (≤ 3.75 V with 1 % resistors).
   * PA4/PA5 (1 nF, τ ≈ 9 µs) follow the clamp; PA3 (100 nF, τ 0.87 ms) follows only partly.
   * **These are TT_a pins.**  3.7 V is inside the 4.0 V absolute maximum (DS12288 Table 14) but
     above the VDD + 0.3 V ≈ 3.55–3.65 V operating limit (Table 17).  TT_a pins have no clamp
     diode to VDD, so no current flows into them (positive injection "not possible", Table 15).
   * **Accepted:** it only happens when the pack disconnects during a brake, lasts < ~0.5 ms, and
     the ADC just reads full scale meanwhile.
   * The 4.0 V abs max is reached only at ≥ ~14 A of clamp current, which is why the regen limit is
     a current limit, measured in §9 step 6.  Staying inside the operating range in every case
     would need ≤ ~6–8 A of regen (VDD and divider tolerance).
5. **Power switch vs a coasting drum:** opening the switch while the drum spins leaves the board
   powered through the motor's body-diode rectification until the drum slows to ~19 k rpm; the
   power LED stays lit meanwhile.  Firmware detects the open switch (pack current ≈ 0 with the bus
   up, §8.1 row 0), coasts the weapon and stops the drives.  Re-closing while the drum still holds
   the bus up is not soft-started.  This case is not simulated, but the step is bounded by the
   drum's rectified BEMF, so it is no larger than the simulated quick re-close (≤ 2.1 V/µs at the
   DRV8316 VM pins).  Tell the pit crew and inspectors.
6. **Weapon stop after disarm is a free coast** (hardware Hi-Z; no braking without ARM):
   estimated 10–40 s.  **Measure it at bring-up** (§9 step 6) against the event's limit (e.g.
   60 s).  A commanded stop while armed brakes at the ~10 A regen limit in ~0.5 s.
7. **Motor phase shorted onto a sensor VS wire** back-feeds VS through the TPS22945 into the
   logic rail.  This needs the harness to be cut through to a phase conductor; not protected.
8. **Main negative lead opening while running** makes the balance lead the only ground return;
   U8 (and R6) will probably not survive.  Secure the negative lead.  The balance taps are
   unfused wires that bypass the power switch: route them away from moving parts.
9. **6S** is not supported (DRV8316 40 V abs max).  The 6S variant uses a DRV8323 + FETs on all
   three channels with the same MCU and header; the dividers already read 25.2 V.
10. **Drive motor:** Repeat Mini Mk4.1 is currently sold out; the design does not depend on it
    beyond the calcs (any 16 mm-class motor with a sensor or sensorless FOC works).
11. **J4 (XH side-entry) is through-hole:** JLC Standard PCBA (THT) or hand-solder it.
12. **STM32 source:** LCSC is not an ST-authorised distributor; check the marking and the device
    ID/UID/revision (ES0430 errata depend on it) at bring-up.
13. **Bench use with USB:** a compute board connected to an earthed PC plus an earthed bench
    supply ties grounds outside the board; use a floating supply or a USB isolator.
14. **No over-current disconnect on the bus.**  U13 has no current limit.  A hard short across VBAT
    pulls BAT_IN below the switch UVLO, which opens Q7/Q8, then the UVLO releases and the switch
    retries into the short with Q7 in its linear region (~1 kW pulses): Q7 will probably fail
    short.  A partial short is not interrupted at all.  **Fit an inline fuse in the pack lead**
    (e.g. a 40 A mini blade or a 30–40 A fusible link; the weapon's 20 A bursts and 22–27 A pack
    peaks set its minimum rating).
15. **Builder's option:** for a fight build the cell monitor (U8, J4, R6–R11, C4–C9, C11, D5) can
    be left unpopulated; it removes the only through-hole part and keeps the unfused balance taps
    out of the robot.  Everything else is unaffected.
16. **Single faults that silently remove a protection** (none is visible in operation):
    * **ARM:** C15 short, R41 open/high, C16 open or U14 stuck high → ARM is no longer dynamic.
      The compute board's timed boot self-test catches all four.  W_ARM_S feeds both the hardware
      gate and the firmware check, so a U14 output fault defeats both; the command-link timeout
      remains.
    * **U6** gate stuck high → one weapon phase enabled without ARM.  No torque at standstill; a
      partial brake (~30–50 A) on a coasting drum.  Safe, not detectable.
    * **Power entry:** D10 short → the soft-start's reversed-pack protection is lost; Q7 short →
      no soft-start; Q8 short → no reverse-polarity protection.  Not detectable.
    * **R302/R402** shorted, or the local VM caps missing → the DRV8316 loses its VM ramp margin
      (loaded bounce ~2.3 → ~3.5 V/µs).  §9 step 0 measures the resistors.
    * **U2 straps:**
      * open R44 (MODE) → 1x PWM, where the disarm state (INL low) *brakes* instead of coasting;
      * shorted R44 → 6x PWM, where INH turns a high side on without ARM;
      * open R46 (VDS) → trip at 0.6 V, 250–430 A: the shoot-through backstop is gone;
      * open R45 (IDRIVE) → 120/240 mA gate drive (sim: VDS 39 V, SHx −9.2 V, over the limits);
      * an open GAIN pin with leakage → CSA gain error.

      **Measure the four strap voltages at bring-up (§9 step 2).**  The firmware boot test (§8 boot
      order, §8.1 row 11) also catches a 6x-mode strap.  It runs only with the drum stopped (all
      W_Vx ≈ 0).  A ≥ 30 µs INH pulse on one phase with INL = 0 must leave that phase's W_Vx at
      ~0 V (6x mode reads ~VBAT/7.8; sample by software trigger inside the pulse, τ ≈ 8.7 µs) and
      draw no current, and the idle CSA offsets must sit at VREF/2.  A failure latches the weapon
      off.
17. **The board is not pack protection.**  Switched on and idle it draws ~95–113 mA (~1.6–1.9 W)
    and flattens a small pack in 2–3 hours; the logic cutoff is 2.3 V/cell.  Switch the robot off
    between matches; the compute board raises a low-cell alarm from the BQ76907/INA239 data.
18. **LiPo 4.20 V/cell only.**  LiHV (4.35 V/cell, 17.4 V full) plus the regen rise reaches
    ~18.1–18.6 V at the 10 A regen limit (~18.8 V at 20 A).  Braking a full LiHV pack therefore
    runs into the 18.5 V coast (and at 20 A the 19 V BOVL), with no margin.
19. **Fit** is decided at layout (§6.13).
20. **The weapon driver U2 also makes the 5 V rail.**  If the weapon stage fails in a way that
    takes U2's buck with it, the whole robot (MCU, compute board, radio) goes dark: fail-safe
    (everything coasts), but immobile.
21. **Weapon phase short and the fast trip.**  A phase short reaches up to ~500 A before the
    DRV8323's fixed 4 µs VDS trip acts (near the FETs' 600 A pulse rating).  When the bridge turns
    off, the loop current dumps onto the shared bus: 6–36 V/µs at the DRV8316 VM pins without the
    R302/R402 filters (review round 9/10 sims, not in spice/).  So the weapon **requires the
    comparator fast trip** (§8).
    * All three weapon CSA outputs reach a comparator (PA0 → COMP3, PA1 → COMP1, PB11 → COMP6)
      feeding TIM1's main break.
    * The bridge turns off 0.7–1.0 µs after the current passes the threshold: CSA lag
      0.13–0.33 µs, comparator + break ~0.05 µs, driver 0.15 µs, gate discharge at 120 mA ~0.4 µs.
      With the filters, the DRV8316 VM then sees ~1–2 V/µs (round 10 sims).
    * §9 step 4 scopes the trip.  Latching and restart rules: §8.1 rows 4–6 and 8.

    **Residual:** a phase-to-*ground* short bypasses the shunts, so only the 4 µs VDS trip acts.
    That gives ~7–8 V/µs at the filtered VM, **above the DRV8316's 4 V/µs abs max**: a
    damaged-harness event that may take the drive ICs with it.
    * R302/R402 then carry ~100 A for ~1 µs (~1 mJ).  The datasheet gives no µs pulse rating; the
      estimated ~3 K film rise is unverified but far from any limit.
    * If a DRV8316 fails shorted, R302/R402 act as its fuse.
    * D1 is the real clamp when the pack disconnects during regen (§7.4); an open D1 is a silent
      single fault.
## 8. Firmware contract (what the hardware assumes)

**Boot order** (each step before the next):

1. Start the **IWDG** (~20 ms; frozen on debug halt in debug builds via DBG_IWDG_STOP); refresh it
   explicitly through the rest of boot.
2. `HAL_PWREx_DisableUCPDDeadBattery()` before any GPIO init (PB4/PB6 dead-battery pull-downs).
3. Clocks: HSI16 → PLL 170 MHz.
4. USART1 and the first heartbeat (the compute board expects it within ~50 ms of reset, §3.5).
5. DBGMCU: freeze TIM1/TIM8/TIM20 on core halt (a halted core then leaves the drives braking and
   the weapon coasting).
6. GPIO (PC11 pull-down; never enable RTC_OUT/TAMP/LSE on PC13–15) → SPI3 → configure U3/U4
   (DRV8316C row: they end coasted) and U7 → W_EN high → CSA offsets → the §7.16 strap boot test
   (drum stopped).
7. Drives: DRV_OFF pin low only when the drives are commanded, always through §8.1 "drives resume".
8. Weapon: TIM1 CHxN only while W_ARM_S (PD2) is high **and** a fresh low→high ARM edge has been
   seen since this reset (the heartbeat carries "ARM edge required" until then) **and** the weapon
   command has been seen at zero.

BOR level is an option byte: program it once over SWD (level 4, ~2.8 V).

| Device | Setting |
|---|---|
| Heartbeat (to the compute board, every ≤ 10 ms) | CRC + an incrementing counter; W_ARM_S level; a latched "W_ARM_S fell" flag with the time since that edge (ms, saturating; held until the compute board acknowledges it, so a glitch shorter than a heartbeat still shows); "ARM edge required"; latch/hold flags with reason; fault counters; DRV8316 register-check status |
| Command link / failsafe | Frames from the compute board carry a CRC and a sequence counter; a frame whose counter has not changed is not fresh (a hung compute board can keep re-sending its last frame from DMA).  No fresh valid frame for 100–250 ms → drives coast (DRV_OFF high), weapon coast (CHxN low); stay stopped until commanded again (weapon: throttle-zero interlock, §8.1) |
| Watchdog / faults | IWDG ~20 ms, refreshed from the main loop only when every task has checked in (control ISRs, command-timeout handler, fault supervisor).  HardFault/NMI handler: DRV_OFF high, TIM1 MOE = 0, then wait for the IWDG.  SYSCFG_CFGR2.CLL = 1 so a core lockup breaks the timers in hardware; CLL acts only on timers with BKE = 1, so set BKE on TIM20 too (no break pin: BKINE = 0).  No flash erase/program while running (a page erase outlasts the IWDG).  U2's ~1 ms wake nFAULT and the INA239 ALERT both pull W_nFAULT (the TIM1 break) low: at boot clear TIM1's break flag only after U2 is awake and DIAG_ALRT has been read; TIM8/TIM20 break flags are cleared inside "drives resume" (§8.1).  Boot-time events are not faults.  Fault handling: §8.1 |
| CPU budget | Two FOC loops at 48 kHz + one at 24 kHz + observers ≈ 60–80 % peak on the 170 MHz M4F: bare-metal ISRs in CCM SRAM, CORDIC for sin/cos, measure cycles at bring-up; fallback: keep 48 kHz PWM (the 2:1 timer lock and the sampling scheme depend on it) and run the drive current loops at 24 kHz (~5–6 updates per electrical cycle at top speed: acceptable only below top speed), or the weapon observer at 12 kHz |
| Drive VM | the DRV8316 VM sits I × 0.1 Ω below VBAT (R302/R402): use VBAT − I_bus × 0.1 Ω for voltage feed-forward (the DRV8316 cannot report its VM) |
| Power budget | One shared budget: weapon + drive current ≤ ~32 A (below the 38 A SOVL trip); **fold back drive and weapon current as VBAT sags toward ~12 V (required: the switch UVLO can open as high as 10.1 V and the logic cutoff at 9.2–10.3 V)**; combined regen limited by a **current** limit (≤ ~10 A: with the switch open during a brake the TVS then clamps ≤ ~28.7 V, keeping the TT_a sense pins PA3–PA5 at ≤ ~3.75 V: inside their 4.0 V abs max, briefly above VDD + 0.3 V, §7.4) sized so the bus stays below 18.5 V (not a bus-voltage regulator, which would hide an open switch) |
| DRV8323RH (U2) | No registers.  ENABLE (W_EN) high at boot and kept high; an 8–40 µs low pulse (t_RST) clears a latched fault without sleeping, a longer one is sleep.  Expect nFAULT low for ~1 ms (t_WAKE) after each wake.  Measure the CSA offsets (bridge idle, INLx = 0) after every wake.  FOC: hold TIM1 CHxN statically high (CCxNE = 0, OSSR = 1, polarity for high off-state); six-step: per-phase Hi-Z via CHxN.  Break (MOE = 0) with OISxN = 0 → INL low → coast.  **AOE = 0** (re-enabling is a firmware decision).  W_nFAULT is a wired-OR of U2's nFAULT and the INA239 ALERT (ALATCH = 1: held until DIAG_ALRT is read), so read and clear DIAG_ALRT before attributing a low W_nFAULT to U2 (§8.1) |
| W_ARM_S (PD2) | EXTI both edges, high priority (U14 gives clean edges).  A **falling** edge acts at once: full weapon stop (CHxN low, current controllers reset) and sets the heartbeat's "W_ARM_S fell" flag (the compute board, which knows when it stopped toggling, does the timing).  A rising edge counts only after W_ARM_S has stayed high ≥ 5 ms.  Re-arm needs a new ARM edge and the weapon command at zero (§8.1 throttle-zero interlock) |
| DRV8316C (U3, U4) | **SPI:** mode 1, ≤ 5.3 MHz, 16-bit frames with an even-parity bit (B8, computed by firmware, not copied from constants); one device selected at a time (never both CS low); one SPI3 owner task for U3/U4/U7.  SDO is Hi-Z while nCS is high (CTRL2 resets to push-pull, 0x60).  Registers reset on any sleep/UVLO: ignore reads before the configuration is written.  **Configuration** (after t_READY 1 ms; at boot with the DRV_OFF pin high; the same sequence is the "rewrite" after an NPOR or mismatch, for one chip with the pin left as it is): CTRL1 0x0603 (unlock) → **CTRL6 0x1019** (BUCK_DIS, BUCK_CL, BUCK_PS_DIS) → **CTRL3 0x0A4E** (OVP 22 V on, SPI faults off nFAULT, OTW *not* on nFAULT: poll it) → **CTRL4 0x0C90** (OCP 16 A latched, a short-circuit backstop; bit 7 DRV_OFF = 1: the chip stays coasted) → **CTRL5 0x0F00** (CSA 0.15 V/A) → **CTRL10 0x1818** (delay compensation on, DLY_TARGET 0x8 = 1.8 µs: covers the worst-case driver delay; TI's 1.2 µs cannot be held at the delay's upper spread) → CTRL2 0x087C (SLEW 200 V/µs, 3x PWM, push-pull SDO) → CTRL2 0x097D (CLR_FLT) → CTRL1 0x0606 (REG_LOCK).  CTRL4 and CTRL5 are written explicitly.  **Release** (only inside §8.1 "drives resume", with the timer already running FOC preset to the back-EMF): CTRL1 0x0603 → CTRL4 **0x0D10** → CTRL2 0x097D (CLR_FLT) → CTRL1 0x0606.  **Per-drive coast:** CTRL1 0x0603 → CTRL4 **0x0C90** → CTRL1 0x0606 (0x0D90 and 0x0C10 have odd parity and are rejected).  **Fault recovery** (a locked chip ignores CLR_FLT): CTRL1 0x0603 → CTRL2 0x097D → CTRL1 0x0606.  **Register check at ~100 Hz:** expect CTRL1 0x06, CTRL2 **0x7C** (CLR_FLT self-clears), CTRL3 0x4E, CTRL4 0x10 released / 0x90 coasted (0x14 / 0x94 inside a 24 A resume window, §8.1), CTRL5 0x00, CTRL6 0x19, CTRL10 0x18, IC_STAT NPOR = 1; also read IC_STAT FAULT (0 on a released chip with the DRV_OFF pin low) and the OTW bit (derate on OTW; a still-low nFAULT gives no new EXTI edge).  A mismatch or NPOR = 0 means the chip reset (it comes up in 6x PWM mode) → rewrite (it ends coasted), report, §8.1 drive events.  OVP 22 V trips at 20 V minimum.  Sample the CSAs in the centre of the low-side-on interval, ≥ 1 µs after it opens + DLY_TARGET; duty ≤ ~81 % (L) / ~86 % (R, rank-2 pair, C = −(A+B)), flat-bottom SVPWM (CTRL3 PWM_100_DUTY_SEL left 0 is fine at that cap).  Current limiting in the FOC loop (ILIM modes unusable with VREF = AVDD); starting limit ~1–1.5 A for the Mk4.1 (traction) |
| STM32 timers/ADC | §3.4: TIM1 24 kHz (ARR 3542, PWM mode 1), TIM8/TIM20 48 kHz (ARR 1771, PWM mode 2) reset-slaved via ITR0 with URS = 1 (TIM8/TIM20 OISx = 1, OSSI = 1, §8.1); the timers never stop (ADC triggers ≤ 1 ms apart).  ADC clock asynchronous PLLP 42.5 MHz /1 for all ADCs; ADC1/ADC2 dual simultaneous; injected on TIM8_TRGO2 (OC6REF, 48 kHz), 3 ranks everywhere, 12.5 cycles, JQDIS = 1; regular (ADC1/ADC2) on TIM1_TRGO2 = OC6REF inside the non-overlap windows (relative to CCR6), 4 ranks with VREFINT (VREFEN) and R_MTEMP both at 247.5 cycles.  Circular DMA; never stop an ADC without disable/enable; set JQDIS before writing JSQR; discard the first samples after every start and debug halt (ES0430: > 1 ms without a trigger); reject rev Z silicon.  TIM1 MMS = update; TIM8/TIM20 combined reset + trigger mode, slaves enabled first.  Trigger details: TIM8 OC6 in PWM mode 2 (rising edge used as TRGO2 = OC6REF; PWM mode 1 would sample 1.5 µs before the valley); TIM1 OC6 for the regular trigger at CCR 568–2311 (PWM mode 2) or 1231–2974 (PWM mode 1); ADC1/ADC2 DUAL = 00001 (combined regular + injected simultaneous); the weapon uses the sample taken while TIM1 counts down near its peak (read TIM1 DIR).  OPAMP5: VM_SEL = follower, VP_SEL = VINP2 (PC3), OPAINTOEN = 1 **before** OPAEN (otherwise it drives PA8), high-speed mode; calibrate the L_SOC offset separately; **do not run HAL OPAMP self-calibration** (it clears OPAINTOEN and drives PA8 against U3's SOA for ~25 ms): use the factory trim.  VREFBUF off (VREF+ is tied to VDDA).  TIM1 BKIN (PC13) and TIM8 BKIN (PB7) active low; R_nFAULT (PC15) EXTI at top priority: record it; §8.1 drive events decide (the DRV8316 already Hi-Zs itself on its own faults).  DRV_OFF low only when the drives are commanded (§8 boot order) |
| Timer inputs | TIM3/TIM2 encoder mode on CH1/CH2 (MT6701 ABZ, 1024 PPR = 4096 counts/rev), Z via CH3 capture interrupt; input filter ICxF ≤ 0b0011; TIM3 extended to 32 bits in software.  Leave the MT6701 power-up absolute ABZ train **off** (the default).  The sensor is powered from +3V3 (TPS22945 ON = VIN): the MCU cannot re-power it.  **Start angle** (ABZ is incremental): whenever the angle is invalid (after a reset, or after ≥ ~20 ms without edges while the observer says the motor turns) and the rotor is still, align one drive at a time in **two steps** (~1 A at +90° electrical, then at 0°, ~100 ms each; a single vector has a dead zone at 180° error where gearbox friction holds the rotor).  Check that the encoder moved by the expected amount (~171 counts) **and sign** and that the other drive's encoder stayed still (catches swapped J2/J3 sensor cables or motor bundles).  Wrong sign on two clean alignments → wiring fault, latch that drive; the other encoder following → left/right crossed (§8.1 drive row 7); too little motion → retry at a higher current, then sensorless and report; a disturbed alignment (robot pushed) is repeated a few times, then sensorless and report.  Set an angle offset (never zero the count, so odometry stays continuous); the wheel moves ≤ ~0.4 mm through 28.5:1.  If the rotor is turning, take the angle from the next Z and the stored Z offset instead.  **Z reference:** Z's electrical offset is measured once at bring-up and stored (§9 step 5).  At the first Z after an alignment, > ~30° electrical from it → keep the alignment and report "Z offset stale" (re-run §9 step 5, e.g. after a magnet re-glue).  At every later Z compare the count (mod 4096; capture Z with the counter's direction bit, or set Z_PULSE_WIDTH = 1 LSB, so a reversal does not shift it): a few counts is drift (correct it); a larger error is lost or extra A/B edges → re-reference; a second one since reset marks the encoder suspect → sensorless and report.  **Encoder plausibility:** above a few thousand rpm compare the encoder angle with the sensorless observer; > ~30° electrical disagreement → that drive goes sensorless and reports.  This is also the only check for a slipped magnet (Z moves with it): an accepted residual.  **Lost encoder at standstill** cannot be told from a pushing stall (ABZ has no status; the pull-ups freeze the count): report "no encoder edges, torque commanded" with its duration in the heartbeat; once moving, the plausibility check catches it.  Return to encoder mode after edges resume and a Z matches the reference.  **Speed cap on the encoder:** ≤ ~50 k rpm motor (MT6701 rated 55 k rpm); field weakening only in sensorless mode |
| Weapon fast trip (required) | The DRV8323 CSA **inverts**: shoot-through and phase-to-phase / phase-to-VBAT shorts pull SOx *low*, so each comparator trips when SOx < ~0.45 V (VREF/2 − 30 A × 40 mV/A; default **30 A**: at the 20 A limit the PWM ripple is ±3–5.5 A and nuisance trips would keep restarting the weapon (§8.1 row 6), so lower it only after measuring).  Inverting inputs from the internal-only DACs (DAC3_CH1, DAC4_CH2; DAC1_CH1/DAC2_CH1 would drive PA4/PA6).  With TIM1 BKP = 0 (active-low nFAULT on PC13) no inversion anywhere: COMPx POL = 0, BKCMPxP = 0.  Outputs to TIM1's **main break (BRK, BKCMPxE)**, not BRK2 (BRK2 would leave the INL enables high through the output polarity in FOC).  TIM1 dead time 0 (the DRV8323 inserts its own; the INL enable only falls after the timer dead time).  OSSI = 1 (otherwise R47–R49 add ~1.5–2 µs), BKF = 0, blanking off by default (the CSA slew already acts as ~120 ns of blanking; a TIM1_OC5 window would be a blind spot).  Comparators enabled only while U2 is awake; comparator interrupts to tell a comparator trip from nFAULT |
| Weapon fast trip (wiring) | COMP3 (PA0, W_SOA), COMP1 (PA1, W_SOB), COMP6 (PB11, W_SOC); each CSA pin reaches only one comparator non-inverting input |
| INA239 timing | shunt and bus conversion ≤ 150 µs each so SOVL/BOVL act within ~0.3–0.45 ms (the alert follows the conversion that sees the limit) |
| Weapon safety | Coast if the bus exceeds 18.5 V (from the INA239 VBUS reading: the VBAT_SNS ADC can read low while a compute board holds its pin at reset), then restart as §8.1 row 1.  **Stall cut-out** (§8.1 row 10): at the current limit with no speed rise for > 0.5 s → coast ~1 s and retry; TH1 > ~100 °C → coast until < ~80 °C; report (a jammed drum otherwise dissipates continuously).  Weapon control at 24 kHz gives ~7–8 updates per electrical cycle at full speed (2822 = 14 poles, 7 pole pairs: confirm): use the sensorless observer with angle prediction there, six-step only at low speed.  **Never short-brake the drum** (all low sides on at 25 k rpm ≈ 14 V BEMF into tens of mΩ = hundreds of A) |
| Braking and reversal | Regen returns to the pack through the switch FETs (bidirectional when on); the bus rises by I × R_pack (~1.4 V at 20 A).  **Weapon:** reverse (e.g. an invertible drum) by a controlled FOC deceleration inside the combined ~10 A regen limit (Power budget row; ≈ 0.5 s from full speed), then spin up; or coast down.  **Drives:** normal FOC braking/reversal inside the same limit.  If the pack is disconnected mid-spin, the INA239 BOVL break + the 18.5 V coast stop the drum from pumping the bus; the DRV8316 OVP Hi-Zs the drives.  INA239 current is signed: negative = regen |
| INA239 (U7) | DEVICE_ID check: DIEID (bits 15:4) = 239h (reads 2391h; 229h = INA229 → 24-bit register handling).  SHUNT_CAL 0x1000 (1 mΩ, ADCRANGE = 1, ±40.96 mV); continuous shunt + bus: **ADC_CONFIG 0xB480** (MODE Bh, VBUSCT = VSHCT = 2h = 150 µs, no temperature, AVG = 1; the reset value runs ~1 ms conversions with temperature and would break the §8.1 timing); use CNVRF to tell which conversion follows an event.  **Write only SOVL = 0x76C0 (38 A) and BOVL = 0x17C0 (19.0 V)**; leave SUVL, BUVL, TEMP_LIMIT and PWR_LIMIT at their reset values (every limit drives ALERT, which is the weapon break).  DIAG_ALRT: ALATCH = 1, CNVR = 0, APOL = 0.  Low-pack warning and switch-open detection (§8.1 row 0) are firmware |
| BQ76907 (from the compute board) | after every POR: Vcell Mode = 4 (CONFIG_UPDATE); cell OV/UV thresholds on ALERT; allow SLEEP; balancing never enabled; I²C address 0x08 (7-bit), CRC off (BQ76907RGRR) |
| Motor NTC | R_ntc = R_measured − 2.2 kΩ (series protection resistor) |
| USART1 | 2 Mbaud; USART1 clocked from PCLK2 = 170 MHz (BRR = 85, exact; HSI16-derived via the PLL) |

### 8.1 Fault policy (thresholds are starting values, tuned in §9)

**Where it runs.**  Interrupts only record: the TIM1 break, the comparator EXTIs (use their
latched flags to tell which source tripped; TIM1 has one break flag for all sources) and the
nFAULT EXTIs store flags, the W_nFAULT level and a timestamp, plus the time since the weapon's
first applied vector after its last restart.  They never block and never touch SPI.  The **SPI
owner task** classifies ~0.5 ms later, after the first INA239 conversion that started after the
event, because the bus evidence of a contact bounce does not exist yet at the moment of the
break.  It reads and clears DIAG_ALRT first (the INA239 ALERT is wired onto W_nFAULT and latched,
ALATCH = 1), so any remaining W_nFAULT low time is U2's own.

**Latch word.**  The weapon, left and right latches (with reason), the holds that need an operator
clear, event counters and a cumulative uptime (ms, updated every ~10 ms: the timebase for rate
limits that span a reset) live in the backup registers (TAMP_BKPxR, magic value + CRC).  VBAT is
on +3V3, so they survive NRST/IWDG/BOR/lockup resets and are lost only when +3V3 collapses.
RTCAPBEN + DBP to write; never change RTCSEL (it resets the backup domain).  A valid word is
always honoured.  An invalid word means a fresh power-up if RCC_CSR BORRSTF is set, otherwise
"all latched".  A power cycle clears the board's latches (a power cycle is itself an operator action; the weapon's
first-start checks, rows 4 and 5, re-detect a real short); the compute board shows latches to the
operator (§3.5).

**Weapon events** (evaluate in order, first match wins; every row is counted and reported):

| # | Evidence | Class → action |
|---|---|---|
| 0 | **Continuous monitor, not tied to a break:** INA239 \|I\| < ~30 mA on every reading for ≥ ~100 ms with VBUS > ~8 V.  With the switch closed the board's own ~100 mA idle draw always flows through RS4; a contact bounce (≤ a few ms) never lasts 100 ms.  Paused (and the 100 ms restarted) while a driven **drive** motor's electrical-power estimate is negative or the weapon is commanded to brake (a drive back-driven by a shove, or braking; not the weapon merely regenerating under a motoring command, which with the pack lead pulled under throttle would keep the robot drivable on drum energy); any protective coast ends the pause | **Switch open** (switched off, or the pack lead pulled) → weapon coast, drives off (DRV_OFF high); hold until the operator clears it or a fresh power-up, whatever VBUS does (a coasting drum keeps the bus and the logic up for seconds).  Its own flag, not a weapon latch, and not persisted: an end-of-match switch-off must not need a clear |
| 1 | DIAG_ALRT BOVL (19 V), or the 18.5 V firmware coast (§8 weapon safety) | **Over-voltage** (regen into a full pack, or the pack lost during a brake) → weapon coast, drives to zero torque (this ends any row 0 pause).  Restart only once pack current is back and VBUS < 18 V, with the regen limit halved; if the current does not come back, row 0 holds.  More than ~3 within 10 s → latch the weapon (bounds the energy into D1) |
| 2 | **Bus event:** the post-event INA239 VBUS < ~10 V, or VBAT_SNS falling faster than ~5 V/ms around the event (a loaded contact bounce ≥ ~7 V/ms; a 0→20 A load step ≤ ~2.5 V/ms) | **Supply** (switch/connector bounce) → DRV_OFF high too; restart everything once VBUS has been steady ≥ 20 ms (supply budget below); never latches |
| 3 | DIAG_ALRT SOVL (38 A) | **Overload** → fold back the shared power budget (never below the drives' traction limit) and restart, ramping back over ~0.5 s; never latches |
| 4 | Comparator trip ≤ ~200 µs after the first applied vector of a restart, on **two consecutive** restarts | **Short** (a hard short re-trips within one PWM period; one fast re-trip can be a badly synchronised catch) → latch the weapon |
| 5 | Phase-pair resistance check failed.  Before spinning up a stopped drum (first start after arming, and every restart from standstill), apply a brief DC current pulse to each phase pair; R below ~half the value stored at bring-up with the drum fitted (§9 step 6) | **Short at standstill** (e.g. a pinched motor lead: with the drum stopped the current loop regulates a phase-to-phase short as load and the comparators never trip) → latch the weapon |
| 6 | Any other comparator trip | **Trip** (impact desync, over-current) → catch-spin restart after ~50–100 ms; more than ~5 within 1 s → weapon off ~1 s, then restart; never latches |
| 7 | W_nFAULT releases in < t_split (~3 ms; §9 step 4: between U2's ~1 ms wake/UVLO recovery and its fixed 4 ms VDS-OCP retry) | **U2 undervoltage** (usually a bounce too light to show on the bus) → weapon restart, counted in the supply budget; never latches |
| 8 | W_nFAULT releases at t_RETRY (~4 ms) | **VDS OCP** (phase-to-ground or shoot-through; a phase-to-ground short bypasses the shunts, so only VDS sees it) → latch the weapon |
| 9 | W_nFAULT low > ~10 ms | TH1 > ~90 °C → **U2 over-temperature**: as row 10.  Otherwise **gate-drive fault** (latched inside U2) → latch the weapon; clearing it also needs a W_EN reset pulse (8–40 µs) |
| 10 | Stall (at the current limit with no speed rise for > 0.5 s) or TH1 > ~100 °C (polled) | Coast ~1 s (or until TH1 < ~80 °C), then restart; never latches (a drum jammed by an opponent retries) |
| 11 | §7.16 strap boot test failed | Latch the weapon |
| 12 | Anything else | **Unknown** → one restart as row 6; a second unknown within ~10 s → latch the weapon |

**Every weapon restart** begins with a catch-spin (pick up the coasting drum's speed and angle) and then runs three-phase FOC, never six-step: six-step leaves a phase floating and hides a phase short from rows 4 and 5.

**Supply budget:** supply-class events (weapon rows 2 and 7, drive supply events, brown-out
resets; one count per event) are counted and reported.  More than ~5 within 1 s → everything off
~1 s, then retry.  A chattering connector never latches; the counts tell the crew to fix it.

**Drive events** (R_nFAULT/L_nFAULT, the ~100 Hz register check incl. NPOR; first match wins).
An nFAULT while the DRV_OFF pin is high, inside a "drives resume", or on a firmware-coasted chip
is expected, not an event (the DRVOFF pin may pull nFAULT low, SLVSH07 §8.4.2).  **On any event
from a released chip, first coast it over SPI:** OVP, CP-UV and OTSD self-clear, and a chip that
recovers with INH idling high (MOE = 0, e.g. the TIM8 break on L_nFAULT) brakes on all three high
sides.

| # | Evidence | Action |
|---|---|---|
| 1 | Both DRV8316s at once; or a bus event (weapon row 2), or a DRV8316 OVP with an INA239 BOVL, within ~1 ms | **Supply** → DRV_OFF pin high; "drives resume" after VBUS is steady ≥ 20 ms (supply budget) |
| 2 | One chip answering: OCP, CP-UV, register mismatch, NPOR = 0 | Per-drive coast → fault recovery → rewrite (ends coasted) → "drives resume"; > ~3 in 1 s → **latch that drive** |
| 3 | One chip not answering (CTRL2 reads 0x00; bit 6 reads 1 on a live chip) with its nFAULT low **and** all its CSAs < ~0.3 V (powered, they idle at AVDD/2) | **Unpowered** (R302/R402 open) → latch that drive, ignore its nFAULT; the other drive continues |
| 4 | One chip silent or garbled otherwise, on ≥ 3 consecutive polls while the other devices answer (DRV8316 read-back has no parity) | **Powered but deaf** (open/stuck nCS; its pull-up deselects it and it follows its timer unverified; only the shared pin can Hi-Z it) → DRV_OFF pin high, **latch both drives**, report; weapon continues |
| 5 | OTW (polled) / OTSD | Derate on OTW; coast until cooled on OTSD; not a latch |
| 6 | Alignment not clean: (a) own encoder still while the other follows both steps on two consecutive alignments → row 7; (b) too little own motion → retry at higher current, then sensorless; (c) any other disturbance → repeat ≤ ~5 times, then sensorless | Report; not counted |
| 6a | Alignment sign wrong on two consecutive clean alignments | **Latch that drive** (phase or encoder wiring swapped) |
| 7 | Row 6 (a): left/right crossed (sensor cables or motor bundles) | **Latch both drives** until an operator clear and a clean re-alignment (latch word) |

A **latched drive** stays coasted across MCU resets (boot releases only unlatched drives); the
register check rewrites it on a mismatch.  Its timer sits at MOE = 0 with OISx = 1 **and
OSSI = 1**, so INH idles high: a chip that resets into 6x mode is then Hi-Z (INL = INH = 1),
whereas floating INH pins read low through the pull-downs and turn a 6x chip's low sides on.

**One event, one count:** a bus event matching weapon row 2 and drive row 1 counts once; a
drive row 2 event while a supply restart is pending is left to that restart; when weapon row 1 defers to
row 0, so do the drives.

**Per-drive coast** (the only per-chip Hi-Z; INL is tied high and the DRVOFF pin is shared):
CTRL1 0x0603 → CTRL4 **0x0C90** (bit 7 DRV_OFF, "Hi-Z FETs", Table 8-21) → CTRL1 0x0606.  The
register check expects CTRL4 0x90 coasted, 0x10 released.  Leave it only through "drives resume".
The rewrite writes CTRL4 before CTRL2 because TI forbids a PWM_MODE change while the FETs operate.
Never write CTRL2 bit 6 as 0.  Bench-verify (§9 step 2) Hi-Z at speed, the nFAULT behaviour, and
normal drive after the Release.

**Drives resume** — used every time the DRV_OFF pin goes low and to un-coast a chip.  A chip
leaves Hi-Z only when its timer already drives the motor's back-EMF voltage; never through
MOE = 0, which in 3x mode is a high-side brake (12–31 A at top speed vs the 10–22 A OCP).
1. Read IC_STAT and registers of each unlatched chip to be resumed; rewrite a silently reset one
   (a VM UVLO at 4.1–4.3 V gives no nFAULT and comes back in 6x mode); make sure each is coasted.
   Running drives are left alone.
2. Lower the pin.  Preset: encoder angle valid → V_q = ω·λ, V_d = 0 (λ from §9 step 5, PWM and
   MT6701 latency compensated); encoder counting but angle unknown → next Z with the stored Z
   offset, if stored and trusted; encoder not counting → 0 (align after step 4); no usable
   encoder → stay coasted for the measured coast-down time (§9 step 6), then 0.  Set TIM8_AF1
   BKINE = 0 (a coasted chip may hold L_nFAULT low; BKE stays 1 for the CLL break; BDTR LOCK = 0),
   clear the break flag, set MOE, run FOC with the preset at zero current demand.
3. Release: CTRL1 0x0603 → CTRL4 **0x0D10** → CTRL2 0x097D (CLR_FLT) → CTRL1 0x0606.
4. nFAULT high within ~5 ms → BKINE = 1 (TIM20 has no break pin).  Otherwise re-coast
   (0x0603 → 0x0C90 → 0x097D → 0x0606), MOE = 0, BKINE = 1: a **failed resume**.  With an
   encoder-derived preset (a cut ABZ cable reads as standstill), mark the encoder suspect and retry
   through the no-encoder branch; no-encoder retries repeat every ~0.5 s, reported, never latched
   (each costs one self-limited OCP trip).  Failed resumes never count toward rows 1–2 or the
   supply budget.  If §9's top-speed resume test trips OCP, fix it then (resume speed cap, or
   OCP_LVL 24 A: coast 0x0D94 / release 0x0C14).

**SPI health:** every DIAG_ALRT read feeds the weapon classifier (it clears SOVL/BOVL with
ALATCH = 1); the poll compares only configuration bits.  Each poll reads the INA239 DEVICE_ID
(DIEID bits 15:4 = 239h; the low nibble is the revision) and reads back CONFIG, ADC_CONFIG, SHUNT_CAL, SOVL, BOVL and DIAG_ALRT settings (a reset
INA239 silently loses SOVL/BOVL: rewrite).  Firmware computes each DRV8316 parity bit (even
parity over the 16-bit word).  Two or three devices failing in one poll → **SPI3 fault**: DRV_OFF
pin high, weapon coast, report, retry every ~100 ms.  The INA239 alone failing (≥ 3 consecutive
polls — a mismatch one rewrite fixes is only reported) →
weapon off until an operator clear (latch word; a still-failing INA239 re-enters at once); the
drives continue on VBAT_SNS.

**MCU resets** (counted in the latch word): latches set before the reset stay set.  An event
still unclassified when the reset hit counts as unknown (row 12).  More than ~3 IWDG, lockup or
HardFault resets within ~10 s latch the weapon (the drives may still run).  A brown-out reset
counts in the supply budget.

**Clearing** needs an operator action forwarded by the compute board: a "clear faults" frame
carrying the operator input, never sent automatically.  For the weapon, clearing also needs a
disarm, a new ARM edge and the weapon throttle at zero, and after a gate-drive fault a W_EN
reset pulse.  **Throttle-zero interlock:** after any arm, re-arm, reset, link recovery or latch
clear, the weapon command must be seen at zero before the weapon may spin up.

## 9. Bring-up checklist

Steps 0–4 are hardware and first firmware; steps 5–6 need motors.  Several later steps store a
calibration that §8 needs (marked **store**).

0. **After assembly (unpowered).**
   * Stake C1, L1 and J2/J3 with adhesive.
   * Check J1 pin 1 against the compute-board socket (mirror image).
   * Fit or leave the DNP set as intended (C110–C112, C114–C116; the §7.15 cell-monitor option).
   * Inspect the bottom side (it faces the compute board); weigh the board.
   * **R302 / R402** (a short is invisible in operation, §7.16): measure each with a 4-wire
     milliohm meter, or force 1 A from a floating current-limited supply between TP10 (VBAT) and
     an L_VM (R_VM) capacitor pad.  R302 is the only DC path; read the voltage on the resistor's
     own two pads, not through the forcing probes.  Expect 0.10 V (100 mΩ).

1. **First power, no motors.**  Floating bench supply on the battery holes, 12 V.
   * Current limit 1.5 A for the first closure (the soft-start draws ~0.8 A for ~8–13 ms; a lower
     limit makes U13 hiccup; keep ≥ 1.5 A whenever the compute board and its hold-up cap are
     attached), then 0.2 A.  Check 5.0 V, 3.3 V, the power LED, current < 60 mA.
   * **Reverse polarity** as a *step* (switch the reversed, current-limited supply on): no
     current beyond the input-capacitor spike.
   * **UVLO sweep:** sweep the supply down.  The 5 V rail drops out near 9.2 V and returns near
     10.4 V; the switch FETs open near 9 V.
   * **Soft-start:** switch a stiff 16.8 V source on and scope VBAT and a DRV8316 VM pin: a clean
     ~8–13 ms ramp.

2. **MCU, drivers, monitors (bench supply, no motors or sensors).**
   * **MCU:** SWD flash; read the STM32 device ID/UID/revision (§7.12; reject rev Z); program the
     BOR option byte (level 4).
   * **U2 strap pins** against AGND (§7.16): MODE ~1.2 V, IDRIVE ~1.1 V, VDS ~0.5 V, GAIN ~2.0 V
     (open).  An open IDRIVE/VDS strap reads ~1.65 V, an open MODE strap ~2.0 V.
   * **DRV8316, U3 then U4:** write the §8 sequence and read it back: BUCK_UV clear and NPOR = 1
     after CLR_FLT, AVDD 3.1–3.47 V.  Run "drives resume" (§8.1; with no motors it only releases,
     with no wait) and check that L_nFAULT/R_nFAULT go high with the DRV_OFF pin low (a coasted
     chip, or the pin high, may hold nFAULT low, SLVSH07 §8.4.2).
   * **Bench check (§8.1, informational):** note whether nFAULT stays low after the pin is lowered
     while the chip is still coasted (the Release always ends with CLR_FLT).
   * **INA239:** DEVICE_ID, bus voltage and current against the bench supply.
   * **Sensor VS:** short each sensor connector's VS to GND.  +3V3 and nSLEEP must stay up
     (scope).
   * **Cells:** with a pack, read the four cell voltages from the compute board over I²C and
     compare them with a meter at the balance plug.

3. **Safety paths.**  Scope TP6 W_ARM, TP7 W_EN, TP8 DRV_OFF, TP9 W_nFAULT; read W_ARM_S from the
   heartbeat.
   * **ARM:** W_ARM rises above ~2.2 V within ~15 ms of W_ARM_CLK toggling at 500 Hz (sim 12 ms).
     A single edge does not arm.
   * **Disarm:** holding W_ARM_CLK high or low, or unplugging the header, drops W_ARM_S within
     ~30–200 ms (sim 52–164 ms; repeat with the board warm).  Halting the compute board's main loop
     (debugger) stops the toggling and W_ARM_S falls.
   * The compute board's timed boot self-test passes.
   * With W_ARM low and TIM1 running, the weapon phases are Hi-Z.
   * An MCU reset with ARM held high does not restart the weapon (a new ARM edge is needed).
   * **Failsafe:** transmitter off → the weapon disarms and the drives stop within ~0.5 s + the
     command timeout.  Stopping command frames alone stops everything within the timeout.
   * The INA239 SOVL and BOVL trip the TIM1 break (inject with a temporarily lowered limit).
   * **Armed soak:** 10 minutes armed with the transmitter and the robot radio on, drum idle.
     Expect **zero** "W_ARM_S fell" events.

4. **Full voltage and the weapon fast trip.**  Raise the supply to 16.8 V.
   * **Store:** with the compute board attached (RS4 carries its load too), record the minimum
     idle pack current, which must sit well above row 0's 30 mA threshold.  Expect ~95–113 mA.
   * **Charge pumps:** U2 VCP ≈ VM + 11 V; DRV8316 CP.
   * **Weapon fast trip** (on a pack, not the bench supply): lock the motor, raise the current
     limit past the comparator threshold, and scope the trip (CSA edge → bridge Hi-Z, ≤ ~1 µs).
     Then run at the 20 A limit and confirm no false trips.
   * **Store t_split** (§8.1 rows 7/8): scope W_nFAULT after a W_EN wake (expect ~1 ms low).  Set
     t_split between that and the DRV8323's 4 ms (typ) VDS-OCP retry, ~3 ms.  Log the W_nFAULT low
     time of any VDS OCP seen later to confirm t_RETRY.

5. **Drives, one motor at a time.**
   * **Program each MT6701 off-board first:** ABZ mode, 1024 PPR, rotation direction, Z pulse
     width 1 LSB, power-up absolute ABZ output off.  Its EEPROM needs 4.5–5.5 V.
   * **Open-loop spin** at a 1 A limit: check encoder direction, pole pairs and the CSA offsets
     (L_SOC through OPAMP5 separately).
   * **Store CCR6:** sweep it at a fixed drive current and take the middle of the flat plateau of
     the measured current (the sampling instant has no pin).  Confirm sampling still holds at the
     duty cap.
   * **Delay compensation:** sweep the duty 0–10 % on a scope to check it on short pulses.
   * **Store the Z electrical offset:** repeat over several Z passes; spread < ~5°.
   * **Store the flux constant λ** for the §8.1 resume preset: closed-loop FOC at a few speeds,
     no load, λ ≈ (V_q − I·R)/ω.  Cross-check with 60 / (√3·2π·KV·pole pairs).
   * Then closed-loop FOC.  Measure the ISR cycle counts (§8 CPU budget).

6. **Full system** (4S pack, or a supply good for ≥ 25 A peaks).

   **Weapon, no drum:** 5 A limit.  Scope SHx and VDS at the FETs, and a DRV8316 VM pin (dV/dt
   well under 4 V/µs, §6.6).  Raise the limit in steps to 20 A.  Confirm the pole count (14 poles
   assumed).

   **Weapon, drum fitted:**
   * **Store the §8.1 row 5 threshold and reference:** the stopped-drum max \|W_Vx\| (the row 5
     threshold) and the three phase-pair ΔV/ΔI values.  Re-measure after any weapon motor or lead
     change.
   * **Measure the free coast-down time** after disarm (§7.6).
   * Spin the drum slowly and check its direction by eye.

   **Regen:** on a freshly charged pack, brake the drum at the chosen regen limit and reverse it,
   with the drives idle and then driving.  Log INA239 VBUS and current.
   * VBUS peak < 18.3 V (below the 18.5 V coast).
   * Pack current ≥ ~−10 A, weapon and drives combined (this sets the D1 clamp current if the
     pack ever disconnects mid-brake, §7.4).
   * No switch-open and no INA239-failure report.
   * Otherwise lower the regen limit.

   **Contact bounce:** with the drum at speed, interrupt the pack + lead for ~0.3 ms and ~1 ms (a
   MOSFET in the lead).  Scope a DRV8316 VM pin: < 4 V/µs (sim ≤ ~2.3 V/µs at 0 °C, §7.2).
   Everything restarts and nothing latches.

   **Switch open:** open the power switch with the drum spinning under throttle and both wheels
   driving.
   * The weapon coasts and the drives stop within ~0.1 s.
   * The heartbeat reports "switch open" (not "INA239 failed").
   * Log the largest \|I\| reading while open with the drives switching.  It must stay well under
     the 30 mA §8.1 row 0 threshold.

   **Weapon faults:**
   * A wire across two weapon phase leads with the drum stopped → the restart resistance check
     refuses to start and latches (§8.1 row 5).
   * Jam the drum at the current limit → the stall cut-out coasts and retries, no latch (§8.1
     row 10).
   * Reconnect the radio with the weapon stick up → no spin-up until the stick returns to zero.

   **Drives:**
   * **Start angle:** power-cycle and MCU-reset with the rotor at a marked position, including
     ~180° from the last aligned position → the aligned start angle is correct.
   * Push against a wall for 5 s → no fault.
   * **Sensor unplug:** unplug a sensor at standstill with torque commanded → the heartbeat's
     no-edges flag.  Unplug it while spinning → that drive goes sensorless and reports.
   * **Link recovery:** let the command link time out and recover → both drives resume with no
     braked wheel.  Repeat at top speed: no current step, no OCP (the §8.1 back-EMF preset).
   * **Store the safe-resume speed** (§8.1 no-encoder branch): with the encoder unplugged, find the
     wheel speed below which a resume without a valid angle is safe (expect ~0.5 m/s), and the
     coast-down time to reach it.
   * **Per-drive coast** of a live chip at speed (CTRL4 0x0C90): its phases go Hi-Z, note its
     nFAULT behaviour, and the other drive keeps running.  After the Release (0x0D10) it drives
     normally.

   **Wiring checks.**  Run these once at bring-up:
   * swap two drive phase wires → the alignment sign check latches that drive (it must not run
     backwards);
   * swap the J2/J3 sensor cables, and separately the left/right motor bundles → "left/right
     crossed", with both drives latched until cleared.

   **After every pit repair that touches a motor lead or sensor cable:**
   * after drive rewiring, command a short forward move and check it by eye (or with the compute
     board's IMU): crossed bundles plus "fixed" sensor cables would drive backwards;
   * after weapon rewiring, spin the drum slowly and check its direction by eye (a swapped weapon
     phase pair reverses it silently).
