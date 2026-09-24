# Round 9 (b): mechanical audit of rev I

Auditor: round 9 b.  Scope: the netlist against the datasheets, the nets, the docs against the generated outputs, footprints and the BOM.
Everything ran on a copy (`/tmp/r9b/mb`).  The sims ran in place with stdout redirected to `/tmp/r9b`.  The C18 sweep spot check imported `sim_hotplug.run()` from a script in `/tmp`.  No design file was edited.
Board area, chassis fit and firmware-contract wording are out of scope.

## How this was checked

| Check | Method | Result |
|---|---|---|
| Netlist | `python3 design/motor_board.py` on the copy | `230 refs (198 placed components), 158 nets, 66 BOM lines` / `checks: OK`.  netlist.csv, nets.md, bom.csv and mcu_pinmap.md are **byte-identical** to the committed files |
| Rev H → I delta | diff against round 8's copy (`/tmp/mb_r8`) | Connection changes: **C14 → 100 nF 100 V 0805 (C28233)**; **R33 100 k 0402 (C25741) VBAT_SNS → VBAT_SNS_H**; **J1.11 moved to VBAT_SNS_H**.  Comment edits: the FET comments (1.4 mΩ), R13 ("unloaded") |
| calcs | `python3 design/calcs.py` on the copy | `calcs.md` identical |
| SPICE | `sim_hotplug.py` (3.9 s) and `sim_arm.py` (3.6 s), hardware venv | `hotplug.out` and `arm.out` reproduced **exactly** (diff empty) |
| C18 sweep | 10 cells of `round8_c18_sweep.md` rerun with `run(iload=20, c18=…, stiff)` | all 10 reproduce: none/0.2 ms 0.08; 10 nF 0.1 ms 4.17, 0.2 ms 0.08; 22 nF 0.3 ms 4.32, 0.5 ms 0.09; 100 nF 1.2 ms 4.33; ESR 20 mΩ 0.1 ms 1.46, 0.3 ms 2.45; 100 mΩ 0.3 ms 3.75; 150 mΩ 0.8 ms 4.02.  The cells shared with hotplug.out (40/60/300 mΩ) match it |
| U1 | the script's position/name/AF check (64/64) plus a direct XML check of every analog/COMP signal in §3.4/§7.21 | OK: PA0 ADC1_IN1/ADC2_IN1/COMP3_INP, PA1 ADC2_IN2/COMP1_INP, PA2 ADC1_IN3/COMP2_INM (no INP), PB1 ADC3_IN1, PB13 ADC3_IN5, PB12 ADC4_IN3, PA8 ADC5_IN1/OPAMP5_VOUT, PA9 ADC5_IN2, PC3 OPAMP5_VINP, PB11 ADC1_IN14, PA3 ADC1_IN4, PF0 ADC1_IN10, PA4 ADC2_IN17, PA5 ADC2_IN13, PA6 ADC2_IN3, PF1 ADC2_IN10, PC13 TIM1_BKIN, PB7 TIM8_BKIN |
| U2 | SLVSDJ3D Table 6-4 (RH column); abs max; 4-/7-level EC rows | 49/49 match.  Strap voltages in §9 step 2 recomputed from RPU/RPD (50 k/84 k four-level, 73 k/73 k seven-level): MODE 1.24 V, IDRIVE 1.11 V, VDS 0.55 V, four-level Hi-Z 2.07 V, seven-level Hi-Z 1.65 V: all match.  (MODE 45 k vs 47 k already covered in R8A N-04) |
| U3/U4 | SLVSH07 Table 6-1, CR column | 41/41 match; NC 1/24 float; VREF/ILIM 37 = own AVDD; PAD = GND |
| U5 | AP2112K SOT25 | 1 VIN, 2 GND, 3 EN, 4 NC, 5 VOUT: match |
| U6 | SCAS283 TSSOP column | match; 4Y floats, 4A/4B to GND |
| U7 | INA239 Table 5-1 | match; IN+ = VBAT_SW (supply side), IN− = VBAT, VBUS = VBAT |
| U8 | BQ76907 Table 5-1, Table 7-1 4S row, EP 21 | match (VC7–VC6, VC5–VC4, VC3–VC2, VC1–VC0; VC6=VC5, VC4=VC3, VC2=VC1) |
| U9/U10 | SCES470F | 1A 1, 3Y 2, 2A 3, GND 4, 2Y 5, 3A 6, 1Y 7, VCC 8: match |
| U11/U12 | SLVS832D DCK | 1 VOUT, 2 GND, 3 OC (OD, floats), 4 ON, 5 VIN: match |
| U13 | SNOSDE5A Table 5-1, abs max | match.  New C14 100 V covers the 40–60 V BAT_IN ring; VS ≤ 65 V; EN = 60 × 15/115 = 7.8 V at the ring peak (≤ 65 V abs max) |
| U14 | DS35124 SOT25/SOT353 drawing; EC −40…85 °C and −40…125 °C | 1 NC, 2 A, 3 GND, 4 Y, 5 VCC: match.  §3.2 "VT+ ≤ ~2.15 V, VT− ~0.9–1.45 V at 3.3 V" = linear interpolation of the 3.0/4.5 V rows: correct |
| Q1–Q8 | HYG015N04LS1C2 (S S S G / tab D), KiCad PQFN-8-EP pads 1–5 | match (Q7 D = BAT_IN, Q8 D = VBAT_SW, common S = PSW_S, G = PSW_G) |
| D1–D10 | KiCad pad 1 = K; Nexperia BAT54S/BAV99 pinning (1 A1, 2 K2, 3 K1/A2) | D1 K=VBAT, D2 K=BUCK_SW, D3 K=GND, D4 K=PSW_G/A=PSW_S, D5 K=CELL0, D10 K=PSW_DV/A=PSW_RG, D7/D8 GND→MTEMP→+3V3, D9 GND→ARM_AC→W_ARM.  All correct |
| J1–J4, wire holes | netlist vs §3.5 and the vendor pinouts | J1 matches the §3.5 table pin for pin (pin 11 = VBAT_SNS_H); J2/J3 1 VS…6 TEMP + MP; J4 B0…B4 |
| Footprints | every non-`thumbsup:` footprint parsed from `/usr/share/kicad/footprints`; pad set compared with the netlist pin set | all **33** exist (incl. the new `C_0805` use); pad set = pin set for **every** part.  BOM.md's alternative `SSOP-8_2.95x2.8mm_P0.65mm` exists |
| Custom footprints | `thumbsup:` = TI_RGF0040E (U3/U4), R_2512_HoLR_1-4mR (RS1–RS3), BOOMELE_1.27-2x10P_SMD (J1), SH1.0-6P_RA_XUNPU (J2/J3) | all four are in DESIGN §6.12 |
| Nets | single-node, 2-node, NC pins, decoupling, pulls | single-node: none.  2-node: **71** (round 8's 70 + **VBAT_SNS_H** = J1.11 / R33.2, intended).  NC unchanged (16 pins, all may float).  C14 is the VS decoupling (TI: 100 nF VS–GND) |
| Abs max | normal, reversed pack, switch open (incl. the loaded-opening BAT_IN ring) | no violation.  C14 now 100 V against a 40–60 V ring.  VBAT_SNS_H: ≤ 3.3 V up to 25.7 V; R33 limits any injection into an unpowered compute board to ~20 µA.  R33's "< 6 % instead of 10–15 %" checks out: 8.72 k Thevenin into 100 k + 50 k gives 5.5 %, against 14.8 % without R33 |
| BOM | bom.csv | 66 lines, Σ Qty **192**, 192 unique refs, Qty = designator count on every line, DNP C110–C112/C114–C116 absent, one footprint per LCSC number, no LCSC number on two lines |
| Class | JLC `selectSmtComponentList/v2`, `{"keyword":"C28233"}` (2026-09-24) | **C28233**: Samsung CL21B104KCFNNNE, 100 nF ±10 % **100 V X7R 0805**, `componentLibraryType = base` (**Basic**), stock **1,694,657**, presale 1,441,870.  Matches BOM.md ("100 nF 100 V X7R 0805, Basic").  BOM.md class list: 24 Extended (U-lines 11) + 4 Preferred + 38 Basic = 66 lines: consistent |
| Docs refdes / LCSC | every refdes in DESIGN, BOM.md, README, datasheets/README, spice/README, calcs.md, CHANGES rev I and round8_c18_sweep (ranges expanded) checked against the netlist; every LCSC number in the BOM.md table checked against the netlist | all exist (the only non-matches are LCSC numbers and the layer names L2–L4); every BOM.md LCSC number matches its part.  datasheets/README lists exactly the 34 PDFs in the folder |
| Doc numbers | DESIGN §1–§9, BOM.md, README, calcs.md vs hotplug.out / arm.out / calcs | counts 192 / 66 / 6 DNP everywhere.  Also matching: 2.19/2.28/2.95/1.28 V/ms; 0.003–0.009 V/µs; 9.48–22.62 A; 13 A reversed / 102–146.5 A without D10; 0.119–1.349 and 3.008–3.444 V/µs re-close; bounce 1.208/3.009/3.045/2.138/3.372/3.366/4.317 V/µs, VM before 4.4–9.7 V; ARM 2.50–2.95 V, 7–10 edges, 52–134 / 67–164 ms.  Every rev I CHANGES row was checked against the files; each claimed edit is present (exceptions below) |

2-node nets (71), all intended: those listed in round 8 plus **VBAT_SNS_H** (J1.11, R33.2).

## Findings

| ID | Sev | Where | Finding | Evidence | Fix |
|---|---|---|---|---|---|
| R9B-01 | MINOR | DESIGN §3.4 l.262 (also the §2 diagram l.62) | **The VBAT_SNS bullet was not updated for R33.**  It reads "VBAT_SNS: R63 68 k / R64 10 k / C68 100 nF (0.87 ms) → PA3, **also on the header**", and neither it nor any other §3.4 line mentions R33.  In rev I the header pin is on its own net, VBAT_SNS_H, through R33 100 k.  A drawer working from §3.4 would tie J1.11 straight to the PA3 net, bypassing R33, which puts back the 10–15 % reading error R8D-04 fixed.  (§2's diagram also lists "VBAT_SNS" on J1: NOTE-level on its own) | nets.md l.122–123: VBAT_SNS = C68, R33.1, R63, R64, U1.17; VBAT_SNS_H = J1.11, R33.2; DESIGN §3.5 row 11 | "VBAT_SNS: R63 68 k / R64 10 k / C68 100 nF → PA3; to J1 pin 11 (VBAT_SNS_H) through R33 100 k"; "VBAT_SNS_H" in the §2 diagram |
| R9B-02 | MINOR | motor_board.py l.403 (J1 pin 11) → nets.md l.123 | **Pin name and net disagree on J1.11.**  The pin is still named "VBAT_SNS", so nets.md prints `VBAT_SNS_H: J1.11(VBAT_SNS), R33.2(2)`.  DESIGN §3.5 calls the pin VBAT_SNS_H.  If the J1 symbol is labelled from the pin names (every other J1 pin name equals its net), a "VBAT_SNS" label on pin 11 would silently merge the two nets and bypass R33 | netlist.csv `VBAT_SNS_H,J1,11,VBAT_SNS`; other J1 pins: name = net, except the spares (NC) | Rename the pin to "VBAT_SNS_H" |
| N-01 | NOTE | DESIGN §3.1 U13 row l.105; §6.10 | R8D-02 asked for two doc edits that were not made.  (1) §3.1 still says only "VS = BAT_IN with C14 100 nF": no 100 V rating (every neighbouring row gives ratings), and no note that a loaded switch opening avalanches Q7 and rings BAT_IN to 40–60 V.  Only the netlist C14 description and BOM.md say this.  (2) The §6.10 flex-crack orientation rule still covers "1206/2512 parts" only.  C14 (0805) is the one ceramic across the unswitched pack: a crack shorts the pack, and only the external switch can stop that | round8_d R8D-02 fix column; CHANGES rev I row R8D-02 (value change only) | §3.1: "C14 100 nF 100 V 0805 (BAT_IN rings to 40–60 V when the switch opens under load; Q7 avalanches by design)"; §6.10: include C14 |
| N-02 | NOTE | spice/README l.17; `sim_hotplug.py` docstring l.1–30 | Neither mentions the loaded contact-bounce cases added in rev I (`iload`, `c18` parameters, 7 bounce rows in hotplug.out).  The README "Question" column still lists only closure, reversed pack and re-close | sim_hotplug.py `bounce` jobs; hotplug.out last block | Add "contact bounce under a 20 A load (0.1–0.8 ms)" and the constant-current motor load to both |
| N-03 | NOTE | DESIGN §7.2 l.499 | "a **0.1–1.5 ms** bounce re-closes hard": the simulation covers 0.1–0.8 ms (hotplug.out) and the sweep goes to 1.2 ms (round8_c18_sweep.md).  1.5 ms is extrapolated | hotplug.out bounce block; sweep table columns | "0.1–1.2 ms (simulated; longer bounces are similar until the UVLO opens)" |
| N-04 | NOTE | Q7 soft-start energy | Carried over from R8B N-02, still unresolved: netlist l.95 "54 mJ" vs l.103 (Q7 description) "53 mJ"; DESIGN §3.1 "53 mJ", §4 "54 mJ", §5 "53–56 mJ"; calcs §9 "54 mJ"; BOM.md "53 mJ" | hotplug.out 53.5 mJ nominal, 52.6–55.8 mJ | Use one figure (≈ 54 mJ) |
| N-05 | NOTE | DESIGN §3.5 compute-board requirements | The R33 description tells the compute board to read VBAT_SNS_H through the 100 k and "add ~10 nF at its ADC pin".  That requirement is only in the netlist comment; the §3.5 requirements list (items 1–7) does not have it | motor_board.py R33 desc | Add it to §3.5 item 3 or 5 |
| N-06 | NOTE | arm.out footer; DESIGN §5 ARM row "(to VT− 1.33 / 0.8 V)"; §3.2 "~50 ms nominal gap" | §3.2 now correctly says VT− can reach ~1.45 V at 3.3 V, but the sim and §5 still stop at 1.33 V (the 3.0 V spec).  With 1.45 V the shortest pause tolerance, 85 °C at 250 Hz, drops from 52 ms to ~45 ms; at the required ≥ 500 Hz it is ~53 ms.  The ≤ 20 ms gap requirement in §3.5 still holds | DS35124 EC; arm.out 85 C 250 Hz 2.50 V → 1.33 V in 52 ms | Optionally add a VT− = 1.45 V column to sim_arm, or note the 3.3 V figure in §5 |
| N-07 | NOTE | R13 100 k 0402 (BAT_IN → PSW_EN) | During the 40–60 V BAT_IN ring R13 sees ~52 V (60 × 100/115) for microseconds.  A 0402 thick-film resistor is typically rated 50 V working and 100 V overload, so this is inside the overload rating: no action needed, but it is the only other small part on that node | R8D-02 ring level; U13 EN divider | None required; 0603 if the ring is ever measured above 60 V |

## Verdict

BLOCKER 0, MAJOR 0, MINOR 2, NOTE 7.  All connections, pinouts (U1–U14, Q1–Q8, D1–D10, J1–J4, wire holes), the rev I changes (C14 100 V 0805 C28233, confirmed Basic; R33 / VBAT_SNS_H), footprints, BOM totals and classes, both sims and the C18 sweep are clean.  The two MINORs are one issue: the header branch of the pack divider.  DESIGN §3.4 still says the PA3 divider node is "also on the header", and J1 pin 11 still carries the pin name "VBAT_SNS" on net VBAT_SNS_H.  Either could lead the drawer to bypass R33.

**BLOCKER 0 / MAJOR 0 / MINOR 2 / NOTE 7**
