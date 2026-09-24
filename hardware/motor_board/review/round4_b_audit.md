# Round 4 — B: mechanical netlist / pin / footprint / BOM / docs audit (rev D)

Auditor: adversarial, read-only.  No design file was edited: the whole package was copied to `/tmp/mb`
and every script ran on the copy.  Date: 2026-09-23 (PDT).

## Method

* `python3 design/motor_board.py` (run on the copy) printed `222 refs (190 placed components), 155 nets, 60 BOM lines` / `checks: OK`.
  The regenerated `netlist.csv`, `nets.md`, `bom.csv` and `mcu_pinmap.md` are byte-identical to the checked-in files.
  `python3 design/calcs.py` also regenerates a `calcs.md` identical to the checked-in one.
* Datasheets were converted with `pdftotext -layout`.  Pin tables were compared by pin number and pin name.
* Footprints were checked by script: each non-`thumbsup:` footprint was opened in `/usr/share/kicad/footprints/*.pretty`,
  and its set of pad names was compared with the netlist pin set for that part.
* LCSC product JSON (`wmsc.lcsc.com/ftps/wm/product/detail`) and JLC `selectSmtComponentList/v2` were queried one
  request at a time, with a 3 s gap and back-off on retry.  This covered all 14 new rev D C-numbers, plus a JLC class check of every other BOM line.
* SPICE (KiCad libngspice via `hardware/tools/spice/ngspice_shared.py`) was used for two checks: the dynamic-ARM
  charge pump (new netlist, below) and the BAT_IN peak in the unmodified `sim_hotplug.netlist()`.

## Findings

| ID | Sev | Where | Finding | Evidence | Fix |
|---|---|---|---|---|---|
| R4B-01 | **MAJOR** | C15/D9/C16/R41 (dynamic ARM); DESIGN §1 Safety, §3.2 "Dynamic ARM", §9 step 3; `motor_board.py` lines 238–240, R41 desc | **When W_ARM_CLK is held HIGH, W_ARM takes ~1.3 s (not ~130 ms) to fall below 0.8 V.**  A hung compute board leaves its GPIO in its last state, so it stops high about half the time.  In that case C15 (1 µF, 10× C16) sits between a stiff 3.3 V and ARM_AC.  As R41 drains C16, D9's rectifier diode conducts, so C15's charge feeds W_ARM.  The decay time constant is then (C15 + C16)·R41 ≈ 1.1 s, not C16·R41 = 100 ms.  The ~130 ms figure holds only when the clock stops LOW or the header is unplugged (R18 then makes a falling edge). | ngspice with a 500 Hz 3.3 V clock for 50 ms, then held: **held high → < 1.5 V after 743 ms, < 0.8 V after 1339 ms**; held low → 67 ms / 120 ms.  W_ARM while toggling = 3.08 V.  Script: `/tmp/armsim/arm.py` (C15 1 µ, D9 as BAT54-like diodes, C16 100 n, R41 1 M, R18 100 k, 50 Ω source) | Add a bleeder from ARM_AC to GND (100 kΩ 0402, C25741, already on the BOM).  Simulated: held high 135 ms, held low 118 ms to < 0.8 V, and W_ARM = 3.02 V while toggling.  Alternative: C15 → 10 nF (112/101 ms, but W_ARM only 2.51 V, which is thin against the 2.31 V MCU VIH).  Then fix the text and add a "hold W_ARM_CLK **high**" case to §9 step 3 |
| R4B-02 | MINOR | DESIGN §5 row "Power-switch closure" | "peak VM dV/dt **0.003–0.055 V/µs** in every case" does not match the captured output.  Every closure case in `hotplug.out` is 0.003–0.009 V/µs, and DESIGN §1 and calcs §9 say ≤ 0.01 / 0.003–0.009 | `spice/hotplug.out` rows 3–8: 0.004, 0.009, 0.009, 0.003, 0.004, 0.008 V/us | Change to 0.003–0.009 V/µs |
| R4B-03 | MINOR | DESIGN §3.1 (R15 row), §5, §7.2; calcs.md §9 "Bus decay"; CHANGES R3A-02 | The re-close numbers are not what the simulation produces.  The text says "1.3–3.3 V/µs" (§3.1, §7.2, calcs, CHANGES) and "0.1–2.4 V/µs, **3.3 V/µs worst with C1 at 300 mΩ**" (§5).  `hotplug.out` has only C1 = 40 mΩ re-close cases: 0.119 / 1.347 / 2.184 / 2.430 V/µs.  `sim_hotplug.py` has **no** 300 mΩ re-close case, so nothing in the package supports the 3.3 figure.  The sim docstring also says the switch opens "at 20 ms", but the code and the output say 60 ms | `hotplug.out` re-close block; `sim_hotplug.py` l.136–139 (`esr=0.040` only), l.22–23 vs l.45 (`60e-3`) | Add the 300 mΩ re-close case to the script and recapture, or quote 0.1–2.4 V/µs everywhere; fix the docstring |
| R4B-04 | MINOR | `design/calcs.md` §7 (from `calcs.py` l.127–130) | Stale rev C rows contradict §9 and DESIGN: "Plug-in VM ramp: 0.04 V/us **with the Q8 inrush limiter**"; "Inrush current 5–8 A peak for ~3 ms"; "**Q8** dissipates 0.05 J".  In rev D, Q7 is the linear FET, the inrush is ~1 A for ~6 ms, the pulse is 53 mJ, and the peak dV/dt is 0.003–0.009 V/µs.  The ripple row also says "C1 polymer and **4 × 10 uF** MLCC", but there are 7 (C25, C26, C31, C302, C308, C402, C408) | calcs.md §7 vs §9; bom.csv line "10uF 50V … Qty 7" | Rewrite the three rows from `hotplug.out`; change 4 → 7 |
| R4B-05 | MINOR | BOM.md "Classes" | **R13 470 k (C25790) is JLC Preferred** (Extended + `preferredComponentFlag`), but it is missing from the Preferred list, so a reader takes it as Basic.  Every other class statement checks out: all 22 Extended lines match the list, the 5 Preferred lines are R13, R20, R22/24/26/63, R45 and R46, and every other line is `base` | JLC C25790: `componentLibraryType expand`, `preferredComponentFlag true`, stock 333,194 | Add "R13 470 k" to the Preferred list |
| R4B-06 | MINOR | calcs.md §9 "Drain with the buck off" | "then **~1 uA** (U13 shutdown)" ignores R13 + R14 (570 k from BAT_IN, which stays on the pack): 6.5 V / 570 k = 11 µA, so ~12 µA in total.  U8 adds ~146 µA if the balance lead is plugged | LM74502 I(SHDN) 0.9 µA typ; netlist R13 BAT_IN–PSW_EN, R14 PSW_EN–GND | "~12 µA (EN/UVLO divider + U13 shutdown)" |
| R4B-07 | MINOR | DESIGN §7.1 | Reversed main pack **with the balance lead plugged** is not a "no high-current path" case.  With GND = pack+ and B0 = pack− (−16.8 V), D5 (anode GND, cathode CELL0) is forward-biased.  About 164 mA then flows through R6: 2.7 W into an 0603, so R6 burns open.  U8's VC0–VC7 are also driven 4–17 V below VSS (abs min −0.3 V).  The reversed pack **alone** is correctly handled: see the BAT_IN check below | nets.md CELL0: D5.1(K), R6.2; GND: D5.2(A) | Say that this combination destroys R6/U8 (unless the fix is a series fuse or a keyed harness), rather than "no high-current path" |
| N-01 | NOTE | BAT_IN (no TVS before the switch) | At plug-in, C14 (100 nF) rings with the lead: **BAT_IN peaks at 32.0–32.5 V and Q7 VDS at 31.4–31.9 V** (40 V part), with PSW_G up to 29.3 V (C13 is 50 V; fine).  Nothing in DESIGN states this margin.  U13 VS (65 V), C14 (50 V) and R13 are fine | `sim_hotplug.netlist()` unmodified, cases nominal / stiff 50 nH / 300 nH: max v(bat_in) 32.0/32.1/32.5 V | Document it in §5; a switch that bounces repeats it |
| N-02 | NOTE | C13 22 nF 50 V 0402 X7R; Q7 peak power | C13 is biased at 2–29 V.  X7R DC-bias loss makes the ramp faster than the 2.7 V/ms figure (IGATE / C nominal), and Q7's peak power rises in proportion.  `hotplug.out` already shows **21.5 W** at the 77 µA gate current, while DESIGN/BOM/calcs quote "16 W peak".  The energy (≈ ½CV²) is unchanged, and dV/dt stays ≪ 4 V/µs | hotplug.out row "gate source at the 77 uA max": 21.5 W | Quote 16–22 W; consider C13 in 0603 50 V (C1532-class 0603) for less derating |
| N-03 | NOTE | D9 BAT54S leakage | This is the same mechanism as R3B-01.  When the board is hot, the reverse leakage of D9's rectifier diode (W_ARM → ARM_AC during the low half-cycle) discharges C16.  About 20–30 µA at 85 °C (Nexperia Fig. 2 typ) gives 0.2–0.3 V of droop per 1 ms half-cycle, which is fine.  At ~125 °C (~200 µA typ) the droop would cross VIH.  The fix in R4B-01 does not change this | BAT54S datasheet IR 2 µA max at 25 °C, typical curves only above that | Check W_ARM ripple with the board hot at bring-up |
| N-04 | NOTE | DESIGN §4a | "the **0402** 100 Ω inputs are not rated for balance current": R6 is now 0603 (R7–R10 are 0402) | netlist R6 `R_0603_1608Metric` | "the 100 Ω input resistors" |
| N-05 | NOTE | `motor_board.py` l.131 (D1 desc); CHANGES N3-2 | D1 still says "after the **RPP** FET" (rev C term).  CHANGES "C110–C116 → 1 nF" includes C113, which does not exist | nets.md | Cosmetic |
| N-06 | NOTE | BOM.md U13 row | The "~8,300" stock figure is not in any of the lookup files BOM.md cites (r6, round2_e, round3_b).  Confirmed today: JLC 8,311 / presale 8,230, Extended | JLC C3236215 | Cite this audit or add it to a lookup file |
| N-07 | NOTE | LM74502 SRC in reverse | Abs max "SRC to GND, V(VS) ≤ 0: ≤ V(VS) + 0.3 V".  With a reversed pack, SRC (PSW_S) is held by Q7's body diode at ≈ BAT_IN + (µA-level Vf).  This is TI's own back-to-back topology (SNOSDE5A §8.3.3), so it is accepted | SNOSDE5A §6.1 | — |
| N-08 | NOTE | Dates | DESIGN, BOM.md and spice/README are dated 2026-09-24.  The files were written 2026-09-23 22:15–22:20 PDT (= 09-24 UTC) | `ls --full-iso` | Fine if UTC is intended |

## 1. Pin audit (netlist ↔ datasheet)

| Part | Source | Result |
|---|---|---|
| U13 LM74502DDFR | SNOSDE5A Table 5-1 | 1 EN/UVLO = PSW_EN, 2 GND, 3 N.C (floats: "No connection"), 4 VCAP, 5 VS = BAT_IN, 6 GATE = PSW_G, 7 OV = GND ("Connect OV pin to ground when OV feature is not used"), 8 SRC = PSW_S (common source).  All match.  C14 100 nF VS–GND (pin table: 100 nF; ROC min 22 nF).  C12 220 nF VCAP–VS (≥ 10 × Ciss, Ciss 4.05 nF × 2 → 81 nF; §9.2.2.4 selects 0.22 µF).  Cdvdt through RG to GND per Fig. 8-2 / Eq. 2.  UVLO: rising 1.16/1.24/1.32 V and falling 1.027/1.14/1.235 V × 5.7 → on 6.6/7.1/7.5 V and off 5.9/6.5/7.0 V, as documented |
| Q7, Q8 (and Q1–Q6) HYG015N04LS1C2 | HUAYI pin figure "S S S G / D D D D" | 1–3 S, 4 G, 5 = D (tab).  Q7 D = BAT_IN, Q8 D = VBAT_SW, S = PSW_S, G = PSW_G: the back-to-back common-source pair.  Q7's body diode blocks forward surge and Q8's blocks a reversed pack.  VGS ±20 V vs GATE–SRC ≤ 15 V (charge pump off at 11–13.9 V): OK |
| U1 STM32G474RET6 | ST XML (script) | 64/64 pins and all required AFs pass (script check) |
| U2 DRV8323RH RGZ-48 | SLVSDJ3D Table 6-4 | All 48 + PAD match (re-extracted: e.g. 29 MODE, 30 IDRIVE, 31 VDS, 32 GAIN, 46 NC, 48 nSHDN) |
| U3/U4 DRV8316CR | SLVSH07 Table 6-1 | All 40 + PAD match (NC 1, 24; nSCS 36; SDO 33; VREF/ILIM 37) |
| U5 AP2112K SOT-25 | pin table | 1 VIN, 2 GND, 3 EN, 4 NC, 5 VOUT |
| U6 SN74LVC08A PW | SCAS283 | 1A1 1B2 1Y3 2A4 2B5 2Y6 GND7 3Y8 3A9 3B10 4Y11 4A12 4B13 VCC14 |
| U7 INA239 DGS | Table 5-1 | 1 CS … 10 IN+; IN+ = VBAT_SW (supply side of RS4), IN− = VBAT: correct high-side polarity |
| U8 BQ76907 | unchanged since round 3 (verified there) | — |
| U9/U10 LVC3G17 DCU | SCES470F | 1A1 3Y2 2A3 GND4 2Y5 3A6 1Y7 VCC8 |
| U11/U12 TPS22945 DCK | SLVS832D | VOUT1 GND2 OC3 (open drain, floats) ON4 VIN5 |
| D9 BAT54S | Nexperia Table 2: 1 A1, 2 K2, 3 K1/A2 | 1 = GND, 3 = ARM_AC, 2 = W_ARM → diode 1 clamps ARM_AC ≥ −Vf and diode 2 rectifies into W_ARM.  Correct |
| D7/D8 BAV99 | Nexperia Table 2: 1 A1, 2 K2, 3 K1/A2 | 1 = GND, 2 = +3V3, 3 = MTEMP: dual clamp.  Correct |
| D1, D2, D3, D5 | KiCad pad 1 = K | D1 K = VBAT, D2 K = BUCK_SW, D3 K = GND, D5 K = CELL0: correct |
| J1 | DESIGN §3.5 | pins 7/18 NC (spare), 19 = W_ARM_CLK beside 20 = GND; all 20 match the table |
| J2/J3, J4, JP1/JP2, TP1–TP12 | DESIGN §3.3/§3.4 | match (TP order 3V3, SWDIO, SWCLK, NRST, GND, W_ARM, W_EN, DRV_OFF, W_nFAULT, VBAT, 5V, GND) |

All NC pins may float: U2.32 GAIN (Hi-Z strap = 20 V/V, intended), U2.46, U3/U4.1/.24, U5.4, U6.11 (output), U8.9/.10 (DSG/CHG open per TI Table 8-3), U11/U12.3 (open-drain flag), U13.3, J1.7/.18.

## 2. Nets

* Every net has ≥ 2 nodes.  Each signal net has a driver and a load; the off-board drivers are MB_RX, W_ARM_CLK and the BMS I²C lines (the compute board, which also carries their pull-ups).
* **70 two-node nets**, all intended: ARM_AC, BAL0–BAL3, BMS_ALERT/SCL/SDA/REG, BOOT0, BUCK_CB, LED_A, L_/R_ CP/CPH/CPL, INHA–C, S1–S3, SOA–SOC,
  SWBK, TEMPJ, nCS; MB_TX; PSW_CAP; PSW_DV; U2_CPH/CPL/DVDD/IDRIVE/MODE/VCP/VDS; W_GHA–C, W_GLA–C, W_INHA–C, W_INLA–C, W_SNA–C, W_SOA–C.
  Rev D added 3 of them: ARM_AC (C15–D9), PSW_CAP (C12–U13 VCAP) and PSW_DV (R1–C13).  BAT_NEG is gone.
* Decoupling: every power pin has its capacitor.  U13 VS C14 and VCAP C12; U7 C3; U8 C9/C11; U2 VM C24, VIN C27, VCP C21, DVDD C22, VREF C23; U3/U4 as before; U1 C60–C64, C65, C66+C71, C74; U5 C69/C70; U6 C40; U9/U10 C47/C50; U11/U12 C45/C48 + C46/C49.
* Pulls: NRST R16 → +3V3; MB_RX R17 → +3V3; W_ARM_CLK R18 → GND; W_ARM R41 → GND; W_EN R40 ↓; DRV_OFF R50 ↑; INA_nCS R12 ↑; W_nFAULT R42 ↑ (U2 nFAULT and U7 ALERT, both open drain); L/R_nFAULT → own AVDD; W_INLx_M R47–R49 ↓; BOOT0 R61 ↓.  All go to the correct rails.
* Voltage ratings:
  * BAT_IN reaches U13 VS (±65 V), C14 50 V, C12 (sees VCAP–VS ≤ 13.9 V; 25 V part), R13 (0402, 50 V), and Q7 D (40 V; 32 V plug-in peak, N-01).
  * Reversed pack (BAT_IN = −16.8 V): U13 VS −65 V OK; EN/UVLO and OV stay within [V(VS), 65 + V(VS)]; Q8 blocks (VDS 16.5 V); nothing downstream sees it.
  * VBAT (≤ 32.4 V TVS clamp) only reaches parts rated ≥ 35 V: U3/U4 VM 40 V; U2 65 V; U7 VBUS 85 V; C21/C303/C403 50 V; R4 0603 75 V; R15 0805 150 V.
  * +5V reaches U5 (6 V), TPS22945 (6 V), JP → VS → LVC3G17 inputs through 1 k (6.5 V): OK.
  * No 16 V capacitor is on a net above 3.7 V.  BUCK_EN reaches 3.7 V at the 32.4 V clamp.

## 3. Documentation ↔ netlist / BOM / calcs / hotplug.out

These all check out:
* Counts: 184 assembled + 6 DNP, 60 lines (DESIGN §1, BOM.md, README).  bom.csv quantities sum to 184, and each Qty equals its designator count.
* §3.1 values: U13, Q7/Q8, R1/C13, R13/R14, R15, RS4/U7, D1, C1, R4/R5/C10, D3/R62; cell block R6 0603 / R7–R10 0402, C4–C8, R11, C9, C11, D5.
* §3.2 C25/C26/C31; §3.3 all refdes and values, including R113/R117 2.2 k 0603, D7/D8 BAV99 and C110–C116 1 nF DNP; the ~17 passives per drive channel.
* §3.4 TP1–TP12 list; §3.5 J1 table; §6.12 custom footprint list; §4 table vs calcs.
* BOM.md watch table; datasheets/README (BAT54S/BAV99 pin mapping, Q7/Q8); spice/README; CHANGES round-3 rows.

The mismatches are R4B-02 … R4B-07 and N-04/N-05 above.

## 4. Footprints

The pad set of every standard footprint equals the part's netlist pin set.  Each footprint exists in `/usr/share/kicad/footprints`:
PQFN-8-EP_6x5mm_P1.27mm_Generic (5), Texas_DDF0008A_SOT-8_1.6x2.9mm_P0.65mm (8), MSOP-10 (10), QFN-20-1EP_3.5x3.5 (21), Texas_RGZ0048A (49), LQFP-64 (64), TSSOP-14 (14), VSSOP-8_2.3x2 (8), SOT-353 (5), SOT-23-5 (5), SOT-23 (3: D7–D9), D_SMB, D_SMA, D_SOD-123, LED_0603, CP_Elec_10x10.5, L_Changjiang_FNR5040S, R/C 0402/0603/0805/1206/2512 (2), JST_XH_S5B-XH-A Horizontal (5), SolderJumper-3 (3), NetTie-2 (2), TestPoint_Pad_D1.0mm (1).
MountingHole_2.2mm_M2 has a single unnamed `np_thru_hole` pad, matching MH1–MH4 with no pins.
All seven `thumbsup:` footprints are listed in DESIGN §6.12, each with its source: SolderPad 4×6 / 3×5 / 2×3, TI_RGF0040E, R_2512_HoLR_1-4mR, BOOMELE_1.27-2x10P_SMD (20 pins), SH1.0-6P_RA_XUNPU (1–6 + MP).

## 5. BOM: new rev D C-numbers (queried 2026-09-23)

| C-no | Refs | MPN / maker | Package | Ratings (LCSC) | JLC class | JLC stock | Verdict |
|---|---|---|---|---|---|---|---|
| C3236215 | U13 | LM74502DDFR / TI | TSOT-23-8 | 3.2–65 V high-side controller | Extended | 8,311 (presale 8,230) | OK (not the H variant) |
| C1532 | C13 | 0402B223K500NT / FH | 0402 | 22 nF 50 V X7R | Basic | 678,793 | OK (N-02) |
| C25790 | R13 | 0402WGF4703TCE / UNI-ROYAL | 0402 | 470 k 1 % 50 V | **Preferred** | 333,194 | OK; see R4B-05 |
| C17772 | R15 | 0805W8F6801T5E / UNI-ROYAL | 0805 | 6.8 k 1 % 125 mW 150 V | Basic | 322,937 | OK (41 mW) |
| C26083 | R41 | 0402WGF1004TCE / UNI-ROYAL | 0402 | 1 M 1 % | Basic | 2,723,349 | OK |
| C2500 | D7, D8 | BAV99,215 / Nexperia | SOT-23 | 100 V 215 mA, 500 nA @ 80 V | Basic | 1,071,192 | OK |
| C47546 | D9 | BAT54S,215 / Nexperia | SOT-23 | 30 V 200 mA, 2 µA @ 25 V | Extended | 136,407 | OK |
| C4190 | R113, R117 | 0603WAF2201T5E / UNI-ROYAL | 0603 | 2.2 k 1 % 100 mW 75 V | Basic | 8,027,692 | OK (74 mW fault case) |
| C22775 | R6, R11 | 0603WAF1000T5E / UNI-ROYAL | 0603 | 100 Ω 1 % 100 mW | Basic | 12,572,480 | OK |
| C1523 | C41–C43 (+ DNP C110–C116) | 0402B102K500NT / FH | 0402 | 1 nF 50 V X7R | Basic | 3,808,801 | OK |
| C21120 | C4–C8, C12 | CL10B224KA8NNNC / Samsung | 0603 | 220 nF 25 V X7R | Basic | 830,364 | OK (C12 ≤ 13.9 V) |
| C52923 | C15, C22, C46, C49, C69, C70 | CL05A105KA5NQNC / Samsung | 0402 | 1 µF 25 V X5R | Basic | 6,728,068 | OK |
| C1525 | 21 × 100 nF 16 V | CL05B104KO5NNNC / Samsung | 0402 | 100 nF 16 V X7R | Basic | 25,326,025 | OK |
| C14663 | C14, C2, C24, C28, C300/301, C400/401 | CC0603KRX7R9BB104 / YAGEO | 0603 | 100 nF 50 V X7R | Basic | 49,156,958 | OK |

The bom.csv checks pass:
* DNP C110–C116 are excluded.
* Quantities sum to 184.
* Each LCSC number appears on exactly one line and with one footprint (the script check and a CSV re-check agree).
* Low stock to reserve: U2 203, U7 111, U1 314 (JLC today).

**Verdict: 1 MAJOR, 6 MINOR (0 BLOCKER), 8 NOTE — not clean.**
