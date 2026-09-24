# Review round 20 / D: system-level review (rev L)

Reviewer role: adversarial system reviewer (power electronics and combat robotics).  I read DESIGN.md rev L end to end,
design/calcs.md, spice/*.out, review/CHANGES.md (rounds 1–19) and round19_d_system.md.  I also read the DRV8316C datasheet
(SLVSH07: UVLO, NPOR, fault table, register resets, 6x truth table).  The package was copied to `/tmp/r20d/`.
`design/motor_board.py` prints "237 refs (205 placed components), 160 nets, 67 BOM lines / checks: OK" and `design/calcs.py`
runs cleanly.  Round 19 changed text only, so no SPICE deck was re-run; the outputs were re-read.  Nothing in the package
was edited apart from this file.

The focus was the round-19 §8.1 text:

* "drives resume";
* the latch word;
* the INA239 cross-check and plausibility gate;
* the overload floor;
* the left/right-crossed row;
* stopped-drum averaging.

Evidence tags: **[D l.N]** = DESIGN.md line, **[S file]** = spice output, **[C §N]** = calcs.md, **[DRV]** = DRV8316C.pdf
(SLVSH07).

---

## 1. Findings

| ID | Sev | Area | Finding | Evidence / numbers | Fix |
|---|---|---|---|---|---|
| R20D-01 | MAJOR | §8.1 drive row 1 + "drives resume": both DRV8316s reset by one bus dip | **Take a supply event that resets both DRV8316s while the MCU stays up.  Drive row 1 classifies it, but row 1 never rewrites the chips.  The robot then loops through the supply budget into the "supply unstable" hold: everything off, weapon included.  An operator clear cannot fix it, because the registers stay wrong; only a power cycle does.**<br>• **The dip is realistic.**  The DRV8316 VM UVLO is 4.1–4.3 V falling [DRV].  The design's own loaded-bounce simulations leave the DRV8316 VM pins at **4.4–4.8 V** after 0.3–0.8 ms bounces [S hotplug.out], only 0.1–0.5 V above it.  The 1 and 3 ms interruptions in the §9 classifier test go lower.  With the drum stopped and only the drives loaded (1–3 A of bus current, 2.7–8 V/ms on ~374 µF), a 2–4 ms XT30/switch bounce reaches 4 V.  The MCU is meant to survive such bounces (the §3.5 470 µF hold-up [D l.362]; the nSHDN filter is ~4.5 ms).<br>• **What the chips do.**  A VM UVLO disables the logic and reports nothing on nFAULT [DRV Table 8-8].  The registers come back at reset values [DRV §8.5.1; D l.612]:<br>&nbsp;&nbsp;– CTRL2 0x60, which is **6x mode**;<br>&nbsp;&nbsp;– CTRL3 0x46, CTRL6 0x00 and CTRL10 0x00;<br>&nbsp;&nbsp;– CTRL4 0x10, which is *released*;<br>&nbsp;&nbsp;– NPOR = 0.<br>• **The path as written.**  Bus event → drive row 1 "Supply" → DRV_OFF high → after 20 ms "drives resume" [D l.673, 677].  Resume only runs the fault recovery (CLR_FLT, if nFAULT is low; that clears NPOR, the evidence) and then sets MOE.  It has **no rewrite**.  With INL = 3V3 in 6x mode, each phase is low-side-on while INH is low and Hi-Z while INH is high, so the FOC PWM gives brake pulses until the poll.  Within ≤ 10 ms the 100 Hz check finds both chips mismatched.  "First match wins" gives row 1 ("both DRV8316s at once") again, not row 2, which is the only row with a rewrite [D l.678].  That is another supply restart with no rewrite.<br>• **The loop.**  One cycle takes ~30 ms.  More than 5 in 1 s gives a 1 s hold; more than 20 in a minute gives **"supply unstable": hold everything until the operator clears it** [D l.669–671].  That is reached ~4–5 s after a single bounce.  A clear runs resume again without a rewrite, and the loop repeats.<br>• **Inconsistency.**  §8 says a mismatch or NPOR = 0 is handled by "§8.1 drive events (the chip is coasted by the rewrite itself)" [D l.612].  R13D-01 made "both chips NPOR" supply class on purpose, but the supply-class action has no rewrite | [DRV] V_UVLO falling 4.1–4.3 V, t_UVLO 3–7 µs; Table 8-8 "VM undervoltage: report —, logic disabled"; §8.3.14.1 NPOR latched low until CLR_FLT; §8.5.1 "registers reset on power up"; reset values CTRL2 60h, CTRL3 46h, CTRL4 10h, CTRL6/CTRL10 00h; Table 8-3 6x mode (INL = 1, INH = 0 → L; 1/1 → Hi-Z).  [S hotplug.out] "0.3/0.8 ms bounce, 20 A load … VM before 4.4–4.8 V".  [D l.612, 669–671, 673, 677–678, 362, 768–769] | In "drives resume", before clearing the break and setting MOE, read IC_STAT and CTRL1–CTRL10 of each unlatched chip.  **NPOR = 0 or any mismatch → run the rewrite** (it ends coasted) and then the Release.  Read NPOR before any CLR_FLT.  This rewrite belongs to the same supply event: no extra count, and it is not a drive row 2 event.  Same in drive row 1's action text.  §9: a 3 ms pack-lead interruption with the drum stopped and the drives running → both drives resume normally, with CTRL2 read back as 0x7C |
| R20D-02 | MINOR | §8.1 row 0 plausibility ("drives/weapon draw ≥ ~1 A") and the INA239 cross-check | **The round-19 load clause treats "≈ 0 A, steady bus, drives drawing ≥ 1 A" as proof that the INA239 is wrong.  A coasting drum can supply the drives, though.  So an open switch while the operator is driving is diagnosed as an INA239 failure: weapon off, drives continue, and switch-open detection is disabled for the rest of the power cycle.  The robot stays drivable on drum energy after its kill switch has been opened.**  This re-opens R17D-02.<br>• **The case.**  The switch is opened with the drum spinning: end-of-match switch-off, or knocked open by a hit.  With the drum disarmed or at throttle zero it coasts and rectifies through the body diodes.  VBUS ≈ BEMF_ll,pk − diode ≈ 13–13.5 V from full speed (14.2 V BEMF [S spinup.out]).<br>• **"Steady" holds.**  With the drives at P = 10–40 W, the bus falls by ΔV/V = P·t / 2E.  At E = 64.5 J [S spinup.out] that is 0.8–3 % in 100 ms, i.e. **0.1–0.5 V**.  The gate's own reference case is "C1 alone would fall ~30 V" [D l.652].  The weapon itself is not driven, and the bus is not above the drum's BEMF, so the only clause that fires is the load clause.  The measured-vs-estimate cross-check (0 A against ≥ 1 A for 200 ms) points the same way.<br>• **The outcome.**  The INA239-failure path runs [D l.693]: weapon off, which is safe.  But the drives stay enabled and commandable until the drum falls below ~18 k rpm (~10 V bus, logic cutoff).  That is ~31 J, i.e. **~1–3 s at 10–30 W**.  §7.5 [D l.522] and §9 step 3 ("open the switch with the drum spinning → firmware coasts everything" [D l.734]) promise the opposite.  The crew also gets a false "INA239 failed" report.<br>• **Why only drives.**  Only the weapon clause is valid.  A driven weapon with positive power can only draw from C1, so its bus falls at P/(C·V) ≈ 2–5 V/ms, which is not steady.  Drive load is exactly what a coasting drum can carry | [D l.652 (plausibility and cross-check text), 693, 522, 734]; [S spinup.out] 64.5 J, 25 573 rpm → 14.2 V; energy from 25.6 k to ~18.4 k rpm (≈ 10.2 V BEMF) = 64.5 × (1 − 0.52) ≈ 31 J; drive power per [C §10] ~20 W mech per motor at 1.5 A | Restrict the load clause to the **weapon's** positive electrical power (≥ ~1 A equivalent).  Keep "drum stopped" and "bus clearly above the drum's BEMF" (the drum is measured on W_Vx while coasting, or taken from the observer).  For the cross-check: when the measurement is ≈ 0 and a spinning drum could be the source (bus not above its BEMF), defer to row 0 (switch-open hold) rather than the INA239 path.  The hold's actions are a superset of that path's.  §9 step 3: repeat "open the switch with the drum spinning" **while driving** |
| R20D-03 | MINOR | §8 timer inputs alignment sign check vs drive row 7 "both moving = nudged" | **A robot pushed during a mid-match re-alignment can latch a drive as a "wiring fault".  The wrong-sign test has no magnitude window, and the "both moving → repeat" escape sits in row 7, which row 6 pre-empts under "first match wins".**<br>• **When alignment runs.**  Alignment runs after every MCU reset (IWDG, a BOR from a bounce, a compute-board NRST pulse) and after an angle invalidation (sensor re-power), once the rotor has stopped [D l.614].  In a pushing match "stopped" is followed by a shove within the 2 × ~100 ms window often enough.<br>• **Why a push wins.**  The alignment torque is 1 A × 2.73 mN·m × 28.5 ≈ 0.078 N·m, ≈ 3.6 N at the tyre [C §10].  That is at or below a 1 lb opponent's push, so the wheels are back-driven.  **1 mm** of wheel travel is 1/(π·43.2 mm) × 28.5 × 4096 ≈ **860 counts**, against the ~171 expected.  The measured Δ between the steps is then set by the push, and its sign is wrong ~50 % of the time.<br>• **Result.**  Drive row 6: "latch that drive: wiring fault, never falls back to sensorless" [D l.682].  The robot is left on one wheel until an operator clear.  A straight push moves both encoders, which row 7 says means "nudged → just repeat" [D l.683], but row 6 matches first.  A push that pivots the robot about the aligning wheel moves only that encoder, and no rule covers that case.<br>• **A real wiring fault looks different.**  It gives |Δ| ≈ the expected 171 counts with the wrong sign, and no motion outside the injection steps | [D l.614, 682, 683]; [C §10] Kt 2.73 mN·m/A, 28.5:1, 43.2 mm wheel; 4096 counts/motor rev (1024 PPR ×4); 6 pole pairs → 90° el = 15° mech = 171 counts | Treat the sign test as valid only if the move is 0.5–2× the expected amount, **and** the encoder is still (< ~10 % of expected) in the ~20 ms before each step and at its end, **and** the other encoder stayed still.  Anything else is a disturbance → repeat the alignment (after ~3 disturbed attempts, sensorless and report; never latch).  Latch the wiring fault only on **two** consecutive clean wrong-sign results.  Move the "both moving" rule above row 6 |
| R20D-N1 | NOTE | INA239-failure path with a stuck SOVL alert | For an open R2/R3 the cross-check catches the drift first (1 A disagreement + 200 ms ≈ 0.25 s at 25 A/s, reading ~6 A).  If the reading then keeps rising to 38 A, SOVL (ALATCH = 1) re-asserts W_nFAULT after every conversion.  Row 3 reads and clears it, but the line never stays high, so row 9 ("stays low > 10 ms → gate-drive fault → latch") can fire.  That persists a weapon latch with the wrong reason, which the compute board mirrors across power cycles.  The weapon is already off, so this is harmless but misleading.  In the INA239-failure path, write SOVL/BOVL to never-trip values (or stop classifying W_nFAULT) and report "INA239 current implausible" as the reason | [D l.652, 655, 661, 691–694] | — |
| R20D-N2 | NOTE | "Drives resume" window brakes | Between lowering the DRV_OFF pin and setting MOE (~1 ms, up to ~6 ms with the nFAULT wait), TIM8/TIM20 idle INH high (OISx = 1, OSSI = 1).  With INL = 3V3 in 3x mode that turns all three high sides on: a short-circuit brake.  After a 20 ms supply restart the robot can still be near top speed (~4.6 kHz electrical).  If the short-circuit current of the Mk4.1 approaches the 16 A OCP (unknown: L_s is not in the package), resume ends in drive row 2 and counts toward the 3/s latch.  Measure it in the §9 "link timeout and recover" test at top speed.  If it trips, write the per-chip coast (0x0C90) before lowering the pin and release it after MOE | [D l.214, 673, 678, 758]; [C §10] 46.5 k rpm, 6 pole pairs | — |

---

## 2. Scenario walk-through (rev L text as of round 19)

| Scenario | Path | Outcome |
|---|---|---|
| Drum impacts, single or flurries | Row 6 catch-spin; > 5/s → 1 s off; row 4 needs two consecutive fast re-trips | Safe, no latch |
| Locked/jammed drum | Row 6 / row 10 retries; row 5 passes at each stopped restart | No latch |
| Weapon phase–phase short, spinning / stopped | Row 4 / row 5 (1 ms-averaged max \|W_Vx\|, stopped-drum gate) | Latched |
| Weapon phase–GND short | Row 8 VDS OCP | Latched |
| Bounce under weapon load, drum at speed | Row 2 supply; the drum holds the bus ≥ its BEMF after the break | Bounded restart |
| Bounce ≥ ~1–3 ms, drum stopped, drives running | Both DRV8316 VM < 4.2 V → registers reset → row 1 → resume without rewrite → loop | **R20D-01**: "supply unstable" hold, match lost |
| Bounce during weapon brake | Row 1 looks open → row 0 decides; current returns → supply restart | Bounded, no hold |
| Switch opened, drum coasting, operator hands off | Row 0 after 100 ms (estimate = idle) | Safe |
| Switch opened, drum coasting, operator driving | Load clause → INA239-failure path; drives run on drum energy ~1–3 s | **R20D-02** |
| Switch opened while braking | Row 1 → row 0 hold; D1 takes one overshoot | Safe |
| Switch opened, weapon armed and motoring | Bus falls ≥ 2 V/ms (not steady) → supply events → budget hold; the drum then coasts → row 0 | Safe, bounded |
| C2 cracked short, drum stopped or spinning | "Bus above drum BEMF" / "drum stopped" → INA239 path | Weapon off, drives on (R19D-02 closed) |
| R2/R3 open | Cross-check at ~0.25 s → INA239 path; later SOVL may mislabel a latch (N1) | Safe |
| Pushing / being pushed; wall stall | Regen suspends row 0; stall 5 s → no fault | Sound |
| MCU reset mid-match, then shoved during alignment | Row 6 wrong-sign latch before row 7's "nudged" rule | **R20D-03** |
| Drive short (one chip) | OCP → row 2 → > 3/s latch, coasted, INH high | Sound |
| DRV8316 unpowered / deaf | Row 3 / row 4 (≥ 3 reads) | Sound |
| Compute-board reboot, radio drop | ARM falls (52–164 ms [S arm.out]); command timeout; resume; new edge + throttle zero | Sound, no operator-less re-arm |
| Power cycle with latches | Board latch lost; compute board mirrors the weapon latch; switch-open hold not persisted | Sound |
| Pit: phase/encoder swap, J2/J3 swap, crossed bundles, weapon swap | Sign latch; row 7 "sensor cables or motor bundles" + §9 forward-move check; weapon by eye | Sound (R19D-01 closed) |

## 3. Checked and found sound

* **Round-19 fixes:**
  * the idle term in the row 0 estimate (R19D-N1);
  * the row 1 note for an open bus under drive load (N2);
  * the row-1 deferral governing drives (N3);
  * IC_STAT FAULT in the 100 Hz poll and the resume fault-recovery (N4);
  * the overload floor at the traction limit;
  * the row 7 "sensor cables or motor bundles" report and the §9 forward-move check;
  * the latch-word contents;
  * TIM1 break clear at boot, with TIM8/TIM20 cleared only through resume.
* **Parity words** (even parity recomputed): 0x0603, 0x0606, 0x1019, 0x0A4E, 0x0C90, 0x0D10, 0x0F00, 0x1818, 0x087C and 0x097D.
* **INA239 limits:** BOVL 0x17C0 × 3.125 mV = 19.0 V; SOVL 0x76C0 × 1.25 µV / 1 mΩ = 38.0 A.
* **No masked short and no operator-less re-arm.**
  * Automatic restarts happen only within a continuous ARM.
  * An ARM fall, a reset, a link recovery or a clear needs a new edge and throttle zero.
  * The drive-side nFAULT exemption applies only while the FETs are off, and resume now handles an nFAULT still low at release.
* **No reversed drive** apart from the pit wiring cases, which are covered by §9.
* **§1 margins** (hardware unchanged since round 16):
  * DRV8316 VM dV/dt: 0.80–2.26 V/µs loaded bounce, 2.66 V/µs at the −40 °C ESR, ≤ 2.09 V/µs re-close, all against 4 V/µs [S hotplug.out].
  * Q7: 16.5 / 22.0 W, 54–57 mJ.
  * ARM: 2.50–2.95 V against VT+ ≤ 2.15 V, 7–10 edges to arm, 52–164 ms to disarm [S arm.out].
  * Spin-up: 22 A peak, 14.1 V minimum.
  * D1: 32.4 V against 35 V (C1) and 40 V (DRV8316).
  * BOVL 19 V against the 20 V minimum DRV8316 OVP.
  * SOVL 38 A against the 32 A budget.
  * MT6701: 47 k rpm duty-capped, 50 k rpm encoder cap, against a 55 k rpm rating.
  * The one new margin observation is the 4.4 V minimum VM against the 4.1–4.3 V DRV8316 UVLO.  It is not a hardware problem, but it makes R20D-01 a normal-bounce case.

## 4. Summary

| ID | Sev | One line |
|---|---|---|
| R20D-01 | MAJOR | A bus dip that resets both DRV8316s (VM UVLO 4.1–4.3 V; sim bounces already reach 4.4 V) goes to drive row 1, and "drives resume" has no rewrite.  The chips run in reset-default 6x mode, the poll re-triggers row 1, and the supply budget ends in "supply unstable" with everything held.  An operator clear cannot fix it.  Fix: resume checks NPOR/registers and rewrites before Release and MOE |
| R20D-02 | MINOR | The row 0 load clause ("drives draw ≥ 1 A proves the pack path") is false when a coasting drum sources the drives.  An opened switch while driving becomes an "INA239 failure" and the robot stays drivable for ~1–3 s on drum energy (re-opens R17D-02).  Fix: weapon-only load clause; the cross-check defers to row 0 when a spinning drum could be the source |
| R20D-03 | MINOR | The alignment sign test has no magnitude/stillness window, and row 6 pre-empts row 7's "nudged → repeat".  A shove during a post-reset re-alignment (≈ 860 counts/mm against 171 expected) latches a drive as a wiring fault.  Fix: validity window, disturbance → retry, two clean wrong-sign results to latch |
| R20D-N1..N2 | NOTE | A stuck SOVL alert after the INA239-failure path can mislabel a weapon latch; the resume window short-brakes the drives (check OCP at top speed) |

**Verdict: 0 BLOCKER, 1 MAJOR, 2 MINOR, 2 NOTE.**  All three findings are firmware-contract text; no hardware change is
needed.  Every other walked scenario ends safe and bounded, with no masked short and no operator-less re-arm.
