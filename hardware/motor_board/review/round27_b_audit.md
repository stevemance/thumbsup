# Round 27 — B: consistency audit (rev L, after round 26)

Method: package copied to /tmp/r27b (`rsync -a --exclude datasheets --exclude review`);
`design/motor_board.py` → "237 refs (205 placed components), 160 nets, 67 BOM lines / checks: OK";
`design/calcs.py` ran clean.  `diff -r` of the regenerated copy against the tree is empty
(netlist.csv, nets.md, bom.csv, mcu_pinmap.md, calcs.md byte-identical).  /tmp/r27b deleted
afterwards.  Line numbers are DESIGN.md unless stated.  §8, §8.1 and §9 were read in full, and the
rest of DESIGN.md was read for cross-references.  Markdown rendering was checked with
`pandoc -f gfm`.

**Result: 0 BLOCKER, 0 MAJOR, 2 MINOR, 1 NOTE.**

## Verified clean

- **Counts:** bom.csv has 67 lines and 199 unique designators.  The 6 DNP parts (C110–C112,
  C114–C116) are outside the CSV, giving 205 placed.  The 237 refs are those 205 plus 11 wire
  holes, TP1–TP12, NT1–NT3, JP1/JP2 and MH1–MH4.  DESIGN :37, BOM.md :4–6 and README :7 agree.
- **netlist.csv ↔ nets.md:** the same 759 (ref, pin, net) triples.  There are 161 nets including
  NC (160 without it), and 233 refs with pins (MH1–MH4 have no pins).
- **BOM.md ↔ bom.csv:** every LCSC number in the "Parts to watch" table matches the CSV.  The
  class list gives 11 IC lines, which matches the CSV.  datasheets/README.md indexes exactly the
  PDFs present in datasheets/.
- **Values and footprints cited in DESIGN §3** match bom.csv and nets.md.  Checked parts:
  - power entry: C12, C13, C14, C18, R1, R13–R15, R32, D4, D10, RS4, R2/R3, C2
  - U2 straps and buck: R44–R46, C20–C23, C27–C30, R20/R21, L1, D2
  - DRV8316 support: R300/R302 (and R400/R402), C300–C310, C305, R301
  - CSA filters: R70–R72, C80–C82, R80–R82, C90–C92
  - MCU support: C60–C68, C71, C74, R16, R61, R63/R64, R33
  - ARM chain: C15, D9, C16, R41, U14, R19
  - sensor chain: JP1/JP2, U9–U12, R54–R59, R110–R117, R52/R53, C72/C73, D7/D8
  - cell monitor: R6–R11, C4–C9, C11, D5
  - test pads TP1–TP12; J1 pins 1–20 (§3.5 table)
- **MCU pins and AFs:** every pin in §3.2–§3.4, §7.21 and §8 matches mcu_pinmap.md and the §3.4 ADC
  table.  I re-checked these against `ref/STM32G474RxTx_pins.xml`:
  - comparator inputs: COMP3_INP PA0, COMP1_INP PA1, COMP6_INP PB11
  - OPAMP5_VINP PC3
  - ADC channels of PA2–PA6, PB1, PB12, PB13, PA8, PA9
  - DAC1_OUT1 = PA4 and DAC2_OUT1 = PA6 (the reason for using the internal DACs)
- **Timer arithmetic** (§3.4, §8):
  - ARR 3542 = 2 × 1771 (24/48 kHz at 170 MHz)
  - regular-trigger windows: 568/170 = 3.34 µs, 2311/170 = 13.59 µs; PWM-mode-1 mirror 2974/1231 → 24.18/34.43 µs
  - regular group 371 ADC cycles at 42.5 MHz = 8.7 µs
- **IC pinouts** re-checked against the PDFs:
  - U2 DRV8323RH RGZ: pins 1–36 including FB 1, VDRAIN 7, VREF 26, nFAULT 28, straps 29–32, ENABLE 33, CAL 34, AGND 35
  - U3/U4 DRV8316C RGF: 1–32
  - U7 INA239: 1–4
  - U13 LM74502 DDF: 1–8
  - U11/U12 TPS22945 DCK: 1–5
  - U14 and U5 match their datasheet pin lists
- **Every DRV8316 SPI word** was recomputed (B15 = W, B14–B9 = address, B8 = even parity over all 16 bits):
  - CTRL1 0x0603, 0x0606
  - CTRL2 0x087C, 0x097D
  - CTRL3 0x0A4E
  - CTRL4 0x0C90, 0x0D10, 0x0D94, 0x0C14
  - CTRL5 0x0F00
  - CTRL6 0x1019
  - CTRL10 0x1818, 0x1915

  All are even and all addresses are correct.  0x0C10 and 0x0D90 are correctly called odd
  (:691–692).  Data fields check out against their descriptions:
  - CTRL4: 0x10 = 16 A latched; 0x14 = 24 A; bit 7 = DRV_OFF
  - CTRL6 0x19: BUCK_PS_DIS, BUCK_CL, BUCK_DIS
  - CTRL10: DLY_TARGET 8 = 1.8 µs, 5 = 1.2 µs

  No SPI word appears outside DESIGN.md.  The INA239 words are not parity-framed and are correct:
  - SHUNT_CAL 0x1000 = 4096
  - ADC_CONFIG 0xB480: MODE B, 150 µs/150 µs, AVG 1
  - SOVL 0x76C0 = 38.0 A
  - BOVL 0x17C0 = 19.0 V
- **Release order after round 26:** the order is the same everywhere.
  - Step 2 (:675): 0x0603 → 0x0D10 → 0x097D → 0x0606.
  - Step 3 (:676): 0x0603 → 0x0D10 [→ 0x097D; 0x0C14 in the 24 A window] → 0x0606.
  - §8 Release (:612): 0x0603 → 0x0D10 → 0x0606, pointing to §8.1.
  - Boot-order summary (:597): the per-chip Release comes after MOE and the back-EMF preset.
  - Step-4 re-coast (:677) and fault recovery (:612) are bracketed by unlock/lock.
  - The 24 A window (0x0D94 → 0x0C14 → back to 0x0D10 within ~50 ms; register check 0x94/0x14) is consistent between steps 2 and 3.
- **Row 0 wording** (:652) is consistent with rows 1 and 2 (:653–654), §8 Weapon safety (:618),
  §9 step 6 (:769) and the switch-open tests (:782–785):
  - "every reading", "restarts the 100 ms every-reading run"
  - "regenerating torque command" (B26-01 landed; no "explicit braking" left)
  - positive-only instant coast; the protective coast ends the pause
  - the brake does not resume until pack current returns
- **Regen current limit:** the ≤ ~10 A current limit (:609) is consistent with the rest of the
  package:
  - SMBJ20A at 10 A: 24.5 V + 7.9 V × 10/18.5 ≈ 28.8 V, and 28.7/7.8 = 3.68 V on PA3 (TT, 4.0 V)
  - §7.6 (:525) and the Braking row (:619) use the same ~10 A
  - row 1 halves the limit
  - §9 step 6 requires < 18.3 V
- **SPICE text vs captured output:** §3.1, §3.2, §3.3, §5 and §7.2 match hotplug.out and arm.out:
  - re-close 0.06–0.7 and 2.09 V/µs
  - bounce 2.26 V/µs, and 2.66 V/µs at −40 °C
  - Q7 16/22.0 W, 54–57 mJ
  - reversed pack 13 / 102–147 A
  - ARM 2.50–2.95 V, 7–10 edges, disarm 52–134 / 67–164 ms
- **CHANGES.md structure:** 26 round headings with no duplicates.  Every table has a header and a
  separator row, and the file ends with a newline.  The Round 26 entries match the text in
  DESIGN.md.  (Its rendering defect is part of MINOR B27-01.)

## Findings

| # | Class | Where | Finding | Fix |
|---|---|---|---|---|
| B27-01 | MINOR | DESIGN.md :652, :653, :657; design/calcs.md :111 (from calcs.py :157); review/CHANGES.md :324, :363, :365, :450, :467, :476, :480 | **Unescaped `\|` inside table cells cuts the rendered tables.**  In GFM a bare `\|I\|`, `\|W_Vx\|` or `\|\|` is a cell delimiter, and cells beyond the header count are dropped.  I rendered these with `pandoc -f gfm`:<br>• **§8.1 row 0:** the action cell renders as "I".  "Switch open → weapon coast and drives off … not a weapon latch" is gone.<br>• **Row 1:** stops at "(row 1 waits for the second, ~0.3 ms more than the other rows),".  The looks-open/over-voltage split and the "more than ~3 in 10 s → latched" rule are gone.<br>• **Row 5:** the action cell renders as "W_Vx".  "Short at standstill → latch the weapon" is gone.<br>• **calcs.md "Bus decay" row:** both the value and the basis are dropped.<br>• **CHANGES.md:** the seven rows are truncated at their first `\|I\|`.<br>The raw text is correct.  The first `\|I\|` in row 0 is already escaped, so the intent is clear.  The truncations are visible (sentences end mid-clause), but a reader of the rendered file loses the actions of three safety rows. | Escape as `\|I\|` / `\|W_Vx\|` in DESIGN.md and CHANGES.md.  In calcs.py :157, write "R15 6.8k ∥ ~66k" (or `\|\|`) and regenerate. |
| B27-02 | MINOR | :748 vs :652, :565, design/calcs.md :121, :725; review/round26_d_system.md :58–63 | **The new §9 step 4 idle-current acceptance ("pass ≥ ~100 mA") equals the design's own nominal idle estimate and has no fail branch.**<br>• Row 0 says "the board alone draws ~100 mA", and calcs.md says "~100–120 mA".  The calcs figure is a typed string, not computed.<br>• Step 4 measures the **minimum** idle current (16.8 V, drives coasted: the pit case row 0 must cover).<br>• A bottom-up figure from calcs §4/§11 is below the nominal: 3.3 V side ~120 mA plus a small compute-board idle load, through the 85 % buck, is ~55–65 mA at 16.8 V.  Adding U2 awake and two DRV8316s not switching gives ~70–100 mA.<br>• §9 step 1 already accepts "< 60 mA" at 12 V (no firmware).  With constant-power loads that is < 43 mA at 16.8 V before firmware wakes the drivers.<br>• So a healthy board can land under 100 mA and "fail" step 4, and the text does not say what follows.  R26D-N3 proposed "otherwise narrow the band", but that part was not carried over.<br>What row 0 needs is idle ≳ 2 × its ~50 mA estimate band **and** ≫ the 30 mA hold threshold. | State the criterion as a ratio: "measured minimum idle ≥ 2 × the row 0 estimate band (default band 50 mA → ≥ 100 mA); if lower, set the band to ≤ idle/2 (and keep the 30 mA hold threshold ≤ idle/3)".  Or state that step 4 sets the band. |
| B27-N1 | NOTE | :609 vs :619 | The Power budget row says "**combined** regen limited by a current limit (≤ ~10 A …)".  The Braking row gives the weapon "regen current limited to ~10 A" and the drives "same regen limit", which reads as 10 A per channel.  The drives' traction-limited regen is small, so the TVS/sense-pin margin is barely affected either way. | In :619, say "the same shared ≤ ~10 A regen budget (§8 Power budget)". |

No other inconsistencies were found in the scope audited.
