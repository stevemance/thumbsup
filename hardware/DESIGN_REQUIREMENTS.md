# ThumbsUp Control Board — Design Requirements

**Robot:** ThumbsUp, 1 lb (454 g) plastic antweight, 3D-printed drum spinner
**Board:** v1 custom PCB — Pico W + three on-board AM32 ESC cells + instrumentation + log flash
**Status (rev v1.2, 2026-09-04):** requirements + verified BOM + generated KiCad schematic (`kicad/`, built from `tools/sch/circuit.py`; KiCad ERC 0 errors, netlist proven equal to the SKiDL source) + **generated layout** (`kicad/thumbsup.kicad_pcb` from `tools/pcb/`, outline from the chassis 3MF, see [LAYOUT.md](LAYOUT.md)) + JLC outputs in `fab/`. Before ordering: same-day stock check on HX6288 / ADXL375 / 74AHCT1G125GW, and confirm XT30 polarity on a physical part. Review history: [REVIEW.md](REVIEW.md).
**AM32 firmware target (locked):** `AT32DEV_F421` (`HARDWARE_GROUP_AT_B` + `AT_045`)

Firmware GPIO in `firmware/include/config.h` is the *wired robot today*. The board remaps Pico pins; `config.h` must be updated to match [PINMAP.md](PINMAP.md) before first power-up.

| Variant | Role | Compute | Control |
|---|---|---|---|
| **v1 (this spec)** | Simple, heavily instrumented | Pico W only | Human, Bluetooth gamepad |
| **v2+** | Fully autonomous | Pico W + daughtercard | On-board policy; gamepad fallback |

v1 fights **and** records the dataset v2 will learn from.

---

## 1. Purpose

One board that:

1. Hosts a **castellated Pico W** (hand-soldered after JLC SMT).
2. Drives **three BLDC motors** (left drive, right drive, weapon) with **three on-board AM32 cells** (AT32F421 + FD6288Q + 6 MOSFETs each). No AliExpress ESC module, no H-bridge path on v1.
3. Instruments **pack, rails, each motor, motion, and operator commands**, and stores a match log in SPI flash.
4. Leaves an expansion header for a later autonomy card.
5. Meets SPARC-style safety: mechanical pack disconnect, failsafe-to-stop, hardware weapon enable, visible power LED.

---

## 2. Architecture

```
3S LiPo -- XT30 J1 (through the wall slot = SPARC disconnect) -- TVS/filter -- 1 mOhm shunt -- VBAT pour
                      |
        +-------------+-------------+-------------+
        |             |             |             |
     ESC_L         ESC_R         ESC_W         5V buck --(D3)--> Pico VSYS
     AM32          AM32          AM32          +3V3_A LDO --> IMU, INA226 x4
                                               +3V3_MCU LDO --> 3x AT32, flash
        |             |             |             |
        +----- DShot300 from Pico ----------------+
        +----- SWD per AT32 (first bootloader) ---+
                      |
              INA226 pack + 3x INA226 channel
              LSM6DS3TR-C + ADXL375
              W25Q128 log flash
              2x SK6812MINI-C + power LED
```

Each ESC cell is a copy of the same netlist, pin-locked to **AM32 `AT32DEV_F421`** so stock hex works after bootloader.

Default stuffing: all three cells populated. Drive ESCs: crawler settings (sine start, bidirectional). Weapon: unidirectional, 10 A firmware current limit for the F2822.

---

## 3. Goals and non-goals

### Goals

- One PCB in the chassis (Pico is a soldered module, not a second flying board).
- JLC assembles everything except the Pico W.
- **Instrumentation first.** USB dump after a match of commands, pack V/I, per-channel I/V, IMU, high-g, weapon eRPM, rail voltages.
- Smooth BLDC drive crawl-to-sprint via AM32 sine mode on a **3S**, **low-KV geared** motor (see AM32 crawler notes).
- Repair: Pico is replaceable; ESC cells are on the board (a dead FET cell is a board swap or rework).

### Non-goals (v1)

- Autonomy, vision, ToF, second CPU.
- Brushed H-bridge population (drive is BLDC). Revisit only if the chosen drive motor is not available.
- 4S/6S. Weapon motor is 3S max.
- Discrete AM32 from an unfrozen pin map. **Do not invent GPIO.**
- SD card. SPI NOR only.
- On-board charging.
- Using an ESC BEC for the Pico.

---

## 4. Constraints

| ID | Constraint |
|---|---|
| C-1 | Ready-to-fight mass ≤ 454 g. |
| C-2 | Electronics target ≤ 40 g (three ESC cells are heavier than H-bridges; stretch 35 g). |
| C-3 | Pack **3S only**: 9.0–12.6 V, abs max 13.5 V. |
| C-4 | Chassis: `models/Chassis - *.3mf`. Outline TBD. Planning ≤ 90 × 60 mm, 4-layer, 1.6 mm, 2 oz on inners if JLC allows. |
| C-5 | Combat shock. No tall unsupported parts. Glue bulk caps. |
| C-6 | Pico W antenna keep-out. |
| C-7 | SPARC-style: mechanical disconnect of drive+weapon in ≤ 15 s; failsafe stops motion; weapon stop ≤ 60 s after power removal; visible power LED. |
| C-8 | JLC SMT. Pico W hand-soldered (castellated). |
| C-9 | AM32 cells must match `AT32DEV_F421` / bootloader `F421_PB4`. |

---

## 5. Motor / ESC cells

| ID | Pri | Requirement |
|---|---|---|
| MOT-1 | SHALL | Three independent AM32 cells: `DRIVE_L`, `DRIVE_R`, `WEAPON`. |
| MOT-2 | SHALL | Each cell: AT32F421K8U7 + FD6288Q + 6× 40 V N-MOSFETs + BEMF dividers + low-side shunt + bootstrap. |
| MOT-3 | SHALL | Pinout **exactly** `HARDWARE_GROUP_AT_B` + `AT_045` + AT32DEV ADC (see PINMAP). Stock `AM32_AT32DEV_F421` hex. |
| MOT-4 | SHALL | Pico talks **DShot300 bidirectional** to each cell input (PB4). |
| MOT-5 | SHALL | Drive cells: AM32 bidirectional + sine startup + complementary PWM. Weapon: unidirectional, 3D off, current limit **10 A** for F2822 (stage rated 15 A cont / 30 A pk). |
| MOT-6 | SHALL | Drive stage rated **10 A cont / 20 A pk** (headroom for a geared BLDC; today’s 030 stall is 2 A). |
| MOT-7 | SHALL | DShot pull-down footprint on each PB4, **DNP** (AM32 enables the AT32 pull-up and its 1-wire serial needs an idle-high line; the Pico drives DShot push-pull through 100 Ω). Weapon FD6288 **VCC P-FET** (R440 4.7 k pull-up, SPICE-verified off state) switched by (GPIO9 **AND** ARM link) through two AO3400A; Q49 (gate node) and Q50 (ARM_N) hold the weapon AT32 in reset while disabled so the driver inputs never exceed VCC+0.3 V. FD6288 has no nSLEEP. |
| MOT-8 | SHALL | SWD header (3V3, SWDIO, SWCLK, NRST, GND) on each AT32 for the first bootloader flash; test points on ISENSE, VSENSE and PB6 telemetry. Weapon cell: ARM link in and 3.3 V on TP40 (WEAPON_EN) to release reset for flashing. |
| MOT-9 | SHALL | Motor lead holes A/B/C per channel (`thumbsup:MotorHoles_1x03_P5.90mm`: 2 mm plated holes in the phase copper between the FET rows, 30 A). Drive: low-KV **geared** BLDC (crawler). Weapon: F2822-1100KV. |
| MOT-10 | SHOULD | Board NTC at the weapon FET cluster → Pico GP28/ADC2 (`AT32DEV_F421` has no NTC input). Per-cell NTCs are a v2 item. |

**Low-speed BLDC:** AM32 crawler path (sine → trapezoidal ~200 RPM handoff). Use a **3S** BEMF divider (not a 6S ratio). Complementary PWM on. See https://wiki.am32.ca/general/Crawler-Hardware-and-AM32.html

---

## 6. Pico / I/O

| ID | Pri | Requirement |
|---|---|---|
| MCU-1 | SHALL | Pico W, castellated SMD footprint `RaspberryPi_Pico_W_SMD_HandSolder`. |
| MCU-2 | SHALL | USB, BOOTSEL, RUN reachable with armor off. |
| MCU-3 | SHALL | VSYS from on-board 5 V buck only. |
| MCU-4 | SHALL | Antenna keep-out per Pico W datasheet. |
| MCU-5 | SHALL | GPIO per PINMAP.md. |

---

## 7. Power

| ID | Pri | Requirement |
|---|---|---|
| PWR-1 | SHALL | XT30 pack input. |
| PWR-2 | SHALL | Mechanical disconnect in VBAT to motors **and** logic: **J4 POWER LINK** (XT30 loop plug) between the entry filter and the shunt. J1 alone may be declared the link (then DNP J4) if the chassis makes J1 reachable in ≤ 15 s. |
| PWR-3 | SHALL | Reverse-polarity protection on the **logic** path (Q1). Motor path polarised by the connector only: **a reversed pack destroys the board** (TVS, FET body diodes, INA226 inputs). Silk '+' at J1 pad 2, '3S ONLY'. |
| PWR-4 | SHALL | TVS on VBAT (SMBJ15A class) + ceramic + electrolytic at entry. |
| PWR-5 | SHALL | Bulk per ESC cell: 470 µF 25 V **hybrid polymer** (≤ 20 mΩ, SMD); weapon 2 × 470 µF; entry 1 × 470 µF. Plus 2 × 10 µF MLCC at each cell's FET drains. Ripple at 10 A: ≈ 5 A RMS worst case — verify can temperature on the bench. |
| PWR-6 | SHALL | 5 V / ≥ 2 A buck (**AP63205WU-7**, FB tied to VOUT) for **Pico VSYS (through a Schottky so USB cannot back-feed the board) + SK6812 + expansion + the two LDOs**. Not FD6288. |
| PWR-7 | SHALL | Two **AP2112K-3.3TRG1** from +5V: `+3V3_A` for IMU and INA226 ×4, `+3V3_MCU` for the 3× AT32 VDD/VDDA and the flash. Pico 3V3 stays separate. |
| PWR-8 | SHALL | FD6288 VCC from **+VDRV = pack after logic RPP** (9–12.6 V). Qg dissipation from 3S is ~0.1 W. Do **not** share Pico 5 V (UVLO+ max 5.0 V). |
| PWR-9 | SHALL | **Firmware** pack-V failsafe at 9.0 V (GP26). **Hardware** AP63205 EN divider 100 k / 27 k: on 5.4 V, off 4.6 V (SPICE with the 1.5 µA / 4 µA EN currents) so a 3 V hit sag from a 9 V pack does not reboot the logic; nothing downstream needs more than 3.8 V in. |

---

## 8. Instrumentation (measure everything practical)

| ID | Pri | What | How |
|---|---|---|---|
| SEN-1 | SHALL | Pack voltage | 1 % divider to Pico GP26, RC, clamp ≤ 3.0 V at 12.6 V |
| SEN-2 | SHALL | Pack current ±40 A | High-side 1 mΩ + **INA226**, I2C; Kelvin via net-ties on the shunt pads |
| SEN-3 | SHALL | Per-channel current | Low-side 1 mΩ in each ESC cell (Kelvin net-ties) → INA180A1 (20 V/V = 20 mV/A, AM32 stock scaling) → AT32 PA3 **and** INA226 to Pico (log ground truth). Note: this is the bus-side average current; regen reads 0 on the AM32 side, the bidirectional INA226 sees it. |
| SEN-4 | SHALL | Per-channel voltage | AT32 PA6 100 k / 10 k (AM32 stock `TARGET_VOLTAGE_DIVIDER 110`) |
| SEN-5 | SHALL | 5 V rail | Pico internal ADC3 (VSYS/3) logged; VSYS = +5V − D3 |
| SEN-6 | SHALL | Analog 3.3 V rail | Pico ADC GP27 via divider or GPIO-ok supervisor |
| SEN-7 | SHALL | 6-axis IMU | **LSM6DS3TR-C**, I2C, ±16 g / ±2000 dps, 1 kHz via FIFO bursts (bus is 400 kHz) |
| SEN-8 | SHALL | High-g accel | **ADXL375** ±200 g, I2C, 800 Hz ODR max at 400 kHz; use FIFO + shock interrupt for peak hold |
| SEN-9 | SHALL | Weapon eRPM / ESC temp | DShot EDT from each AM32, logged; not the only current sensor |
| SEN-10 | SHOULD | Board temp | 10 k NTC at the weapon FET cluster → GP28/ADC2 |
| SEN-11 | MAY | Motor NTC header | 2-pin |
| SEN-12 | SHALL | Sample electrical + commands ≥ 100 Hz; IMU decimated to 100 Hz with high-g **peak-hold** between samples |

Do not use EDT as the only current measurement.

---

## 9. Logging

| ID | Pri | Requirement |
|---|---|---|
| DAT-1 | SHALL | SPI NOR **W25Q128** (≥ 16 MB) circular match log. |
| DAT-2 | SHALL | Record: `t_ms`, gamepad, drive L/R cmd, weapon cmd, arm/estop/failsafe, pack V/I, I_L, I_R, I_W, V_L, V_R, V_W, 5 V, 3V3, gyro xyz, accel xyz, high-g xyz or peak, eRPM×3 if valid, event flags. |
| DAT-3 | SHALL | Dump over USB after match. Decoder in `tools/`. Must not block 100 Hz control. |
| DAT-4 | SHOULD | Event bits: impact, brownout, failsafe, weapon OC, invert. |
| DAT-5 | MAY | Unstuffed encoder footprints on drive. |

---

## 10. Safety / indicators / expansion

Hardware weapon enable (Pico GPIO9 **and** physical ARM link on J2, sensed on GP8), power LED on +5V independent of firmware, 2× SK6812 on **GP22** with 5 V level shift, reset button, expansion header J3 (5 V, 3V3_A, GND, I2C, UART0 on GP12/13, GP10/11, RUN), IMU interrupts on GP2/GP3, 300 mA spare on 5 V.

---

## 11. Firmware impact

- `config.h` pin map → PINMAP.md
- Three DShot300 bidirectional channels
- INA226 ×4 at 0x40/0x41/0x44/0x45, LSM6DS3TR-C (INT1 on GP2), ADXL375 (INT1 on GP3), W25Q128 logger, NTC on GP28, LEDs on GP22
- Weapon enable GPIO
- AM32 crawler settings on drive; 10 A limit on weapon; stock `AT32DEV_F421` hex needs no divider/current rescaling
- Bootloader on each AT32 once (SWD), then DShot config

---

## 12. Acceptance (first article)

1. Logic-only (no motors): 5 V ±5 %, 3V3 ±3 %, Pico enumerates.
2. Pack V on GP26 within 2 % of DMM after calibration.
3. Pack INA226 within 5 % on a 2 A load.
4. Each ESC cell: flash `F421_PB4` bootloader + `AM32_AT32DEV_F421`, beep on 3S current-limited supply **without** motor, then spin an unloaded motor, stop on Pico reset.
5. Weapon enable open ⇒ no spin even if firmware arms.
6. 30 s bench run writes a USB log ≥ 100 Hz with V/I/IMU.
7. Both IMUs enumerate; tilt and tap visible.
8. Bluetooth ≥ 2 m in chassis.
9. Board+Pico mass recorded.

**First power of each ESC cell is on a current-limited bench supply on J1 (USB alone powers only the Pico). No drum.** Weapon cell: ARM link in + 3.3 V on TP40 releases its reset. Set the AM32 current limit (10 A weapon) after flashing — stock EEPROM has it disabled.

---

## 13. Open items

- [ ] Chassis keep-out / holes
- [ ] Drive BLDC motor P/N (geared, 3S, crawler)
- [x] Stackup: 4-layer, 2 oz outer, 1 oz inner (LAYOUT.md §1); confirm 2 oz outer + Standard PCBA orderable together
- [ ] Log binary layout
- [ ] Expansion header pin freeze
- [x] AT32F421K8U7 QFN32 pin numbers verified against the Artery datasheet (2026-09-03)
- [x] FD6288Q out of stock → HX6288 C54423134 (pin-identical, EP = COM per its datasheet) is the ordered part
- [x] INA180A1IDBVR = C122228
- [x] SK6812MINI-C footprint drawn from the OPSCO land pattern; HYG015N04LS1C2 pin mapping fixed
- [ ] FHD4020S-4R7MT pads vs `L_Changjiang_FNR4020S` (both 4×4 mm)
- [ ] Confirm XT30 '+' pin on a physical connector (KiCad: pad 2)
- [ ] Update `firmware/include/config.h` per the migration table in PINMAP.md
- [ ] Decide J1-as-link (DNP J4) vs J4 fitted, from the chassis
- [ ] ADXL375 vs H3LIS331: H3LIS only if stock recovers; v1 stuffs ADXL375

See also [PARTS.md](PARTS.md), [PINMAP.md](PINMAP.md), schematic in `kicad/`.
