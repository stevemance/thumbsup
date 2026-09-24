# ThumbsUp motor board — design (rev A, 2026-09-23)

The power half of the two-board stack: battery in, three motor channels out, 5 V down to the
compute board through one header.  This is the brushless variant: **sensorless weapon + two
FOC drive motors with sensors**, 4S.  Everything here is meant to be drawn in KiCad by hand
from [`design/motor_board.py`](design/motor_board.py) (the netlist) and built by JLCPCB.

| File | What it is |
|---|---|
| this file | architecture, circuit blocks and their values, safety, layout rules, bring-up |
| [`design/motor_board.py`](design/motor_board.py) | **the netlist**: every part, pin and net; run it to regenerate the outputs below and re-check |
| [`design/nets.md`](design/nets.md), [`design/netlist.csv`](design/netlist.csv) | generated connection lists (draw from these) |
| [`design/mcu_pinmap.md`](design/mcu_pinmap.md) | STM32G474RET6 pin plan, every alternate function verified against ST's pin database |
| [`design/bom.csv`](design/bom.csv), [`BOM.md`](BOM.md) | JLC-format BOM and the part notes (stock, alternates, what to confirm) |
| [`design/calcs.py`](design/calcs.py) → [`design/calcs.md`](design/calcs.md) | every sizing number in section 4 |
| [`spice/`](spice/) | ngspice checks: battery hot-plug, weapon bridge switching, weapon spin-up |
| [`datasheets/`](datasheets/) | PDFs of every non-generic part, indexed in its README |
| [`ref/`](ref/) | ST pin database for the MCU (BSD-3), datasheet references |

## 1. Requirements this board meets

| Area | Requirement | How |
|---|---|---|
| Battery | 4S LiPo (16.8 V full, 12 V sagged); survive plug-in; survive a reversed pack | Low-side reverse-polarity FET, TVS + 470 µF polymer (SPICE: 1.7 V/µs, no overshoot) |
| Battery monitoring | Pack voltage, current, power, energy and charge (mAh) used; **per-cell voltages**; pack over-current trip; deep-discharge cutoff | INA229 on a 1 mΩ high-side shunt (20-bit, hardware energy/charge accumulators); BQ76907 on the balance lead (cell voltages; its balancing is not used); INA229 ALERT kills the weapon PWM; buck UVLO turns the logic off below ~9.2 V |
| Weapon | Sensorless BLDC, Repeat 2822 Mk3 1800 KV class, 20 A current limit, ~280 W bursts | DRV8323RS + 6 × 40 V 1.4 mΩ FETs + 3 × 2 mΩ shunts |
| Drive | 2 × FOC BLDC with Hall or magnetic-encoder feedback, ~1 A running / 4 A limit, full telemetry, odometry | 2 × DRV8316R (integrated FETs + current sense) + sensor connectors |
| Telemetry | Per-phase currents (9), bus voltage, weapon phase voltages, weapon FET temp, motor temps, speed/position | 16 ADC channels + 2 encoder timers on one MCU |
| Compute link | 5 V / ≤ 0.45 A to the compute board, UART, reset + SWD programming, weapon ARM | 20-pin 1.27 mm header (5 spare) |
| Safety | Weapon cannot run without the compute board's ARM; everything off in reset | Hardware AND gate on DRV8323 ENABLE; pulled-down enables; DRVOFF pulled up |
| Build | JLCPCB assembly, single-sided | All parts on LCSC; 113 placed components (vs ~310 for the three-AM32 board) |

Not on this board (compute board): Pico/MCU for control, IMU + high-g accel, logging flash,
Bluetooth, status LEDs, the physical ARM link.  All power functions (pack input, protection, monitoring, regulation) are here.

## 2. Architecture

```
  BAT+ ── RS4 1mΩ ─┬── D1 TVS ── C1 470u ──┬──────────────┬──────────────┬─────────┐
  BAT− ── Q7 RPP   │  U7 INA229 (V,I,P,    │              │              │         │
          → GND    │   energy, charge)     │              │              │         │
                   │               U2 DRV8323RS      U3 DRV8316R    U4 DRV8316R    │
                   │               gate drv + 3 CSA  drive L        drive R        │
                   │               + 5 V buck ───┐   (FETs+CSA      (FETs+CSA      │
                   │               Q1..Q6, RS1..3│    inside)        inside)       │
                   │                  │          │      │               │          │
                   │              weapon A/B/C   │   drive L A/B/C  drive R A/B/C  │
                   │                             │   J2 sensor      J3 sensor      │
                   │                     +5V ────┴── U5 LDO ── +3V3 ───────────────┘
                   │                      │                  │
                   │                      │          U1 STM32G474RET6
                   │                      │   TIM1 → U2   TIM8 → U3   TIM20 → U4
                   │                      │   SPI3 → U2,U3,U4   TIM3/TIM2 ← J2/J3
                   │                      │   16 × ADC (9 currents, VBAT, 3 weapon phase V, temps)
                   │                      │
                   └──────── J1 header to the compute board: +5V, GND, UART, W_ARM, NRST, SWD, VBAT_SNS
```

Design choices (the "why"):

* **One MCU for all three motors.** The G474 has three advanced timers (TIM1/TIM8/TIM20), five
  ADCs and FOC-grade math hardware, and it is what ST's motor SDK, SimpleFOC and moteus-class
  firmware already run on.  One MCU, one firmware image, one programming port.
* **Integrated drive stages.** The DRV8316R contains the six FETs *and* three current-sense
  amplifiers (no shunts).  Each drive channel is one IC and ~9 passives.
* **3x PWM mode everywhere.** The drivers generate the complementary signals and dead time; the
  MCU needs 3 PWM pins per motor.  That is what makes the pin budget fit on LQFP-64.
* **The weapon driver also makes the 5 V rail.** The DRV8323R's integrated 0.6 A buck powers the
  compute board and the 3.3 V LDO, so there is no separate regulator IC.  Its buck has its own
  enable (nSHDN, left floating = on), so the weapon interlock does not affect it.
* **No pack reverse-polarity FET.** Battery connection is by soldered pads to a pigtail with an
  XT30; a reversed pack destroys the board (TVS, driver body diodes).  This was a deliberate
  mass/part-count call — see §7.

## 3. Circuit blocks

Reference designators match `design/motor_board.py`; pin numbers are the datasheet's.

### 3.1 Power entry, protection and battery monitoring

Path: **BAT+ pad → RS4 (1 mΩ) → VBAT** and **BAT− pad → Q7 → GND**.

| Part | Value | Notes |
|---|---|---|
| J_BAT+ / J_BAT− | 4 × 6 mm pads | 16–18 AWG pigtail to an XT30 on the lead (XT30: 15 A cont / 30 A burst; pack peak is 22 A for 0.5 s).  **The external power switch is soldered into the + wire** (see below) |
| Q7 | HYG015N04LS1C2 (same as the weapon FETs) | **Reverse-polarity protection** in the ground return: drain = BAT−, source = GND.  At plug-in its body diode conducts, then R1 (100 k from VBAT) turns the channel on (1.4 mΩ, ~1 W at 22 A vs ~11 W for a diode).  A reversed pack makes Vgs negative: off, nothing on the board is powered.  D4 12 V zener clamps Vgs (TVS events reach 32 V; Vgs max 20 V) |
| RS4, U7 | 1 mΩ 2512 + INA229 | **Pack monitor.** High-side shunt, Kelvin to U7 through R2/R3 10 Ω with C2 100 nF (TI §8.1.4 short-circuit dV/dt robustness).  VBUS = VBAT.  ±41 A range at 78 µA/LSB; hardware **energy (J) and charge (C) accumulators** = mAh used per match, plus power and die temperature.  SPI on the shared bus (CS = PA11).  ALERT (open drain) is wired onto W_nFAULT, so a programmed pack over-current limit trips TIM1's break input and cuts the weapon PWM in hardware |
| D1 | SMBJ20A | After the RPP FET (a reversed pack must not forward-bias it).  Standoff 20 V > 16.8 V; clamps ~32 V, below the DRV8316's 40 V absolute max |
| C1 | 470 µF 25 V polymer (EEHZK1E471P) | **Mandatory**: without it the DRV8316 VM ramp at plug-in is 4.4–5.5 V/µs (> 4 V/µs limit). With it, 1.7–1.8 V/µs and no overshoot (`spice/sim_hotplug.py`) |
| R4 / R5 | 390 k / 51 k on U2 nSHDN | **Deep-discharge cutoff**: the 5 V buck (and so the MCU and compute board) switches off below ~9.2 V and back on above ~10.4 V (worst-case spread 7.4–10.3 V off, from the LMR16006's SHDN threshold tolerance).  Worst-case off threshold still clears the 13.7 V minimum bus during a 25 A weapon spin-up.  The real low-battery handling is firmware (cell-average warnings from the INA229); this is the backstop for a robot left switched on |
| D3 / R62 | red LED, 1 k from +5V | **Power LED** independent of firmware (SPARC visible-power requirement) |

**Cell monitoring (U8 BQ76907 + J4 balance lead).**  The pack's 4S balance lead
(JST-XH 5-pin) plugs into J4.  Each tap goes through a 100 Ω resistor (R6–R10) with 100 nF across
each cell and from VC0 to VSS (C4–C8): a 10 µs filter, well inside TI's 10–1000 Ω / RC ≤ 200 µs
limits (it would also set a ~14 mA balancing current, which is not used — §4a).  4S wiring per the BQ76907 datasheet Table 7-1: cells on VC7–VC6, VC5–VC4, VC3–VC2 and
VC1–VC0, with VC6=VC5, VC4=VC3 and VC2=VC1 shorted on the board.  U8 is powered from the top
balance tap through R11 10 Ω / C9 1 µF (TI's application circuit), so it runs whenever the balance
lead is plugged in (~30–175 µA normal, µA in sleep/shutdown); its VSS is board GND.  Unused
functions are terminated per TI Table 8-3: SRP/SRN and TS to VSS, CHG/DSG/REGOUT open, REGSRC to
BAT.  The coulomb counter and protection FET drivers are not used: the INA229 measures current
and this board must never disconnect the motors on its own.

The **compute board is the I²C host** (header pins 15–17: SDA, SCL, ALERT; pull-ups on the
compute board): every I/O of the motor MCU is already in use, and cell data is slow.  Firmware
there reads the cells before a match (weak or imbalanced cell) and logs them during it.
The BQ76907 handles 2–7 cells, so the same part and footprint serve a 6S variant.

**External power switch (the main power disconnect).**  Off the board, in series with the pack's
+ lead: pack XT30 → screw switch on the chassis wall → BAT+ pad.  FingerTech Mini Power Switch
(40 A continuous / 100 A burst with 16 AWG, 2.15 g) or Repeat Screw Switch (1.5 g; confirm its
current rating).  Switching the + side is sufficient: with it open nothing on the board is
powered except U8, which runs from the balance lead at µA and has no path into VBAT.  Closing the
switch is a hot-plug event, covered by `spice/sim_hotplug.py` (C1 keeps the DRV8316 ramp at
~1.7 V/µs even with contact bounce).  The power LED D3 shows the switch state.  If a detachable
switch is preferred later, two "switch loop" pads (BAT+ in, switched + out) can be added with no
BOM change.

Pack monitoring summary: pack voltage (INA229 VBUS, 20-bit; VBAT_SNS divider on the ADC and the
header), current, power, energy, charge (mAh), each cell's voltage, and 9 phase currents +
board/motor temperatures from the motor channels.

### 3.2 Weapon channel — U2 DRV8323RS + Q1–Q6

* **Bridge:** Q1/Q2 (A), Q3/Q4 (B), Q5/Q6 (C), HYG015N04LS1C2 (40 V, 1.4 mΩ @ 10 V, PDFN 5×6;
  leads 1–3 = S, 4 = G, tab = D).  High-side drains on VBAT; U2 VDRAIN (pin 7) Kelvin to the drains.
* **Shunts:** RS1–RS3 2 mΩ 2512 low-side.  SPx to the FET-source side (net W_SLx), SNx via a
  net-tie NT1–NT3 to the shunt's ground pad.  CSA gain 20 V/V → 40 mV/A, ±35 A linear range,
  20 mA/LSB.
* **Gate drive:** direct from U2 (no gate resistors); set **IDRIVE ≈ 60 mA source / 120 mA sink**
  over SPI.  Faster settings overshoot (§5).
* **Charge pump:** C20 47 nF 50 V (CPH–CPL), C21 1 µF 25 V (VCP–VM).  DVDD C22 1 µF.  VREF pin 26 =
  +3V3 with C23 (the CSAs reference the same 3.3 V as the ADC, so readings are ratiometric).
* **Control:** INHA/B/C ← TIM1_CH1/2/3 (PA8/PA9/PA10); INLA/B/C ← TIM1_CH1N/2N/3N (PB13/14/15),
  i.e. timer-controlled per-phase Hi-Z for six-step/coast, all high for FOC.  nFAULT → PC13
  (TIM1_BKIN, hardware PWM kill) with R42 pull-up.  CAL tied low (calibrate over SPI).
* **Phase voltage sense:** R22–R27 68k/10k dividers → PA4/PA5/PB11.  Needed to catch a coasting
  drum (restart after a brown-out/reset) and for six-step BEMF.
* **FET temperature:** TH1 10 k NTC at the FETs with R43 → PB12.
* **Enable interlock:** U6 74LVC1G08: ENABLE = W_EN (PA12, R40 100 k pull-down) AND W_ARM (header,
  R41 100 k pull-down).  ENABLE low puts the DRV8323 to sleep: all six gates held low.
* **5 V buck (inside U2):** VIN pin 47 from VBAT (C27 2.2 µF 50 V); L1 22 µH (Isat ≥ 1.2 A);
  D2 B5819W catch diode; C28 100 nF CB–SW; R20 56 k / R21 10 k → 5.05 V; C29/C30 22 µF 25 V.

### 3.3 Drive channels — U3 (left), U4 (right) DRV8316R

Per channel (U3 values shown; U4 is identical with 4xx designators):

| Pin(s) | Connection |
|---|---|
| VM 9/10/11 | VBAT; C300/C301 100 nF 50 V at the pins + C302 10 µF 50 V |
| CP 8 / CPH 7 / CPL 6 | C303 1 µF 50 V CP–VM; C304 47 nF 50 V CPH–CPL |
| AVDD 25 | C305 1 µF |
| VREF/ILIM 37 | tied to the chip's own AVDD (pin 25), C306 100 nF.  VREF must stay ≤ AVDD (3.1–3.465 V), so it cannot come from the external 3.3 V LDO; firmware measures the zero-current SOx offset at start-up |
| SW_BK 5 / FB_BK 3 / GND_BK 4 | **buck unused but must be populated** (TI §9.2.1.1.5): R300 22 Ω SW→FB, C307 22 µF 6.3 V FB→GND; set BUCK_DIS over SPI |
| INHA/B/C 27/29/31 | TIM8_CH1/2/3 = PB6/PC7/PB9 (left); TIM20_CH1/2/3 = PB2/PC2/PC8 (right) |
| INLA/B/C 28/30/32 | tied to +3V3 (3x PWM mode: INL = phase enable; Hi-Z is done with DRVOFF) |
| DRVOFF 21 | shared DRV_OFF net (PC14), R50 10 k pull-**up**: both drive bridges are off until firmware drives it low |
| nSLEEP 23 | +3V3 (fault clear via SPI CLR_FLT).  Because nSLEEP and the nFAULT pull-up share the same rail, the chip only wakes once nFAULT is already pulled > 2.2 V, which avoids TI's test-mode entry at power-up |
| nFAULT 22 | pull-up R301 → PB7 (left, TIM8_BKIN) / PC15 (right); must be > 2.2 V at power-up or the part enters test mode |
| SOA/SOB/SOC 40/39/38 | ADC: left PC0/PC1/PC3, right PA6/PA7/PB1; gain 0.15 V/A → ±9.3 A range |
| OUTA/B/C | motor pads J_LA..J_LC / J_RA..J_RC (2 pins each on the IC) |

**Sensor connector J2/J3** (JST SH 6-pin): 1 VS, 2 GND, 3 S1, 4 S2, 5 S3, 6 motor NTC.
S1–S3 go to TIM3_CH1/2/3 (PC6/PB5/PB0, left) and TIM2_CH1/2/3 (PA15/PB3/PB10, right), so they
work with **Hall sensors (UVW, timer Hall interface)** or an **MT6701 in ABZ (encoder mode) or
UVW mode**.  VS is 3.3 V by default (solder jumper JP1/JP2 bridged 1–2); 2–3 selects 5 V for 5 V
Hall sensors, which must then be open-drain (use the MCU pull-ups) since not every assigned pin
is 5 V tolerant.  The MT6701 is configured once over its I²C pads on the sensor PCB.
Motor NTC: R52/R53 10 k pull-up → PF0/PF1.

### 3.4 MCU and logic

* U1 STM32G474RET6 (LQFP-64).  Full pin plan in [`design/mcu_pinmap.md`](design/mcu_pinmap.md).
* VDD × 4: C60–C63 100 nF + C64 4.7 µF.  VDDA/VREF+ (+3V3A) via R60 0 Ω (swap for a ferrite
  if ADC noise needs it) with C65 100 nF + C66 1 µF.  VBAT pin to +3V3.
* NRST C67 100 nF (internal pull-up).  BOOT0 (PB8) R61 10 k to GND.  No crystal: the HSI
  (±1 %) is fine for UART; add an 8 MHz crystal on PF0/PF1 only if CAN-FD is ever wanted
  (those pins then lose the motor-NTC inputs).
* SPI3 (PC10/11/12) shared by U2/U3/U4; chip selects PD2 (weapon), PC9 (L), PB4 (R); R51 pull-up
  on MISO (DRV8323 SDO is open drain).
* USART1 PC4 (TX) / PC5 (RX) to the compute board.
* PA11 = INA229 chip select (the only LED is the hardware power LED; status LEDs live on the compute board).
* VBAT_SNS: R63 68 k / R64 10 k / C68 100 nF → PA3, also on the header for the compute board.
* U5 AP2112K-3.3 from +5V: 3.3 V for the MCU, CSA references, sensors (~115 mA used of 600).

### 3.5 Header to the compute board — J1, 2 × 10, 1.27 mm (BOOMELE 1.27-2*10P, C59981)

| Pin | Signal | Pin | Signal |
|---|---|---|---|
| 1 | +5V out | 2 | +5V out |
| 3 | GND | 4 | GND |
| 5 | MB_TX (motor board → compute) | 6 | MB_RX |
| 7 | W_ARM (compute → weapon enable, active high) | 8 | NRST (compute can hold the motor MCU in reset) |
| 9 | SWDIO | 10 | SWCLK |
| 11 | VBAT_SNS (÷7.8, 3.3 V-safe up to 25.7 V) | 12 | GND |
| 13 | +5V out | 14 | GND |
| 15 | BMS_SDA (BQ76907 I²C data) | 16 | BMS_SCL |
| 17 | BMS_ALERT (open drain) | 18–19 | spare |
| 20 | GND | | |

The compute board needs the mating 1.27 mm 2 × 10 SMD female socket (pick it with that board;
LCSC lists BOOMELE 1.27 mm female headers in 2 × 5 … 2 × 50).
The compute board drives W_ARM only when its own WEAPON_EN **and** the physical ARM link are
present.  SWD on the header lets the compute board (e.g. a Pico running a debug-probe
firmware) flash the motor MCU in the robot; TP1–TP5 are the same signals as bare pads for the
bench.

## 4. Sizing summary (details in `design/calcs.md`)

| Item | Number |
|---|---|
| Weapon spin-up (2822 1800 KV, 20 A limit) | 25.6 k rpm, 54 m/s tip, 64 J, 0.52 s to 90 % |
| Pack current peak / bus sag | 22 A / 14.1 V (4S, 70 mΩ pack+lead) |
| Weapon FET loss at 20 A | 0.84 W conduction + ~1.1 W switching (60 mA IDRIVE) per switching FET — 0.5 s bursts |
| Drive channel loss | 0.14 W at 1 A rms, 1.3 W at 3 A rms (+33 °C JEDEC); ≤ 2.5–3 A continuous |
| Current sense | drive ±9.3 A @ 5.4 mA/LSB; weapon ±35 A @ 20 mA/LSB |
| Voltage sense | 68k/10k: 16.8 V → 2.15 V, 6.3 mV/LSB (also reads 6S) |
| 5 V budget | 600 mA buck; MCU side ~115 mA at 3.3 V → **~450 mA available to the compute board** |
| Pack monitor | ±41 A, 78 µA/LSB; shunt 0.48 W and RPP FET ~1 W at 22 A peak |
| Deep-discharge cutoff | logic off ~9.2 V / on ~10.4 V (spread 7.4–10.3 V off) |
| Odometry | MT6701 1024 PPR on the motor behind 28.5:1: 116 k counts per wheel rev; Halls: 342 counts |

## 4a. Cell balancing: not used

The BQ76907 can bleed-balance cells (~14 mA per cell, commanded by the host), but the robot is
only powered for the minutes around a fight, so balancing would never accomplish anything; the
external charger balances the pack.  Firmware never enables it.  It costs nothing to leave
available: the 100 Ω / 100 nF cell-input networks are needed as filters either way.  The cell
monitor is kept for pre-match checks (a damaged or imbalanced cell) and for logging cell sag
under load (the early sign of a failing pack).

## 4b. Telemetry rates

"Measured" is how often the hardware produces a new value; "reported" is the proposed stream on
the UART to the compute board (USART1 at 2 Mbaud ≈ 200 kB/s; a 64-byte fast frame at 1 kHz uses
~64 kB/s, leaving room for commands and a 10 Hz slow frame).

| Quantity | Source | Measured | Reported (proposed) |
|---|---|---|---|
| Phase currents, 3 per motor (9) | DRV8316/DRV8323 CSAs → ADC, sampled at the PWM centre | 24 kHz (every PWM cycle; CSA settles in 0.6–1 µs) | 1 kHz (per-motor Iq/Id or phase RMS) |
| Drive rotor angle / wheel position | Hall or MT6701 ABZ into TIM3/TIM2 (hardware counting) | continuous; read every FOC cycle (24 kHz) | 1 kHz (position counts, velocity) |
| Weapon speed (eRPM) | sensorless observer / BEMF | 24 kHz | 1 kHz |
| Weapon phase voltages | 68k/10k dividers → ADC | 24 kHz | on demand (used internally) |
| Bus voltage (fast) | VBAT_SNS divider → ADC | 24 kHz | 1 kHz |
| Pack voltage, current, power (precise) | INA229, 20-bit | 50 µs–4.1 ms per conversion; e.g. 280 µs shunt + 280 µs bus ≈ 1.8 kHz | 100 Hz–1 kHz |
| Pack energy (J) and charge (mAh) | INA229 hardware accumulators | integrated every conversion | 10 Hz |
| Cell voltages (4) | BQ76907 | every scan loop: 1.1–24 ms (with 4 cells, ~15 ms at full resolution) | 10 Hz (compute board reads it directly over I²C) |
| FET / motor temperatures (NTC) | ADC | any rate; thermal time constants are seconds | 10 Hz |
| Driver faults | nFAULT pins → timer break (weapon, drive L) / interrupt (drive R); SPI status | hardware: < 1 µs PWM shutdown; status regs polled ~100 Hz | event + 10 Hz |
| Pack over-current | INA229 ALERT → weapon timer break | one conversion (≥ 50 µs) | event |
| Cell over/under-voltage | BQ76907 ALERT → compute board | per scan loop | event |

## 5. SPICE results (`spice/`)

| Check | Result |
|---|---|
| Battery hot-plug (`sim_hotplug.py`) | As designed (surge through Q7's body diode and RS4): VM 16.2 V peak, 1.7–1.8 V/µs. **Without C1**: 4.4–5.5 V/µs (violates DRV8316's 4 V/µs) and up to 23.5 V overshoot with a stiff pack |
| Weapon bridge switching (`sim_weapon_bridge.py`) | At IDRIVE 400 mA the high-side VDS rings to 36–44 V and SHx undershoots past −7 V even with a 3 nH loop. At **60 mA** with a **3–6 nH** commutation loop: VDS ≤ 29 V (40 V part), SHx ≥ −4.6 V (−7 V limit). At 12 nH, SHx reaches −7.3 V: the loop must stay short. SPx peaks at +3.2 V for a few ns from the 2512 shunt's ~1 nH ESL (limit ±3 V for 200 ns), so a low-inductance wide-terminal shunt (2512 reverse-geometry / 1225) is worth fitting if one is in stock. An RC snubber across the FETs made no difference. The FET model is calibrated to the datasheet capacitances and gate charge but is not a vendor model: read the table as trends |
| Weapon spin-up (`sim_weapon_spinup.py`) | See §4; 15 A limit → 0.68 s, 25 A → 0.43 s, pack peak 27 A |

## 6. Layout rules (what matters, in order)

1. **Weapon commutation loop ≤ 6 nH, target 3 nH:** C25/C26 (10 µF) directly across each
   half-bridge's drain and shunt ground on the same layer, bridge → shunt → cap in the tightest
   possible loop, solid GND plane on layer 2 directly under it.  4-layer board.
2. **Kelvin sense:** SPx/SNx as a pair from the inner edges of each shunt pad (net-ties NT1–NT3);
   DRV8316 needs no shunts.  VDRAIN Kelvin to the high-side drains.
3. **DRV8316 thermal pads:** full via array to inner GND planes; each drive IC needs copper area
   (RθJA 25.7 °C/W is the JEDEC 4-layer figure).
4. **Hot-plug / power entry:** RS4, Q7 and C1 in the main current path with wide pours; U7 Kelvin traces from RS4's pad inner edges; C1 close to the battery pads *and* the bridges; the DRV8316 VM pins get their
   own 100 nF + 10 µF within 2 mm.
5. **Buck:** SW node tiny; L1/D2/C29 loop tight per the LMR16006 layout guide; FB divider at
   pin 1 away from L1.
6. **Analog:** CSA outputs and dividers routed away from phase nodes; ADC pins on the MCU side.
7. Balance connector J4 near the pack side; the cell-input resistors and caps at U8, the tap traces thin (signal only).  Sensor connectors near the drive ICs' board edge; motor pads sized for 20 AWG (drive) and
   16–18 AWG (weapon).

## 7. Decisions to confirm (please read)

1. **Reverse pack with the balance lead plugged in.**  Q7 protects the board from a reversed XT30
   only while the balance lead is unplugged: with it plugged, the cell-monitor inputs give the
   reversed pack a path (through the 100 Ω resistors) into the board's ground.  Both connectors are
   keyed, so this needs a mis-wired pigtail; plug the balance lead in last.
2. **Weapon FET package:** 5×6 HYG015N04LS1C2 (proven, in stock).  A 3.3×3.3 40 V ≤ 5 mΩ FET
   would save ~40 % of the bridge area.
3. **C1 stock:** EEHZK1E471P showed very low LCSC stock when checked.  Alternatives in BOM.md;
   it must stay a low-ESR polymer ≥ 220 µF (the hot-plug margin depends on its ESR damping).
4. **6S** is not supported (DRV8316 40 V abs max).  The 6S variant uses a DRV8323 + FETs on all
   three channels with the same MCU and header; the dividers already read 25.2 V.
5. **Drive motor** is still open (Repeat Mini sold out; 16 mm Hall gearmotors are the fallback).
   The board supports both Hall and encoder feedback without changes.

## 8. Firmware configuration the hardware assumes

| Device | Setting |
|---|---|
| DRV8323RS | PWM_MODE = 3x; IDRIVEP/N ≈ 60/120 mA (tune on the bench); CSA_GAIN = 20 V/V; VREF_DIV = 1 (bidirectional); OCP/VDS level ~0.45 V; buck on |
| DRV8316R ×2 | PWM_MODE = 3x; CSA_GAIN = 0.15 V/A; BUCK_DIS = 1; slew rate mid; OCP/ILIM per motor; clear faults with CLR_FLT |
| STM32G474 | TIM1/TIM8/TIM20 centre-aligned ~24 kHz, ADC injected conversions triggered at the PWM centre; TIM1 BKIN on PC13, TIM8 BKIN on PB7; DRV_OFF (PC14) low only when drives armed; W_EN (PA12) low except when the weapon is commanded |
| BQ76907 (from the compute board) | 4S cell configuration (VCELL_MODE) written at start-up; cell OV/UV alerts on ALERT; balancing never enabled; SHUTDOWN when stored |
| INA229 | SHUNT_CAL for 1 mΩ, ADCRANGE = 1 (±40.96 mV); continuous shunt+bus conversions; SOVL (shunt over-limit) ≈ 35 A with ALERT enabled so it trips the weapon break; read ENERGY/CHARGE for mAh used; BUVL for a low-pack alert |
| Boot order | 3.3 V up → configure drivers over SPI → release DRV_OFF → enable W_EN only after the compute board asserts W_ARM |

## 9. Bring-up checklist

1. Bench supply on the battery pads, 12 V current-limited to 0.2 A, **no motors**: check 5.0 V,
   3.3 V, the power LED, current < 60 mA.  Reverse the supply briefly (current-limited): nothing
   should draw current.  Sweep the supply down: the 5 V rail drops out near 9.2 V and returns near
   10.4 V.
2. SWD flash (TP pads or header), read all three drivers' status registers and the INA229 over SPI; check INA229 bus voltage and current against the bench supply.  With a pack: read all four cell voltages from the compute board over I²C and compare with a meter at the balance plug.
3. Raise to 16.8 V; check DRV8323 charge pump (VCP ≈ VM + 11 V) and DRV8316 CP.
4. One drive motor with sensor: open-loop spin at 1 A limit; verify Hall/encoder direction and
   the CSA offsets (±50 mA spec).
5. Weapon: motor without drum, 5 A limit, IDRIVE 60 mA; scope SHx and VDS at the FETs; raise
   the limit in steps to 20 A.  Then the drum.
