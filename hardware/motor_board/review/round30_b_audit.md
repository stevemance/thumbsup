# Round 30 — B: consistency audit (rev L)

Scope: cross-file consistency of the rev L package: netlist.csv, nets.md, bom.csv, mcu_pinmap.md, BOM.md, DESIGN.md, README.md, calcs.md, datasheets/README.md and spice/README.md.  Also checked: DESIGN.md internal numeric consistency, the parity of every DRV8316 SPI word, Markdown tables, revision/round labels and whether review/CHANGES.md is well-formed.  Settled items in CHANGES rounds 1–29 are not re-raised unless they are wrong.  Out of scope: board area/fit, prose style and the archived per-round reports.

## Method

* Copied the package to `/tmp/r30b` (rsync, excluding `datasheets/` and `review/`).  `design/motor_board.py` printed `237 refs (205 placed components), 160 nets, 67 BOM lines` and `checks: OK`.  `design/calcs.py` ran with rc 0.
* Diffed the regenerated `netlist.csv`, `nets.md`, `bom.csv`, `mcu_pinmap.md` and `calcs.md` against the tree: **all identical**.  Also re-ran `spice/sim_hotplug.py` and `spice/sim_arm.py` from the copy.  Their outputs match `hotplug.out` and `arm.out` exactly (apart from trailing whitespace).  `/tmp/r30b` was deleted afterwards.
* bom.csv: 67 lines, Σ Qty = 199, and the designator count equals Qty on every line.  No LCSC number appears on two lines, and C110–C112 / C114–C116 are absent (6 DNP).  205 placed − 6 DNP = 199.  This matches README:7, BOM.md:4–5, DESIGN.md:37 and the nets.md DNP line.  BOM.md:44 "ICs U1–U14 (11 lines)" is correct.
* BOM.md "Parts to watch" and the DESIGN §3.1–§3.5 values, refs and LCSC numbers agree with bom.csv and motor_board.py for every part checked.  That covers all IC, FET, diode, connector, shunt and L1 lines, plus C12–C19, C300–C310, R1/R4/R13–R15/R32/R33/R41/R44–R46/R302, the CSA filters, the sensor network and TP1–TP12.  The J1 pin table (DESIGN §3.5) matches the netlist pin for pin.
* IC pinouts: re-read the INA239, LM74502, TPS22945 and BQ76907 pin tables in `datasheets/`, and they match the netlist.  The others are unchanged since rounds 27–29.
* MCU: re-checked against `ref/STM32G474RxTx_pins.xml`: the ADC channels in the §3.4 table, the COMP3/COMP1/COMP6 inputs on PA0/PA1/PB11, OPAMP5_VINP on PC3, and TIM1_BKIN/TIM8_BKIN on PC13/PB7.  The 16 analog inputs claimed in §1 were counted on the pin map.
* DRV8316 SPI words, decoded (R/W, address, parity, data) and checked against SLVSH07 Tables 8-18 … 8-24.  Each has even parity and the intended fields: 0x0603 / 0x0606 (CTRL1 unlock/lock), 0x087C / 0x097D (CTRL2: reserved 01, SDO push-pull, 200 V/µs, 3x, CLR_FLT), 0x0A4E (CTRL3: OVP 22 V on, SPI_FLT_REP 1, OTW_REP 0), 0x0C90 / 0x0D10 / 0x0C14 / 0x0D94 (CTRL4: DRV_OFF, OCP_DEG 0.6 µs, 16 / 24 A, latched), 0x0F00 (CTRL5 0.15 V/A), 0x1019 (CTRL6 0x19), 0x1818 / 0x1915 (CTRL10 1.8 / 1.2 µs).  The odd-parity 0x0D90 and 0x0C10 appear only as counter-examples (DESIGN.md:692–693).  INA239 words: SHUNT_CAL 0x1000, ADC_CONFIG 0xB480, SOVL 0x76C0 = 38.0 A and BOVL 0x17C0 = 19.0 V are all correct.
* DESIGN figures checked against calcs.md, hotplug.out, arm.out and spinup.out.  All agree except the items below:
  * soft-start ramp and energies, re-close, bounce and reversed-pack figures;
  * ARM levels, edge counts and disarm windows;
  * spin-up 25.6 k rpm / 0.52 s / 22 A / 14.1 V (and the 15 / 25 A cases);
  * UVLO figures (9.0 / 9.8 / 7.7–10.1 / 10.8, buck 9.2 / 10.4 / 7.4–10.3);
  * drive losses, the R302 figures, the board heat total of 4.4 W, the 120 / 450 mA logic budget, the INA239 range and loss, Q7+Q8 2.0–2.5 W, the VDS trip 62–93 A;
  * top speed and FOC update counts, odometry, the NTC short current, τ = 2.3 s, VBAT_SNS_H 25.7 V / ~109 kΩ, TIM1/TIM8 ARR, the regular-trigger CCR ranges vs the µs windows, and the regular group time of 8.7 µs.
* Every relative link in the package .md files resolves.  The datasheets/README table lists exactly the PDFs present.  A column-count check over every table in the package .md files and CHANGES.md (escaped pipes and code spans handled) found no broken row and no table without a separator or blank line.  CHANGES.md has Round 1 … Round 29 headings in order, with no duplicates, and each has a two-column table.  The §7.x / §9 step / §6.x cross-references point at the right items.

## Findings

| ID | Class | Evidence | Finding | Fix |
|---|---|---|---|---|
| B30-01 | MINOR | DESIGN.md:9 "rev L rounds 11–28"; README.md:7 "after twenty-eight adversarial review rounds"; review/CHANGES.md:516 "## Round 29 (round29_a, b, d) → rev L (text only)" | Round 29 changed rev L text, but the labels still stop at round 28.  This is the same slip as B24-05, B26-02 and B28-01. | "rounds 11–29" / "twenty-nine" (and bump them with every future text round). |
| B30-02 | MINOR | DESIGN.md:422 (§4b) "50 µs–4.1 ms per conversion (e.g. 280 µs shunt + 280 µs bus ≈ 1.8 kHz)" vs DESIGN.md:618 "shunt and bus conversion ≤ 150 µs each", DESIGN.md:621 "VBUSCT = VSHCT = 2h = 150 µs", DESIGN.md:633 "at 150 µs conversions", DESIGN.md:653 "3 consecutive conversions (~1 ms)" | The §4b example is a leftover from before R9D-03 / R20A N-03.  The firmware contract fixes both conversions at 150 µs, so this board measures pack V/I at ~3.3 kHz (300 µs per shunt + bus pair), not 1.8 kHz.  280 µs is code 3h, which §8 rules out, and the "Measured" column contradicts §8. | "150 µs shunt + 150 µs bus (§8) ≈ 3.3 kHz". |
| B30-N1 | NOTE | design/motor_board.py:118 "the 0-5 uA EN sink adds only 0.3-0.5 V" vs calcs.py:154 (typ uses 3 µA) and calcs.md:110 / DESIGN.md:108 "0–5 µA" | Round 29 (B29-N3) widened the sink range to 0–5 µA but left its consequence at 0.3–0.5 V, which is the old 3–5 µA figure.  0–5 µA × 100 k adds 0–0.5 V.  The thresholds themselves are right. | "adds at most 0.5 V (0.3 V at the 3 µA typ)". |
| B30-N2 | NOTE | design/motor_board.py:231 "(8.8 us; …)" vs DESIGN.md:561 "τ ≈ 8.7 µs" and DESIGN.md:184 "≪ ~9 µs"; motor_board.py:198 "VDS OCP 0.13 V (~60 A hot …)" vs DESIGN.md:160 / calcs.md:78 "62 A" | These are rounding differences in netlist descriptions.  68 k ∥ 10 k × 1 nF = 8.72 µs, and the hot VDS trip is 62 A.  Neither changes a value to be drawn. | Optional: "8.7 us"; "~62 A hot". |

## Summary

**0 BLOCKER, 0 MAJOR, 2 MINOR, 2 NOTE.**

* The generators run clean (`checks: OK`) and every generated output matches the tree.  The two re-run SPICE captures also reproduce exactly.
* Counts are 199 parts / 67 lines / 6 DNP everywhere.  Refs, values, footprints, LCSC numbers, IC pinouts and MCU pins/AFs agree across all files.
* Every DRV8316 SPI word has even parity and the intended field values.
* Markdown tables and links are intact, and CHANGES.md is well-formed.
* Only two things are wrong:
  * The round labels were not moved on for round 29.
  * A stale 280 µs INA239 conversion example in §4b contradicts the §8 150 µs setting.
