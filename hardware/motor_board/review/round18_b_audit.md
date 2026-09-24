# Round 18 — B: consistency audit (rev L)

Scope: the whole package, with DESIGN.md §3.5, §8, §8.1 and §9 as edited in round 17 as the focus.
Line numbers refer to the working tree as audited (DESIGN.md is 767 lines).

## Reproduction

* The package was copied to `/tmp/r18b/`.  `design/motor_board.py` printed "237 refs (205 placed
  components), 160 nets, 67 BOM lines / checks: OK".  `design/calcs.py` ran cleanly.
* The regenerated `netlist.csv`, `nets.md`, `bom.csv`, `mcu_pinmap.md`, `calcs.md` and `BOM.md` are
  **byte-identical** to the tree.
* bom.csv has 67 lines and a total Qty of 199, with no DNP rows.  The 6 DNP parts (C110–C112,
  C114–C116) are in the netlist only, and they are listed the same way in BOM.md:4–6, DESIGN.md:37
  and README.md:7.
* A script cross-checked every "Rxx/Cxx/… value" mention in DESIGN.md, BOM.md, calcs.md,
  spice/README.md and datasheets/README.md against bom.csv.  The only hits were the range
  "R22–R27 68k/10k" and the DNP C116, so there were no real mismatches.
* A script cross-checked every "SIGNAL PXn" and "PXn = SIGNAL" mention against mcu_pinmap.md:
  0 mismatches.  The U2 and U3 pin numbers quoted in §3.2 and §3.3 match nets.md.

## DRV8316 SPI words (SLVSH07 Table 8-9: B15 W0, B14–9 address, B8 even parity over the word)

| Word | Addr | Data | Meaning checked against SLVSH07 Tables 8-18…8-24 | 1s | Parity |
|---|---|---|---|---|---|
| 0x0603 | 03 CTRL1 | 03 | unlock | 4 | OK |
| 0x0606 | 03 CTRL1 | 06 | REG_LOCK | 4 | OK |
| 0x1019 | 08 CTRL6 | 19 | BUCK_PS_DIS, BUCK_CL, BUCK_DIS | 4 | OK |
| 0x0A4E | 05 CTRL3 | 4E | rsvd b6 = 1, OVP_SEL 22 V, OVP_EN, SPI_FLT_REP = 1, OTW_REP = 0 | 6 | OK |
| 0x0C90 | 06 CTRL4 | 90 | DRV_OFF, OCP_DEG 0.6 µs, 16 A, latched | 4 | OK |
| 0x0D10 | 06 CTRL4 | 10 | same with DRV_OFF = 0 | 4 | OK |
| 0x0F00 | 07 CTRL5 | 00 | CSA 0.15 V/A | 4 | OK |
| 0x1818 | 0C CTRL10 | 18 | DLYCMP_EN, 1.8 µs | 4 | OK |
| 0x1915 | 0C CTRL10 | 15 | (TI's 1.2 µs, not used) | 6 | OK |
| 0x087C | 04 CTRL2 | 7C | rsvd = 01, push-pull, 200 V/µs, 3x | 6 | OK |
| 0x097D | 04 CTRL2 | 7D | + CLR_FLT | 8 | OK |
| 0x0C10 / 0x0D90 | 06 | — | quoted as the wrong words | 3 / 5 | odd, as the text says |

All read-back expectations match these words: CTRL2 0x7C, CTRL3 0x4E, CTRL4 0x10/0x90, CTRL6 0x19,
CTRL10 0x18, and NPOR = 1 (DESIGN.md:612).  Every DRV8316 word in the package appears only in
DESIGN.md.

## Row and step references

Every row and step reference was checked: §8.1 row 0/5/6/10, drive rows 6/7, "rows 1–12", "after 3",
§9 steps 0/2/4/5/6, and §3.5 "§8.1 clearing".  They all resolve to the intended row or step.

---

## Findings

### B18-01 — MAJOR — §8.1 does not handle an nFAULT pulled low by the DRV_OFF **pin**: every commanded all-drive stop can look like "both DRV8316s at once"

**Evidence**

* SLVSH07 §8.4.2 (p.53): "Since DRVOFF pin independently disables MOSFET, it can trigger fault
  condition resulting in nFAULT getting pulled low."  The package accepts this: §9 step 2 says
  "the DRV_OFF pin high, may hold nFAULT low" (DESIGN.md:726).
* Firmware drives the shared pin high for many deliberate stops:
  * the command-link timeout, "stay stopped until commanded again" (DESIGN.md:605);
  * row 0 switch open (:651);
  * weapon row 2 supply (:653);
  * drive row 4, both latched (:679);
  * the SPI3 fault hold (:691);
  * the HardFault handler (:606).
* The only exemption is in the per-drive-coast paragraph: "an nFAULT raised by a commanded coast is
  expected and not an event" (:688).  In context that paragraph is about the CTRL4 bit.
* Drive row 1 (:676): "Both DRV8316s at once … → **Supply** → DRV_OFF high, restart both after 20 ms
  steady (supply budget)".  The drive table has no first-match or precedence statement.

**Consequences if §8.1 is implemented as written**

* A link-loss stop, a row 0 hold or a row 4 double latch is followed by two nFAULT edges.  Those edges
  classify as drive row 1, whose action is "restart both".  That contradicts "stay stopped" and "hold".
* Each such stop also counts toward the supply budget (:668–670).  A weapon row 2 bounce is counted
  a second time through drive row 1.  About 20 radio dropouts in a minute therefore reach "hold
  everything … supply unstable until the operator clears it", which stops the robot mid-match.
* L_nFAULT is TIM8_BKIN (:216).  While the pin (or the CTRL4 coast bit) holds L_nFAULT low, the TIM8
  break stays asserted:
  * The Watchdog row's single boot-time break-flag clear "after … the DRV8316 fault clear" (:606)
    cannot leave TIM8 MOE set.  At boot the chips are now coasted with the pin high (:612).
  * Nothing says that MOE (TIM8) must be re-enabled after the Release or after the pin goes low, and
    AOE is not specified for TIM8.
  * The left drive then sits at its OISx idle level after Release.  With OISx = 1 in 3x mode, that
    is a high-side brake.

**Fix**

* In §8.1, state that an nFAULT low within ~X ms of the firmware raising the DRV_OFF pin, or while
  the pin is high, is expected.  It is not a drive event and does not count in any budget.
* Evaluate drive events only for released chips with the pin low.
* Give the drive table the same "first match wins; a hold or latch outranks a restart" rule as the
  weapon table.
* In the §8 Watchdog row and at Release: clear BIF and set MOE on TIM8 (and TIM20 for symmetry) after
  the Release and after nFAULT is high.  Leave AOE = 0.

### B18-02 — MINOR — weapon row 1 uses "pack current at the trip", but §8.1 gathers only post-event evidence

**Evidence**

* Row 1 (DESIGN.md:652): "Pack current ≥ ~0 A (not charging the pack) at the trip → the switch is
  open: row 0 hold at once".
* "Where it runs" (:627–634): the ISRs record only flags, the W_nFAULT level and timestamps.  The
  SPI owner classifies ~0.5 ms later from the first INA239 conversion that started *after* the event.
* By then the BOVL break has coasted the weapon.  The source of the regen is gone, and the reading is
  ≥ 0 because the board's own ~100 mA flows forward.
* An over-voltage from regen into a full pack (§7.18 LiHV, a hard brake on a fresh pack) therefore
  reads exactly like an open switch.  It lands in the row 0 hold, which drops the drives too and
  lasts until the operator clears it or the robot is power-cycled.

**Fix:** row 1 uses the last INA239 current completed *before* the event.  The SPI owner keeps the
most recent pre-event reading; regen braking lasts ~0.4 s, so a reading ≤ 10 ms old is still
negative.  Name that reading in "Where it runs".

### B18-03 — MINOR — the round-17 "held until the operator clears it" states are neither latches nor defined non-latches

**Evidence**

* The latch word (DESIGN.md:636–645) stores only the weapon, left and right latches, the reason and
  counters.
* Three states added or kept in round 17 are cleared by the operator but are not in that list, and
  their persistence is not stated:
  * row 1: "more than ~3 within 10 s → weapon held until the operator clears it" (:652);
  * supply budget: "supply unstable until the operator clears it" (:669);
  * drive row 7: sensorless "until a clean … re-alignment after an operator clear" (:682).
* After an IWDG or NRST reset these holds are lost.  The heartbeat then reports "ARM edge required"
  with **no weapon latch**, and §3.5 (:356) has the compute board re-arm automatically.  The row 1
  bound on the energy into D1 is therefore defeated by any MCU reset.
* The compute board mirrors only "the weapon latch" (:373, :644), so the row 1 hold is also lost
  across a power cycle.
* Drive row 7 and row 0 re-assert themselves after a reset: the alignment catches the swapped cables
  again, and the 100 ms monitor catches the open switch again.  Rows 1 and the supply budget do not.

**Fix:** give each of these states one of two definitions:
* "a weapon latch (reason = BOVL / supply)", so it is persisted in the latch word and mirrored; or
* "a hold, lost on reset, intentionally".

### B18-04 — MINOR — B17-09 applied only in part: the break idle level is stated two ways, and OISx needs OSSI = 1

**Evidence**

* §3.3 DRVOFF row (DESIGN.md:214) still says "a timer break forces the **low sides** on = brake".
  Since B17-09 (drive row 2, :677), "TIM8/TIM20 OISx = 1" makes the idle state INH **high**.  In 3x
  mode that is the high sides on.
* The OISx idle level only reaches the pin when OSSI = 1 (RM0440, "Output control bits for
  complementary OCx and OCxN channels with break feature").  With MOE = 0 and OSSI = 0 the output is
  disabled, and the pin floats to the DRV8316's 100 kΩ INHx pull-down (SLVSH07 RPD), which is low.
* OSSI = 1 is specified only for TIM1 (:615).  Without it on TIM8/TIM20, a latched drive whose chip
  resets into 6x mode still sees INH = 0 / INL = 1 (low side on).  B17-09 was meant to prevent
  exactly that.
* The debug-halt note (:595, "drives braking") also depends on the idle state.

**Fix:**
* Change :214 to "forces the idle level (OISx = 1: INH high = high sides on in 3x mode) = brake".
* Add "OSSI = 1 on TIM8/TIM20" next to OISx = 1 in drive row 2 or in the §8 STM32 timers row.

### B18-05 — MINOR — the §8 boot order stops at the DRV_OFF pin and never issues the per-chip Release

**Evidence**

* Boot order (DESIGN.md:597): "… → release DRV_OFF when the drives are commanded → …".
* Since round 16 the configuration sequence leaves CTRL4 bit 7 = 1 (:612).  "Release" is a separate
  SPI step (CTRL1 0x0603 → CTRL4 0x0D10 → CTRL1 0x0606) for unlatched drives only.
* A firmware author following the boot order would lower the pin and see both drives stay coasted.
  This fails safe and is caught at bench.  It is still a stale step, and it is the one sequence §8
  presents as the order to follow.

**Fix:** "→ when the drives are commanded: DRV_OFF pin low, then the §8 Release for each unlatched
drive, then TIM8/TIM20 MOE (B18-01)".

### B18-06 — MINOR — the rev and round labels are stale after round 17

**Evidence**

* DESIGN.md:9 says "rev L rounds 11–16".
* README.md:7 says "after sixteen adversarial review rounds".
* review/CHANGES.md:330 records round 17 as rev L.  Earlier rounds treated the same drift as a
  finding (B14-06, B16-08).

**Fix:** "rounds 11–17" and "seventeen" (or the round-18 values when this round closes).

---

## Notes

* **N1 — the §9 step 2 "check BUCK_UV/NPOR clear after CLR_FLT" (DESIGN.md:725–726) is still
  ambiguous.**  NPOR reads 0 when a POR *was* detected (SLVSH07 Table 8-13), so "NPOR clear" reads
  naturally as the fault state.  R7C-01 asked for "NPOR = 1, BUCK_UV = 0" here, but only §8 was
  changed (CHANGES.md:186).  §8 (:612) is correct.
* **N2 — the SPI-failure partition has a gap.**
  * Drive row 4 needs the INA239 **and** the other DRV8316 to answer (:679).
  * "All three failing" goes to the SPI3 fault (:690).
  * "The INA239 alone" is covered (:692).
  * The INA239 plus one DRV8316 failing matches no rule.  Both DRV8316s failing while the INA239
    answers falls into drive row 1 (supply → restart loop → supply budget), not into a hold.  Both
    are unlikely, but neither is defined.
* **N3 — §9 step 2 is at the wrong voltage for its placement.**  It asks for "the minimum idle
  current at 16.8 V (row 0 threshold)" (:727).  The bench is still at the step 1 12 V / 0.2 A
  setting, and step 4 (:740) is where the procedure says "Raise to 16.8 V".  Either move the
  measurement to step 4 or say "briefly at 16.8 V".
* **N4 — the switch-open hold is not in the latch word.**  The row 0 hold is an intentionally
  unpersisted flag, so an MCU reset during the hold (the drum holding the bus up) drops it.  The
  100 ms monitor then re-detects it and re-asserts the hold, so this is acceptable.  It is noted for
  completeness with B18-03.
* **N5 — round-17 text is otherwise internally consistent.**  Checked:
  * row 5's stopped-drum gate: 25 mV / 7.8 = 3.2 mV ≈ 4 counts at 0.81 mV/LSB, and ≈ 45–50 rpm at
    1800 KV;
  * the row 0 suspension wording;
  * the drive row 2 OISx rationale against SLVSH07 Table 8-3 (6x: INH 1 / INL 1 = Hi-Z);
  * §3.5 disarm-then-persist, which matches the latch word and :644;
  * the boot-order heartbeat against the §3.5 ~50 ms expectation;
  * §9 step 2's nFAULT criterion (after Release, pin low);
  * the §9 step 6 row 5 calibration step;
  * the classifier expectations against rows 4/5/6/10.

## Counts

BLOCKER 0 · MAJOR 1 · MINOR 5 · NOTE 5
