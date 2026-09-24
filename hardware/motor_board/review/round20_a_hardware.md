# Round 20 / A: hardware (rev L): the round-19 §8/§8.1/§9 text against the datasheets and the netlist

Scope: the hardware facts behind the round-19 edits: the "drives resume" procedure, the latch-word contents, the ~1 ms
averaged stopped-drum test, the INA239 cross-check and widened plausibility gate, the overload floor, the drive row 7
wording, the IC_STAT FAULT poll, OSSI in the timers row, and INA239 AVG/CNVRF.  Board area, prose and firmware
preferences are out of scope.  This file is the only one I wrote in the package.

**Snapshot.**  I copied the package to `/tmp/r20a`.  `design/motor_board.py` prints "237 refs (205 placed components), 160
nets, 67 BOM lines, checks: OK".  The regenerated nets.md, netlist.csv, bom.csv and mcu_pinmap.md are byte-identical to the
working tree.  `calcs.py` reproduces calcs.md (the only difference is a trailing blank line).  Round 19 changed text only,
so I did not re-run the SPICE decks.

References: [D] DESIGN.md rev L; [N] nets.md / netlist.csv; [DRV16] DRV8316C SLVSH07; [INA] INA239 SLYS027A;
[G4] STM32G474 DS12288.

## Verification of the facts the round-19 text relies on

| Claim | Verdict | Evidence |
|---|---|---|
| IC_STAT has a FAULT bit, and NPOR = 0 means a power-on reset was seen | Correct | [DRV16] Table 8-13 p.58 (bit 0 FAULT, bit 3 NPOR) |
| A VM/AVDD undervoltage reset **does not report on nFAULT**.  The chip resets and "normal operation resumes" when VM returns | Correct, and it matters (R20A-01) | [DRV16] Table 8-8 p.48 (VM UV and AVDD UV: REPORT "—", recovery automatic); §8.3.14.1 p.49 |
| Reset defaults: CTRL2 0x60 (PWM_MODE 00 = 6x), CTRL4 0x10 (DRV_OFF bit 0, OCP 16 A latched) | Correct | [DRV16] Table 8-19, Table 8-21 p.65 |
| 6x mode with INLx = +3V3: INH high → Hi-Z, INH low → low side on | Correct | [DRV16] Table 8-3 p.20; [N] U3/U4 INLA/B/C (pins 28/30/32) on +3V3 |
| DRV8316 VM UVLO 4.1–4.3 V falling, 4.3–4.5 V rising | Correct as used | [DRV16] EC table p.13 |
| The DRV_OFF pin "can trigger fault condition resulting in nFAULT getting pulled low" (resume runs fault recovery if nFAULT is still low) | Correct as quoted | [DRV16] §8.4.2 p.53 |
| L_nFAULT = PB7 = TIM8_BKIN; R_nFAULT = PC15, no break; DRV_OFF on PC14 with R50 pull-up to +3V3 | Correct | [N] L_nFAULT, R_nFAULT, DRV_OFF nets |
| INA239 AVG reset value 0h = 1 sample; CNVRF is set after all conversions and averaging, and is cleared by a DIAG_ALRT read | Correct | [INA] Table 7-6 (AVG), §7.3.3 p.14–15, Table 7-13 (CNVRF) |
| INA239 150 µs conversions need a write: reset ADC_CONFIG is FB68h (MODE Fh with temperature, 1052 µs each) | Correct (see N-03 for the value) | [INA] Table 7-6 (reset FB68h; VBUSCT/VSHCT 2h = 150 µs; MODE Bh = continuous shunt + bus) |
| Cross-check example: R2/R3 open → drift and saturation at ±41 A | Correct | [N] R2 VBAT_SW→IN+, R3 VBAT→IN−, C2 across IN+/IN−, VBUS pin on VBAT; ±40.96 mV / 1 mΩ |
| Stopped-drum test: ~0.8 LSB rms per sample, a ~1 ms mean keeps a 5.8 Hz (50 rpm) BEMF | Correct | R19A-02; 50 rpm × 7 pole pairs / 60 = 5.8 Hz, 172 ms period, inside the 200 ms window.  A hand-turned drum at ~100 rpm gives ~56 mV > 25 mV |
| Backup registers hold the larger latch word | Correct | [G4] §3.26: 32 × 32-bit TAMP backup registers |
| Drive row 7: crossed motor bundles look the same as crossed sensor cables | Correct | Aligning U3 moves the right motor, whose encoder is on J3: "other encoder moved, own still" |
| Overload floor at the drives' traction limit | Consistent | ~1–1.5 A phase per drive gives a bus current of a few A, far below the 38 A SOVL |
| OSSI in the timers row | Present | [D] l.613 |

## Findings

| ID | Sev | Where | Finding | Evidence | Fix |
|---|---|---|---|---|---|
| R20A-01 | **MAJOR** | [D] §8.1 "Drives resume" (l.673), drive row 1 (l.677), §8 DRV8316 row (l.612) | **After a supply event in which both DRV8316s reset, "drives resume" re-enables them in their reset state.  The 100 Hz check then sees both at NPOR, which drive row 1 treats as another supply event, and the loop ends in a "supply unstable" hold.**<br><br>**(1) The scenario is expected, not a corner case.**  The ~470 µF hold-up on the compute board's 5 V exists so that the MCU survives millisecond bounces (§3.5).  During a bounce the bus is clamped at ~4.4 V: +5V back-feeds VBAT through U2's buck high-side body diode, as [D] l.332 notes.  The clamp falls as the hold-up drains, at ~0.5 V/ms for ~0.25 A.  When +5V drops below ~4.8 V, VM falls below the DRV8316 UVLO (4.1–4.3 V), so **both** chips reset.  The AP2112K keeps +3V3 up until +5V falls to ~3.4 V, a few ms later.  So bounces of roughly 2–6 ms give "both DRV8316s reset, MCU alive".  §9 step 6 even includes a 3 ms interruption test.<br><br>**(2) nFAULT does not flag the reset.**  A VM/AVDD UVLO has no nFAULT report (Table 8-8).  Any CP-UV or BUCK_UV during the dip has cleared automatically by the time the pin is lowered, 20 ms after the bus is steady.  So the resume step sees nFAULT high, runs no CLR_FLT and no rewrite, lowers the pin and sets MOE.  The chips are then in their reset state: 6x mode, unlocked, buck enabled.  With INL = +3V3, each INH-low interval turns that phase's low side on, so the three-phase short brake is pulsed until OCP (16 A latched default) or the next poll.<br><br>**(3) The loop.**  Within ≤ 10 ms the ~100 Hz check reads NPOR = 0 on **both** chips.  That matches drive row 1 ("both DRV8316s at once"), so: supply → DRV_OFF high → 20 ms → drives resume, again without a rewrite → NPOR still 0.  NPOR is cleared only by CLR_FLT ([DRV16] §8.3.14.1).  One loop takes ~30 ms.  After more than 5 in a second there is a 1 s hold, and after more than 20 in a minute (~4 s) the "supply unstable" hold is persisted in the latch word until an operator clear.  **One ~3 ms contact bounce leaves the robot immobile for the rest of the match.**  The §8 DRV8316 row says a NPOR "goes to §8.1 drive events (the chip is coasted by the rewrite itself)", but only row 2 (one chip) rewrites.  Row 1 and the resume step do not | [DRV16] Table 8-8 p.48, §8.3.14.1–.2 p.49, EC p.13 (V_UVLO), Tables 8-3/8-13/8-19/8-21; [D] l.332, l.362, l.612, l.673, l.677, l.769; [N] U3/U4 INLx on +3V3 | Text only.  In "drives resume", **before** lowering the pin (with the pin still high), read IC_STAT and the CTRL registers of each unlatched chip.  On NPOR = 0 or a mismatch, write the full §8 sequence (it ends coasted, and its CLR_FLT sets NPOR = 1), then the Release, then the existing nFAULT wait and MOE.  In drive row 1, state that a both-chip NPOR or mismatch is repaired by that rewrite inside the resume step.  Count it once, in the supply budget, as part of the event that caused it (not as a new event).  Add to the §9 step 6 classifier test: after the 3 ms interruption, both drives run again, and the heartbeat shows one supply event, not a hold |
| R20A-02 | **MAJOR** | [D] §8.1 row 0, "Plausibility" (the "≥ ~1 A by firmware's estimate" clause) and "INA239 cross-check" (l.652) | **A coasting drum holds the bus steady under amps of drive load with the switch open.  So the new ≥ 1 A clause (and the cross-check) calls a real switch-open an INA239 failure: no switch-open hold, and the drives keep running.**<br><br>• With the switch open and the weapon coasting (throttle zero, drum spinning down: a common end-of-match state), the six weapon body diodes rectify the drum's BEMF onto the bus.  §7 item 5 ([D] l.519) says so: the board stays powered until the drum slows to ~19 k rpm.  The bus sits at ~BEMF − 2 V_f ≈ 12.8 V from 25.6 k rpm.<br>• Its sag under load is slow.  dV/dt = V·P/(2E) = 12.8 V × 40 W / (2 × 64 J) ≈ **4 mV/ms** for both drives at ~3 A of bus current.  That is "steady" next to the ≥ 7 V/ms C1-only collapse that my R19A N-01 assumed.  I missed this source in that note, and round 19 adopted the clause without a drum condition.<br>• The result: INA239 ≈ 0 A, estimate ≥ 1 A, steady bus → "the INA239 reading is wrong" → INA239-failure path (weapon off, **drives continue on VBAT_SNS**) instead of the row 0 hold.  The cross-check (\|0 − estimate\| > 1 A for 200 ms) reaches the same path.  It can also win while the row 0 mean keeps restarting under brief regen suspensions.<br>• The drives then respond to commands until the bus falls to the ~9.2 V logic cutoff.  That is 28.7 J of drum energy (25.6 → 19 k rpm): ~0.7 s at 40 W, ~2.4 s at 12 W.  This happens right after a person has opened the switch, and it defeats the §9 step 3 test "open the switch with the drum spinning → firmware coasts everything" whenever the drives are commanded.  The report also names the wrong culprit ("INA239 failed").<br>• The third clause ("bus clearly above the drum's back-EMF") is sound: with the switch open, a coasting drum cannot hold the bus above its own rectified BEMF | [D] l.519 (§7 item 5), l.384 (64 J, 25.6 k rpm, 1800 KV), l.113 (logic cutoff ~9.2 V), l.652, l.733; C1 374 µF | Text only.  Apply the "≥ ~1 A estimated load" clause only when the drum is **stopped or actively driven by the weapon FOC**, not while it coasts.  With a coasting drum, use only the "bus clearly above the drum's rectified BEMF (minus two diode drops)" clause.  Exclude the same case from the cross-check: a measured \|I\| < ~30 mA with the bus at or below the coasting drum's rectified BEMF belongs to row 0, not to the cross-check.  Add to the §9 step 3 test: open the switch with the drum coasting **while driving** → the switch-open hold, drives stop within ~100 ms |

## Notes

| ID | Sev | Note |
|---|---|---|
| N-01 | NOTE | **Boot order inside "drives resume".**  At boot the chips are still coasted by the CTRL4 bit (0x0C90) when the pin is lowered.  If that bit holds nFAULT low (still "bench-verify", §8.1), a resume step run at the moment the pin is lowered would time out (≤ 5 ms) into drive row 2, giving a spurious count and a rewrite at every boot.  State the order as: pin low → Release of each unlatched chip → then the ~1 ms / ≤ 5 ms nFAULT wait and MOE (one pass, not one pass per trigger) |
| N-02 | NOTE | **IC_STAT FAULT has no expected value.**  The 100 Hz read now includes IC_STAT FAULT, but the expected-values list gives only NPOR = 1.  Say FAULT = 0 for a released chip.  For a coasted chip, the value is whatever the §8.1 bench check finds.  FAULT = 1 on a released chip → drive row 2.  The same eight status bits come back in the first byte of every SDO frame ([DRV16] §8.5.1, Table 8-10), so no extra read is needed |
| N-03 | NOTE | **Write ADC_CONFIG explicitly.**  "Shunt and bus ≤ 150 µs, AVG = 1" is not the reset state (FB68h: temperature on, 1052 µs each, i.e. ~3 ms per cycle, which would break the row 1 timing).  The value is **0xB480** (MODE Bh, VBUSCT 2h = 150 µs, VSHCT 2h = 150 µs, VTCT 0, AVG 0).  150 µs is code 2h, not 3h (3h = 280 µs) |

## Independent re-checks (no finding)

* **Resume after an OCP or a pin-induced fault**: the fault recovery (CLR_FLT with unlock/lock) clears latched OCP and
  CP-UV bits ([DRV16] Table 8-8).  The ≤ 5 ms wait covers t_READY and the charge-pump restart.  TIM8's break is
  level-sensitive, so MOE is set only after L_nFAULT is high.  TIM20's break can only come from CLL (BKINE = 0).
* **Latched drive through an NPOR**: that chip loses the coast bit, but its INH outputs are held high (OISx = 1, OSSI = 1),
  which is Hi-Z in 6x mode (Table 8-3).  This is settled and still correct.
* **CNVRF counting**: if the DIAG_ALRT reads are slower than the 300 µs shunt + bus cycle, two completions merge into one
  CNVRF.  Firmware then uses a *later* conversion, which is the safe direction.  At ~0.2 V/ms the VBUS > 18 V margin
  holds for several ms.
* **Row 0 with the switch open and the drum stopped**: the bus falls below 8 V in ~30 ms (374 µF at ~0.1 A), and the logic
  shuts off near 9.2 V.  Row 0 never needs to mature, and the hold-up clamp (~4.4 V) is below the 8 V gate.

**Verdict: 0 BLOCKER, 2 MAJOR, 0 MINOR, 3 NOTE.**  Both MAJORs are text-only fixes in §8.1:
* **Drives resume:** read NPOR and the registers, and rewrite reset chips, before lowering the DRV_OFF pin.
* **Row 0 plausibility and cross-check:** apply the "≥ 1 A under load" clause and the cross-check only when the drum is not coasting.

No circuit change is needed.
