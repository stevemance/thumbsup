# Round 24 — B: consistency audit (rev L, after round 23)

Method: package copied to /tmp/r24b (without datasheets/, review/); `design/motor_board.py` →
"237 refs (205 placed components), 160 nets, 67 BOM lines / checks: OK"; `design/calcs.py` ran
clean; every regenerated file in `design/` (netlist.csv, nets.md, bom.csv, mcu_pinmap.md,
calcs.md) is byte-identical to the tree.  /tmp/r24b deleted afterwards.  Line numbers are DESIGN.md
unless stated.

## Verified clean

- **Counts:** bom.csv 67 lines, Qty sum 199; 6 DNP (C110–C112, C114–C116) out of the CSV; 199 + 6 =
  205 placed.  DESIGN :37, BOM.md :4–5 and README :7 agree.
- **LCSC:** every BOM.md table row's refs map to the same LCSC code as bom.csv; every LCSC code in
  DESIGN.md and datasheets/README.md is in bom.csv.
- **MCU pins** used in §8/§8.1 (PC13 TIM1_BKIN, PB7 TIM8_BKIN, PC14 DRV_OFF, PC15 R_nFAULT, PD2,
  PC11, PB4/PB6, PA0/PA1/PB11, PC3, PA8/PA9) match mcu_pinmap.md.  U3 pinout in §3.3 matches netlist.csv.
- **Every DRV8316 SPI word** (frame B15 W, B14–9 address, B8 parity, even parity over 16 bits per
  SLVSH07 §8.5):

  | Word | Addr | Data | Parity | Decoded against SLVSH07 Tables 8-18…8-24 |
  |---|---|---|---|---|
  | 0x0603 / 0x0606 | 03h CTRL1 | 03 / 06 | even | unlock / REG_LOCK |
  | 0x087C | 04h CTRL2 | 7C | even | rsvd 1, SDO push-pull, SLEW 200 V/µs, 3x PWM |
  | 0x097D | 04h CTRL2 | 7D | even | same + CLR_FLT |
  | 0x0A4E | 05h CTRL3 | 4E | even | rsvd 1, OVP 22 V on, SPI_FLT_REP off nFAULT, OTW_REP 0, PWM_100 0 |
  | 0x0C90 | 06h CTRL4 | 90 | even | DRV_OFF 1, DEG 0.6 µs, 16 A, latched |
  | 0x0D10 | 06h CTRL4 | 10 | even | released, 16 A |
  | 0x0D94 / 0x0C14 | 06h CTRL4 | 94 / 14 | even | coasted / released at OCP_LVL 24 A |
  | 0x0F00 | 07h CTRL5 | 00 | even | CSA 0.15 V/A |
  | 0x1019 | 08h CTRL6 | 19 | even | BUCK_PS_DIS, BUCK_CL 150 mA, BUCK_DIS |
  | 0x1818 | 0Ch CTRL10 | 18 | even | DLYCMP_EN, DLY_TARGET 8h = 1.8 µs |
  | 0x1915 (TI value, cited) | 0Ch | 15 | even | 1.2 µs |
  | 0x0C10 / 0x0D90 (cited as wrong) | 06h | — | odd | correctly called odd at :691–692 |

  Register-check expectations (:612 CTRL2 0x7C, CTRL3 0x4E, CTRL4 0x10/0x90, 0x94/0x14 in the 24 A
  window :675, CTRL5 0x00, CTRL6 0x19, CTRL10 0x18, reset CTRL2 0x60) agree with the words and the
  datasheet reset values.
- **References:** every §-reference resolves (§6.12/§6.13, §7.2/.3/.15/.16/.17/.21, calcs §5/§10/§11,
  §9 steps 2/4/5/6 for t_split, idle draw, Z offset, λ, row 5 threshold, safe-resume speed).
  Weapon rows 0–12 and drive rows 1–7/6a cross-refs resolve.  Parentheses balance in :597–:782.
- Round-23 edits applied consistently: boot order :597 and the §8 DRV8316 row :612 say back-EMF
  preset / Release only inside drives resume; the rewrite ends coasted; row 0's weapon clause
  (:652) is self-consistent with the plausibility test (that test needs the weapon *motoring*);
  the latch word :637 lists left/right-crossed; §9 step 6 :771–772 expects both drives latched.

## Findings

| # | Class | Evidence | Finding | Fix |
|---|---|---|---|---|
| B24-01 | MINOR | :675 "BKINE = 0 from here to the end of step 4, ≤ ~10 ms"; :676 step 3 "a still rotor without a valid angle is aligned now"; :614 alignment is two steps "~100 ms each", "one drive at a time"; :677 step 4 waits for nFAULT only afterwards | The B23-01 move of the alignment into step 3 puts a ≥ ~200 ms (≥ ~400 ms for two still drives aligned in turn) current injection inside the BKINE = 0 window that step 2 bounds at ≤ ~10 ms, and before step 4 has confirmed nFAULT high on the just-released chip.  A literal implementation either breaks the 10 ms bound or aligns a chip with an unconfirmed fault. | Say the still-rotor alignment runs after step 4 (nFAULT high, BKINE = 1 again), with FOC at zero current until then; boot-order summary :597 can add "then aligns a still rotor". |
| B24-02 | MINOR | :677 "if still low, re-coast the chip (CTRL4 0x0C90), run the fault recovery CTRL1 0x0603 → CTRL2 0x097D → CTRL1 0x0606" | After step 3 the chip is locked (Release ends CTRL1 0x0606).  As sequenced, the coast word precedes the unlock and is ignored; CLR_FLT then re-enables the bridge with CTRL4 still 0x10 (released) and MOE = 1, breaking the "coasted until released" invariant (:612).  Steps 1 and the 24 A window (:674, :675) use the same shorthand but have no competing explicit sequence next to them. | Write it as one sequence: CTRL1 0x0603 → CTRL4 0x0C90 → CTRL2 0x097D → CTRL1 0x0606 (or "per-drive coast (below), then the fault recovery"). |
| B24-03 | MINOR | :614 "Return to encoder mode only after edges resume and a Z matches the stored offset (never after a left/right-crossed report, §8.1 drive row 7)"; :688 row 7 now latches both drives "until an operator clear and a clean one-at-a-time re-alignment" | Stale from the pre-round-23 row 7 (sensorless, keep driving, R23D-N4).  "Never" now contradicts the row 7 clear path, after which the drives must run on their encoders again. | "(not while the left/right-crossed latch is set, §8.1 drive row 7)". |
| B24-04 | MINOR | :675 "its angle error calibrated per unit (§9 step 5)"; :754–759 step 5 | Dangling reference: step 5 measures the Z offset and λ but has no angle-error (or latency) calibration item; the resume preset's 15° budget depends on it. | Name what is calibrated (Z offset? MT6701 INL sweep? latency?) and add it to step 5, or point to the Z-offset item explicitly. |
| B24-05 | MINOR | DESIGN.md:9 "rev L rounds 11–22"; README.md:7 "after twenty-two adversarial review rounds" | Round 23 has been applied (CHANGES.md :442) but the labels were not advanced (same item as B22-08). | "rounds 11–23" / "twenty-three". |
| N1 | NOTE | :677 "then BKINE = 1 again"; :606 TIM20 "BKINE = 0" | Step 4's restore applies to TIM8 only; TIM20 must stay BKINE = 0.  The boot order (:597) says "TIM8" explicitly; step 4 does not. | "then TIM8 BKINE = 1 again". |
| N2 | NOTE | :675 "an OCP at a zero preset marks the encoder suspect … does not count toward a latch" | A real standstill phase short on a drive with a working encoder is then reported as an encoder fault and retried every ~0.5 s forever (never latches).  Energy per retry is negligible and the chip self-protects, so acceptable; the report should say "OCP at zero preset" rather than only "encoder suspect". | Report wording only. |
| N3 | NOTE | :652 "with the switch closed a regenerating drum still leaves a pack current" | False when motoring drives absorb the drum's regen (pack ≈ 0 while braking the drum with the switch closed).  Consequence is only a weapon coast and an immediate catch-spin restart when current returns (already specified), so no safety effect. | Qualify "unless the drives absorb it". |
| N4 | NOTE | :733 §9 step 2 "no motors connected yet, so it only releases" | With sensors absent the encoder reads "not counting" → the still-rotor branch, which also runs an alignment that ends "too little motion → sensorless, report" (:614).  Harmless; the expectation text just omits the report. | Optional: "(expect a 'no motion' alignment report)". |

## Counts

BLOCKER 0, MAJOR 0, MINOR 5, NOTE 4.
