# Round 28 B: consistency audit (rev L, after round 27)

Scope: netlist.csv, nets.md, bom.csv, mcu_pinmap.md, BOM.md, DESIGN.md, README.md, calcs.md,
datasheets/README.md, spice/README.md, review/CHANGES.md.  Board area/fit and prose style are out
of scope.

**Result: 0 BLOCKER, 0 MAJOR, 2 MINOR, 5 NOTE.**

## Method and reproduction

* Copied the package to `/tmp/r28b/` without `datasheets/` and `review/`.
  `python3 design/motor_board.py` printed `237 refs (205 placed components), 160 nets, 67 BOM lines` / `checks: OK`.
  `python3 design/calcs.py` ran cleanly.  `diff -rq` against the tree showed **no differences**, so
  nets.md, netlist.csv, bom.csv, mcu_pinmap.md and calcs.md are current.
* Re-ran `spice/sim_hotplug.py` and `spice/sim_arm.py` with the hardware venv.  The output matches
  `hotplug.out` and `arm.out` byte for byte.
* bom.csv has 67 lines and Qty sums to 199.  Each line's Qty equals its designator count, and no
  designator appears twice.  205 placed − 199 = 6 DNP (C110–C112, C114–C116), as BOM.md:4–6,
  DESIGN.md:37 and README.md:7 say.
* Every value, footprint and LCSC number in DESIGN §3.1–§3.4 and in the BOM.md "Parts to watch"
  table matches bom.csv.  The IC pinouts in DESIGN match netlist.csv: U2 pins 1/7/26/29–35/47/48,
  U3/U4 3–11/21–25/27–32/37–40, U6, U7, U13, U14, D9, J1 (all 20 pins), J2 and TP1–TP12.  The
  "11 Extended IC lines" count is correct.
* The MCU pins and AFs in DESIGN §3.2–§3.4, §7.21 and §8 match mcu_pinmap.md.  This covers the
  ADC table (PA0 ADC1_IN1, PB11 ADC1_IN14, PA1 ADC2_IN2, PB1 ADC3_IN1, PB13 ADC3_IN5,
  PB12 ADC4_IN3, PA8/PA9 ADC5_IN1/2, PA2/PA3/PF0 ADC1, PA4/PA5/PA6/PF1 ADC2), the comparators, and
  TIM1/8/20/2/3, SPI3, USART1, PD2, PC13/PB7/PC15 and PC14.
* **DRV8316 SPI words.**  Every word in the package has the right address (bits 14–9) and even
  parity: 0x0603, 0x0606, 0x087C, 0x097D, 0x0A4E, 0x0C90, 0x0D10, 0x0D94, 0x0C14, 0x0F00,
  0x1019, 0x1818, and 0x1915 (TI's value, cited only).  0x0C10 and 0x0D90 appear only as the named
  odd-parity counter-examples (DESIGN.md:692–693).  The CTRL4 data bits check out: 0x90/0x10 are
  DRV_OFF with OCP_DEG 01 and 16 A latched, and 0x94/0x14 are the same at 24 A.
* **INA239 constants.**  SHUNT_CAL 0x1000 = 4096, SOVL 0x76C0 = 38 A, BOVL 0x17C0 = 19.0 V and
  ADC_CONFIG 0xB480 (MODE Bh, VBUSCT = VSHCT = 2h, AVG 0) are consistent with each other.
* **Markdown tables.**  Every table in the 10 package .md files has the same column count on
  every row, and none has an unescaped `|` in a cell or a `|` inside a code span.  CHANGES.md
  (rounds 1–27, one heading each, uniform two-column tables) is well-formed.
* **Round-27 edits.**  The R27A-01 current log is in §9 step 6.  The §3.2 short-spike wording, the
  §9 step 4 "half the measured idle" rule, the Braking row pointer, the Z-count "encoder suspect"
  rule and the §7.2 window are all present.  The regen numbers check out: 28.7 V clamp,
  3.69 V nominal / 3.75 V worst, 4.0 V at ~12–14.5 A, and ~0.4 s at 10 A for 64 J.

## Findings

| # | Class | Evidence | Problem | Fix |
|---|---|---|---|---|
| B28-01 | MINOR | DESIGN.md:9 "rev L rounds 11–26"; README.md:7 "after twenty-six adversarial review rounds"; CHANGES.md:494 "Round 27 … → rev L (text only)" | Round 27 changed rev L text, but the labels were not moved on.  This is the same item as B24-05 and B26-02. | "rounds 11–27" / "twenty-seven". |
| B28-02 | MINOR | DESIGN.md:510 (round-27 addition) "to ~1.3 ms under a sustained 2.5 A load: ≤ 2.33 V/µs at 0 °C, 2.82 V/µs only at C1's −40 °C limit"; against DESIGN.md:36 "keep **every** simulated switch/bounce event ≤ 2.75 V/µs even with C1 at its −40 °C ESR limit"; calcs.py:131 → calcs.md:87 "every switch/bounce event <= 2.75 V/us … C1 up to its -40 C ESR"; DESIGN.md:511–512 (the next sentence of the same item) "loaded bounce ≤ 2.26 V/µs … at its aged 0 °C bound … and 2.66 V/µs even at its −40 °C limit"; also DESIGN.md:208 and :434 (2.26 / 2.66) | (a) The new −40 °C figure, 2.82 V/µs, breaks the "every simulated event ≤ 2.75 V/µs" claim in §1 and calcs §7.  The in-environment worst case is now 2.33 V/µs at 0 °C, not the 2.26 V/µs that §7.2 states one sentence later and §3.3/§5 repeat.  (b) "Under a sustained 2.5 A load" misstates the case.  Per round27_d_system.md:19 and :60, these runs kept the 20 A weapon load and added a second 2.5 A load that continues below the 5 V weapon cutoff.  All values are still under the 4 V/µs limit, so this is a documentation contradiction, not a hazard. | Change §1 and calcs.py:131 to "≤ 2.82 V/µs (≤ 2.33 V/µs within 0–50 °C)", or scope them to the captured `hotplug.out` cases.  In §7.2 say "20 A weapon load plus 2.5 A continuing below the weapon cutoff (review/round27_d_system.md)".  Qualify the 2.26 / 2.66 figures in :511–512 (and optionally :208/:434) as the 0.1–0.8 ms `hotplug.out` cases. |
| N1 | NOTE | DESIGN.md:186 "≤ ~3.75 V at the pins"; DESIGN.md:610 "PA3–PA5 at ≤ ~3.7 V" | These are the same 10 A / 28.7 V case, given as the worst-tolerance and the nominal value (round27_a_hardware.md:52, :85).  Both are correct, but they are unlabelled. | Optional: "3.69 V nominal, 3.75 V with 1 % tolerances". |
| N2 | NOTE | DESIGN.md:569–570 "LiHV (4.35 V/cell) plus regen reaches ~18.8 V" | This is round 5's 17.4 V + 1.4 V, which uses the 20 A rise (DESIGN.md:620).  With today's ≤ ~10 A regen limit it is ~18.1–18.6 V (round26_d_system.md:119 uses +1.2 V at 10 A).  That still reaches the 18.5 V coast at the upper end, so the "4.20 V/cell only" conclusion stands. | Optional: "~18.6 V at the 10 A regen limit". |
| N3 | NOTE | DESIGN.md:763–764 "… PA3–PA5 reach 4.0 V at ~12–14 A)⏎(below the 18.5 V coast), else lower the regen limit" | The round-27 insertion leaves "(below the 18.5 V coast)" hanging after the current clause.  It belongs to "VBUS peak must stay < 18.3 V". | Move the parenthetical next to "< 18.3 V". |
| N4 | NOTE | DESIGN.md:749 "expect ~95–113 mA; row 0's 50 mA estimate band must stay ≤ about half the measured minimum"; DESIGN.md:566 and calcs.md "~100–120 mA (~1.6–1.9 W)" | The two idle ranges differ slightly.  1.6–1.9 W at 16.8 V is 95–113 mA, so §7.17 and calcs have mA and W that disagree.  At the low end of §9's range (95 mA), half is 47.5 mA, so the 50 mA band would already need narrowing.  The "narrow it" clause covers this. | Optional: use one range everywhere. |
| N5 | NOTE | review/round13_d_system.md:20, round14_a_hardware.md:36, round18_d_system.md:21, round20_d_system.md:30, round2_b_drive_sensors.md:31–32 (unescaped `\|I\|`-style pipes); r5_bom.md:87–95 (rows one cell short) | Tables in the frozen historical review reports render with shifted columns.  The package documents and CHANGES.md are clean. | None needed (archives); escape them only if the reports are meant to render. |

## Checked and clean (no finding)

* Refs, values, footprints and LCSC numbers agree across bom.csv, BOM.md, DESIGN and nets.md.
  C3/C17/C24/C40/C69/C70, the local decoupling, appear only in the generated lists, which is enough
  to draw from.
* The 36 datasheets/README.md entries match the 35 PDFs plus the README.  spice/README.md matches
  the scripts and the captured outputs.
* The spice/arm.out figures quoted in DESIGN §3.2, §3.5 and §5 are right: 7–10 edges, 12 ms at
  500 Hz, 52–134 / 67–164 ms disarm, and a ~50 ms nominal gap.
* The hotplug.out figures quoted in DESIGN §3.1, §5 and §7.2 are right.  The only exceptions are the
  round-27 extras in B28-02.
* The §8 Power budget, Braking and Timer inputs rows, §8.1 drives-resume steps 2–4, and §9 steps 4
  and 6 are internally consistent (SPI sequences, 24 A window, BKINE handling, the 18.0 < 18.3 < 18.5
  < 19 < 20 V chain).  The only issues are N2–N4.
