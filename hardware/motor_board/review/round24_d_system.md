# Review round 24 / D: system-level review (rev L)

**Reviewer role:** adversarial system reviewer (power electronics and combat robotics).

**What I read:**
* DESIGN.md rev L, all of it (783 lines).
* design/calcs.md and spice/*.out.
* review/CHANGES.md for rounds 1–23.
* round23_d_system.md, plus the R23A-01 entry of round23_a_hardware.md, which is the origin of the round-23 row 0 text.

**Scripts:**
* I copied the package without datasheets/ and review/ to `/tmp/r24d/`, ran `design/motor_board.py` and `design/calcs.py` there, then deleted the copy.
* `motor_board.py` printed "237 refs (205 placed components), 160 nets, 67 BOM lines / checks: OK".
* The regenerated calcs.md, nets.md, netlist.csv and bom.csv are byte-identical to the package.
* I did not re-run the SPICE decks, because the hardware has not changed since round 16.
* I wrote a small pure-Python model of the INA239 conversion stream (0.3 ms per shunt+bus pair) through a weapon brake, to check the row 0 numbers below.

Apart from this file, nothing in the package was edited.

**Evidence tags:**
* **[D l.N]** = a DESIGN.md line (current numbering).
* **[S file]** = a spice output.
* **[C §N]** = a calcs.md section.

---

## 1. Findings

| ID | Sev | Area | Finding | Evidence / numbers | Fix |
|---|---|---|---|---|---|
| R24D-01 | **MAJOR** | §8.1 row 0, with the round-23 change "the weapon never suspends it" | **After an ordinary weapon brake, the signed 100 ms mean of pack current passes slowly through zero.  Nothing suspends row 0 at that point, so the plausibility clause sends the board to the INA239-failure path, and the weapon is held off until an operator clear.  This happens with the switch closed and nothing broken.**<br><br>**1. The rule.**  Row 0 tests "pack current \|I\| < ~30 mA … as a ≥ ~100 ms mean (INA239 readings averaged)".  The readings are averaged first and the magnitude is taken afterwards, so this is a *signed* mean.<br><br>**2. What changed in round 23.**<br>• Before round 23, a regenerating weapon suspended row 0, and the suspension dropped those samples and restarted the mean.  The negative regen samples never entered the average.<br>• Round 23 removed the weapon from the suspension: "the weapon never suspends it, and its negative term is left out of the estimate test".<br>• So a commanded weapon brake is now averaged together with whatever follows it.<br><br>**3. The mechanism.**  In a brake to stop, the pack current goes from about −10 A of regen, back through 0, to +idle.  A 100 ms window that holds the end of that brake plus the idle current that follows has a mean that crosses zero slowly.<br><br>**4. The numbers.**  I modelled a brake to stop at a constant 10 A of regen over 0.4 s, sampled every 0.3 ms.  For t between 0.4 and 0.5 s the window mean is M(t) = I_board − 125·(0.5 − t)² A.<br>• **Drives idle** (I_board ≈ 0.11 A): \|M\| < 30 mA for **8.1 ms**, which is ~27 consecutive conversions.  It is always caught.<br>• **Drives drawing 1 A:** \|M\| < 30 mA for **2.4 ms**, ~8 conversions.  Also always caught.<br>• **Reversal** (brake, then +20 A of spin-up): the mean crosses zero within ~1 sample.  About one reversal in a few is caught.<br>• With non-overlapping 100 ms blocks instead of a sliding window, about 8 % of brakes to stop are caught (drives idle).<br><br>**5. What each case does.**<br>• **Brake to stop:** the crossing comes ~5–65 ms after the drum has stopped, with the bus at the pack voltage.  None of the suspensions applies: no drive is regenerating, and the estimate (idle + drives) is ≥ 0.11 A.  Plausibility then matches "≈ 0 A with a steady bus while the drum is stopped" and takes the INA239-failure path.  The weapon is off until the operator clears it, and the hold is stored in the latch word [D l.698–700].<br>• **Brake to a lower speed:** plausibility matches "bus clearly above the drum's back-EMF", with the same result.<br>• **Reversal:** the weapon is motoring at ≥ 1 A, so plausibility matches and the result is the same.<br>• **If plausibility did not match:** row 0 itself holds.  Drives go off and everything stays held until an operator clear.<br><br>**6. Why it matters.**  Any commanded weapon stop or deceleration in a match can lose the weapon until the driver clears it, disarms and re-arms.  The contract offers braking explicitly: "a commanded stop while armed can brake at the ~10 A regen limit", and an invertible drum reverses by a controlled deceleration [D l.523, l.619].<br><br>**7. Why round 23 did not see it.**  Round 23 argued that "a regenerating dip lasts only milliseconds" and so cannot hold the mean.  That is true of a bounce, but not of a mean that passes through zero after a sustained brake.<br><br>**8. Not caught by the §9 tests.**  §9 step 6 ("brake hard into a full pack with it closed → row 1 over-voltage restart, no hold") only looks at the row 1 outcome.  Nothing afterwards checks for a spurious INA239-failure report or a spurious hold. | [D l.652] row 0 text: signed mean, weapon excluded from the suspension, plausibility clauses; [D l.698–700] INA239-failure hold; [D l.619] regen ~10 A, ≈ 0.4 s from full speed; [C §9] idle 100–120 mA; CHANGES R17A-02 (the averaged mean relied on the suspension) and R23D-01 fix text; model output above | Make the row 0 statistic immune to a sign change.  Use **either**:<br>• **\|I\| < ~30 mA on every conversion** (or on each ~1 ms average) over ≥ 100 ms.  The idle ≥ 0.1 A then breaks the run the moment regen ends.<br>• **The mean of \|I\|** instead of the \|mean\|.<br><br>Apply the same statistic to the plausibility and cross-check inputs.  Optionally also let a weapon under a **braking (negative-torque) command** suspend row 0 again, with the samples dropped and the mean restarted.<br><br>Keying the suspension on the *command* keeps the R23D-01 fix: a weapon under throttle has a positive command, so it still never suspends row 0.  An open switch during a commanded brake is caught by the bus rise (18.5 V coast / row 1) [D l.653, l.769].<br><br>Add to §9 step 6: "brake the drum to a stop and reverse it with the switch closed, drives idle and driving → no INA239-failure report and no switch-open hold" |
| R24D-02 | MINOR | §8.1 row 0 instant-coast clause (R23A-01 wording) | **The instant coast also fires on the closed-switch zero crossing at the end of every weapon brake.  An invertible drum's reversal becomes a stopped-drum restart.**<br><br>**1. The clause.**  It coasts "a weapon under FOC with electrical power ≤ 0 while the INA239 reads \|I\| < ~50 mA on 3 consecutive conversions (~1 ms)".  The round-22 qualifier "motoring command" (B22-04) was dropped in the round-23 rewrite, so a commanded brake qualifies.<br><br>**2. The dwell is longer than the test.**<br>• During a constant-torque brake the weapon's bus current falls linearly with speed: 10 A → 0 in 0.4 s, which is 25 A/s.<br>• The pack current (board load + weapon) therefore sits inside ±50 mA for 0.1 A / 25 A/s ≈ **3.9 ms** (model).  That is > 3 conversions, so the clause fires deterministically.<br>• R23A-01 called a closed-switch match "a rare coincidence".  At the end of every brake it is not.<br><br>**3. Where the crossing falls.**  It is where the weapon's regen equals the board load:<br>• ~1 % of full speed (~280 rpm) with the drives idle;<br>• ~11 % (~2.8 k rpm) with 1 A of drive load.<br><br>**4. Consequences.**<br>• **Brake to stop:** harmless.<br>• **Brake to a lower speed, drives loaded:** a coast plus a catch-spin gap.<br>• **Reversal with the drives near idle:** the weapon restarts at once because pack current returns.  But the drum is at ≲ 280 rpm, so the restart counts as a "restart with the drum stopped" and row 5's resistance check runs first (≥ 200 ms window, waits for a stop, times out at ~2 s) [D l.657].  The reversal is delayed by **0.2–2 s**, and the event is counted and reported as the open-switch signature, which is misleading.<br><br>**5. Severity.**  Bounded and safe, and it clears without an operator.  A nuisance, not a latch | [D l.652] clause; [D l.657] row 5 applies to "every restart with the drum stopped"; [D l.619] ~10 A regen, ≈ 0.4 s; CHANGES B22-04 ("motoring command") vs R23A-01; model: 3.9 ms inside ±50 mA, first at 394 ms (drives idle, 1.1 % speed) / 354 ms (1 A, 11 %) | Restore the command qualifier: the instant coast applies only with a **non-negative torque command** (throttle held, or zero-torque FOC).<br><br>An open switch during a commanded brake is not lost: the bus rises (the 18.5 V coast, or row 1 "looks open") and row 0 follows [D l.653; §9 l.769].<br><br>Optionally, do not count a coast in which the pack current returns within one conversion as a "switch-open" event |

**NOTEs** (no change needed, or wording only):

* **R24D-N1: "encoder suspect" also absorbs a drive short at standstill.**
  * Step 2 treats "an OCP at a zero preset" as a dead encoder: it goes to the no-encoder branch, never latches, and is retried every ~0.5 s.
  * With a healthy encoder and a truly still rotor, a zero preset draws no current.  An OCP there is therefore a phase-to-GND or phase-to-VBAT short, not an encoder fault.
  * The same applies to an OCP during the step-3 alignment, which has no valid angle, so it goes to "see (2)".
  * The result is a masked short, but it is harmless: the DRV8316's latched OCP ends each attempt within its deglitch, and one attempt every 0.5 s is negligible stress.  A phase-to-phase short is current-regulated by FOC and ends in row 6 (b) → sensorless.
  * Suggested: report it as "OCP at standstill or dead encoder", so the pit crew looks at the harness as well.
* **R24D-N2: the §9 switch-open-while-braking test may exercise the 18.5 V firmware coast rather than row 1.**
  * An open bus under 10 A of regen rises ~27 V/ms (10 A / 374 µF), so VBUS crosses 18.5 V and 19 V inside one conversion.
  * Whichever path acts first, row 0 then holds, so the expected result "switch-open hold" is right.
  * Only the "(row 1 →" label may not match what the log shows [D l.769].
* **R24D-N3: the round-23 fixes read correctly.**
  * The zero-preset "encoder suspect" rule closes R23D-02.
  * With the switch open under throttle, the drum's energy balance makes the weapon power ≤ 0 while the INA239 reads ~0.2 mA (U13 plus R13/R14 only), so the instant coast fires within ~1 ms.  Row 0 then confirms in 100 ms, because the estimate is idle ≥ 0.1 A.  §9's "drives stopped within ~0.1 s" is met.
  * Row 7 latching both drives removes the crossed-bundle reverse-drive case (R23D-N4).

---

## 2. Scenario walk-through (current text)

| Scenario | Path through §8.1 | Outcome |
|---|---|---|
| Impact flurry, drum at speed | Row 6 catch-spin; > 5/s → 1 s off; row 4 needs two fast re-trips | Safe, bounded, no latch |
| Jammed drum / hot FETs | Rows 10 and 6 retry; row 5 passes at a stopped restart | No latch |
| Weapon phase–phase short (spinning / stopped) | Row 4 / row 5 | Latched: no masked short |
| Weapon phase–GND short | Row 8 VDS OCP | Latched |
| Bounce under spin-up load, switch closed | Row 2 → supply budget; the instant coast may also fire for ~1 ms and restarts on the next conversion; a DRV8316 reset silently is rewritten in resume step 1 | Bounded, non-latching |
| **Weapon brake to stop, switch closed, drives idle or driving** | Instant coast at the zero crossing (harmless); the signed 100 ms mean crosses zero for 2–8 ms after the stop → plausibility → INA239-failure path | **R24D-01**: weapon held until operator clear |
| **Invertible-drum reversal** | Instant coast near zero speed → restart counted as stopped → row 5 check; mean crossing ~1 sample | **R24D-02** delay 0.2–2 s; sometimes R24D-01 |
| Switch opened, throttle held | Weapon power ≤ 0 by energy balance, INA239 ~0.2 mA → instant coast in ~1 ms → row 0 hold in 100 ms | Safe; §9 test passes |
| Switch opened, drum coasting, driving | Estimate ≥ idle, INA239 ≈ 0 → row 0 hold | Safe |
| Switch opened while braking | Bus rise → 18.5 V coast / row 1 "looks open" → row 0 | Safe (N2 label) |
| Switch bounce during regen (closed) | Row 1 looks open → pack current returns inside 100 ms → supply restart | Non-latching |
| Link blip at top speed, encoders good | Command-timeout coast; resume with the back-EMF preset → Release; weapon needs a new edge and throttle zero | Safe, no brake step |
| MCU reset while rolling | Encoder counting → Z → preset → Release; a weapon event ≤ 2 s before latches the weapon; the compute board's automatic re-arm still needs throttle zero | No operator-less weapon spin-up |
| Encoder cut while coasted, then resumed rolling | Zero preset → OCP → encoder suspect → no-encoder branch, never latches | Degraded, no latch (R23D-02 closed) |
| Dead encoder + shove during alignment | Row 6 (a) needs step-correlated motion twice → (c) repeat → sensorless | Sound |
| Pit: J2/J3 crossed or motor bundles crossed | Row 6 (a) → row 7: both drives latched until clear + re-alignment | No reversed drive |
| Pit: swapped phase or encoder pair | Two clean wrong-sign alignments → row 6a latch | No reversed drive |
| Drive short at standstill | OCP at zero preset / during alignment → no-encoder retry every 0.5 s | Harmless; label only (N1) |
| DRV8316 unpowered / deaf / resetting | Row 3 / row 4 / row 2 (> 3/s latch, INH high) | Sound |
| Compute-board hang | ARM falls in 52–164 ms [S arm.out]; ≤ 2 NRST pulses per 10 s | Safe, bounded |
| End-of-match switch-off with the drum coasting | Row 0 hold (not persisted); board dies when the bus falls below the logic cutoff; a fresh power-up clears it | Sound |

## 3. §1 margins (outputs re-read; hardware unchanged since round 16)

* **DRV8316 VM dV/dt:**
  * loaded bounce 0.80–2.26 V/µs (C1 up to its aged 0 °C bound);
  * 2.66 V/µs at C1's −40 °C limit;
  * re-close ≤ 2.09 V/µs;
  * all ≤ the §1 claim of 2.75 V/µs and within the 4 V/µs limit [S hotplug.out].
* **Soft-start:** 1.28–2.95 V/ms; Q7 22.0 W / 54–57 mJ at worst.
* **Reversed pack:** 13.1 A (the C14 spike) with D10.
* **ARM:** armed at 2.50–2.95 V against VT+ ≤ 2.15 V; 7–10 edges to arm; disarm in 52–164 ms [S arm.out].
* **Spin-up:** 22.1 A peak and 14.06 V minimum, against the 10.3 V worst-case logic cutoff.  22 A for 0.5 s is inside the XT30's 30 A burst rating [S spinup.out].
* **Weapon bridge** at 60 mA / 6 nH: VDS 29.4 V (< 40 V), SHx −4.58 V (> −7 V) [S bridge.out].
* **Voltage chain:** 16.8 + 1.4 = 18.2 V < 18.3 V (test) < 18.5 V (coast) < 19 V (BOVL) < 20 V (OVP minimum); D1 32.4 V < 35 V (C1) < 40 V.
* **Row 1 "open bus decays ~0.2 V/ms":** the board's ~1.8 W at 19 V is ≈ 95 mA, and 95 mA / 374 µF = 0.25 V/ms.  Consistent.
* **Current and speed limits:** SOVL 38 A > the 32 A budget; MT6701 at 46.5 k rpm against its 55 k rpm rating; VBAT_SNS_H 25.7 V / 7.8 = 3.29 V.

## 4. Summary

| ID | Sev | One line |
|---|---|---|
| R24D-01 | MAJOR | Round 23 took the weapon out of row 0's suspension, but row 0 still uses a signed 100 ms mean.  After every ordinary weapon brake that mean passes through zero (for 2–8 ms after a brake to stop).  The plausibility clause then takes the INA239-failure path, and the weapon is held until an operator clear, with no fault present.  Fix: test \|I\| per conversion (or the mean of \|I\|); optionally suspend on a braking command |
| R24D-02 | MINOR | The instant coast lost its "motoring command" qualifier.  The closed-switch zero crossing at the end of a brake lasts ~3.9 ms, longer than the 3-conversion test, so the clause fires.  A reversal becomes a stopped-drum restart (row 5, 0.2–2 s).  Fix: fire only with a non-negative torque command |
| N1–N3 | NOTE | An OCP at standstill is labelled "encoder suspect" (harmless); the §9 braking-open test may show the 18.5 V coast rather than row 1; the round-23 fixes verified |

**Verdict: 0 BLOCKER, 1 MAJOR, 1 MINOR, 3 NOTE.**  Both findings are firmware-contract text in §8.1 row 0 and come from the round-23 edit; no hardware change is needed.
