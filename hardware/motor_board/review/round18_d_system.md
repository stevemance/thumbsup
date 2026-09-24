# Review round 18 / D: system-level review (rev L)

Reviewer role: adversarial system reviewer (power electronics and combat robotics).  I read DESIGN.md rev L end to end,
design/calcs.md, spice/hotplug.out, arm.out and spinup.out, review/CHANGES.md (rounds 1–17) and round17_d_system.md, plus
the INA239 datasheet (input bias) and the netlist entries for the INA239 input network.  The package was copied to
`/tmp/r18d/`; nothing in the package was edited apart from this file.  The focus was the round-17 §8.1 text: the row 0
monitor and its suspension rules, row 1 (BOVL with the pack-current sign and a restart cap), the row 5 stopped-drum check
with its timeout, drive row 7 (swapped sensor cables), and the separate, non-persisted switch-open hold.

Evidence tags: **[D l.N]** = DESIGN.md line, **[S file]** = spice output, **[C §N]** = calcs.md, **[INA]** = INA239.pdf,
**[N]** = design/motor_board.py / nets.md.

---

## 1. Findings

| ID | Sev | Area | Finding | Evidence / numbers | Fix |
|---|---|---|---|---|---|
| R18D-01 | MINOR | §8.1 row 1: BOVL with pack current ≥ ~0 → "row 0 hold at once" | **Row 1 turns a contact bounce during regen into the full-robot, operator-clear hold, skipping row 0's 100 ms persistence.  Round 16 added that persistence (R16D-01) precisely so that bounces never cause this hold.**<br>• Net regen into the bus while the contact is open charges the ~374 µF bus at I/374 µF: **26.7 V/ms** during a 10 A weapon brake, and ~1.3–2.7 V/ms at 0.5–1 A net drive regen (a robot shoved backwards with the weapon idle or coasting: 2 × ~5 W back-driven at 1–1.5 A, minus the ~0.1 A idle).<br>• From a ~16–16.5 V bus, 19 V is reached after ~0.1 ms (weapon brake) or ~1.1–2.3 ms (drive regen).  One 150 µs bus conversion later, BOVL trips.  These are inside the 0.1–3 ms bounce range the design itself simulates and tests [S hotplug.out; D l.763].<br>• For a bounce of ≳ 0.4 ms, the shunt conversion before the trip lies wholly inside the open window, so it reads ≈ 0 A.  Row 1 then says "the switch is open: row 0 hold at once, no restart".  The weapon coasts and the drives go off until the operator clears it: the same match-losing outcome R16D-01 was rated MAJOR for.<br>• "At the trip" is also ambiguous against the classifier architecture, which evaluates ~0.5 ms after the event on post-event conversions [D l.631–634].  After the break the weapon has stopped regenerating, and the pack is back (bounce over, or never gone in the rare pack-connected BOVL).  Post-event current is therefore ≥ 0 (the idle ~+0.1 A, after a brief C1 discharge into the pack).  So a **pack-connected** over-voltage, the branch row 1 means to restart, is classified as "switch open" and held.<br>• The restart cap added in round 17 already bounds the D1 energy.  The immediate hold is not needed for safety | [D l.651 (row 0, ≥ 100 ms), 652 (row 1), 617 (150 µs conversions), 631–634 (post-event classification), 619 (~10 A regen limit), 763–764 (bounce tests 0.1–3 ms, "no latch")]; [S hotplug.out] bounce set 0.1–0.8 ms; 374 µF [D l.109]; drive regen: Kt 2.73 mN·m/A [C §10] × 1.5 A × 1309 rad/s (1 m/s push) ≈ 5.4 W per motor | On BOVL with the pre-trip pack current ≥ ~0: coast the weapon, block weapon regen and **hand over to the row 0 monitor**, with no restart until pack current is seen again.  If pack current (> ~+50 mA, or any charging current) returns within row 0's 100 ms, count a supply event (supply budget) and restart as row 2 does.  Otherwise row 0 holds.  The weapon stays coasted meanwhile, so no further regen reaches D1.  Define "at the trip" as the most negative shunt reading in the ~1 ms before the break, from a short history.  Do not use the post-event register.  §9 step 6: a 1 ms pack-lead interruption during a weapon brake gives a supply event, no hold |
| R18D-02 | MINOR | §8.1 row 0 suspension: "or while firmware's own pack-current estimate is within ~50 mA of zero" | **The second suspension clause re-opens R17D-02.  Round 17 excluded coasting motors from the negative-power clause only.**<br>• A pack-current estimate built from measured phase power (V × I summed over all channels, + idle) includes the coasting drum.  During coast the CSAs and W_Vx still measure its body-diode rectification [D l.150–152, 183].<br>• With the switch open, that rectified power is exactly what feeds the board (§7.5).  A physically correct estimate therefore equals the true pack current, ≈ 0.  Row 0 is then suspended for its whole main case: switch opened at end of match with the drum coasting disarmed.  The robot stays drivable on drum energy for seconds (down to ~19 k rpm) while the crew handles it.<br>• With the switch closed, a coasting drum never rectifies (BEMF ≤ 14.2 V < pack, R17D-02).  So restricting the estimate costs nothing | [D l.651, 522 (§7.5)]; [S spinup.out] 25 573 rpm, 1800 KV → 14.2 V | Say that the estimate is idle + the power of **actively driven** channels only (commanded, or measured on enabled bridges).  A coasting (Hi-Z) channel contributes 0, as in the first clause |
| R18D-03 | MINOR | §8.1 row 0 with a failed pack-current channel (INA239 reads ~0 A with the pack connected) | **One shorted 0603 cap makes row 0 hold the whole robot at every clear.  The design's stated response to an INA239 loss is the opposite: weapon off, drives continue [D l.692–693].**<br>• C2 (100 nF 0603, directly across IN+/IN− [N l.128; nets INA_INP/INA_INN]) sits in the pack-current region.  §6.10 itself names flex cracks as the realistic MLCC impact failure, and a cracked MLCC typically fails short.<br>• With C2 shorted, the INA239 reads its offset, ≈ 0 A.  DEVICE_ID and every config read-back stay correct, so the SPI-health check passes.<br>• Row 0 then matures 100 ms after any idle period (|I| < 30 mA, VBUS > 8 V, no regen) and holds everything.  After an operator clear it fires again within 100 ms.  Mid-match (a crack on impact) the robot is **immobile for the rest of the match**.<br>• SOVL protection is also silently gone: it can never trip on a zero reading.<br>• Distinguishing this from a real open switch is cheap.  With the switch open, only a spinning drum can hold the bus up (or regenerating drives, which already suspend row 0).  C1 alone at the ~0.1 A idle falls ~27 V in 100 ms (0.27 V/ms).  So "|I| ≈ 0 for 100 ms, VBUS steady, drum stopped (W_Vx line-to-line ≈ 0) or its BEMF well below VBUS" is impossible with the switch open: the pack is connected and the current channel has failed | [D l.110, 651, 692–693, 480–481 (§6.10 flex cracks)]; [N] C2 100 nF 50 V 0603 on INA_INP–INA_INN; bus decay 0.1 A / 374 µF = 0.27 V/ms.  (An open R2/R3 instead drifts at IB/C2 ≤ 2.5 nA / 100 nF = 25 mV/s [INA] and saturates within seconds: SOVL, row 3 fold-back loops, weapon unusable, drives unaffected; bounded, and not this case) | Add a plausibility gate to row 0: it may match only while the bus is decaying (≳ 0.1 V/ms), or while a spinning drum can be supplying it (weapon line-to-line BEMF ≥ VBUS − ~1 V).  A steady bus with |I| ≈ 0 and no such source → "INA239 current implausible" → the INA239-only failure path (weapon off, drives continue on VBAT_SNS, report).  Optionally also check that weapon motoring ≥ ~5 A for ≥ 50 ms shows ≥ half of that as pack current |
| R18D-N1 | NOTE | Row 0 mean vs suspensions | The text still does not say whether a suspension restarts the ≥ 100 ms mean or only drops the suspended samples (asked in R17D-01).  Restarting it lets an operator who keeps braking the drives (switch open, drum holding the bus) postpone the hold.  This is bounded by the drum's hold-up time, but state "suspended samples are excluded; the mean is not restarted" | [D l.651] | — |
| R18D-N2 | NOTE | Drive row 7 false positive on a disturbance | "The other encoder moved" is the only criterion [D l.682].  A robot nudged during a mid-match re-alignment (after an MCU reset) moves both encoders and sends **both drives to sensorless** until an operator clear: weak standstill torque in a pushing match.  The two cases separate cleanly.  With swapped cables the aligning drive's **own** input sees ~0 and the other ~171 counts.  With a disturbance the own input sees the expected motion and the other moves too.  Take row 7 only when the own input stayed still; on a disturbance, retry the alignment | [D l.614, 682] | — |
| R18D-N3 | NOTE | Drive row 1 "bus event" has no over-voltage branch | During an open-contact regen spike (R18D-01, or the switch opened while braking) the bus crosses the DRV8316 OVP (20 V min, spread to 22 V).  Often only one chip trips.  That is drive row 2 (per-drive, counted toward > 3/s latch), not supply.  One event per bounce is far from the latch count, so this is bounded.  Add "BOVL or VBUS > ~19 V within ~1 ms" to the drive row 1 evidence for consistency | [D l.612 (OVP 20 V min), 676–677] | — |

---

## 2. Scenario walk-through (current rev L text)

| Scenario | Path | Outcome |
|---|---|---|
| Drum impacts, single or flurries | Row 6 → catch-spin after 50–100 ms; > 5/s → 1 s off; row 4 needs two consecutive fast re-trips ≤ 200 µs after the first vector; row 5 only at a stopped drum (~3 ms, passes on a healthy motor) | Safe, no latch |
| Bounce under heavy load (weapon motoring) | Bus falls; U2 UVLO break → row 2 (VBUS < 10 V or slope ≥ 7–10 V/ms) → restart after 20 ms steady; row 0 needs a 100 ms mean | Bounded, no hold |
| Bounce under light load | No break, or row 7 (counted) | Accepted residual (R16) |
| Bounce during net regen (weapon brake, or drives back-driven with the weapon idle) | BOVL → row 1 → pre-trip current ≈ 0 → immediate row 0 hold | **R18D-01** |
| Pushing / being pushed | Drives regenerate → row 0 suspended (actively driven, negative power) | Sound |
| Jammed drum | Row 10: 0.5 s at the limit, 1 s coast, retry; row 5 at each stopped restart passes | Retries, no latch |
| Wheel in the air | Duty cap 46.5 k rpm < 50 k encoder cap < 55 k MT6701 [C §10] | Sound |
| Weapon phase–phase short, spinning | Row 6 → second fast re-trip → row 4 latch; or the short brakes the drum → stopped → row 5 latch | Latched, bounded |
| Weapon phase–phase short, stopped | Row 5 at the first start after arming or at any stopped restart | Latched |
| Weapon phase–GND / phase–VBAT short | VDS OCP → row 8; or the comparator → rows 6/4 | Latched |
| Row 5 gate stuck (drum creeping > 50 rpm) | 2 s timeout → catch-spin restart without the check, reported; a real short brakes the drum to a stop, so the gate passes | Bounded (a missed short needs a second fault) |
| Drive short | DRV8316 OCP → drive row 2 → > 3/s latch, coasted, INH high | Sound |
| Dead / unpowered / deaf DRV8316 | Rows 3 / 4 (≥ 3 confirmed reads with the other devices healthy) | Sound |
| SPI3 fault / INA239 ID lost | Hold with retry / weapon off, drives on VBAT_SNS | Sound |
| INA239 current channel reads 0 (shorted C2) | Row 0 hold at every clear | **R18D-03** |
| Compute-board reboot | ARM decays 52–164 ms [S arm.out]; command timeout; new session, self-test at zero throttle; ARM edge + throttle zero | Sound |
| Radio drop | ≤ 0.5 s → ARM stop + command stop; throttle-zero on recovery | Sound |
| Switch opened mid-match, drum driven | Bus collapses → row 2 → supply budget; row 0 (not suspended: motoring) matures in 100 ms → hold | Safe, bounded |
| Switch opened while braking the drum | BOVL → row 1, pre-trip I ≈ 0 → row 0 hold; one D1 overshoot (~10 A × ~23 V × ≤ 0.3 ms ≈ 70 mJ) | Safe (round-17 fix works for this case) |
| Switch opened, drum coasting, disarmed | Row 0 after 100 ms, provided the estimate clause excludes the coasting drum | **R18D-02** |
| Switch opened, drum stopped | Bus reaches the 9.2 V buck cutoff in ~17–20 ms (32 mJ at 1.6–1.9 W), before row 0 matures; board off | Safe |
| Switch re-closed while the drum still holds the bus | Hold persists until operator clear; step ≤ 2.1 V/µs at VM | Intended |
| Regen into a full pack | 18.5 V firmware coast; BOVL (19 V) needs I × R ≥ 2.2 V over 16.8 V OCV, i.e. ≥ 31 A at 70 mΩ, so it is reached only with a high-R pack or lead; then row 1 → restart (cap 3/10 s), unless the post-event current is used (R18D-01) | Sound apart from R18D-01 |
| Pit repair | Drive phase swap → sign latch; encoder A/B swap → sign latch; J2/J3 swap → row 7, both drives sensorless (no reversed torque; disturbance false positive N2); weapon wire swap → visual check; weapon motor swap → re-measure the row 5 reference | Sound |
| Power cycle with latches | Board latch lost; compute board mirrors, disarms, persists and refuses until the operator clears it; switch-open hold not persisted; a forgotten short latch is re-caught by row 5 at the first start after arming | Sound |
| MCU reset / IWDG | Latch word honoured; boot coasts both DRV8316s, releases only unlatched drives, aligns one at a time; ARM edge + throttle zero | Sound |

## 3. Checked and found sound

* **§1 / §5 margins** (hardware unchanged since round 16; outputs re-read):
  * DRV8316 VM: loaded bounce 0.80–2.26 V/µs, 2.66 V/µs at C1's −40 °C ESR, re-close ≤ 2.09 V/µs, closure ≤ 0.005 V/µs, all against 4 V/µs [S hotplug.out].
  * Q7: 16.5 / 22.0 W, 53.8–56.9 mJ.
  * Reversed pack: 13.1 A with D10.
  * ARM: 2.50–2.95 V, 7–10 edges, disarm 52–164 ms.
  * Spin-up: 22.1 A pack peak, 14.06 V minimum bus.
  * D1 clamp 32.4 V against 35 V (C1) and 40 V (DRV8316).
  * SOVL 0x76C0 = 30 400 × 1.25 mA = 38.0 A against the ≤ 32 A budget; BOVL 0x17C0 = 6080 × 3.125 mV = 19.0 V against the 20 V minimum DRV8316 OVP.
* **Round-17 changes, verified:**
  * Row 1 sign test: with the switch open, RS4 carries only the C14/U13 current, so I ≈ 0 while the bus is pumped.  With the pack connected, regen is clearly negative.  The ≤ 3-in-10 s cap bounds D1.
  * Row 0 restricted to actively driven motors (clause 1).
  * The switch-open hold is a non-persisted flag.
  * Drive row 7 never re-enters encoder mode on a Z match alone.
  * Row 5 gate at ~4 LSB with calibration, averaging and a 2 s timeout.  At < 50 rpm the BEMF is ≤ 28 mV, ≤ ~10 % of the 0.25–0.5 V test drop.
* **No operator-less re-arm into a latch.**  Automatic restarts stay within a continuous ARM.  An ARM fall, reset, link recovery or clear needs a new edge and throttle zero.  Clearing is operator-only.  The compute board disarms before it persists a latch copy.
* **No reversed drive.**  A phase swap or encoder A/B swap is caught by the sign latch.  A J2/J3 swap forces sensorless, which depends only on phase order.

## 4. Summary

| ID | Sev | One line |
|---|---|---|
| R18D-01 | MINOR | Row 1's "pack current ≥ 0 → row 0 hold at once" turns a ≳ 0.4 ms contact bounce during regen (weapon brake, or drives back-driven with the weapon idle) into the full-robot operator-clear hold, bypassing row 0's 100 ms persistence.  "At the trip" read post-event also misclassifies a pack-connected BOVL.  Fix: hand over to row 0 with the weapon coasted, and use the pre-trip current |
| R18D-02 | MINOR | The second row 0 suspension ("pack-current estimate ≈ 0") is not restricted to actively driven channels.  An estimate that includes the coasting drum equals the true ≈ 0 A with the switch open and masks the end-of-match switch-off case |
| R18D-03 | MINOR | A shorted C2 (0603 across the INA239 inputs) reads 0 A with all config checks passing.  Row 0 then holds the whole robot at every clear, although the design's INA239-loss policy is to keep driving.  Fix: a physical plausibility gate (bus steady with no drum source → sensor fault, not switch open) |
| R18D-N1..N3 | NOTE | Row 0 mean handling on suspension; drive row 7 disturbance discriminator; over-voltage in the drive row 1 bus-event evidence |

**Verdict: 0 BLOCKER, 0 MAJOR, 3 MINOR, 3 NOTE.**  The hardware and the §1 margins are clean.  Every walked scenario ends
safe and bounded.  No masked short, operator-less re-arm or reversed drive was found.  The three MINORs are nuisance and
masking edges in the row 0/row 1 switch-open logic.  All are firmware-contract text fixes; no hardware change is needed.
