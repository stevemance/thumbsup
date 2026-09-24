# Round 6 (b): mechanical audit of rev F

Auditor: round 6 b.  Scope: netlist ↔ datasheets, nets, docs ↔ generated outputs, footprints, BOM.
All scripts were run on a copy (`/tmp/r6b/motor_board`); no design file was edited.

## How this was checked

| Check | Method | Result |
|---|---|---|
| Netlist | `python3 design/motor_board.py` on the copy | `226 refs (194 placed components), 156 nets, 62 BOM lines` / `checks: OK`; netlist.csv, nets.md, bom.csv, mcu_pinmap.md **byte-identical** to the committed files |
| calcs | `python3 design/calcs.py` vs `design/calcs.md` | identical (except a trailing newline) |
| SPICE | `sim_arm.py`, `sim_hotplug.py` re-run with the hardware venv | `arm.out` and `hotplug.out` reproduce exactly (both runs finished in minutes, not the ~15 min / ~1 h in spice/README) |
| U1 | ST XML: names, power pins, AFs (the script checks AFs); DS12288 pin table for FT/TT types | all 64 pins OK; PD2 FT, PA3/PA4/PA5/PB0/PB10/PB11/PC5 TT_a (4.0 V abs max) as the docs say |
| U2 | SLVSDJ3D Table 6-4 (48-pin, RH column), strap EC table (l.1644–1853 of the pdftotext) | 49/49 pins match; MODE 47k→AGND = 3x, IDRIVE 75k→AGND = 60/120 mA, VDS 18k→AGND = 0.13 V, GAIN Hi-Z = 20 V/V |
| U3/U4 | SLVSH07 Table 6-1 (DRV8316CR column) | 41/41 pins match; NC 1/24 float |
| U5 | AP2112K SOT25: 1 VIN 2 GND 3 EN 4 NC 5 VOUT | match |
| U6 | SCAS283 PW column | match; 4Y floats, 4A/4B to GND |
| U7 | INA239 Table 5-1 | match; IN+ = VBAT_SW (supply side), IN− = VBAT; MISO tri-states with CS high (l.924) |
| U8 | BQ76907 Table 5-1, Table 7-1 (4S row), Table 8-3 | match: cells VC7–6/VC5–4/VC3–2/VC1–0, VC6=VC5, VC4=VC3, VC2=VC1; SRP/SRN/TS to VSS; DSG/CHG float; REGSRC=BAT |
| U9/U10 | SCES470F pin table (1A1 3Y2 2A3 GND4 2Y5 3A6 1Y7 VCC8) | match |
| U11/U12 | SLVS832D DCK (1 VOUT 2 GND 3 OC 4 ON 5 VIN) | match; OC floats (open drain) |
| U13 | SNOSDE5A Table 5-1 | match; C12 VCAP→VS as the datasheet asks (VCAP-to-VS rating, CVCAP ≥ 0.1 µF); OV to GND per the pin text |
| U14 | DS35124 SOT353: 1 NC 2 A 3 GND 4 Y 5 VCC | match |
| Q1–Q8 | HYG015N04LS1C2 p.1 pin drawing (rendered): 1–3 S, 4 G, tab D | match; KiCad PQFN-8-EP generic pads 1–4 + EP "5" |
| D1–D5 | K on pin 1 = KiCad pad 1 (cathode) for D_SMB/D_SMA/D_SOD-123 | D1 K=VBAT, D2 K=BUCK_SW, D4 K=PSW_G, D5 K=CELL0: correct polarity |
| D3 | LED_0603 pad 1 = K (silk marker at pad 1) | K = GND, A = LED_A: correct |
| D7/D8, D9 | Nexperia BAV99 / BAT54S Table 2: 1 A1, 2 K2, 3 K1/A2; KiCad SOT-23 pads 1-2-3 | clamp/rectifier directions correct (BAV99: MTEMP→+3V3 and GND→MTEMP; BAT54S: GND→ARM_AC→W_ARM) |
| J1–J4, wire holes | vendor pinouts; `Connector_Wire:SolderWire-*` 1 pad | J4 B0…B4, J2/J3 1 VS…6 TEMP + MP; all wire holes 1 pad |
| Footprints | every non-`thumbsup:` footprint opened in `/usr/share/kicad/footprints`; numbered-pad set compared with the netlist pins | all exist; pad sets equal the netlist pins for every part |
| Custom footprints | `thumbsup:` = TI_RGF0040E (U3/U4, 41 pads), R_2512_HoLR_1-4mR (RS1–RS3), BOOMELE (J1, 20), SH1.0-6P XUNPU (J2/J3, 6 + MP) | all four listed in DESIGN §6.12 with the source drawing |
| Nets | single-pin nets: none; 2-node nets: 70 (below); pulls; decoupling | 70 two-node nets all intended; every IC power pin has its capacitor; every reset-floating input has a pull or an internal pull |
| BOM | bom.csv 62 lines, Σ Qty 188, no duplicate refs, DNP (C110–C112, C114–C116) absent; one footprint per LCSC (script) | OK |
| Classes | JLC `selectSmtComponentList/v2` for **all 62** LCSC numbers, sequential, 2.5 s gaps | BOM.md class list is exact: 24 Extended lines (U-lines = 11), 4 Preferred (R20, R22/24/26/63, R45, R14/R46), 34 Basic |
| Stock | LCSC `product/detail` + JLC, 2026-09-23 | U1 210 JLC (presale 87), LCSC 157; U2 203; **U7 101** (BOM.md "~111"); U13 8,311; U14 5,406 |
| Docs refdes | every refdes in DESIGN/BOM/README/datasheets README/spice README/calcs/CHANGES rev F exists in the netlist | OK (only "C110–C116" spans a non-existent C113, and L2–L4 are copper layers) |
| Docs values | DESIGN §3–§5, §9, BOM.md table (LCSC per line), calcs.md, arm.out, hotplug.out, spinup.out, bridge.out | matches except the findings below |

2-node nets (70), all intended: ARM_AC, BAL0–BAL3, BMS_ALERT/REG/SCL/SDA (I²C pull-ups on the compute board, by design), BOOT0,
BUCK_CB, LED_A, L_/R_ CP/CPH/CPL, L_/R_ INHA/B/C, L_/R_ S1–S3, L_/R_ SOA/B/C, L_/R_ SWBK, L_/R_ TEMPJ, L_/R_ nCS, MB_TX,
PSW_CAP, PSW_DV, U2_CPH/CPL/DVDD/IDRIVE/MODE/VCP/VDS, W_GHA–C, W_GLA–C, W_INHA–C, W_INLA–C, W_SNA–C (net-tie to GND),
W_SOA–C.

## Findings

| ID | Sev | Where | Finding | Evidence | Fix |
|---|---|---|---|---|---|
| R6B-01 | MAJOR | `spice/sim_hotplug.py` l.63 (`bsink`); results in `hotplug.out`, DESIGN §3.1 R15 row, §5, §7.2; calcs §9; CHANGES rev F R5A-06/R5B-02 row ("worst corner now 3.4 V/µs") | **The model's gate sink leaks and switches the FETs off ~0.7 V too early, so the worst re-close is never simulated.**  `bsink = Vgs/2 · 0.5 · (1 − tanh(50·(EN − vth_f)))` still sinks ~74 µA at EN = 1.14 V (vth_f = 1.027). That is more than the 60 µA gate source, so in the "min UVLO" cases the gate collapses at EN ≈ 1.14 V (bus 7.77 V), not at 1.027 V (bus 7.03 V, calcs' own minimum).  The same leak moves the nominal off point from ~7.8 V to ~8.3–8.5 V.  With the sink made sharp (`×2000`), the model gives **3.70 V/µs** at a 500 ms re-close (bus 7.11 V, C1 300 mΩ, min UVLO), not 3.38 V/µs.  At the **nominal** threshold, the 300 ms re-close (bus 7.94 V) is **hard at 2.47 V/µs**; `hotplug.out` reports it as soft (0.004 V/µs).  Hardware is still under the DRV8316's 4 V/µs abs max, but the margin is ~0.3 V/µs, not 0.6, and the published numbers are not the worst case | trace (`/tmp/r6b/motor_board/spice/sim_trace.py`, rdiv 18.7k, min UVLO): t = 400 ms (340 ms off) VBAT 7.77 V, EN 1.140, Vgs falling 11.28 V; t = 450 ms Vgs 0, BAT_IN 2.58 V.  Fixed-sink sweep (`sim_probe_fix.py`): off 300 ms 7.95 V 3.384; **400 ms 7.52 V 3.548; 500 ms 7.11 V 3.704**; 550 ms soft.  Nominal vth 1.14, 40 mΩ (`sim_probe_fix2.py`): **300 ms 7.94 V 2.470 V/µs**; 400 ms soft | Make the sink a sharp comparator (or `tanh(… ×2000)`) and the source/sink thresholds true hysteresis.  Re-sweep 300–700 ms for nominal and min UVLO, recapture `hotplug.out`.  Re-quote: "0.1–2.5 V/µs typ, ~3.7 V/µs worst (min UVLO, −40 °C C1)", and say that the margin to 4 V/µs is ~8 % |
| R6B-02 | MINOR | calcs.py l.154–156, 168 (calcs.md §9 "Bus decay", "Drain with the buck off"), calcs §2 "x4 dividers ~0.9 mA"; `sim_hotplug.py` `rdiv 18.7k`; DESIGN §3.1 R15 row, §7.2 ("~0.3–0.4 s"); CHANGES rev F R5B-03 | **The VBAT divider load is ~66 kΩ, not 18.7 kΩ, and "~0.4 s at the minimum threshold" contradicts calcs' own numbers.**  (a) The three weapon phase dividers R22/R23, R24/R25 and R26/R27 hang on W_A/W_B/W_C, not on VBAT.  With the bridge Hi-Z (disarmed, the normal state when the switch opens) they have no DC path from VBAT: the high-side body diodes point toward VBAT.  With the switch open, the only divider loads on VBAT are R63/R64 (78 k) ∥ R4/R5 (441 k) = 66 kΩ.  R5B-03 made this error.  (b) Even at 18.7 kΩ, τ = 1.93 s from 9.2 V down to the 7.03 V minimum off point takes ln(9.2/7.03)·1.93 = **0.52 s**, but the text says ~0.4 s.  With 66 kΩ, τ = 2.38 s, which gives ~0.64 s.  (c) The flat-pack drain is ~1.3–1.5 mA, not 1.6–1.9 mA.  The "wait ≥ 2 s" rule still covers all of this | netlist: R22.1 = W_A, R24.1 = W_B, R26.1 = W_C; VBAT loads: R63, R4, R15, U7.8 (VBUS), U2/U3/U4 VM (asleep once +3V3 falls).  Fixed-sink sim with `rdiv 66k`, min UVLO, 300 mΩ: 500 ms VM 7.47 V **3.566 V/µs** (still hard), 700 ms soft | Use `rdiv ≈ 66k` (or bracket 18.7k–66k), compute the window instead of hard-coding it ("~0.3–0.6 s"), fix the drain figure, and add a note to calcs §2 that the phase dividers load VBAT only while a high side conducts |
| R6B-03 | MINOR | DESIGN §3.5, the paragraph under the header table | **Stale single-sided text:** "J1 is the only part on the **bottom** side …; everything else is on top."  This contradicts §1 Build ("two-sided … low-profile passives/logic and J1 on the bottom"), §6.13 (U5–U14 and passives on the bottom) and CHANGES rev F R5D-01 | DESIGN l.316–317 vs l.36, l.464–467 | "J1 is on the bottom side (it faces the compute board), with the low-profile parts of §6.13" |
| R6B-04 | MINOR | `design/motor_board.py` comments/descriptions (the file the user draws from) | **Stale wording left in the netlist source:** l.229 "INLx = TIM1_CHxN AND **W_ARM**" and l.231 "**W_ARM** also goes to the MCU (PD2, FT)" (both are W_ARM_S; R5B-04 asked for this fix and CHANGES rev F marks it done for §2/§3.2 only).  l.136 "deep-discharge cutoff" and U2's desc "(pack **deep-discharge cutoff**)" (renamed "logic cutoff" in rev F, R5D-07).  l.97 and R15's desc "within **~1 s**" (DESIGN says ~0.3 s; see R6B-02) | motor_board.py l.97, 120, 136, 191, 229, 231 | Edit the comments; no net changes |
| R6B-05 | MINOR | `spice/README.md` "Captured results" | **arm.out is missing from the captured-results list** ("hotplug.out, bridge.out, spinup.out"), although sim_arm.py is in the table and DESIGN §5 cites arm.out.  Also, both sims finished within a few minutes here, against the stated "~1 h" / "~15 min" | spice/README l.22–23; `/tmp/r6b/arm_rerun.out`, `/tmp/r6b/hotplug_rerun.out` identical to the committed files | Add `arm.out` (date) and correct the run times |
| N-01 | NOTE | DESIGN §6.13 "bottom (≤ 1.2 mm tall) … U5–U14" | U5 AP2112K SOT25 body is 1.00–1.30 mm (Diodes table dim K).  SOD-123 (D4, D5, which sit beside U13/U8) is 1.25 mm max (CJ outline A).  Irrelevant against the 5–6 mm gap, but the stated limit is not met | AP2112K.pdf SOT25 table; B5819W_CJ.pdf SOD-123 A 1.05–1.25 | Say "≤ ~1.5 mm" |
| N-02 | NOTE | DESIGN §6.13 vs §6.6 | §6.13 puts U13 (and by its "same side as the IC" rule its gate network R1/C13/D4) on the bottom.  §6.6 wants "U13, C12, C14, R1, C13 next to Q7/Q8; the gate trace short".  Q7/Q8 are on top | DESIGN l.436, l.464–468 | State that U13 goes on top next to Q7/Q8 (or accept the gate via) |
| N-03 | NOTE | DESIGN §3.2 "a gap in the toggling of up to ~50 ms is tolerated" | That is the nominal-part figure (arm.out minimum 52 ms).  With tolerances the disarm starts at ~30 ms (§1, §9).  §3.5's "no gap longer than ~20 ms" is the binding and consistent number | arm.out; DESIGN l.35, l.180, l.334 | "~50 ms nominal, ≥ ~30 ms worst case" |
| N-04 | NOTE | R_nCS (PB4) | No external pull on R_nCS.  During MCU reset the UCPD dead-battery pull-down on PB4 (§8) overrides the DRV8316's internal 100 k nSCS pull-up (SLVSH07 RPU to AVDD), so U4 is selected while the MCU is in reset.  This is benign: SCLK/SDI have internal 100 k pull-downs (no clocks), the INA239 and U3 are deselected, and firmware disables the dead-battery pull-down first | DRV8316C.txt l.824–833, l.2495; DESIGN §8 boot order | Optional 100 k pull-up to +3V3 on R_nCS/L_nCS; or leave it as is |
| N-05 | NOTE | BOM.md stock figures | U7 INA239 is now **101** at JLC (BOM.md "~111"; presale 65).  D9 BAT54S is 286,332 (BOM.md "136k"; round-5 N-06, not refreshed).  U1 is 210 but presale 87 | JLC API 2026-09-23 | Refresh on order day; reserve U1/U2/U7 |
| N-06 | NOTE | MB_RX / R17 | With the compute board on USB and the motor board off, the compute board's idle-high TX back-feeds +3V3 through R17 10 k (~0.3 mA).  PC5 (TT_a, 4.0 V absolute) is not over-stressed | DS12288 abs max table (TT_xx 4.0 V) | None, or note it for bench work |
| N-07 | NOTE | DESIGN/BOM.md headers "2026-09-24", spice/README "hotplug 2026-09-24" | Dated one day after the parts lookups and today's run (2026-09-23) | — | Cosmetic |
| N-08 | NOTE | PA3 VBAT_SNS (TT_a) | VBAT_SNS reaches the 4.0 V TT abs max at VBAT = 31.2 V.  VBAT only gets there at a TVS clamp (SMBJ20A Vc 32.4 V), and C68 (0.87 ms) filters it.  Accepted, as for W_Vx | calcs §2 ratio 7.80 | None |

## Verdict

BLOCKER 0, MAJOR 1, MINOR 4, NOTE 8. Connections, pinouts, footprints and BOM are clean. The open items are the re-close
simulation's gate-sink leak (R6B-01) and documentation/wording (R6B-02…05).
