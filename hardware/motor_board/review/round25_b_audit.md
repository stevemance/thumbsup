# Round 25 — B: consistency audit (rev L, after round 24)

Method: package copied to /tmp/r25b (without datasheets/, review/); `design/motor_board.py` →
"237 refs (205 placed components), 160 nets, 67 BOM lines / checks: OK"; `design/calcs.py` ran
clean; `diff -rq` of the regenerated copy against the tree is empty (netlist.csv, nets.md, bom.csv,
mcu_pinmap.md, calcs.md byte-identical).  /tmp/r25b deleted afterwards.  Line numbers are DESIGN.md
unless stated.  Only DESIGN.md and README.md changed in round 24 (file times), so the hardware
cross-checks were re-run as spot checks and the DESIGN.md §8/§8.1/§9 text was read in full.

**Result: 0 BLOCKER, 0 MAJOR, 2 MINOR, 4 NOTE.**

## Verified clean

- **Counts:** bom.csv 67 lines, Qty sum 199; 6 DNP (C110–C112, C114–C116) outside the CSV; 205
  placed.  DESIGN :37, BOM.md :4–5, README :7 agree.  Revision labels: DESIGN :9 "rounds 11–24",
  README :7 "twenty-four".
- **LCSC:** every LCSC code in DESIGN.md, README.md and datasheets/README.md is in bom.csv; the
  codes in BOM.md that are not in bom.csv are all named alternates (C1235414, C529413, C18213,
  C2150467, C2846803, C53055322, C6053).
- **MCU pins/AFs:** every pin named in §3.2–§3.4, §7.21 and §8 (PC13 TIM1_BKIN, PB7 TIM8_BKIN,
  PC14, PC15, PD2, PA11/PA12, PC9/PB4, PC10–12, PA0/PA1/PB11 COMP3/1/6, PA8/PA9/PC3, PB12/PB13/PB1,
  PB6/PC7/PB9, PB2/PC2/PC8, PC0/PC1/PA10, PA7/PB14/PB15, PC6/PB5/PB0, PA15/PB3/PB10, PA2–PA6, PF0/PF1,
  PC4/PC5, PB8) matches mcu_pinmap.md and the §3.4 ADC table.
- **IC pinouts:** U3 (DRV8316C) pins 3–11, 21–23, 25, 27–32, 37–40 and U2 (DRV8323RH) pins 7, 26,
  29–32, 34, 35, 47 in netlist.csv match the §3.2/§3.3 tables; U6/U7/U13/U14 pins match their text.
- **Every DRV8316 SPI word** in DESIGN.md (frame B15 W, B14–B9 address, B8 parity; SLVSH07 §8.5
  "even number of 1s"), recomputed: 0x0603, 0x0606 (CTRL1); 0x087C, 0x097D (CTRL2); 0x0A4E (CTRL3);
  0x0C90, 0x0D10, 0x0D94, 0x0C14 (CTRL4); 0x0F00 (CTRL5); 0x1019 (CTRL6); 0x1818, 0x1915 (CTRL10) —
  all even.  0x0C10 and 0x0D90 are correctly called odd (:691–692).  CTRL4 decode checked against
  SLVSH07 Table 8-21: 0x90 = DRV_OFF 1, OCP_DEG 0.6 µs, OCP_LVL 16 A, latched; 0x94/0x14 = same at
  OCP_LVL 24 A (15–30 A per the EC table).  The INA239 words (0x1000, 0xB480, 0x76C0, 0x17C0) are not
  parity-framed.
- **§8.1 round-24 edits:** B24-01 (still-rotor alignment after step 4, :675 and :614 agree); B24-02
  (one unlocked re-coast sequence, :677); B24-03 (row 7 clear path, :614); B24-04 ("per unit"
  gone, latency compensation only, :675); N1 ("TIM8 BKINE", :677); row 6(b) → §8 timer-row path
  (:686 ↔ :614); resume-OCP count vs encoder-suspect branch (:675 ↔ :677) consistent; 24 A window
  (≤ ~50 ms, register check 0x94/0x14) vs BKINE window (≤ ~10 ms) are separate and consistent;
  §9 step 2 "no motion" expectation (:733); §9 step 6 safe-resume speed/coast-down item (:765)
  matches the :675 reference.  R24D-01 (every-reading |I| statistic) and R24D-02 (zero or positive
  torque command) are in :652.

## Findings

| # | Class | Evidence | Finding | Suggested fix |
|---|---|---|---|---|
| B25-01 | MINOR | :652 "(not a signed mean …)" vs later in the same cell "(a suspension drops those samples and restarts the **100 ms mean**)"; :652 "also paused while the weapon has a braking command" vs "(the weapon **never suspends it** …)" | The R24D-01 fix changed the row 0 statistic to "\|I\| < ~30 mA on every reading for ≥ ~100 ms", but the suspension clause still says it restarts "the 100 ms mean".  An implementer following that sentence rebuilds the averaged statistic whose zero crossing after a weapon brake was the round-24 MAJOR.  In the same cell, the new braking-command pause contradicts the older "the weapon never suspends it" literally (the latter means the weapon's *negative power* term), and the pause's effect on the run (drop/restart?) is not stated. | "restarts the 100 ms run"; "the weapon's negative power never suspends it (only its braking command pauses it, which also restarts the run)". |
| B25-02 | MINOR | :675 step (2) "if an nFAULT raised by the pin is still latched (decided at the §9 step 2 bench check), **send one CLR_FLT** before the Release"; :612 "a locked device ignores CLR_FLT" / Fault recovery 0x0603 → 0x097D → 0x0606; :733 §9 step 2 | Every other DRV8316 action in §8.1 now names its full bracketed word sequence; this one names a bit.  At step (2) the chip is locked (the configuration and every coast end with 0x0606), so a bare 0x097D is ignored and step (4)'s single repeat is spent on every resume (the R24A-N3 consequence this clause was meant to remove).  The cited "§9 step 2 bench check" does not exist as a decision item: :733 only checks nFAULT high after a complete drives resume, which passes either way (step 4's repeat hides the latched case). | "send one fault recovery (CTRL1 0x0603 → CTRL2 0x097D → CTRL1 0x0606) while the chip is still coasted"; add to §9 step 2: "with a chip coasted by CTRL4, lower the DRV_OFF pin and note whether its nFAULT stays low (decides the step (2) fault recovery)". |
| N1 | NOTE | :677 step (4) "if still low, re-coast and recover …, once, and repeat from (2); else classify …, then TIM8 BKINE = 1 again"; :675 "BKINE = 0 from here to the end of step 4, ≤ ~10 ms"; :675 no-encoder branch "between retries restore BKINE = 1 and MOE = 0" | When step (4)'s repeat re-enters (2) and (2) now takes the no-encoder branch (OCP at a zero preset → encoder suspect → fixed coast time, possibly seconds), the text does not say explicitly that BKINE = 1 / MOE = 0 are restored before that wait; "then TIM8 BKINE = 1 again" reads as belonging to the else branch.  No safety effect (the chip is coasted, CLL still acts). | "…and repeat from (2) (restore TIM8 BKINE = 1 and MOE = 0 first if (2) waits)". |
| N2 | NOTE | :675 "wait for the next Z pulse … take the angle from the stored Z offset"; :614, :759 (Z offset stored in §9 step 5) | Before §9 step 5 has stored a Z offset (first power-ups, §9 steps 2–5) the turning-rotor branch has no offset to use; only "Z offset stale" is routed to the no-encoder branch. | Treat "no stored Z offset" like "Z offset stale". |
| N3 | NOTE | :597 boot-order summary of "drives resume" | Summary omits the BKINE = 0 step (it says "re-enables … BKINE") and the still-rotor alignment after step 4.  It defers to §8.1, so harmless. | Optional. |
| N4 | NOTE | review/CHANGES.md:457 and :467 | The "Round 24" section is duplicated (the second copy adds the R24A/R24D rows). | Delete the first copy. |
