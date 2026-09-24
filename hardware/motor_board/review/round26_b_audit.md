# Round 26 — B: consistency audit (rev L, after round 25)

Method: package copied to /tmp/r26b (`rsync -a --exclude datasheets --exclude review`);
`design/motor_board.py` → "237 refs (205 placed components), 160 nets, 67 BOM lines / checks: OK";
`design/calcs.py` ran clean.  `diff -r` of the regenerated `design/` against the tree is empty
(netlist.csv, nets.md, bom.csv, mcu_pinmap.md, calcs.md byte-identical; calcs.py stdout identical).
/tmp/r26b deleted afterwards.  Line numbers are DESIGN.md unless stated.  §8, §8.1 and §9 were read
in full; the rest of DESIGN.md was read for cross-references.

**Result: 0 BLOCKER, 0 MAJOR, 2 MINOR, 1 NOTE.**

## Verified clean

- **Counts:** bom.csv 67 lines, 199 designators; 6 DNP (C110–C112, C114–C116) outside the CSV;
  205 placed.  DESIGN :37, BOM.md :4–6, README :7 agree.
- **BOM.md ↔ bom.csv:** every designator → LCSC in BOM.md matches bom.csv.  LCSC codes not in the
  CSV appear only in BOM.md and are all named alternates (C1235414, C529413, C157991, C18213,
  C2150467, C2846803, C53055322, C6053).  DESIGN.md, README.md, calcs.md and datasheets/README.md
  cite only CSV codes.  datasheets/README.md lists exactly the 35 PDFs in datasheets/.
- **Values/footprints:** ~120 designators cited in DESIGN §3 (power entry, ARM chain, U2 straps and
  buck, DRV8316 VM filter/CP/AVDD/buck parts, CSA filters, MCU support, sensor/NTC parts) match
  bom.csv comment and footprint.
- **MCU pins/AFs:** every pin named in §3.2–§3.4, §7.21 and §8 matches mcu_pinmap.md and the §3.4
  ADC table (the generator checks AFs against the ST pin database).
- **IC pinouts:** U2 (all 49 pins), U3 (all 41), U13, U14 in netlist.csv match the §3.2/§3.3 text
  and tables (VDRAIN 7, VREF 26, straps 29–32, CAL 34, AGND 35, VIN 47, nSHDN 48; DRV8316 3–11,
  21–23, 25, 27–32, 36–40).  DRV_OFF / nFAULT / nCS nets match §3.3/§3.4.
- **Every DRV8316 SPI word** (B15 W = 0, B14–B9 address, B8 even parity over all 16 bits),
  recomputed: CTRL1 0x0603, 0x0606; CTRL2 0x087C, 0x097D; CTRL3 0x0A4E; CTRL4 0x0C90, 0x0D10,
  0x0D94, 0x0C14; CTRL5 0x0F00; CTRL6 0x1019; CTRL10 0x1818, 0x1915 — all even, addresses correct.
  0x0C10 and 0x0D90 are correctly called odd (:691–692).  The new round-25 sequences — the folded
  Release 0x0603 → 0x097D → 0x0D10 → 0x0606 (:675), the step-4 re-coast 0x0603 → 0x0C90 → 0x097D →
  0x0606 (:677), fault recovery (:612) — are all bracketed by unlock/lock and use only these words.
  INA239 words (0x1000, 0xB480, 0x76C0, 0x17C0) are not parity-framed.
- **Round-25 edits landed:** R25A-01/B25-02 fold (:675) and §9 step 2 decision item (:733) agree;
  BKINE window "≤ ~12 ms … not a hard 10 ms timeout" (:675; no other 10 ms BKINE figure remains);
  R25D-01 pause keyed on a regenerating FOC torque command, ended by any protective coast, no brake
  resume with |I| < 50 mA (:652), row 1 sentence (:653), current-type regen limit (:609), §9
  expectation (:769); R25D-N1 positive-only instant coast (:652); R25D-N2 18.5 V coast → row 1
  (:618); switch-open |I| logging (:784–785); "restarts the 100 ms every-reading run" (:652).
- **Cross-references:** §9 step 2 (:733) ↔ resume step 2; §9 step 4 idle current (:748) ↔ row 0;
  t_split (:751–753) ↔ row 7; Z offset / λ (:759) ↔ resume step 2 and §8 timer row; row 5 threshold
  and ΔV/ΔI (:761) ↔ row 5; safe-resume speed (:765) ↔ resume step 2; §6.6 VM dV/dt ↔ §9 step 6
  (:760); switch-open tests at the end of step 6 (:782) ↔ step 3 pointer (:740).  Parentheses
  balance over :591–625, :652–653, :673–677, :730–736, :760–774.
- **review/CHANGES.md:** 25 round sections (Round 1 … Round 25), one heading each, each followed by
  a two-column table header; no duplicate section (the round-24 duplicate is gone); file ends
  cleanly.

## Findings

| # | Class | Evidence | Finding | Suggested fix |
|---|---|---|---|---|
| B26-01 | MINOR | :652 "also paused while the weapon is under FOC with a regenerating torque command — an explicit brake **or a speed-loop deceleration**" vs, later in the same cell, "a regenerating weapon never suspends it (**only its explicit braking command pauses it**, above)"; CHANGES.md:480 (R25D-01 "pause keyed on a regenerating FOC torque command (brake or speed-loop decel)") | Leftover of the B25-01 wording that R25D-01 replaced.  The parenthetical now contradicts the pause definition it points back to: read literally, a speed-loop deceleration is not paused.  That is the R25D-01 §5 case (an unpaused end-of-decel zero crossing can dwell > 100 ms inside ±30 mA after repeated row 1 halvings → a false switch-open hold with the switch closed).  Rare and non-latching, but the row is the firmware contract. | "(only its regenerating torque command pauses it, above)". |
| B26-02 | MINOR | DESIGN.md:9 "rev L rounds 11–24"; README.md:7 "after twenty-four adversarial review rounds"; CHANGES.md:471 "Round 25 … → rev L (text only)" | Round 25 changed rev L text, but the labels were not advanced (same item as B22-08 / B24-05). | "rounds 11–25" / "twenty-five". |
| N1 | NOTE | :675 step (2) "fold one CLR_FLT into the Release: CTRL1 0x0603 → CTRL2 0x097D → CTRL4 0x0D10 → CTRL1 0x0606"; :676 step (3) "Release that chip (CTRL1 0x0603 → CTRL4 0x0D10 → CTRL1 0x0606)"; :612 §8 Release; :597 boot order; :675 24 A window "coast 0x0D94 → release 0x0C14" | The optional fold is stated only in step (2), while the Release itself is performed in step (3), which quotes the unfolded sequence (as do §8 and the boot-order summary).  The fold combined with the 24 A window (0x0603 → 0x097D → 0x0C14 → 0x0606) is left to inference.  Step (4)'s single repeat recovers either way, so no safety effect. | Step (3): "Release that chip (CTRL1 0x0603 → [CTRL2 0x097D if step (2) says so →] CTRL4 0x0D10, or 0x0C14 in the 24 A window → CTRL1 0x0606)". |
