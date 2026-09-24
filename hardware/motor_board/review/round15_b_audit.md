# Round 15 — B: consistency audit (rev L, after round 14)

Auditor B.  I copied the package to `/tmp/r15b/`, ran `design/motor_board.py` there (it printed `237 refs (205 placed
components), 160 nets, 67 BOM lines` / `checks: OK`) and ran `design/calcs.py`.  `diff -rq` against the tree finds no
difference: netlist.csv, nets.md, bom.csv, mcu_pinmap.md and calcs.md match the committed files byte for byte.

**Result: 0 BLOCKER, 1 MAJOR, 3 MINOR, 6 NOTE.**  Every finding is in the firmware contract (§8 / §8.1 / §9).
Nothing affects the schematic the user will draw.

## What was checked and is clean

- **Counts.**  bom.csv has 67 lines, Qty sum 199, 199 unique designators.  205 placed = 199 + 6 DNP (C110–C112,
  C114–C116).  BOM.md:4–5, DESIGN.md:37 and README.md:7 all agree.  Rev L and "rounds 11–14 / fourteen" match in
  DESIGN.md:1,9, BOM.md:1 and README.md:7.
- **BOM.md vs bom.csv.**  Every "Parts to watch" row has the same LCSC number as the bom.csv line for that ref.  The
  LCSC numbers that appear in BOM.md but not in the CSV are all stated alternates: C157991, C6053, C1235414,
  C529413, C2846803, C2150467, C18213, C53055322.  "U1–U14 (11 lines)" is correct.
- **DESIGN values vs bom.csv.**  I spot-checked 46 refs (C19, R302/R402, C309/C410, R50, R301, R19, R18, R41, C15,
  C16, R33, R12, R16, R17, R61, C13, R32, R1, R15, R13, R14, C18, R4, R5, R44–R46, R113/R117, R52, C305, R300, C307,
  C20, C21, C27, L1, R20, R21, C29, R40, R42, R47, R62).  Values and footprints match.
- **MCU pins.**  mcu_pinmap.md matches every pin and AF named in DESIGN §3.2–§3.4, the ADC table and §8.  Netlist
  facts that §8.1 relies on are true: U1 pin 1 VBAT is on +3V3; U3/U4 INLA/B/C and nSLEEP are on +3V3; DRV_OFF is
  shared (U3.21, U4.21, R50 pull-up, PC14); R301/R401 pull up to each chip's own AVDD; W_nFAULT = U2.28 + U7.3 ALERT
  + C19 + R42 + PC13.
- **Per-drive coast.**  The 6x-mode coast in §8.1 matches SLVSH07 Table 8-3 (6x mode: INL = 1, INH = 1 → Hi-Z;
  INL = 1, INH = 0 → L).  The datasheet note "set all INHx/INLx low before changing PWM_MODE" is acknowledged at
  DESIGN.md:655.
- **Other docs.**  datasheets/README lists every PDF in the folder, and spice/README matches its scripts and
  outputs.  calcs.md has no fault-policy text that could have gone stale.
- **Round-14 items re-read, now consistent.**  §3.5 re-arm (DESIGN.md:355–358) matches §8.1 clearing and the
  throttle-zero interlock.  §7.21 (DESIGN.md:578) matches §8.1 rows 1, 2 and 5.  The comparator-default 30 A text
  (DESIGN.md:610) points at row 2.  §9 step 6's "one restart, then latch" (DESIGN.md:735) matches rows 1 and 2.
  "Hold-off" and "fault classes" no longer appear anywhere in DESIGN.md.

## MAJOR

### B15-01: SOVL and BOVL breaks match §8.1 row 4 first, so rows 7 and 8 can never fire

The evidence is at DESIGN.md:635, 638, 639 and 605.

- The INA239 ALERT is wire-ORed onto W_nFAULT (netlist; DESIGN.md:167, 605).  Any SOVL or BOVL alert therefore
  pulls W_nFAULT low and breaks TIM1.
- Row 4 tells the handler to "re-read and clear DIAG_ALRT every ≤ 0.5 ms while [W_nFAULT] is low".  With ALATCH = 1,
  the alert releases as soon as DIAG_ALRT is cleared, so W_nFAULT goes high within ≤ 0.5 ms, well under t_split
  (~3 ms).
- The table says "evaluate in this order, first match wins".  An SOVL-only or BOVL break has no comparator flag
  (rows 1–2) and no bus event (row 3), so it matches row 4: "Supply (U2 UVLO/wake)".  Supply means DRV_OFF high
  and restart everything after 20 ms of steady VBUS, not counted.

Consequences:

- **Overload (row 7) is unreachable.**  An overload SOVL above the 38 A budget stops both drives and restarts the
  weapon into the same load, with no fold-back and no count.  This undoes the B14-04 / R14A-02 rule ("SOVL without a
  bus event or U2 UVLO is overload").
- **Over-voltage (row 8) is unreachable.**  A regen or switch-open BOVL restarts after 20 ms of steady VBUS, which
  can happen with VBUS still above 18 V, instead of "restart below 18 V".  In the pack-disconnected regen case,
  that restarts the weapon at 19 V.

Row 4's parenthetical only stops a late INA239 latch being taken for a *stuck* nFAULT.  It does not attribute a
quick release to the INA239.

**Fix (text only).**  After the bus-event row, branch on the DIAG_ALRT flags read in the handler:

- BOVL set → row 8.
- SOVL set, and W_nFAULT releases once DIAG_ALRT is cleared → row 7.
- Apply the timing rows 4–6 only to W_nFAULT that is still low **after** DIAG_ALRT has been cleared, which is U2's
  own nFAULT.

An SOVL together with a U2 UVLO (the R14A-02 recharge case) then still lands in supply, because U2 holds the line
after the clear.  Add a §9 step 3/6 check: an injected SOVL (lowered limit) → overload fold-back with the drives
unaffected; an injected BOVL → weapon held until VBUS < 18 V.

## MINOR

### B15-02: the DRV_OFF sequence for single-chip drive events is stated two ways, and the "mute chip" branch cannot be followed

The evidence is at DESIGN.md:607, 608, 647, 651–659 and 730.

**Two contradictory sequences.**

- DESIGN.md:607 (DRV8316 row): on a register mismatch or NPOR = 0, "DRV_OFF high, rewrite the sequence … count it
  per §8.1".
- DESIGN.md:608 (timers row): R_nFAULT → "DRV_OFF high, then §8.1 drive events (per-drive coast if only U4 stays
  faulted)".
- §8.1 row 2 (DESIGN.md:647) calls for per-drive coast, rewrite and restart.  The per-drive coast paragraph
  (DESIGN.md:657–659) reserves DRV_OFF for a chip that does not answer on SPI.
- Neither place says when DRV_OFF is released again in the answering-chip case: after the rewrite, or after the
  6x coast is in place.

**The mute-chip branch assumes a mute chip is unpowered.**  DESIGN.md:657–659 says a chip that does not answer (read
0x0000) "is then unpowered and needs nothing", and to hold DRV_OFF "only until the read-back shows it is not
driving".  A chip that does not answer cannot show that.

The §9 step 6 test (DESIGN.md:730, "hold R_nCS high (a dead U4) → the right drive latches, the left resumes") is
exactly the counter-case.  U4 is powered, configured in 3x mode and reads 0x0000.

- If firmware releases DRV_OFF so the left drive resumes, U4 follows TIM20's static outputs.  In 3x mode with INL
  tied high that is low sides on (outputs low) or high sides on (outputs high): a **braked** wheel, not "it stays
  coasted" (DESIGN.md:647).
- If firmware does not release DRV_OFF, the §9 expectation fails.

The braked outcome is safe, but the contract and the test disagree.

**Fix.**

- State one sequence: DRV_OFF high at the event → rewrite → either restart (then release DRV_OFF) or 6x coast
  (then release DRV_OFF).
- For a chip that does not answer, either:
  - tell "unpowered" from "powered but mute" by its nFAULT level (R301/R401 pull up to the chip's own AVDD, so an
    unpowered chip reads low), or
  - accept that a latched, powered, mute chip is held braked with its timer outputs low, and write that into row 2
    and the §9 step 6 expectation.

### B15-03: the 100 Hz register check would undo a per-drive coast

The evidence is at DESIGN.md:607 and 651–656.

- The read-back expects CTRL2 = 0x7C (3x, PWM_MODE = 10b).
- A chip put into the §8.1 per-drive coast has PWM_MODE = 00b and reads 0x78.  The check then sees a mismatch →
  "DRV_OFF high, rewrite the sequence" (back to 3x) → counts another drive event.
- A latched drive therefore gets rewritten to 3x every 10 ms.  Once DRV_OFF is released it brakes, because its timer
  outputs are forced high = all high sides on in 3x mode.  It also keeps adding to the event count.

**Fix.**  Make the expected CTRL2 per drive state: 0x7C when running, 0x78 when coasted.  Say that the check
re-applies the coast, not the run sequence, to a coasted or latched chip.

### B15-04: TH1 > 100 °C latches in one place and restarts in another

The evidence is at DESIGN.md:613, 666–667 and 637.

- The §8 "Weapon safety" row and the §8.1 stall cut-out say "TH1 > 100 °C → latch" and "latch only on TH1 > 100 °C".
- §8.1 row 6 says "OTSD (TH1 high) → cool-down, then restart".  It uses TH1 as the only way to tell OTSD from GDF,
  since the DRV8323RH has no registers.
- A hot-bridge OTSD with TH1 above 100 °C is therefore latched by one rule and restarted by the other.  It is also
  unclear whether the 100 °C latch applies generally or only during a stall.

**Fix.**  Give row 6 its own TH1 threshold, below the 100 °C latch, for "OTSD, cool down".  State that
TH1 > 100 °C latches the weapon from any state.

## NOTE

- **N1: §9 step 4 and the DRV8323 row lag §8.1.**
  - DESIGN.md:717 says "to set the §8 class boundary"; it should say the §8.1 t_split and t_RETRY.
  - DESIGN.md:605 still gives the old discrimination: "~4 ms = VDS OCP; one that stays is GDF/OTSD/UVLO".  It does
    not mention that a short release is U2 UVLO/wake (supply, row 4) or that t_RETRY is measured.  A pointer to §8.1
    would remove the second copy.
- **N2: there is no separate power-on reset flag.**  DESIGN.md:626 says "(+3V3 POR flag)".  In the STM32G4
  RCC_CSR, BORRSTF is set by both POR and BOR, and there is no separate POR flag (from RM0440; the reference manual
  is not in the package).  The rule works as "invalid word + BORRSTF → no latches".  Name the flag so a deep brown-out
  that wipes the backup domain is understood to clear latches, as B14 intended.
- **N3: §8.1 omits two latch-related items.**
  - The §7.16 strap boot-test failure latches the weapon (DESIGN.md:555), but §8.1, "one ordered procedure", does
    not list it as a latch reason.
  - Clearing a GDF latch also needs U2's short ENABLE pulse (DESIGN.md:167, 605); §8.1 "Clearing"
    (DESIGN.md:674–676) does not say so.
- **N4: §3.3 does not mention the per-drive Hi-Z path.**  DESIGN.md:213–214 says "Hi-Z is done with DRVOFF" and
  "This is the drives' coast path".  That is still true for both drives at once, but a pointer to the §8.1 per-drive
  6x coast would help.
- **N5: "explicit restart" is not defined.**  The W_ARM_S row (DESIGN.md:606) says "re-arm needs an explicit restart
  and a new ARM edge".  The §8.1 throttle-zero interlock (DESIGN.md:676–677) is what defines that restart; point to
  it.
- **N6: the "≤ ~34 A" figure is not explained.**  §8.1 row 2 (DESIGN.md:633) says "slow over-current ≤ ~34 A"
  without saying where the figure comes from; the comparator default is 30 A (DESIGN.md:610).  If it is the CSA's
  ±35 A linear limit, say so.
