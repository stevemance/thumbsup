# Round 5 — B: mechanical netlist / pin / footprint / BOM / docs audit (rev E)

Auditor: adversarial, read-only.  No design file was edited.  The whole package was copied to `/tmp/mb`, and every
script ran on the copy.  Scratch simulations are in `/tmp/r5b/`.  Date: 2026-09-23 (PDT).

## Method

* `python3 design/motor_board.py` (run on the copy) printed `225 refs (193 placed components), 156 nets, 64 BOM lines` / `checks: OK`.
  The regenerated `netlist.csv`, `nets.md`, `bom.csv` and `mcu_pinmap.md` are byte-identical to the checked-in files.
  `python3 design/calcs.py` also regenerates a byte-identical `calcs.md`.
* Every datasheet was converted with `pdftotext -layout`.  Pin tables were compared by number and name.
* Footprints were checked by script: each non-`thumbsup:` footprint was opened in `/usr/share/kicad/footprints/*.pretty`,
  and its set of pad names was compared with the netlist pin set.
* LCSC detail JSON (`wmsc.lcsc.com/ftps/wm/product/detail`) was queried for the 7 rev E C-numbers.  JLC
  `selectSmtComponentList/v2` was queried for those 7 and then for **all 64 BOM lines**.  Requests ran one at a time,
  3 s apart, with exponential back-off.
* SPICE used KiCad libngspice with `hardware/tools/spice/ngspice_shared.py`.  Two checks were run:
  * the dynamic-ARM pump, using round 4's `sim_arm.py` netlist with the rev E values;
  * a denser re-close sweep of the unmodified `spice/sim_hotplug.py` model.

## Findings

| ID | Sev | Where | Finding | Evidence | Fix |
|---|---|---|---|---|---|
| R5B-01 | MINOR | DESIGN §1 (Safety row), §3.2 "Dynamic ARM", §9 step 3; `motor_board.py` comment l.240–242 and R41 desc; CHANGES rev E row R4A-01 | **The ARM disarm time and armed level are quoted from a 0.8 V threshold, but U14 disarms at its VT−, which is 0.8–1.3 V.**  "100–160 ms at 25–85 °C" and "2.74–2.83 V" do not hold.  Even round 4's own fix simulation gives **81 ms** (85 °C, stuck low, < 0.8 V).  At VT− = 1.3 V the disarm is 56–97 ms, and 48–86 ms with C16 at −15 % DC bias (2.2 µF 16 V 0603 X5R at 2.8 V).  The armed level is 2.78–2.96 V (higher when hot).  The hardware is fine: a faster disarm is safe, and a 20 ms pause still leaves W_ARM ≥ 2.15 V vs VT− ≤ 1.3 V.  But the §9 step 3 pass window "drops W_ARM_S within 100–160 ms (repeat with the board warm)" will **fail a correct warm board**.  Also, no ARM simulation is in `spice/`, so none of these figures can be reproduced from the package | [74LVC1G17] DS35124 p.5 (VCC = 3 V): VT+ 1.50–2.00 V, **VT− 0.80–1.30 V** (1.33 at 125 °C).  `/tmp/r4a/spice/arm_fix.out`: "470n 2.2u 47k 85 C … stuck low <0.8 V **81 ms**".  `/tmp/r5b/arm_e.py` (same netlist, 500 Hz, 50 Ω source, BAT54 fit): 25 °C W_ARM 2.78–2.82 V, stuck high <1.3 V 97 ms / <0.8 V 157 ms, stuck low 79 / 129 ms; 85 °C 2.91–2.96 V, stuck high 68 / 99 ms, stuck low **56** / 81 ms; C16 = 1.9 µ at 85 °C: stuck low **48** / 70 ms; rise to 2.0 V 8–10 ms; 20 ms low pause min 2.15–2.31 V | Quote "~50–160 ms (U14 VT− 0.8–1.3 V, 25–85 °C)" and "2.8–3.0 V".  Make the §9 pass criterion "disarms in 30–250 ms, stuck high and stuck low" (the self-test's 300 ms hold still covers it).  Add the ARM sim to `spice/` |
| R5B-02 | MINOR | DESIGN §3.1 (R15 row), §5 (re-close), §7.2; calcs.md §9 "Bus decay" | **The re-close figures "0.1–2.4 V/µs, 3.3 V/µs with a cold C1: still under 4 V/µs" leave out the worst re-close time.**  The sweep in `sim_hotplug.py` jumps from 300 ms to 1000 ms.  The worst case lies in that gap: the latest re-close while the FETs are still on, when the bus is lowest and the step largest.  The model also cuts the gate source at a single EN level of 1.19 V (no hysteresis).  So its FETs open at ~7.0 V, but the datasheet thresholds keep them on down to 6.6 V typ and 5.7 V min.  At the datasheet-minimum EN thresholds (with the real divider load, R5B-03), the package's own model reaches **3.98 V/µs**, against the DRV8316's 4 V/µs abs max.  Extrapolated to a 5.7 V step start, that is ~4.2 V/µs.  This is the −40 °C C1-ESR corner of a residual that is already documented (a quick re-close is needed, which an intermittent XT30 can do).  The stated margin does not exist there | Unmodified model, stiff pack, 50 nH, re-close off-time sweep (`/tmp/r5b/reclose.py`): C1 300 mΩ: 300 ms 3.33 V/µs, **500 ms 3.61 V/µs** (VM 7.35 V), 600 ms soft; C1 40 mΩ: 500 ms 2.64 V/µs.  EN at min thresholds (1.16/1.027 V, no sink) + 18.7 kΩ (`/tmp/r5b/reclose_min.py`): C1 300 mΩ **700 ms 3.98 V/µs** (VM 6.39 V), 500 ms 3.70 V/µs; C1 40 mΩ 700 ms 2.91 V/µs; ≥ 800 ms soft in every case.  [LM74502] SNOSDE5A 6.5: V(EN_UVLOF) 1.027/1.14/1.235 V | Add 400–900 ms off-times and an EN-hysteresis/min-threshold case to `sim_hotplug.py`.  Quote "up to ~3.6 V/µs typ, ~4 V/µs at the min UVLO with a −40 °C C1".  Either accept that corner explicitly in §7.2 or raise the UVLO (e.g. R14 18 k → off ~7.9 V) so the step shrinks |
| R5B-03 | MINOR | `spice/sim_hotplug.py` (docstring + `rdiv vbat 0 35k`); calcs.md §9 "Bus decay (R15 6.8k + ~35k …) tau ~2.2 s", "Drain with the buck off … ~3 mA" | **The divider load on VBAT is ~18.7 kΩ, not ~35 kΩ.**  The load is four 68k+10k dividers (R22–R27, R63/R64) in parallel = 19.5 kΩ, plus R4+R5 = 441 kΩ.  calcs §2 itself says "x4 dividers: ~0.9 mA total".  τ is ~1.9 s, not 2.2 s.  The flat-pack drain is ~1.6–1.9 mA at 6.6–9.2 V (R15 + dividers; drivers asleep), not "~3 mA".  The error is benign in direction: the bus bleeds faster | netlist: R22/R23, R24/R25, R26/R27, R63/R64 on VBAT–GND; R4/R5 VBAT–BUCK_EN–GND.  6.8k ∥ 18.7k × 386 µF = 1.93 s | Change `rdiv` to 18.7k, recapture `hotplug.out`, and fix the calcs text |
| R5B-04 | MINOR | DESIGN §3.2 "Control" bullet ("INLA/B/C ← U6 = TIM1_CH1N/2N/3N … **AND W_ARM**"), §2 diagram + design-choices bullet; `motor_board.py` l.229 / **l.231 "W_ARM also goes to the MCU (PD2, FT)"** | **Stale rev D wording: U6's B inputs and PD2 are W_ARM_S (U14's output), not W_ARM.**  The §3.2 Control bullet and the §3.2 Dynamic ARM bullet disagree.  Someone drawing U6 from the Control bullet would bypass U14, which reopens R4A-03 (slow RC edge into a non-Schmitt LVC08) | nets.md **W_ARM_S**: U1.55(PD2), U14.4(Y), U6.2(1B), U6.5(2B), U6.10(3B); **W_ARM**: C16, D9.2, R41, TP6, U14.2 | Write "AND W_ARM_S (W_ARM through U14)" in §3.2 Control and the §2 diagram; fix the l.229/231 comments |
| R5B-05 | MINOR | `design/bom.csv`; BOM.md / DESIGN §1 "64 lines" | **One LCSC number, C25792, is on two BOM lines**: R41 "47k" and R44 "47k 1%".  The script groups by Comment, so the same 1 % UNI-ROYAL part is split.  JLC flags or merges duplicate part numbers, and round 4's "each LCSC number on exactly one line" no longer holds | bom.csv lines "47k,R41,…,C25792,1" and "47k 1%,R44,…,C25792,1"; JLC C25792 = 0402WGF4702TCE ±1 % | Set R41's value to "47k 1%" (or merge by LCSC in the script); the count becomes 63 lines |
| R5B-06 | MINOR | DESIGN §4a | Stale text carried over from round 4 (R4B N-04, not fixed although CHANGES says the notes were done): "the **0402** 100 Ω inputs are not rated for balance current".  R6 is 0603 | netlist R6 `R_0603_1608Metric`, R7–R10 0402 | "the 100 Ω input resistors" |
| N-01 | NOTE | D4 MMSZ5242B, U13 GATE | **D4 conducts in normal operation, not only during a sag.**  U13's pump regulates VCAP−VS at 10.3–13.9 V (typ 11.6–12.4).  At the ~60 µA gate current, the 12 V zener's knee is below ~11.4 V (Vz min at 20 mA; Zzk 600 Ω at 0.25 mA).  So the 60 µA gate source flows into D4 continuously, and Vgs settles at ~10.5–12 V.  That is fine: HYG RDS(on) is specified at 10 V, the zener dissipates < 1 mW, and the pump sources 162–600 µA.  DESIGN §3.1 describes D4 only as a sag clamp | SNOSDE5A 6.5 (I(GATE) 40/60/77 µA; CP on 10.3–13, off 11–13.9 V; I(VCAP) 162–600 µA); MMSZ5242B (JSCJ) table: 11.40–12.60 V @ 20 mA, ZZK 600 Ω @ 0.25 mA, IR 1 µA @ 9.1 V | Mention it in §3.1; check Vgs ≥ 10 V at bring-up |
| N-02 | NOTE | calcs.md §9 "Drain with the buck off … then 50-140 uA (R13/R14 + **U13 shutdown**)" | Below the UVLO but above V(ENF) (0.32–0.94 V on EN, i.e. BAT_IN above ~1.8–5.2 V), U13 is in UVLO, not in its 1 µA shutdown.  Its supply current there is not specified; the operating I(Q) is 45/65 µA.  Expect ~100–200 µA until the pack is very flat | SNOSDE5A 6.5: V(ENF) 0.32/0.64/0.94 V, I(SHDN) 0.9 µA only at EN = 0 V, I(Q) 45/65 µA | Reword, or measure at bring-up |
| N-03 | NOTE | `motor_board.py` l.97; `spice/sim_hotplug.py` docstring l.9 | Stale labels: "EN/UVLO turns the pair off below **~6.5 V**" (rev E: ~6.6 V); "**Rev D** power entry" in a docstring that describes the rev E values (100k/22k, D4) | — | Cosmetic |
| N-04 | NOTE | DESIGN §3.2, CHANGES rev E; calcs §4 | C17 (100 nF, U14 VCC) is correct in the netlist, but DESIGN and CHANGES never name it.  calcs §4's logic list ("U6, U9, U10, U11, U12") leaves out U14 (µA) | nets.md +3V3: C17.1; GND: C17.2 | Add "U14 decoupled by C17" to §3.2 |
| N-05 | NOTE | U14 thresholds | DS35124 gives VT± only at VCC = 3 V and 4.5 V.  At the 3.3 V rail, VT+ max interpolates to ~2.1 V.  The armed level of ≥ 2.78 V keeps ≥ 0.6 V of margin | DS35124 p.5 | None |
| N-06 | NOTE | BOM.md stock figures | JLC today: **U1 210** (BOM.md "~316"), U2 203, U7 111, D9 286,362 (BOM.md "136k"), J1 7,393, RS1–RS3 3,115.  U1/U2/U7 are the reserve-first parts | JLC `selectSmtComponentList/v2`, 2026-09-23 | Refresh on order day |
| N-07 | NOTE | LM74502 SRC with a reversed pack | Unchanged from R4B N-07: SRC ≈ BAT_IN + (µA body-diode Vf) vs the "SRC ≤ V(VS) + 0.3 V" abs max.  This is TI's own back-to-back topology; accepted | SNOSDE5A 6.1 | — |

## 1. Pin audit (netlist ↔ datasheet)

| Part | Source | Result |
|---|---|---|
| U1 STM32G474RET6 | ST XML via the script | 64/64 pin names + every required AF pass |
| U2 DRV8323RHRGZR | SLVSDJ3D Table 6-4 (RH column) | All 48 + PAD match.  Details: 1 FB, 2 PGND, 3 CPL, 4 CPH, 5 VCP, 6 VM, 7 VDRAIN, 8–22 gate/SH/SP/SN, 23–25 SOC/SOB/SOA, 26 VREF, 27 DGND, 28 nFAULT, 29 MODE, 30 IDRIVE, 31 VDS, 32 GAIN (NC = Hi-Z level, intended), 33 ENABLE, 34 CAL, 35 AGND, 36 DVDD, 37–42 INH/INL, 43 BGND, 44 CB, 45 SW, 46 NC ("can be left floating"), 47 VIN, 48 nSHDN |
| U3/U4 DRV8316CRRGFR | SLVSH07 Table 6-1 (CR column) | All 40 + PAD match; 1 and 24 are NC ("No connection, open").  SDO is push-pull at reset (CTRL2 reset 60h, SDO_MODE = 1), so the shared MISO is safe before configuration |
| U5 AP2112K SOT-25 | Diodes pin table | 1 VIN, 2 GND, 3 EN, 4 NC, 5 VOUT |
| U6 SN74LVC08APWR | SCAS283T | 1A1 1B2 1Y3 2A4 2B5 2Y6 GND7 3Y8 3A9 3B10 4Y11 4A12 4B13 VCC14; B inputs = W_ARM_S; 4Y (output) floats |
| U7 INA239 DGS | pin figure | 1 CS, 2 MOSI, 3 ALERT, 4 MISO, 5 SCLK, 6 VS, 7 GND, 8 VBUS, 9 IN−, 10 IN+; IN+ = VBAT_SW (supply side of RS4) |
| U8 BQ76907RGR | SLUSE96A Table 5-1, Table 7-1 (4S), Table 8-3 | 1 VC4 … 20 VC5 match.  4S: VC7–VC6, VC5–VC4, VC3–VC2, VC1–VC0 on real cells; VC6=VC5, VC4=VC3, VC2=VC1 shorted.  SRP/SRN/TS → VSS; DSG/CHG float (TI: "must be left floating"); REGSRC = BAT; VC0 via R6 + C8 to VSS |
| U9/U10 SN74LVC3G17DCU | SCES470F | 1A1 3Y2 2A3 GND4 2Y5 3A6 1Y7 VCC8 |
| U11/U12 TPS22945DCK | SLVS832D | VOUT1 GND2 OC3 (open drain, floats) ON4 VIN5; ON tied to VIN ("do not leave floating": satisfied) |
| U13 LM74502DDF | SNOSDE5A Table 5-1 | 1 EN/UVLO, 2 GND, 3 N.C, 4 VCAP, 5 VS, 6 GATE, 7 OV = GND ("connect OV to ground when not used"), 8 SRC |
| **U14 74LVC1G17SE-7** (new) | DS35124 pin assignment (SOT25/SOT353) + ordering table ("SE : SOT353") | 1 NC, 2 A = W_ARM, 3 GND, 4 Y = W_ARM_S, 5 VCC = +3V3.  Match.  The input tolerates 5.5 V; IOFF protects an unpowered board |
| Q1–Q8 HYG015N04LS1C2 | HUAYI pin figure | 1–3 S, 4 G, 5 (tab) D.  Q7 D = BAT_IN, Q8 D = VBAT_SW, S = PSW_S, G = PSW_G (back-to-back common source).  Bridge: high side D = VBAT, S = W_x; low side D = W_x, S = W_SLx |
| D1 SMBJ20A / D2 SS34 / D3 LED / D5 B5819W | KiCad pad 1 = K; band = cathode (CJ, MDD) | D1 K = VBAT, D2 K = BUCK_SW, D3 K = GND (A = LED_A), D5 K = CELL0.  Correct |
| **D4 MMSZ5242B** (new) | JSCJ SOD-123; KiCad D_SOD-123 pad 1 = K | K = PSW_G, A = PSW_S: reverse-conducts at Vgs ≈ 11–12.6 V; forward-clamps Vgs ≥ −0.7 V.  Correct (see N-01) |
| D7/D8 BAV99 | Nexperia Table 2: 1 A1, 2 K2, 3 K1/A2 | 1 GND, 2 +3V3, 3 MTEMP: clamps both ways.  Correct |
| D9 BAT54S | Nexperia Table 2: 1 A1, 2 K2, 3 K1/A2 | 1 GND, 2 W_ARM, 3 ARM_AC: diode 1 clamps ARM_AC ≥ −Vf, diode 2 rectifies into W_ARM.  Correct |
| J1 | DESIGN §3.5 table | 20/20 match; 7 and 18 NC (spare); 19 W_ARM_CLK beside 20 GND |
| J2/J3 | DESIGN §3.3 | 1 VS, 2 GND, 3–5 S1–S3, 6 TEMP, MP = GND |
| J4 | DESIGN §3.1 / §6.9 | 1 BAL0 (B−) … 5 BAL4 (B4+) |
| JP1/JP2, TP1–TP12, NT1–NT3, pads, MH1–MH4 | DESIGN §3.3, §3.4, §6.10 | match |

**NC pins (all may float):** U2.32 GAIN (Hi-Z = 20 V/V), U2.46, U3/U4.1/.24, U5.4, U6.11 (output), U8.9/.10,
U11/U12.3 (open-drain flag), U13.3, **U14.1**, J1.7/.18.

## 2. Nets

* The netlist has 156 nets, and every net has ≥ 2 nodes.
* **70 two-node nets.**  All are intended and unchanged in kind from round 4:
  * power entry: PSW_CAP, PSW_DV;
  * ARM: ARM_AC;
  * cell monitor: BAL0–BAL3, BMS_ALERT/SCL/SDA/REG;
  * MCU and header: BOOT0, MB_TX;
  * buck and LED: BUCK_CB, LED_A;
  * drive channels (L_ and R_): CP, CPH, CPL, INHA–C, S1–S3, SOA–SOC, SWBK, TEMPJ, nCS;
  * weapon driver: U2_CPH, CPL, DVDD, IDRIVE, MODE, VCP, VDS;
  * weapon bridge: W_GHA–C, W_GLA–C, W_INHA–C, W_INLA–C, W_SNA–C, W_SOA–C.
* **Rev E nets.**
  * W_ARM: C16, D9, R41, TP6, U14.A.
  * W_ARM_S: U14.Y → U6 ×3, PD2.  It is driven push-pull by U14 whenever +3V3 is up.
* **Drivers and pull-ups.**
  * Off-board drivers: MB_RX (R17 ↑), W_ARM_CLK (R18 ↓) and the BMS I²C lines (the compute board has the pull-ups; they float on the bench, as documented).
  * Open drains: W_nFAULT (U2 + U7 ALERT, R42 ↑ +3V3), L/R_nFAULT (↑ own AVDD), BMS_ALERT (compute board).
  * SPI_MISO is shared tri-state, with the PC11 pull-down.
  * Other pulls: INA_nCS R12 ↑, W_EN R40 ↓, DRV_OFF R50 ↑, W_INLx_M R47–R49 ↓, NRST R16 ↑, BOOT0 R61 ↓, W_ARM R41 ↓.
  * All go to the correct rails.
* **Decoupling** is present on every power pin:
  * U1: C60–C64, C65, C66 + C71, C74.
  * U2: C24 (VM), C27 (VIN), C21 (VCP), C22 (DVDD), C23 (VREF).
  * U3/U4: x00/x01/x02/x08, x03–x07.
  * U5: C69/C70.  U6: C40.  U7: C3.  U8: C9, C11.  U9/U10: C47/C50.  U11/U12: C45/C48 + C46/C49.
  * U13: C14 (VS) and C12 (VCAP).  **U14: C17**.
* **Voltages vs abs max.**
  * BAT_IN (plug-in ring up to ~32 V, round 4 N-01): U13 VS ±65 V; C14 50 V; C12 sees VCAP−VS ≤ 13.9 V (25 V part).  R13 0402 50 V sees BAT_IN − EN ≤ 28 V.  EN = 0.18 × BAT_IN ≤ 5.8 V (65 V limit).  C13 50 V sees ≤ ~31 V.
  * Reversed pack: BAT_IN = −16.8 V; U13 VS OK.  EN = −3.0 V and OV = 0 V are within [V(VS), 65 + V(VS)].  Q8 blocks 16 V.  D1, U7 and everything on VBAT see nothing.  SRC: see N-07.
  * Switch open: BAT_IN floats.  U8 stays powered from the balance lead, with GND = pack− via BAT−.  If the compute board is USB-powered while the motor board is off, a toggling W_ARM_CLK puts ≤ 3 V on U14.A (IOFF, 5.5 V tolerant), and W_ARM_S stays 0.
  * PSW_G–PSW_S: ≤ 12.6 V with D4 (15 V limit).
  * VBAT (≤ 32.4 V TVS clamp) reaches only ≥ 35 V parts (DRV8316 40 V).
  * The new ARM parts (C15 25 V, C16 16 V, R41) see ≤ 3.6 V.
  * No 16 V capacitor sits on a net above 3.7 V.

## 3. Documentation ↔ netlist / BOM / calcs / sim outputs

**Checked and consistent.**

* Counts:
  * 187 assembled + 6 DNP, 64 lines (DESIGN §1, BOM.md, README).
  * bom.csv Qty sums to 187, and each Qty equals its designator count.
  * C110–C112/C114–C116 are excluded.
  * 16 analog inputs, 9 currents.
* Every refdes range named in DESIGN, BOM.md, README, the datasheets README, spice/README, calcs.md and CHANGES rev E exists in the netlist.
* DESIGN §3.1–§3.5 values and pins, including:
  * the U13 network, R13/R14 100k/22k, D4, R15, RS4/R2/R3/C2/R12, R4/R5/C10;
  * the cell block;
  * straps, ADC channel map, TP1–TP12, the J1 table.
* §4 against calcs.md.
* §5 against `hotplug.out`: 0.003–0.010 V/µs, 2.67 / 3.42 V/ms, 16 / 21.5 W, 53 mJ, 9–23 A.  Re-close rows 0.12–2.43 / 3.33 V/µs.  See R5B-02 for what the sweep misses.
* §5 against `bridge.out` and `spinup.out`.
* UVLO arithmetic (SNOSDE5A thresholds, 3–5 µA sink):
  * off 6.62 V typ / 7.35 V worst;
  * on 7.18 V typ / 7.82 V worst;
  * worst off (7.35 V) < buck worst off (7.4 V).
* INA239 SOVL 0x76C0 = 38 A, BOVL 0x17C0 = 19.0 V, SHUNT_CAL 0x1000.
* CHANGES rev E rows match the netlist: C15 470 n, C16 2.2 µ, R41 47 k, U14 C212314, D4, R13/R14.
* The round-4 fixes R4B-02/03/04/05/06/07 and N-05 are done; N-04 is not (R5B-06).

**Mismatches:** R5B-01 to R5B-06 and N-02 to N-04 above.

## 4. Footprints

* Every standard footprint exists in `/usr/share/kicad/footprints`, and its pad set equals the netlist pin set.  The script found no exception.  New in rev E:
  * `Package_TO_SOT_SMD:SOT-353_SC-70-5` (U14, 5 pads);
  * `Diode_SMD:D_SOD-123` (D4, 2 pads).
* MountingHole_2.2mm_M2 has one unnamed NPTH pad (MH1–MH4, no pins).
* All seven `thumbsup:` footprints are listed in DESIGN §6.12, with their sources:
  * SolderPad 4×6 / 3×5 / 2×3;
  * TI_RGF0040E (TI RGF0040E drawing);
  * R_2512_HoLR_1-4mR (Milliohm HoLR land);
  * BOOMELE_1.27-2x10P_SMD (BOOMELE drawing);
  * SH1.0-6P_RA_XUNPU (XUNPU drawing).

## 5. BOM

### Rev E C-numbers (LCSC detail + JLC, 2026-09-23)

| C-no | Refs | MPN / maker | Package | Ratings | JLC class | JLC stock | Verdict |
|---|---|---|---|---|---|---|---|
| C212314 | U14 | 74LVC1G17SE-7 / Diodes | SOT-353 | 1.65–5.5 V Schmitt buffer, push-pull, −40…125 °C | Extended | 5,406 (presale 5,372) | OK |
| C21567 | D4 | MMSZ5242B / JSCJ | SOD-123 | 12 V (11.4–12.6), 350 mW, IR 1 µA | Extended | 3,849 | OK |
| C25768 | R14 | 0402WGF2202TCE / UNI-ROYAL | 0402 | 22 k 1 % 62.5 mW 50 V | Basic | 937,701 | OK |
| C1623 | C15 | CL10B474KA8NNNC / Samsung | 0603 | 470 nF 25 V X7R | Basic | 946,333 | OK |
| C23630 | C16 | CL10A225KO8NNNC / Samsung | 0603 | 2.2 µF 16 V X5R | Basic | 2,852,188 | OK (DC-bias: R5B-01) |
| C25792 | R41, R44 | 0402WGF4702TCE / UNI-ROYAL | 0402 | 47 k 1 % 50 V | Basic | 5,818,491 | OK; split over two lines (R5B-05) |
| C25741 | R12, R13, R18, R40, R47–R49 | 0402WGF1003TCE / UNI-ROYAL | 0402 | 100 k 1 % 50 V | Basic | 9,092,696 | OK |

### Whole-BOM checks

**Class check of all 64 lines (JLC).**
* **24 Extended lines:**
  * the 11 IC lines U1, U2, U3/U4, U5, U6, U7, U8, U9/U10, U11/U12, U13, U14;
  * Q1–Q8, C1, D1, D4, D9, L1, RS1–RS3, RS4, TH1, R4, J1, J2/J3, J4.
* **4 Preferred lines:** R20 (C25796), R22/R24/R26/R63 (C36871), R45 (C25798), R46 (C25762).
* **Every other line is Basic**, including R13 (now 100 k, C25741), which correctly left the Preferred list.
* This matches the BOM.md class list exactly.

**bom.csv.**
* DNP parts are excluded.
* Every LCSC number maps to one footprint (script check).
* The only duplicate LCSC number across lines is C25792 (R5B-05).

**Verdict: 0 BLOCKER, 0 MAJOR, 6 MINOR, 7 NOTE — not clean.**
