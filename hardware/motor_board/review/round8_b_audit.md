# Round 8 (b): mechanical audit of rev H

Auditor: round 8 b.  Scope: the netlist against the datasheets, the nets, the docs against the generated outputs, footprints and the BOM.
Everything ran on a copy (`/tmp/mb_r8`).  The two sims ran in place: they only print to stdout, and their output was redirected to `/tmp`.  No design file was edited.
Board area, chassis fit and firmware-contract wording are out of scope.

## How this was checked

| Check | Method | Result |
|---|---|---|
| Netlist | `python3 design/motor_board.py` on the copy | `229 refs (197 placed components), 157 nets, 65 BOM lines` / `checks: OK`.  netlist.csv, nets.md, bom.csv and mcu_pinmap.md are **byte-identical** to the committed files |
| Rev G → H delta | diff against round 7's copy (`/tmp/r7b`) | Connection change: **C18 100 nF 16 V 0402 (C1525) PSW_EN–GND** only.  Comment edits: l.95, l.97, C13, R32, R13, D4, R15 |
| calcs | `python3 design/calcs.py` on the copy | `calcs.md` identical |
| SPICE | `sim_hotplug.py` (3.5 s) and `sim_arm.py` (3.7 s), hardware venv | `hotplug.out` and `arm.out` reproduced **exactly** (diff empty) |
| U1 | ST XML: every position name compared with MCU_PINS; AFs (script); the ADC/COMP/OPAMP signals of every analog pin; DS12288 I/O types | 64/64 OK.  Every ADC channel in the §3.4 table exists (PA0 ADC1_IN1/ADC2_IN1, PA1 ADC2_IN2, PA2 ADC1_IN3, PB1 ADC3_IN1, PB13 ADC3_IN5, PB12 ADC4_IN3, PA8/PA9 ADC5_IN1/2, PC3 OPAMP5_VINP, PA8 OPAMP5_VOUT, PB11 ADC1_IN14, PA3 ADC1_IN4, PF0 ADC1_IN10, PA4 ADC2_IN17, PA5 ADC2_IN13, PA6 ADC2_IN3, PF1 ADC2_IN10).  PA0 COMP3_INP and PA1 COMP1_INP as §7.21 says.  PB0/PB10/PC5/PA3/PA4/PA5/PB11 are TT_a; PD2 is FT |
| U2 | SLVSDJ3D Table 6-4 (RH column); strap EC rows | 49/49 match.  IDRIVE 75k→AGND = 60 mA source.  VDS 18k→AGND = 0.13 V.  MODE 47k = 3x (§8.3.1.1.2).  GAIN Hi-Z = 20 V/V.  NC 46 floats.  Abs max: nSHDN ≤ VIN (divider), digital ≤ 5.75 V, SOx ≤ VREF + 0.3 V |
| U3/U4 | SLVSH07 Table 6-1, CR column; abs max; RoC | 41/41 match; NC 1 and 24 float.  nSCS has an internal 100 k pull-up to AVDD, and SCLK/SDI/INHx/DRVOFF have 100 k pull-downs.  So the PB4 dead-battery pull-down on R_nCS during reset gives no SPI clocks.  DRV_OFF = 2.75 V with R50 against 2 × 100 k |
| U5 | AP2112K SOT25 pinout | 1 VIN, 2 GND, 3 EN, 4 NC, 5 VOUT: match |
| U6 | SCAS283 PW pin table | match; 4Y floats, 4A/4B to GND |
| U7 | INA239 Table 5-1 + abs max | match; IN+ = VBAT_SW; ALERT ≤ VS + 0.3 (pulled to +3V3) |
| U8 | BQ76907 Table 5-1, Table 7-1 (4S row), EP 21 | match: VC7–VC6, VC5–VC4, VC3–VC2, VC1–VC0; VC6=VC5, VC4=VC3, VC2=VC1 shorted |
| U9/U10 | SCES470 pin table | match |
| U11/U12 | SLVS832D DCK pin table; TPS2294x table (TPS22945 ON active high) | match; OC floats; ON = VIN ≤ 6 V abs max |
| U13 | SNOSDE5A Table 5-1, abs max, EN thresholds | match.  New C18: EN = 2.19 V at 16.8 V; reversed pack −2.19 V steady state and 0 V during the step (inside V(VS)…65 + V(VS)).  UVLO range recomputed from V(EN_UVLOF) 1.027/1.14/1.235 V and I(EN) 0–5 µA: 7.7/9.0/10.1 V off, ≤ 10.8 V on.  Matches DESIGN, calcs and the R13 description |
| U14 | DS35124 SOT353 drawing; EC tables | 1 NC, 2 A, 3 GND, 4 Y, 5 VCC: match (see N-01 for the thresholds) |
| Q1–Q8 | HYG015N04LS1C2 drawing (S S S G / D D D D), KiCad PQFN-8-EP (1–4 leads, custom pad 5 = tab) | match; C12 220 nF ≥ 10 × 2 × Ciss (4.05 nF) |
| D1–D10 | KiCad pad 1 = K (D_SMB, D_SMA, D_SOD-123, LED_0603); Nexperia BAV99/BAT54S Table 2 (1 A1, 2 K2, 3 K1/A2) | D1 K=VBAT, D2 K=BUCK_SW, D3 K=GND, D4 K=PSW_G, D5 K=CELL0, D10 K=PSW_DV / A=PSW_RG; D7/D8 GND→MTEMP→+3V3; D9 GND→ARM_AC→W_ARM.  All correct.  The 1N4148W sheet (Semtech, SOD-123) is now in datasheets/ |
| J1–J4, wire holes | netlist vs §3.5 / vendor pinouts; KiCad SolderWire files | J1 matches the §3.5 table pin for pin; J2/J3 1 VS…6 TEMP + MP; J4 B0…B4.  1.5 mm² = drill 2.15 / pad 3.9; 0.5 mm² = drill 1.15 / pad 2.15.  Both match DESIGN |
| Footprints | every non-`thumbsup:` footprint parsed from `/usr/share/kicad/footprints`; pad set compared with the netlist pin set | all 33 exist; pad set = pin set for **every** part (MH: no pads).  BOM.md's alternative `SSOP-8_2.95x2.8mm_P0.65mm` exists |
| Custom footprints | `thumbsup:` = TI_RGF0040E (U3/U4), R_2512_HoLR_1-4mR (RS1–RS3), BOOMELE_1.27-2x10P_SMD (J1), SH1.0-6P_RA_XUNPU (J2/J3) | all four in DESIGN §6.12 |
| Nets | single-node: none.  2-node: 70 (same list as round 7; PSW_EN now has 4 nodes).  Decoupling on every IC power pin; every pull | OK |
| Abs max | normal, reversed-pack, switch-open (incl. coasting drum) | no new violation; C18 adds none.  PA3/PA4/PA5/PB11 reach 4.0 V only at a 31 V TVS clamp (accepted in R6B N-08) |
| BOM | bom.csv | 65 lines, Σ Qty **191**, 191 unique refs, Qty = designator count on every line, DNP C110–C112/C114–C116 absent, one footprint per LCSC number |
| Classes / stock | JLC `selectSmtComponentList/v2`, 7 sequential requests 4 s apart (2026-09-24) | **C521608** STM32G474RET6: `expand`, stock **209**, presale 86.  **C543035** DRV8323RHRGZR: `expand`, **203**, presale 186.  **C2876522** INA239AIDGSR: `expand`, **101**, presale 65.  All match BOM.md (~210 / ~203 / ~101).  Spot checks: C51118 AP2112K `expand` (U-line, counted Extended); C13564 TH1 `expand`; C29823 4.7 µF 50 V **X7R** 1206 `base`; C1525 (C18) `base`.  Class list: 24 Extended + 4 Preferred + 37 Basic = 65 |
| Docs refdes / LCSC | every refdes (ranges expanded) in DESIGN, BOM.md, README, datasheets/README, spice/README, calcs.md, CHANGES rev H checked against the netlist; every LCSC number in the BOM.md table checked against the netlist | all exist except "C110–C116" (N-06); every LCSC number matches.  datasheets/README lists exactly the PDFs in the folder |
| Doc numbers | DESIGN §1–§9, BOM.md, calcs.md vs hotplug.out / arm.out / spinup.out / bridge.out / calcs | see findings; everything else matches (2.19/2.28/2.95/1.28 V/ms, 0.003–0.009 V/µs, 9.48–22.62 A, 13 A reversed / 102–146.5 A without D10, 0.119–1.349 V/µs typical re-close, 3.008–3.444 V/µs min-UVLO, 2.50–2.95 V armed, 7–10 edges, 52–134 / 67–164 ms, 191 parts / 65 lines, SOVL/BOVL/SHUNT_CAL codes, ARR 3542/1771) |

2-node nets (70), all intended:
- Power-entry and cell-monitor nodes: ARM_AC, BAL0–BAL3, BMS_ALERT/SCL/SDA (pull-ups on the compute board), BMS_REG, BOOT0, BUCK_CB, LED_A, PSW_CAP, PSW_RG.
- Drive channels (L_ and R_): CP/CPH/CPL, INHA/B/C, S1–S3, SOA/B/C, SWBK, TEMPJ, nCS.
- U2 straps and supplies: U2_CPH/CPL/DVDD/IDRIVE/MODE/VCP/VDS.
- Weapon: MB_TX, W_GHA–C, W_GLA–C, W_INHA–C, W_INLA–C, W_SNA–C (net-ties), W_SOA–C.

NC pins, all allowed to float: J1.7/18, U11.3/U12.3 (OC, open drain), U13.3, U14.1, U2.32 (GAIN Hi-Z), U2.46, U3/U4.1/24, U5.4, U6.11 (4Y output), U8.9/10 (DSG/CHG).

## Findings

| ID | Sev | Where | Finding | Evidence | Fix |
|---|---|---|---|---|---|
| R8B-01 | MINOR | DESIGN §7.2 l.494 | **The worst re-close figure is stale.**  The text says "0.1–1.4 V/µs in simulation, **3.3 V/µs** at the worst corner".  Rev H's sim gives 3.44 V/µs.  §3.1 (R15 row), §5 and CHANGES R7B-01 already say 3.44 | hotplug.out "off 400 ms, C1 ESR 300 mOhm min UVLO … 3.444V/us"; DESIGN l.108, l.421 | "0.12–1.35 V/µs typical, 3.44 V/µs at the worst corner" |
| R8B-02 | MINOR | DESIGN §3.1 R1/D10/C13/R32/D4 row l.106 | **The inrush figure is stale.**  The row says "~2.2 V/ms … **~1 A** into ~380 µF".  CHANGES R7A-03 says the inrush was changed to ~0.8 A, and §2, §4, calcs §9 and the netlist C13 description all say ~0.8 A | CHANGES rev H row 3; calcs §9 "~0.8 A into ~380 uF"; 2.19 V/ms × 380 µF = 0.83 A | "~0.8 A (0.5–1.1 A over the gate-current spread) into ~380 µF" |
| R8B-03 | MINOR | `spice/sim_hotplug.py` docstring l.9–16; CHANGES rev H row R7B-07 | **CHANGES says the docstring was updated, but it was not.**  The row says "(D10/R32, reversed pack, sweep range, rev)".  The docstring still reads "**Rev G** power entry" and describes the gate network as "RG 4.7k + Cdvdt 22 nF to GND", with no D10 or R32.  The model itself has D10 (`d10 psw_rg psw_dv`), R32, C18 and the reversed-pack cases | sim_hotplug.py l.9, l.12; netlist lines `d10`, `r32`, `c18` | "Rev H"; "RG 4.7k → D10 1N4148W → Cdvdt 22 nF ∥ R32 1M to GND"; mention the reversed-pack cases |
| N-01 | NOTE | DESIGN §3.2 (Dynamic ARM) "VT+ ≤ ~2.15 V, VT− 0.8–1.33 V **at 3.3 V**"; netlist U14/R41 descriptions; sim_arm.py | The VT+ limit is interpolated to 3.3 V, but VT− 0.80–1.33 V is the **3.0 V** spec.  Interpolating the 3.0 V and 4.5 V rows gives VT− ≈ 0.88–1.45 V at 3.3 V.  The disarm upper bound (VT− min) barely moves.  The earliest disarm, and so the pause tolerance, shortens: about 52 → ~45 ms at 85 °C / 250 Hz (nominal parts).  §3.5 asks the compute board for gaps ≤ ~20 ms, so the requirement still holds | DS35124 EC: VT− 0.80–1.33 V @ 3 V, 1.21–1.95 V @ 4.5 V; arm.out 85 C 250 Hz 2.50 V → 1.33 V in 52 ms | Label the VT− range "at 3.0 V" or quote ~1.45 V max at 3.3 V; optionally add a VT− = 1.45 V column to sim_arm |
| N-02 | NOTE | netlist l.95 "54 mJ" vs Q7 desc l.103 "53 mJ"; DESIGN §3.1 "53 mJ" / §4 "54 mJ" / §5 "53–56 mJ"; BOM.md "53 mJ"; DESIGN §3.1 "100–145 A" vs §5 "100–146 A" | Small inconsistencies.  The netlist file now disagrees with itself (rev H changed l.95 only).  §5's "Q7 16 W peak, 53–56 mJ" leaves out the 12 V-pack case (11.4 W, 26 mJ) | hotplug.out 53.5 mJ nominal, 52.6–55.8 mJ at 16.8 V; 146.51 A | Use one figure (≈ 54 mJ, 146 A) |
| N-03 | NOTE | DESIGN §6.6; §7.16 | §6.6 places "U13, C12, C14, R1, C13" next to Q7/Q8 but leaves out the new **C18**.  C18 must sit at U13 pin 1 to filter anything, so it matters.  D10 and R32 are also still missing.  §7.16 (silent single faults) still leaves out D10 (R7B N-04 carried over) | netlist PSW_EN (C18, R13, R14, U13.1), PSW_RG, PSW_DV | Add C18 (at U13 pin 1), D10 and R32 to §6.6; add D10 to §7.16 |
| N-04 | NOTE | DESIGN §7.5 l.505 | "A re-close while the drum still holds the bus up is not soft (**≤ 3.4 V/µs**, simulated)": no drum case was simulated, and the worst simulated re-close is 3.44 V/µs | hotplug.out | "(~3.4 V/µs worst in the re-close simulation)" |
| N-05 | NOTE | DESIGN §7 | Item 21 (weapon phase short) sits between items 16 and 17 | DESIGN l.534 | Renumber or move it to the end |
| N-06 | NOTE | DESIGN §9 step 0 | "the DNP set … (C110–C116)" includes C113, which does not exist (C113 is not a netlist part; DNP = C110–C112, C114–C116) | netlist; BOM.md l.5 | "C110–C112, C114–C116" |
| N-07 | NOTE | netlist l.66 (`"FET"` comment "2.0 mOhm") and l.218 ("40 V, 2 mOhm") | These comments quote the 4.5 V RDS(on).  DESIGN, BOM.md and calcs use 1.4 typ / 1.7 max mΩ at 10 V | HYG015N04LS1C2 EC: 1.4/1.7 mΩ @ 10 V, 2.0/2.4 @ 4.5 V | "1.4 mOhm @ 10 V" |
| N-08 | NOTE | DESIGN §7.21 (firmware wording) | "W_SOC on PA2 has no comparator input": PA2 has **COMP2_INM**, just no non-inverting input, so a DAC threshold cannot be used there | ST XML PA2: COMP2_INM, COMP2_OUT | "no comparator non-inverting input" |
| N-09 | NOTE | BOM.md "Before ordering" 1 | Step 1 says to reserve U2 and U7, but the parts table says to reserve U1 as well.  U1 has 209 in stock with only **86 presale** | JLC API 2026-09-24 | "reserve U1, U2 and U7" |
| N-10 | NOTE | calcs §3 (calcs.py) "Ripple current" rows | "inductor Isat >= 1.2 A (the LMR16006 current limit) recommended" contradicts the Inductor row and DESIGN §3.2 in the same file ("TI's 1.6 A recommendation") | calcs.md §3 | "Isat >= 1.6 A (TI)" |
| N-11 | NOTE | stock snapshot | U1 209 (presale 86), U2 203 (presale 186), U7 101 (presale 65) at JLC on 2026-09-24.  They match BOM.md; each board uses 1 of each | JLC API | Re-check on order day |

## Verdict

BLOCKER 0, MAJOR 0, MINOR 3, NOTE 11.  Connections, pinouts (U1–U14, Q1–Q8, D1–D10, J1–J4, wire holes), the new C18, diode polarities, footprints, BOM totals, classes and stock are clean.  What remains is three pieces of stale text: §7.2 still says 3.3 V/µs where the sim gives 3.44, §3.1 still says ~1 A of inrush where the other docs say ~0.8 A, and the sim_hotplug docstring still says rev G (CHANGES claims it was updated).
