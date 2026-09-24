# Review round 23 / D: system-level review (rev L)

**Reviewer role:** adversarial system reviewer (power electronics and combat robotics).

**What I read:**
* DESIGN.md rev L, all of it.
* design/calcs.md and spice/*.out.
* review/CHANGES.md for rounds 1–22, and round22_d_system.md.
* The findings list of round23_b_audit.md, which appeared while this review ran.

**DESIGN.md changed during the review.**  The B23-01/02 fixes were applied while I was reading: the step-2 alignment moved to after the Release, and the stale "FOC at zero current" summaries were fixed.  Every finding below is against the text as it stood at the end of the review, re-read after the change.

**Scripts:** I copied the package without datasheets/ and review/ to `/tmp/r23d/`, ran it there, then deleted the copy.
* `design/motor_board.py` printed "237 refs (205 placed components), 160 nets, 67 BOM lines / checks: OK".
* The regenerated calcs.md, nets.md, netlist.csv and bom.csv are byte-identical to the package.

**Scope:** the hardware has not changed since round 16, so I re-read the SPICE outputs but did not re-run them.  Apart from this file, nothing in the package was edited.

**Evidence tags:**
* **[D l.N]** = a DESIGN.md line (current numbering).
* **[S file]** = a spice output.
* **[C §N]** = a calcs.md section.

---

## 1. Findings

| ID | Sev | Area | Finding | Evidence / numbers | Fix |
|---|---|---|---|---|---|
| R23D-01 | MINOR | §8.1 row 0: the round-22 "switch open under throttle" clause | **The instant coast cannot fire in the case it was written for.  Row 0 therefore stays suspended for as long as the weapon throttle is held with the switch open.**<br><br>**1. The two readings agree by energy balance.**<br>• The clause coasts a motoring weapon whose power is < −20 W "while the INA239 reads ≈ 0 A **and firmware's signed estimate does not**".<br>• The estimate is "idle draw plus the actively driven channels".  A motoring weapon is actively driven, so its negative power is part of the estimate.<br>• With the switch open, the drum is the only source on the bus.  The weapon's electrical power is therefore −(idle + drives) at every instant, up to C1's charge term.<br>• So the signed estimate is ≈ 0, which is exactly what the INA239 reads.  The clause fires only through estimation error, which is noise.<br><br>**2. Both suspension clauses then hold.**<br>• An actively driven motor (the weapon) has negative power.<br>• The estimate is within 50 mA of zero.<br>• Worked example with the drives idle: weapon ≈ −1.7 W / 15 V = −0.11 A, plus 0.11 A of idle, gives ≈ 0.  The −20 W floor is not reached at all.<br><br>**3. Nothing else catches it.**<br>• The cross-check compares 0 against ≈ 0.<br>• Plausibility wants the weapon motoring at ≥ +1 A, and here it is negative.<br><br>**Outcome.**  The weapon stays under a motoring command, working as a generator, and the drives stay live on drum energy.  This lasts until the throttle is released (the weapon then coasts and the 100 ms mean holds) or until the drum's back-EMF falls below the logic cutoff (§7.5: ~19 k rpm).  That is roughly 1–3 s from top speed, where windage is ~30–40 W.  The end state is safe and bounded, but:<br>• the §9 step 6 test "with the weapon throttle held → switch-open hold, drives stopped within ~0.1 s" fails;<br>• in the pit the robot still answers the sticks after the switch is opened.<br><br>**A second defect in the same clause.**  If the clause does fire on estimation noise and a shove keeps row 0 suspended, then "not held within 100 ms → catch-spin restart" re-drives the weapon on the open bus, and this repeats while the drum lasts | [D l.652] (clause, suspension, cross-check, plausibility); [D l.522] §7.5; [D l.782] §9 test; [C §11] idle ~1.6–1.9 W; R22D-01 steady state (2.7 A windage current at 15.2 V) | **Keep a motoring weapon out of both suspension tests.** Only commanded regen and back-driven drives suspend row 0.  Also leave its negative term out of the "estimate ≈ 0" test.<br>• The ordinary 100 ms \|I\| < 30 mA mean then catches the open switch under throttle.<br>• With the switch closed, a regenerating dip lasts only milliseconds.  It cannot hold a 100 ms mean inside ±30 mA.<br>• The instant coast and its restart rule can then go.<br><br>**Alternative, if the instant coast is kept:** compare the INA239 with the estimate of the loads only (idle plus positive-power channels), not with the signed total |
| R23D-02 | MINOR | §8.1 "drives resume" step 2 (text revised in round 23) | **A dead encoder reads as "rotor still", so the resume releases a turning wheel at a zero preset.  That can latch the healthy motor's drive.**<br><br>**1. The branch.**  Step 2 says "with the rotor still (encoder not counting), the preset is 0".  §8 notes that a cut ABZ cable freezes the count through the pull-ups [D l.614].<br><br>**2. How it happens.**  The cable dies while the drive is coasted: a supply-event or link coast, often the same hit.  It can also die at standstill, before a later coast.  Either way, a later resume while the robot rolls or is shoved sees:<br>• "not counting", so the rotor is treated as still;<br>• the angle is still "valid", because nothing marked it invalid;<br>• ω = 0, so V_q = 0: a three-phase short at speed.<br><br>**3. The current.**  λ = Kt/(1.5·pp) = 0.30 mWb.  At 1 m/s, E_ph ≈ 2.4 V; at 2 m/s, ≈ 4.8 V.  The phase \|Z\| is ~0.12–0.33 Ω (0.2–0.3 Ω line-to-line, L 5–20 µH).  That gives 7–40 A against the 10–22 A OCP.<br><br>**4. The latch.**  With a "valid encoder angle", more than 3 resume OCPs in a second latch that drive [D l.677].  The retries follow each other within milliseconds while the robot is still rolling, so a single broken sensor cable costs the whole drive (and the motor itself is healthy) until an operator clear.  The designed degraded path — sensorless, retry every 0.5 s, never latch — is never reached, because the firmware believes the encoder | [D l.614, 675–677]; [C §10] Kt 2.73 mN·m/A, 6 pole pairs, 46.5 k rpm at 3.7 m/s, R 0.2–0.3 Ω line-to-line | Treat a resume OCP released at a **zero preset from a non-counting encoder** as "encoder suspect".  That OCP:<br>• goes to the no-encoder branch (fixed coast, retry every 0.5 s, never latches, sensorless once running);<br>• reports "no encoder edges";<br>• does not count toward the latch.<br><br>Count resume OCPs toward the latch only when the encoder showed motion that matches the preset.<br><br>§9 step 6: unplug a sensor while the drive is coasted and the robot is pushed, then let the link recover → no drive latch |

**NOTEs** (no change needed, or wording only):

* **R23D-N1: row 6 (a) wording.**
  * The text says "~171 counts each" for **both** alignment steps.  Only the step-1 → step-2 motion (90° electrical) is deterministic.
  * Step 1 starts from an unknown angle, so its motion can be anywhere in ±342 counts.
  * On a real crossed-cable board the first alignment therefore fails (a).  It arguably matches none of (a)–(c), and the drive table has no default row.
  * Repeats still converge: the rotor rests at 0° after step 2, so the next step 1 moves exactly +171.  Row 7 follows after three alignments, well within the ~5 allowed.
  * Suggested wording: "~171 counts between the steps with the expected sign, and still before step 1".
* **R23D-N2: the Z-only resume angle uses a known-stale offset.**
  * The Z-pulse path [D l.675] takes the stored Z offset even after "Z offset stale" has been reported [D l.614], for example after a magnet re-glue without the §9 step 5 re-calibration.
  * A later reset or invalid-angle resume at speed then presets at the wrong angle, which gives resume OCPs and the drive latch.
  * This needs two events: an ignored report plus a reset.
  * Suggested fix: while "Z offset stale" is set, treat the Z path as "no usable encoder".
* **R23D-N3: a sensor re-power during a coast is invisible.**
  * A VS short that trips the TPS22945 while the drive is coasted is not detected: there is no observer while coasted, so the "≥ 20 ms without edges while the observer says it turns" rule cannot run.
  * The count then carries an offset until the next Z corrects it.  The resume can happen before that Z.
  * Cheap guard: when the rotor is turning, require one Z match before the Release.  That costs one motor revolution (≤ 1.3 ms at top speed).
  * This needs two events: a cable short during a coast.
* **R23D-N4: row 7 keeps driving.**
  * Row 7 does not stop the drives.  It runs both drives sensorless.  Round 22-D's walk-through described it as "no drive until cleared", which misreads the row.
  * With crossed **sensor cables** that is correct.  With crossed **motor bundles** the robot steers correctly but drives backwards on a forward command.
  * The design accepts this and relies on the report and the §9 "forward move by eye after any rewiring" check (R19D-01).  This note records it so it is not re-read as a hold.

---

## 2. Scenario walk-through (current text)

| Scenario | Path through §8.1 | Outcome |
|---|---|---|
| Impact flurry, drum at speed | Row 6 catch-spin; > 5/s → 1 s off; row 4 needs two fast re-trips | Safe, bounded, no latch |
| Jammed drum, TH1 hot | Rows 10 and 6 retry; row 5 passes at a stopped restart | No latch |
| Weapon phase–phase short (spinning / stopped) | Row 4 / row 5 | Latched: no masked short |
| Weapon phase–GND short | Row 8 VDS OCP | Latched |
| Bounce under spin-up load | Row 2 → supply budget; a silently reset DRV8316 is rewritten in resume step 1, counted once | Bounded |
| Drive reversal or bounce, drum saturated, switch closed | Weapon power < 0, but INA239 ≠ 0 → no instant coast; row 0 suspended only for the dip | Non-nuisance (R22D-01 closed) |
| Switch opened, drum coasting, driving | Estimate = idle + drives ≫ 30 mA, INA239 ≈ 0 → row 0 hold in ~100 ms | Safe |
| Switch opened, weapon throttle held | Estimate ≈ INA239 ≈ 0 by energy balance → row 0 suspended until the throttle is released or the logic browns out | **R23D-01**: ends safe; §9 test fails |
| Switch opened while braking | Row 1 "looks open" → row 0 | Safe |
| Link blip at top speed, encoders good | Command timeout coast; ARM falls → new edge + throttle-zero; resume with back-EMF preset → Release | Safe, no brake step (bench-verified at top speed) |
| MCU reset while rolling, encoders good | Angle invalid, encoder counting → next Z (≤ 1.3 ms at top speed) → preset → Release; reset within 2 s of a weapon event latches the weapon | Safe; no operator-less re-arm |
| Encoder lost while running | Observer mismatch → sensorless → later resumes use the fixed-coast branch, retry every 0.5 s | Degraded, never latches |
| Encoder lost while coasted / stationary, then resumed rolling | "Not counting" = still → preset 0 at speed → OCP ×3/s → drive latch | **R23D-02** |
| Dead encoder + shove during alignment | Row 6 (a) now needs step-correlated motion twice → (c) repeat → sensorless | Sound (R22D-04 closed) |
| Pit: J2/J3 crossed | Row 6 (a) → row 7, sensorless, report | Sound (N1 wording) |
| Pit: motor bundles crossed | Row 7, sensorless → drives backwards on forward | Procedural (N4, R19D-01) |
| Pit: swapped phase or encoder pair | Two clean wrong-sign alignments → row 6a latch; a single dead-zone wrong sign is not repeated | No reversed drive |
| DRV8316 short / unpowered / deaf | Row 2 (> 3/s latch, INH high) / row 3 / row 4 | Sound |
| Compute-board hang | ARM stops in 52–164 ms [S arm.out]; ≤ 2 NRST pulses per 10 s | Safe, bounded |
| Power cycle with latches | Board latches lost; the compute board mirrors the weapon latch; the switch-open hold is not persisted | Sound |

## 3. Checked and found sound

* **Round-22 fixes.**
  * The back-EMF preset is now required everywhere: steps 2–3, the boot-order summary and the DRV8316 row after the round-23 edit.
  * Resume OCPs never reach row 1 or the supply budget.
  * BKINE = 0 keeps CLL active through BKE = 1.  The TIMx_AF1 BKINE bit exists on TIM1/TIM8/TIM20 of the G474.
  * The 24 A fallback words 0x0D94 and 0x0C14 have even parity (6 and 4 ones).  So do 0x0C90 and 0x0D10 (4 each).
  * Row 7 now needs the step-correlated signature.
* **Preset-error claim ("15° → ~10 A").**  At 46.5 k rpm, E_ph ≈ 8.9 V.  A 15° error is 2.3 V across 0.12–0.33 Ω, which gives 7–19 A.  The claim is consistent, and it is bench-verified in §9 step 6.
* **No operator-less re-arm.**
  * Every automatic weapon restart stays inside a continuous ARM.
  * ARM fall, reset, link recovery and clear all need a new edge plus throttle-zero.
  * Operator-clear holds are never cleared by firmware.
* **§1 margins** (outputs re-read; the hardware is unchanged):
  * DRV8316 VM: 0.80–2.26 V/µs for a loaded bounce, 2.66 V/µs at C1's −40 °C ESR, ≤ 2.09 V/µs on re-close [S hotplug.out].  All are within the 4 V/µs limit and the §1 claim of ≤ 2.75 V/µs.
  * Soft-start: 1.28–2.95 V/ms; Q7 22.0 W / 54–57 mJ worst.
  * Reversed pack: 13.1 A (the C14 spike) with D10.
  * ARM: armed at 2.50–2.95 V against VT+ ≤ 2.15 V; 7–10 edges to arm; disarm in 52–164 ms [S arm.out].
  * Spin-up: 22.1 A peak, 14.06 V minimum, against the 10.3 V worst-case logic cutoff [S spinup.out].
  * Weapon bridge at 60 mA / 6 nH: VDS 29.4 V (< 40 V), SHx −4.58 V (> −7 V) [S bridge.out].
  * Voltage chain: 16.8 + 1.4 = 18.2 V < 18.3 V (test) < 18.5 V (coast) < 19 V (BOVL) < 20 V (OVP minimum); D1 32.4 V < 35 V (C1) < 40 V.
  * SOVL 38 A > the 32 A budget.
  * MT6701: 46.5 k rpm against its 55 k rpm rating.
  * VBAT_SNS_H: 25.7 V / 7.8 = 3.29 V.

## 4. Summary

| ID | Sev | One line |
|---|---|---|
| R23D-01 | MINOR | With the switch open, the signed estimate equals the INA239's ≈ 0 by energy balance.  The round-22 instant coast never fires, and row 0 stays suspended while the weapon throttle is held.  The drives stay live on drum energy for ~1–3 s; the end state is safe, but the §9 "stopped within 0.1 s" test fails.  Fix: a motoring weapon never suspends row 0 and is left out of the ≈ 0 estimate test |
| R23D-02 | MINOR | A dead encoder (count frozen) reads as "rotor still" at a resume.  The zero preset at speed trips the OCP (7–40 A vs 10–22 A), and the drive latches under the "valid angle" rule.  Fix: an OCP at a zero preset from a non-counting encoder means "encoder suspect" and takes the no-encoder branch |
| N1–N4 | NOTE | Row 6 (a) step-1 wording; stale Z offset used by the Z path; sensor re-power during a coast; row 7 keeps driving with crossed bundles (accepted) |

**Verdict: 0 BLOCKER, 0 MAJOR, 2 MINOR, 4 NOTE.**  Both findings are firmware-contract text; no hardware change is needed.
