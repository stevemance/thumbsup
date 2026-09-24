# Round 10 (b): mechanical audit of rev J

Auditor: adversarial netlist/documentation audit, 2026-09-24.  No design file was edited.  Everything that regenerates
output (motor_board.py, calcs.py, both sims) ran on a copy in `/tmp/r10b/hw/motor_board`, with `hw/tools` symlinked so the
sims' `../../tools/spice` import resolves.

Out of scope: board area and chassis fit.  Firmware-contract wording appears only as NOTEs.

## Method and raw results

| Step | What was run / read | Result |
|---|---|---|
| Netlist | `python3 design/motor_board.py` (on the working tree, then again on the copy) | `230 refs (198 placed components), 158 nets, 66 BOM lines`, `checks: OK`.  netlist.csv, nets.md, bom.csv and mcu_pinmap.md regenerate **byte-identical** |
| Calcs | `python3 design/calcs.py` (copy) | calcs.md regenerates byte-identical |
| Sims | `sim_hotplug.py` 3.96 s, `sim_arm.py` 3.60 s (copy, hardware venv) | `diff` against the committed `hotplug.out` and `arm.out`: **identical** |
| Datasheets | `pdftotext -layout` of every PDF in datasheets/; ST XML `ref/STM32G474RxTx_pins.xml` | pin tables below |
| Footprints | every standard footprint parsed from `/usr/share/kicad/footprints/*.pretty`; pad names compared with the netlist pin set of every ref | all present, pads = pins (below) |
| JLC | `POST …/selectSmtComponentList/v2 {"keyword":"Cxxxx"}` for **all 66 BOM lines** (2 s gaps), per the method in review/r6_parts_lookup.md / round2_e_bom.md | classes below |

### 1. Pins vs datasheets

| Part | Source | Result |
|---|---|---|
| U1 STM32G474RET6 | ST XML (64 positions): name + AF (script) plus a direct dump of every analog/COMP signal; DS12288 Table 12 for I/O type | OK.  Every §3.4, §7.21 and §8 claim exists: PA0 ADC1_IN1/ADC2_IN1/COMP3_INP; PA1 ADC2_IN2/COMP1_INP; **PB11 ADC1_IN14 + COMP6_INP** (and ADC2_IN14); **PA2 ADC1_IN3** (COMP2_INM only, no INP); PA3 ADC1_IN4; PA4 ADC2_IN17; PA5 ADC2_IN13; PA6 ADC2_IN3; PB1 ADC3_IN1; PB12 ADC4_IN3; PB13 ADC3_IN5; PA8 ADC5_IN1 (also OPAMP5_VOUT, as §8 says); PA9 ADC5_IN2; PC3 OPAMP5_VINP; PF0/PF1 ADC1_IN10/ADC2_IN10 (script).  Each weapon CSA pin reaches exactly one COMPx_INP, as §8 claims.  The timer, SPI3, USART1 and SWD AFs match.  UCPD1_CC1 = PB6 and CC2 = PB4, as §8's dead-battery note says.  I/O types: PA2 **FT_a**; PB11, PA0, PA1, PA3–PA6, PC3, PC5, PB0, PB10 TT_a; PD2 FT |
| U2 DRV8323RH (RGZ) | SLVSDJ3D Table 6-4 | 49/49 OK.  Straps vs the EC table: MODE 47k→AGND = 3x PWM (Hi-Z = 1x); IDRIVE 75k→AGND = 60/120 mA (Hi-Z 120/240); VDS 18k→AGND = 0.13 V (Hi-Z 0.6 V); GAIN Hi-Z = 20 V/V; NC pin 46 "can be left floating" |
| U3/U4 DRV8316CR (RGF) | SLVSH07 Table 6-1 | 41/41 OK (NC 1, 24 "open").  nSCS has an internal 100 k pull-up to AVDD; SCLK/SDI/INHx/DRVOFF have internal 100 k pull-downs |
| U5 AP2112K | datasheet | 1 VIN, 2 GND, 3 EN, 4 NC, 5 VOUT: OK |
| U6 SN74LVC08A PW | SCAS283 | OK; unused 4th gate: inputs to GND, 4Y open |
| U7 INA239 | Table 5-1 | 10/10 OK.  ALERT is open drain (wire-OR on W_nFAULT is legal); MISO push-pull |
| U8 BQ76907 | Table 5-1, Table 7-1 (4 cells), Table 8-3 | 21/21 OK.  Cells VC7–VC6, VC5–VC4, VC3–VC2, VC1–VC0; VC6=VC5, VC4=VC3, VC2=VC1 shorted; SRP/SRN/TS to VSS; CHG/DSG open; REGSRC=BAT; VC0 through R6 + C8 to VSS |
| U9/U10 SN74LVC3G17 DCU | SCES470 | 1A1 3Y2 2A3 GND4 2Y5 3A6 1Y7 VCC8: OK |
| U11/U12 TPS22945 DCK | SLVS832D | 1 VOUT, 2 GND, 3 OC (open drain, open), 4 ON, 5 VIN: OK |
| U13 LM74502 DDF | SNOSDE5A Table 5-1 | 8/8 OK (pin 3 N.C.; OV to GND as the datasheet directs) |
| U14 74LVC1G17 SOT353 | DS35124 | 1 NC, 2 A, 3 GND, 4 Y, 5 VCC: OK |
| Q1–Q8 | HYG015N04LS1C2 / KiCad PQFN-8-EP generic (pads 1–4 + 5 = tab) | 1–3 S, 4 G, 5 D: OK.  Q7 D = BAT_IN, Q8 D = VBAT_SW, common S/G |
| D1, D2, D4, D5, D10 (KiCad pad 1 = K) | datasheets | D1 K = VBAT; D2 K = BUCK_SW; D4 K = PSW_G / A = PSW_S; D5 K = CELL0 / A = GND; D10 K = PSW_DV / A = PSW_RG (C13 can only absorb gate current): all polarities correct |
| D3 LED | KiCad pad 1 = K | K = GND: OK (the vendor numbering caveat is documented) |
| D7/D8 BAV99, D9 BAT54S (SOT-23) | Nexperia pinning tables | 1 = A1, 2 = K2, 3 = K1/A2.  D7/D8: GND→MTEMP→+3V3 clamp; D9: GND→ARM_AC clamp, ARM_AC→W_ARM rectifier: OK |
| J1–J4, wire holes | DESIGN §3.5/§3.3/§3.1 | J1 20 pins = §3.5 table; J2/J3 1 VS 2 GND 3–5 S1–S3 6 TEMP + MP; J4 1 = B0 … 5 = B4; J_BAT±, J_WA–C (1.5 mm²), J_LA–J_RC (0.5 mm²): OK |

NC pins (16): J1.7/18 spare, U11/U12.3 OC (open-drain flag), U13.3, U14.1, U2.32 (GAIN Hi-Z = intended setting), U2.46, U3/U4.1/24, U5.4, U6.11 (output), U8.9/10 (TI: "must be left floating").  Every one may float.

### 2. Nets

* **Single-node nets:** none.  **158 nets.**
* **Two-node nets (73), all intended:**
  * **Point-to-point control:** W_INHA/B/C, W_INLA/B/C, L_/R_INHA/B/C, L_/R_nCS, L_/R_S1–S3, MB_TX.
  * **CSA straight into the MCU:** W_SOA/B/C.
  * **CSA into its filter R:** L_/R_SOA/B/C.
  * **Gates:** W_GHA/B/C, W_GLA/B/C.
  * **Kelvin ties:** W_SNA/B/C.
  * **Straps and pumps:** U2_MODE/IDRIVE/VDS, U2_CPH/CPL/VCP/DVDD, BUCK_CB, L_/R_CP/CPH/CPL.
  * **Unused DRV8316 buck:** L_/R_SWBK.
  * **Soft-start and LDO nodes:** PSW_CAP, PSW_RG, BMS_REG.
  * **Balance taps:** BAL0–BAL3.
  * **Compute-board I²C and alert** (pull-ups are on the compute board by design): BMS_SCL/SDA/ALERT.
  * **Other ends:** VBAT_SNS_H (header only through R33), BOOT0, ARM_AC, LED_A, L_/R_TEMPJ.
* **Driver and load:** every signal net has one driver and at least one load.  Open-drain nets have their pull-ups: W_nFAULT R42, L_/R_nFAULT to their own AVDD.
* **Pull resistors, each on the correct rail:**
  * **Pull-downs:** W_EN (R40), W_INLx_M (R47–R49), W_ARM_CLK (R18), W_ARM_S (R19), BOOT0 (R61).
  * **Pull-ups to +3V3:** DRV_OFF (R50), INA_nCS (R12), NRST (R16), MB_RX (R17).
* **Decoupling:** every supply pin is decoupled.
  * **U1:** VDD ×4 (C60–C63 + C64), VDDA (C65), VREF+ (C71 + C66), VBAT (C74).
  * **U2:** VM (C24), VIN (C27), VREF (C23), DVDD (C22), VCP (C21), CPH/CPL (C20), CB (C28).
  * **U3/U4:** VM (C×00/C×01 + C×02/C×08), CP, CPH/CPL, AVDD (C×05), VREF (C×06), CBK (C×07).
  * **The rest:** U5 C69/C70, U6 C40, U7 C3, U8 C9/C11, U9 C47, U10 C50, U11 C45/C46, U12 C48/C49, U13 C14, U14 C17.
* **Absolute maximum ratings:**
  * **Reversed pack.** The LM74502 limits all hold:
    * VS −16.8 V vs −65 V.
    * EN = −2.2 V ≥ V(VS).
    * OV = 0 V ≤ 65 + V(VS).
    * Q8's body diode blocks.
    * D10 stops C13 from lifting the gate.
    * D4 holds Vgs ≥ −0.7 V.
  * **Switch open (only the balance lead powered):** U8 returns through D5.  The inputs of U7 (after the switch) stay ≥ −0.3 V.
  * **TT pins:**
    * U9/U10 limit the PB0/PB10 inputs to 3.3 V.
    * The CSA outputs come from a 3.3 V VREF.
    * PC5 is pulled to 3.3 V.
    * The dividers give 2.15 V at 16.8 V.
  * **Sensor inputs:** U9/U10 accept 5.5 V.
  * **DRV8316:** nFAULT is pulled to AVDD (not +3V3).  VREF is tied to AVDD, so it can never exceed AVDD.

### 4. Footprints

* **Standard footprints (30 distinct):** all exist, and pad names match the netlist pin set exactly.  Paste-only pads are unnamed.
  * PQFN-8-EP: pads 1–5.
  * RGZ0048A: 1–49.
  * QFN-20: 1–21.
  * DDF0008A: 1–8.
  * The rest match as well.
* **thumbsup: footprints:** there are four, and all are listed in DESIGN §6.12.
  * BOOMELE_1.27-2x10P_SMD (J1, 20 pads)
  * R_2512_HoLR_1-4mR (RS1–RS3, 2 pads)
  * SH1.0-6P_RA_XUNPU_WAFER-SH1.0-6PWB (J2/J3, pads 1–6 + MP)
  * TI_RGF0040E_VQFN-40-1EP… (U3/U4, pads 1–41)

### 5. BOM

* **bom.csv:** 66 lines, Qty sum = designator count = 192.  The DNP parts C110–C112 and C114–C116 are excluded.  66 unique LCSC numbers, each with one footprint.  The script check "one LCSC, one footprint" also holds across the DNP C1523 uses.
* **JLC classes today** (all 66 lines).
  * **Extended:**
    * The 11 IC lines (U1–U14).
    * Q1–Q8, C1, D1, D4, D9, L1.
    * RS1–RS3, RS4, TH1, R4.
    * J1, J2/J3, J4.
  * **Extended + preferred:** R20, R22/R24/R26/R63, R45, R46.
  * **Basic:** everything else, including C14 (C28233), D2, D5, D7/D8 and D10.

  This is **exactly the list and the counts in BOM.md.**
* **C21122:** Samsung CL10B223KB8NNNC, 22 nF 50 V X7R ±10 % 0603.  `componentLibraryType = base` (**Basic**), not preferred, stock 967,829, presale 844,027.  This matches C13 (22 nF 50 V 0603) in the netlist and the CHANGES rev J line.

### 3. Documents vs netlist, BOM, calcs and sims

I read these against netlist.csv, bom.csv, calcs.md, hotplug.out and arm.out:
* DESIGN.md (all sections); BOM.md; README.md.
* datasheets/README.md, spice/README.md.
* calcs.md, mcu_pinmap.md.
* CHANGES rev J; round8_c18_sweep.md.

**Checked and correct:**
* **Refdes, values and pins:** every refdes/value/pin in §3.1–§3.5, §6 and §9.  This covers the DRV8316 pin table, the J1 table, TP1–TP12, the strap pins and U13 pin 1.
* **§3.4 ADC table:** every channel, and the rank pairings (A+B, C+A, C+B; PA0 never on both ADCs in one rank).
* **Counts and sensing:**
  * 16 analog inputs.
  * 17 passives per drive channel.
  * CSA ranges ±8.7–9.9 A and ±35 A.
* **INA239 register values:** SOVL/BOVL/SHUNT_CAL = 38 A / 19.0 V / 0x1000.
* **Dividers and time constants:**
  * VBAT_SNS_H: ~109 kΩ source, 25.7 V limit, < 6 % shift.
  * Filter time constants: 0.87 ms, 1.3 ms, 4.5 ms, 8.7 µs, 22 ms, 103 ms.
* **Every hotplug number in §1, §3.1, §4, §5, §7.2, calcs §9 and CHANGES:**
  * Ramp: 2.19 / 1.28 / 2.95 V/ms.
  * Peak dV/dt: 0.003–0.009 V/µs.
  * Q7: 16.2 / 21.5 W, 52.6–55.8 mJ.
  * Peak current: 9.48–22.62 A.
  * Reversed pack: 13 A, and 102/146 A without D10.
  * Re-close: 0.119–1.349 V/µs, and 3.008–3.444 V/µs at the minimum UVLO.
  * Loaded bounce: 1.208–3.755 V/µs, 4.317 V/µs at −40 °C.
* **Every ARM number in §1, §3.2, §3.5, §5 and §9:**
  * Armed level: 2.50–2.95 V.
  * 7–10 edges; 12 ms at 500 Hz.
  * Disarm: 52–134 and 67–164 ms.
* **calcs.md vs DESIGN §4:** all rows agree.  VDS trip 62–93 A, 450 mA budget, 3.8 W, 3.7/3.1 m/s, 0.89/1.35/1.93 W, and so on.
* **Rev J PA2 ↔ PB11 swap:** propagated to §3.2, §3.4, §6.8, §7.21, §8, mcu_pinmap.md and motor_board.py, apart from findings N-01 and N-02.

## Findings

| ID | Sev | Where | Finding | Evidence | Fix |
|---|---|---|---|---|---|
| R10B-01 | MINOR | README.md line 8 | The README says "192 JLC-assembled parts (**rev I, after eight** adversarial review rounds)".  The package is rev J, after nine rounds (DESIGN.md title and intro; CHANGES "Round 9 → rev J").  This is the entry page the drawer starts from | README.md:8; DESIGN.md:1, :9 | "rev J, after nine …" |
| R10B-02 | MINOR | BOM.md title | "Motor board BOM notes (**rev I**, 2026-09-24)".  bom.csv carries rev J content: C13 is now C21122, 22 nF 50 V (CHANGES R9A N-02) | BOM.md:1; bom.csv C13 row; CHANGES.md:222 | "rev J" |
| R10B-N01 | NOTE | DESIGN §3.2 "Phase voltage sense"; motor_board.py C41–C43 desc | Stale after the rev J move.  Both texts say the 1 nF keeps a spike "below the 4 V abs max of these **TT** pins" / "the TT_a 4 V abs max".  W_VC is now on **PA2, which is FT_a** (abs max min(VDD,VDDA)+4 V); only PA4/PA5 are TT_a.  The claim is conservative, so there is no hardware impact | DS12288 pin table (PA2 FT_a, PA4/PA5 TT_a); Table 14 | "…below the TT_a 4 V abs max of PA4/PA5 (PA2 is FT_a)" |
| R10B-N02 | NOTE | DESIGN §6.8 | "keep them away from PA0, PA1, PB11 and PC3 (**the weapon CSA inputs**) and PA2".  PC3 is L_SOC_F (drive L CSA into OPAMP5), not a weapon CSA.  The rule itself is still right: PC3 is pin 11, next to PC1 (W_INHB, pin 9) | netlist U1.11 = L_SOC_F | "PA0, PA1, PB11 (weapon CSAs), PC3 (drive L CSA) and PA2" |
| R10B-N03 | NOTE | round8_c18_sweep.md 100 mΩ row vs text/CHANGES/DESIGN | The table shows **3.75** at 0.3/0.8 ms, while the text, CHANGES and DESIGN say "worst **3.76** V/µs".  hotplug.out has 3.755/3.751, so this is a rounding difference only | hotplug.out bounce rows; sweep table | Use one rounding (3.76) |
| R10B-N04 | NOTE | DESIGN §7.2 "0.1–1.2 ms bounce (simulated range)"; sim_hotplug.py docstring "(0.1-1.2 ms)" | The committed sim runs 0.1 / 0.3 / 0.8 ms bounces only (sim_hotplug.py case list; hotplug.out).  1.2 ms appears only in the round-8 C18 sweep (identical results: flat from 0.3 ms) | sim_hotplug.py bounce job list | Say "0.1–0.8 ms (sim; 1.2 ms in the C18 sweep)" or add a 1.2 ms case |
| R10B-N05 | NOTE | sim_hotplug.py docstring | Says "Rev I power entry"; the modelled values are rev J (C13 22 nF) | sim_hotplug.py:10–12, :84 | "Rev J" |
| R10B-N06 | NOTE | DESIGN §7.21 | "6–36 V/µs at the DRV8316 VM pins (sim, round 9)" and "≤ 3.8 V/µs" with the comparator trip come from a round-9 reviewer simulation that is not in spice/.  spice/README lists four scripts and none models the fault-clear kick, so the numbers cannot be reproduced from the package | spice/README.md; round9_d_system.md:37, :74 | Add the script, or cite round9_d as the source |
| R10B-N07 | NOTE | mcu_pinmap.md (generated) | Only one function per pin is listed and checked.  The script therefore does not auto-verify PA0 COMP3_INP/ADC2_IN1, PA1 COMP1_INP or PB11 ADC1_IN14, which §3.4/§7.21 rely on.  I verified them by hand against the XML (all present).  Tooling only | motor_board.py MCU_PINS / check_mcu_af | Allow a tuple of required signals per pin |
| R10B-N08 | NOTE | BOM.md U1 stock | JLC shows **199** today, against BOM.md "~210".  U2 203 and U7 101 unchanged | JLC API 2026-09-24 | Re-check on order day (already instructed) |
| R10B-N09 | NOTE | U4 R_nCS on PB4 | PB4 = UCPD1_CC2.  Its dead-battery Rd pulls R_nCS low (U4 selected) during every MCU reset, until firmware disables it.  This is harmless: DRV8316 SCLK/SDI have internal pull-downs, so there are no clocks, and U3/U7 are deselected, so there is no MISO contention.  DESIGN §8 already disables it first thing.  Recorded only because R_nCS has no external pull-up | XML PB4; SLVSH07 8.3.10.1/2 | None required |
| R10B-N10 | NOTE | DESIGN §3.1 cell filter "22 µs" | 100 Ω × 220 nF is 22 µs per tap.  The differential (cell) time constant with a 100 Ω in each tap is ~44 µs.  Both are inside TI's RC ≤ 200 µs | R6–R10, C4–C7 | Optional wording |
| R10B-N11 | NOTE | Footprints | The four thumbsup: footprints do not exist yet, so their pad counts can only be checked against the netlist pin sets (20; 2; 6+MP; 41), which match §6.12.  Check them when drawn | §6.12 | At drawing time |

No BLOCKER or MAJOR finding.  Every connection, polarity, footprint pad set, AF/ADC/COMP claim, BOM total, JLC class and
simulated number was checked, and each one matches its source.

**Verdict: 0 BLOCKER, 0 MAJOR, 2 MINOR, 11 NOTE.**
