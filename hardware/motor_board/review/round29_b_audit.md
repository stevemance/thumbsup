# Round 29 — B: consistency audit (rev L)

Scope: cross-file consistency of the rev L package: netlist.csv, nets.md, bom.csv, mcu_pinmap.md, BOM.md, DESIGN.md, README.md, calcs.md, datasheets/README.md and spice/README.md.  Also checked: DESIGN.md internal numeric consistency, parity of every DRV8316 SPI word, Markdown tables, revision/round labels and CHANGES.md.  Settled items in CHANGES rounds 1–28 are not re-raised unless wrong.  Out of scope: board area/fit, prose style.

## Method

* Copied the package to `/tmp/r29b` (rsync, excluding `datasheets/` and `review/`).  Ran `design/motor_board.py`: `237 refs (205 placed components), 160 nets, 67 BOM lines`, `checks: OK`.  Ran `design/calcs.py` (rc 0).
* Diffed the regenerated `netlist.csv`, `nets.md`, `bom.csv`, `mcu_pinmap.md` and `calcs.md` against the tree: **all identical**.  Deleted `/tmp/r29b` afterwards.
* bom.csv: 67 lines, Σ Qty = 199.  Designator count equals Qty on every line.  No LCSC number appears on two lines.  C110–C112 and C114–C116 are absent (6 DNP).  205 placed − 6 DNP = 199.  This matches README:7, BOM.md:4–5 and DESIGN.md:37.  BOM.md "ICs U1–U14 (11 lines)" is correct.
* Spot-checked every value, footprint and LCSC number quoted in DESIGN §3.1–§3.4 and BOM.md "Parts to watch" against bom.csv: all match.  This covers C12–C19, C300–C310, R1/R13–R15/R32/R33/R41/R44–R46/R302, L1, D1–D10 and U1–U14, among others.
* IC pinouts: netlist pins for U7 (INA239), U8 (BQ76907), U9/U10 (SN74LVC3G17 DCU), U11/U12 (TPS22945) and U13 (LM74502) were checked against the pin tables in the datasheets in `datasheets/`: all match.  U3 (DRV8316C RGF) and U2 (DRV8323RH RGZ) netlist pins match DESIGN §3.2/§3.3.  The same holds for the U14, BAV99, BAT54S, D3 and Q pin notes in BOM.md and datasheets/README.md, and for J1, J2/J3, JP1/JP2, TP1–TP12, NT1–NT3 and the wire holes.
* MCU: every mcu_pinmap.md row matches the DESIGN §3.2–§3.4 text: ADC channels, TIM1/TIM8/TIM20 CHx/CHxN, TIM3/TIM2 inputs, the PC13/PB7 BKIN pins, the SPI3/USART1 pins, the COMP3/COMP1/COMP6 inputs and OPAMP5_VINP on PC3.  The STM32 datasheet confirms PA3–PA5 are TT_a and PA2 is FT_a, as §3.2/§8 state.
* Derived figures recomputed: all RC constants (0.87 ms, 1.3 ms, 4.5 ms, 22 ms, 103 ms, 8.7 µs, 1.6 µs / 99 kHz), SOVL 0x76C0 = 38.0 A, BOVL 0x17C0 = 19.0 V, SHUNT_CAL 0x1000, ADC_CONFIG 0xB480 fields, TIM1 OC6 CCR ranges 568–2311 / 1231–2974 against the [3.34, 13.59] / [24.18, 34.43] µs windows, FOC updates per electrical cycle (10.3 / 12.4; 5–6 at 24 kHz; weapon ~8), odometry 116 736 counts, and the heat-budget sum 4.43 W.  All agree.
* SPICE figures quoted in DESIGN §1/§3.1/§3.2/§3.3/§5/§7.2, calcs and spice/README were checked against `hotplug.out` and `arm.out`: re-close 0.06–0.7 and 1.8–2.09 V/µs, bounce 0.8–2.26 and 2.66 V/µs, Q7 16/22.0 W and 54–57 mJ, reversed pack 13 / 102–147 A, ARM 2.50–2.95 V, 7–10 edges, 12 ms at 500 Hz, and 52–134 / 67–164 ms.  The ~1.3 ms figures (2.33 / 2.82 V/µs) are labelled as round-27 extra cases outside `hotplug.out`.
* Markdown tables: a script counted cells (with `\|` excluded) in every table of the package .md files and CHANGES.md.  No column-count mismatches, no orphan rows, and every table has a blank line before it.
* Labels: DESIGN:9 "rev L rounds 11–28", README:7 "twenty-eight", and DESIGN:1 / BOM.md:1 "rev L, 2026-09-24" all agree.  CHANGES.md has Round 1 … Round 28 headings in order, with no duplicates.  Each heading has a two-column table, and every referenced review file exists.

## DRV8316 SPI words (frame = W0 | A5..A0 | P | D7..D0, even parity over 16 bits)

| Word | Register | Data | Ones (addr + P + data) | Parity | Data meaning checked against SLVSH07 §8.6.2 |
|---|---|---|---|---|---|
| 0x0603 | CTRL1 (3h) | 03 | 2+0+2 = 4 | OK | REG_LOCK 011b unlock |
| 0x0606 | CTRL1 | 06 | 2+0+2 = 4 | OK | REG_LOCK 110b lock |
| 0x1019 | CTRL6 (8h) | 19 | 1+0+3 = 4 | OK | BUCK_PS_DIS, BUCK_CL 150 mA, BUCK_DIS |
| 0x0A4E | CTRL3 (5h) | 4E | 2+0+4 = 6 | OK | bit6 reserved = 1, OVP_SEL 22 V, OVP_EN, SPI_FLT_REP off, OTW_REP off |
| 0x0C90 | CTRL4 (6h) | 90 | 2+0+2 = 4 | OK | DRV_OFF = 1, OCP_DEG 01, 16 A latched |
| 0x0D10 | CTRL4 | 10 | 2+1+1 = 4 | OK | DRV_OFF = 0 (reset value) |
| 0x0D94 | CTRL4 | 94 | 2+1+3 = 6 | OK | coasted, OCP_LVL 24 A |
| 0x0C14 | CTRL4 | 14 | 2+0+2 = 4 | OK | released, OCP_LVL 24 A |
| 0x0F00 | CTRL5 (7h) | 00 | 3+1+0 = 4 | OK | CSA 0.15 V/A |
| 0x1818 | CTRL10 (Ch) | 18 | 2+0+2 = 4 | OK | DLYCMP_EN, DLY_TARGET 8h = 1.8 µs |
| 0x1915 | CTRL10 | 15 | 2+1+3 = 6 | OK | (TI's 1.2 µs alternative, 5h = 1.2 µs) |
| 0x087C | CTRL2 (4h) | 7C | 1+0+5 = 6 | OK | SDO push-pull, SLEW 200 V/µs, 3x PWM |
| 0x097D | CTRL2 | 7D | 1+1+6 = 8 | OK | same + CLR_FLT |

The words described as rejected are also correctly odd: 0x0C10 = 3 ones and 0x0D90 = 5 ones (DESIGN:692–693).  The read-back values listed in the §8 DRV8316 row (0x06, 0x7C, 0x4E, 0x90/0x10, 0x00, 0x19, 0x18) match these data bytes.  Sequence order agrees in every place it appears:

* configuration: DESIGN:613
* Release and Release with CLR_FLT: DESIGN:613, 676, 677
* fault recovery: DESIGN:613
* re-coast: DESIGN:678
* per-drive coast: DESIGN:692
* 24 A window: DESIGN:676

## Findings

| ID | Severity | Where | Finding |
|---|---|---|---|
| B29-01 | MINOR | DESIGN.md:526 vs DESIGN.md:620 | **Armed brake time stated two ways.**  §7.6 says a commanded stop "can brake at the ~10 A regen limit (~0.4 s)".  The §8 Braking and reversal row says "≈ 0.5 s from full speed".  Round 28 (R28D-N2, CHANGES.md:511 "armed brake ≈ 0.5 s") corrected only the §8 row.  Fix: §7.6 "~0.4 s" → "~0.5 s". |
| B29-N1 | NOTE | DESIGN.md:590 vs DESIGN.md:618 (and :427) | The INA239 BOVL latency is given as "0.3–0.8 ms" in §7.21 and as "~0.3–0.45 ms" in the §8 INA239 timing row.  Round 16 (N-03) judged 0.8 ms a loose but consistent outer bound, so this is not wrong.  Using one figure (≤ ~0.45 ms) in both places would remove the apparent disagreement. |
| B29-N2 | NOTE | DESIGN.md:208 (and motor_board.py:296) vs DESIGN.md:434 | The pre-filter loaded-bounce figure is "3.75 → 2.26 V/µs" in §3.3 but "up to 3.76 / 4.3 V/µs" in §5.  The two come from the round-10 and round-9 sims (CHANGES R10D-01 / R9A-01).  The difference is immaterial. |
| B29-N3 | NOTE | DESIGN.md:108 vs calcs.md:110 / motor_board.py:118 | The LM74502 EN sink is "0–5 µA" in DESIGN §3.1 and in the calcs value column, but "3–5 uA" in the calcs Basis label and in the R13 description.  The worst-case numbers (7.7–10.1 V) use 0–5 µA consistently, so only the label differs. |
| B29-N4 | NOTE | design/nets.md:29, :43–48 | nets.md, which README says to draw from, lists C110–C112 / C114–C116 with no DNP marker.  The DNP status is given in BOM.md:5, DESIGN §3.3 and motor_board.py:343.  An optional "(DNP)" suffix in the generator's nets.md output would carry it to where the schematic is drawn. |

## Result

**0 BLOCKER, 0 MAJOR, 1 MINOR, 4 NOTE.**  The generators run clean (`checks: OK`) and their outputs match the tree exactly.  Counts are 199 parts / 67 lines / 6 DNP everywhere.  IC pinouts, MCU pins/AFs, refs, values, footprints and LCSC numbers agree across all files.  Every DRV8316 SPI word has correct even parity and the intended field values.  All Markdown tables are intact, and the revision/round labels and CHANGES.md are well-formed.  The only real inconsistency is the §7.6 brake time that round 28 left behind.
