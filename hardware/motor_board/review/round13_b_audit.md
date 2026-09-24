# Round 13 (b): mechanical audit of rev L (after the round-12 fixes)

Auditor: adversarial netlist and documentation audit, 2026-09-24.  I edited no design file.  All regeneration and
simulation ran on copies (`/tmp/r13b/`, `/tmp/r13b_h/`).  Out of scope: board area/fit and prose style.

## Method and raw results

| Step | What I ran or read | Result |
|---|---|---|
| Netlist | `python3 design/motor_board.py` (copy) | `237 refs (205 placed components), 160 nets, 67 BOM lines`, **`checks: OK`**.  netlist.csv, nets.md, bom.csv, mcu_pinmap.md regenerate **byte-identical** to the tree |
| Calcs | `python3 design/calcs.py` (copy) | calcs.md **byte-identical** |
| Sims | `sim_hotplug.py`, `sim_arm.py` re-run in a copy with the hardware venv | output **identical** to `spice/hotplug.out` and `spice/arm.out` |
| Delta since round 12 | diff vs the round-12 snapshot (`/tmp/r12/motor_board`) | netlist.csv unchanged.  motor_board.py: L1 maker comment, R302 desc 2.26, DNP C110–C116 value "1nF 50V" (DNP, so no BOM line).  calcs.py: Q7 22.0 W / 54–57 mJ, DRV8323 heat row.  DESIGN/BOM.md/README: the round-12 rows |
| Counts | bom.csv | 67 lines, Qty sum = **199**; DNP C110–C112, C114–C116 (6); 205 − 6 = 199.  README, BOM.md, DESIGN §1 agree |
| LCSC | every LCSC number in the BOM.md "Parts to watch" table vs the refs it names (ranges expanded) | all match motor_board.py; one footprint per LCSC number (script check) |
| Footprints | every standard footprint opened in `/usr/share/kicad/footprints`, pad names vs netlist pins for every ref | all exist, pads = pins; the 4 `thumbsup:` footprints are the ones in DESIGN §6.12 |
| Refs in docs | every R/C/U/Q/D/L/J/TP/MH/RS/NT/TH/JP designator in DESIGN, BOM.md, README, calcs.md, spice/README, datasheets/README | all exist in the netlist (only false hits: layer names L2–L4, LCSC C-numbers).  Value-next-to-ref heuristic on DESIGN: no mismatches |
| MCU | ST XML: every analog/COMP/OPAMP/BKIN signal quoted in DESIGN §3.2–§3.4 and §8 | all correct (PA0 COMP3_INP/ADC12_IN1, PA1 COMP1_INP/ADC2_IN2, PB11 COMP6_INP/ADC1_IN14, PC3 OPAMP5_VINP, PC13 TIM1_BKIN, PB7 TIM8_BKIN, PB12 ADC4_IN3, PB13 ADC3_IN5, PB1 ADC3_IN1, PA8/PA9 ADC5_IN1/2, PF0/PF1 ADC1/ADC2_IN10) |
| IC pins | pdftotext of the datasheets | DRV8323RH RGZ table (FB 1 … nSHDN 48, CAL 34, GAIN 32, VREF 26, SOx 23–25), DRV8316C (FB_BK 3 … VREF/ILIM 37), LM74502 (8/8), INA239 (10/10), TPS22945 DCK (1 VOUT, 2 GND, 3 OC, 4 ON, 5 VIN; ON active-high for the '45), SN74LVC3G17 DCU (1A1 3Y2 2A3 GND4 2Y5 3A6 1Y7 VCC8), BAT54S/BAV99 orientation: all match |
| Round-12 text | each CHANGES round-12 row checked against the files | rev L labels (DESIGN:1/:9, BOM.md:1, README:7, CHANGES heading); 2.09 / 0.8–2.26 / 2.66 V/µs in §3.1/§5/§7.2 (= hotplug.out 2.092 / 2.258 / 2.662); τ ≈ 2.3 s; heat ~4.4 W (calcs §11 sums to 4.43 W; DESIGN §4 matches); §8 fault classes; §8 start angle + Z reference + encoder speed cap; §9 step 0 R302 force test (TP10 = VBAT confirmed), step 3 armed soak, step 6 regen/start-angle checks; §7.16 R44-short 6x note; §8 SDO Hi-Z (SLVSH07 8.5: SDO Hi-Z with nSCS high; CTRL2 reset 0x60, SDO_MODE = 1); L1 Changjiang — **all landed**, with the exceptions below |
| Datasheet index | files vs datasheets/README.md | 35 PDFs, 35 rows, one to one |

## Findings

| ID | Sev | Where | Finding | Evidence | Fix |
|---|---|---|---|---|---|
| R13B-01 | MINOR | DESIGN.md:576 (§7.21); DESIGN.md:608 (§8 "Weapon fast trip (required)") | **The weapon fault-latch policy is stated two ways.**  Round 12 (R12D-01) rewrote §8's Watchdog/faults row: a **single** comparator trip (no VDS OCP, VBAT normal) → catch-spin restart after ~50–100 ms; latch only on a VDS OCP or a **second** comparator trip within ~1 s.  Two older sentences still describe the round-11 policy: <br>• §7.21: "The first large trip latches the weapon off (no retries)." <br>• §8 fast-trip row: "a nuisance trip latches the weapon off, so lower it only after measuring". <br>A firmware author reading §7.21 or the fast-trip row implements latch-on-first-comparator-trip, which contradicts the §8 fault-class row | DESIGN.md:599 vs :576, :608 | §7.21: "A VDS OCP or a second comparator trip within ~1 s latches the weapon off (§8 fault classes)".  §8 fast-trip row: "…repeated nuisance trips latch the weapon off" |
| R13B-N01 | NOTE | DESIGN.md:207 (§3.3 VM row); DESIGN.md:548 (§7.16) | R12B-N03 was fixed only in motor_board.py:296.  DESIGN §3.3 still says "loaded contact bounce 3.75 → **2.2** V/µs … (review round 10 sims, **not in spice/**)".  The bounce and re-close figures are now in `spice/hotplug.out` (2.258, 2.092).  Only the fault-clear kick comes from the review sims.  §7.16 "loaded bounce 2.2 → ~3.5 V/µs" has the same rounding | hotplug.out bounce row 2.258 V/µs; motor_board.py:296 already says 2.26 | "3.75 → 2.26 V/µs, worst re-close 3.44 → 2.1 V/µs (spice/hotplug.out), weapon fault-clear kick 9–11 → ~1–2 V/µs (review round 10 sims, not in spice/)"; §7.16 "2.26 →" |
| R13B-N02 | NOTE | DESIGN.md:606 (§8 STM32 row) | R12B-N04 was half-applied.  The OPAMP5 row now reads "OPAINTOEN = 1 before **OPAMPEN**".  In RM0440 the OPAMPx_CSR enable bit is **OPAEN** | RM0440 OPAMPx_CSR | "OPAINTOEN = 1 before OPAEN" |
| R13B-N03 | NOTE | design/calcs.py:182 → calcs.md:127–128 (§10 top speed rows) | R12D-04 landed in DESIGN §3.3 and §8: field weakening only in sensorless mode, and an encoder speed cap of ≤ ~50 k rpm.  calcs §10 still says "field weakening can add some", with no qualifier | DESIGN.md:198, :607 | "…; field weakening only in sensorless mode (MT6701 55 k rpm)" |
| R13B-N04 | NOTE | DESIGN.md:106 (§3.1 Q7), DESIGN.md:386 (§4), design/motor_board.py:95, :103, BOM.md:25 | The Q7 closure energy is still "54 mJ" in five places.  calcs §9 (which §4 cites) and DESIGN §5 say **54–57 mJ**.  hotplug.out gives 53.8–56.9 mJ; nominal is 54.7 mJ at 16.5 W peak, which the text rounds to "16 W".  None of this changes a conclusion (SOA margin ≥ 2×) | hotplug.out closure rows | "54–57 mJ" in §4 at least (the row that cites calcs) |

These items are settled and I did not re-raise them: the script cannot detect an omitted pin (R11B-N11); I re-checked
every pad set by script and they all match.  The same goes for L1 Isat, the DRV8316 SDO before configuration and the
U14 thresholds at 3.0 vs 3.3 V.

**Checked and correct beyond the table:**
* The heat-budget arithmetic: 0.82 + 1.62 + 0.29 + 0.38 + 0.32 + 1.00 = 4.43 W.
* Charge-pump budget: 3 × 59 nC (HYG015N04LS1C2 Qg at 10 V) × 24 kHz = 4.2 mA.
* Start-angle wheel travel: ½ electrical rev at 6 pole pairs through 28.5:1 on a 43.2 mm wheel = 0.40 mm.
* Encoder counts: 4096 per motor rev.
* Fast-trip threshold: 1.65 − 30 × 0.04 = 0.45 V.
* R44-short check: VBAT/7.8 on W_Vx.
* R302 force test: 1 A × 0.1 Ω = 0.10 V, and no parallel DC path conducts at 0.1 V.
* CTRL2 0x087C: parity and fields.
* BOM.md Extended/IC line counts: 11 IC lines, 25 Extended.

**Verdict: 0 BLOCKER, 0 MAJOR, 1 MINOR, 4 NOTE.**  All five findings are documentation.  I found no wiring,
pin, footprint, AF, LCSC or count error.  The generated files, calcs.md, hotplug.out and arm.out all reproduce exactly.
