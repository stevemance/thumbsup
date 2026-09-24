# Review round 25 / D: system-level review (rev L)

**Reviewer role:** adversarial system reviewer (power electronics and combat robotics).

**What I read:**
* DESIGN.md rev L, all of it.
* design/calcs.md and spice/*.out (hotplug, arm).
* review/CHANGES.md for rounds 1–24, round24_d_system.md, and round23_d_system.md §1.

**DESIGN.md changed during the review.**  The round-25 A/B fixes landed while I was reading:
* row 0 now says "a suspension, or the weapon-braking pause, restarts the 100 ms every-reading run";
* the pause is keyed on "its **explicit** braking command";
* the Release now carries the folded CLR_FLT (0x0603 → 0x097D → 0x0D10 → 0x0606);
* §9 logs the largest |I| with the switch open;
* the duplicate Round 24 heading in CHANGES.md is gone.

Every finding below is against the text as it stood at the end of the review, re-read after the change.  Two NOTEs I had drafted (the leftover "mean" wording and the duplicate heading) were fixed by B25-01 and are dropped.

**Scripts:**
* I copied the package without datasheets/ and review/ to `/tmp/r25d/`, ran `design/motor_board.py` and `design/calcs.py` there, then deleted the copy.
* `motor_board.py` printed "237 refs (205 placed components), 160 nets, 67 BOM lines / checks: OK".
* The regenerated calcs.md, nets.md, netlist.csv and bom.csv are byte-identical to the package.
* I did not re-run the SPICE decks: the hardware has not changed since round 16.
* The row 0 and row 1 numbers below are hand calculations from the package's own values: C_bus ≈ 374 µF, idle ≈ 0.1 A, regen ≤ ~10 A over ≈ 0.4 s, drive bus load 0.5–2.1 A (row 1's own "1.4–5.7 V/ms"), drum ≈ 64 J.

Apart from this file, nothing in the package was edited.

**Evidence tags:**
* **[D l.N]** = a DESIGN.md line (current numbering).
* **[S file]** = a spice output.
* **[C §N]** = a calcs.md section.

---

## 1. Findings

| ID | Sev | Area | Finding | Evidence / numbers | Fix |
|---|---|---|---|---|---|
| R25D-01 | MINOR | §8.1 row 0 weapon-braking pause (round 24) vs row 1 and the 18.5 V coast | **While an explicit weapon braking command is held, an open switch is only detected if the bus rise ends in row 1 "looks open".  Two other paths let the brake resume on the open bus.  Row 0 is paused all the while, so row 1's promise "the continuous row 0 monitor still catches the open switch within ~100 ms" no longer holds.**<br><br>**1. What happens when the switch opens during a brake.**<br>• The drum is the only source on the bus.  If regen is greater than the load, the bus rises: (10 − 2.1 − 0.1) A / 374 µF ≈ 21 V/ms, or (10 − 0.1) A / 374 µF ≈ 26 V/ms with the drives idle.<br>• Three things can act on that rise:<br>&nbsp;&nbsp;(a) The firmware 18.5 V coast [D l.618].  It has **no restart rule**, so a firmware that brakes again below ~18 V turns the brake into a hysteretic regulator of the open bus.<br>&nbsp;&nbsp;(b) Row 1, classed as **over-voltage** when the drives keep pulling 1.4–5.7 V/ms after the coast [D l.653].  That class restarts the brake at half the regen limit (10 → 5 → 2.5 A).  Each restart is ≥ the drive load again, so it re-trips or settles.<br>&nbsp;&nbsp;(c) The §8 power-budget wording "combined regen limited so the bus stays below 18.5 V" [D l.609].  If this is implemented as a bus-voltage regen limiter, the bus never reaches either trip; the brake simply feeds the loads.<br>• In all three cases the INA239 reads ≈ 0.2 mA (U13 + R13/R14 only), because by energy balance the drum feeds exactly the loads.  Row 0 would see that, but it is **paused**.  The instant-coast clause needs a zero or positive torque command, so it does not apply either.<br><br>**2. How long it lasts.**  Until the braking command ends:<br>• A brake to stop that feeds only the board (~1.7 W) plus windage takes about the free coast-down time, **10–40 s** [D l.524].  With the drives driving (~30 W) it takes ~2 s.<br>• For an invertible-drum reversal the "brake" phase lasts until the drum stops.  The reverse spin-up then collapses the bus, and the board browns out.<br><br>**3. What the robot does meanwhile.**<br>• The drives are live and answer the sticks.<br>• The weapon keeps cycling brake/coast.<br>• No switch-open flag is raised.<br>• With (b), if a fourth over-voltage class lands within 10 s, the result is a **persisted weapon latch labelled "over-voltage"**.  That is the crew-training outcome row 0 is meant to avoid.<br><br>**4. When row 1 "looks open" does fire** (the bus rise reaches BOVL, the drives are OVP'd or idle, and VBUS stays above 18 V for 0.6 ms):<br>• The weapon coasts, and the drives are deferred to row 0.<br>• But row 0 stays paused for as long as the operator's explicit braking command is held.<br>• Everything is inert, which is safe, but the hold and its report wait on the stick.<br>• The §9 step 6 expectation "open the power switch while braking → (row 1 →) switch-open hold" [D l.768–769] is therefore met only after the brake is released.<br><br>**5. The other direction ("explicit").**  A speed-loop deceleration is a negative torque command without an explicit brake, so it is not paused.  Its end-of-brake crossing dwell in ±30 mA is 60 mA ÷ slope:<br>• 2.4 ms at the 10 A limit;<br>• 38 ms after two row 1 halvings (2.5 A);<br>• **154 ms** after three halvings (1.25 A).<br>Beyond 100 ms, a closed-switch false switch-open hold is possible.  It needs three prior over-voltage events, so it is rare.<br><br>**6. Severity.**  Everything is bounded by the drum's energy, and every end state coasts or browns out.  No damage and no latch in the common case.  But the "no masked open switch" property and row 1's text are wrong while a brake is held | [D l.652] pause "while the weapon has a braking command … only its explicit braking command pauses it"; [D l.653] "may read as over-voltage instead; the continuous row 0 monitor still catches the open switch within ~100 ms", over-voltage → restart with the regen limit halved, > 3 in 10 s → latch; [D l.609] "regen limited so the bus stays below 18.5 V"; [D l.618] 18.5 V coast, no restart rule; [D l.619] ~10 A, ≈ 0.4 s; [D l.524] coast-down 10–40 s; [D l.768–769] §9 test; [C §9] idle ~100–120 mA; rise and dwell arithmetic in the Finding column | Key the pause on the **weapon controller's state**, not on the operator input.<br>• It applies while the weapon is under FOC with a **negative (regenerating) torque command**, including a speed-loop deceleration.<br>• It ends at once when any protection coasts the weapon (18.5 V coast, BOVL/row 1, break).<br><br>After **any** over-voltage coast (the 18.5 V firmware coast or row 1 "over-voltage") whose post-coast INA239 readings show \|I\| < ~50 mA, do **not** resume the brake until pack current returns (\|I\| > ~50 mA).  This is the same rule as the instant coast.  With the switch closed the dump leaves ≥ +idle, so a closed-switch full-pack brake is unaffected.<br><br>State that the regen limit is a **current** limit (checked by the §9 step 6 < 18.3 V peak), not a bus-voltage regulator.<br><br>Fix row 1's sentence to "… row 0 catches it within ~100 ms once the weapon is coasted".<br><br>In §9, expect the hold ~100 ms after the coast, with the brake stick still held |

**NOTEs** (no change needed, or wording only):

* **R25D-N1: the instant coast also fires on a zero-torque weapon with the switch closed.**
  * The clause admits a *zero* torque command.  At zero torque the weapon's power sits at ≈ 0, which is "≤ 0" by noise.
  * When the drives regenerate (robot braking), pack current = idle − drive regen crosses zero.  At a ~5 A/s drive-regen slope the dwell inside ±50 mA is ~20 ms, longer than the 3-conversion (~1 ms) test.
  * The result is a coast of a weapon that was producing no torque, plus a "switch-open signature" count.  If the drum is stopped, the "restart when pack current returns" then runs the row 5 DC steps at zero throttle (a small drum twitch).
  * Harmless.  Suggested: for a zero command, coast without a restart or a count; restart only on the next non-zero command.
* **R25D-N2: the 18.5 V firmware coast has no restart or classification rule of its own** [D l.518, l.618].  Row 1 covers BOVL (19 V) only.
  * With the switch closed, a brake into a full pack that peaks between 18.5 and 19 V is coasted, and nothing says when it resumes.
  * Suggested: "handled as row 1", which also closes the (a) path of R25D-01.
* **R25D-N3: the round-24 row 0 fixes check out numerically for the closed switch.**
  * The every-reading test rejects the end-of-brake zero crossing (2.4 ms dwell at 25 A/s, drives idle, vs 100 ms).
  * The instant coast no longer fires during a brake (negative command).
  * The brake-and-reverse with the switch closed, drives idle or driving, gives no hold and no INA239-failure report (the new §9 test at [D l.780–781] covers it).
  * A switch opened under throttle is caught: the instant coast within ~1 ms, then the row 0 hold at 100 ms, since the estimate is ≥ idle.
  * A coasting drum in the pit is held within 100 ms.  The body-diode feed is never a suspension, and the plausibility clauses do not match.

---

## 2. Scenario walk-through (current text)

| Scenario | Path through §8.1 | Outcome |
|---|---|---|
| Weapon brake to stop, switch closed, drives idle / driving | Paused while braking; the end-of-brake zero crossing lasts 2.4 ms (< 100 ms); the cross-check is off while braking; no instant coast (negative command) | Clean |
| Invertible-drum reversal, switch closed | Pause during decel; spin-up draws ≥ idle + copper loss (power > 0 at ω ≈ 0) | Clean, no row 5 delay (R24D-02 closed) |
| Brake into a full pack, switch closed | 18.2 V < 18.3 V (§9) < 18.5 V; a BOVL dump reads ≥ +idle → over-voltage restart at half regen; > 3 in 10 s → latch | Bounded; see N2 for the 18.5 V coast |
| **Switch opened during a brake, drives idle** | Rise ~26 V/ms → BOVL → looks open → row 0, paused while the brake stick is held | Safe, inert; the hold waits for the stick (R25D-01 §4) |
| **Switch opened during a brake, drives pulling** | Rise ~21 V/ms; 18.5 V coast with no rule, or row 1 over-voltage → brake resumes at half regen on the open bus; row 0 paused | **R25D-01**: drives live on drum energy until the brake ends (~2 s, up to 10–40 s idle-loaded); possibly a persisted "over-voltage" latch |
| Switch opened in the brake's tail (regen < load) | Bus falls; fold-back or brown-out within the remaining ≤ ~85 ms of brake | Safe |
| Switch opened under throttle | Instant coast (~1 ms) → row 0 hold in 100 ms | Safe (N3) |
| Switch opened, drum coasting (disarmed), with or without driving | INA ≈ 0.2 mA, estimate ≥ idle → hold in 100 ms | Safe |
| Switch opened while shoved (drive regen) | Row 0 suspended while a drive regenerates; the robot's KE is ≈ 3 J, so this lasts < 1 s | Safe, bounded |
| Contact bounce 0.1–3 ms under spin-up, switch closed | Row 2 supply; the instant coast may fire on ≥ 1 ms bounces and restarts when current returns | Bounded, non-latching |
| Bounce during regen, switch closed | Row 1 looks open → pack current returns → supply restart | Non-latching |
| Row 0 hold, cleared with the switch still open | Drives resume, row 0 re-holds within 100 ms; the weapon needs a disarm, a new ARM edge and throttle zero | Bounded |
| MCU reset while the switch-open hold is active | The hold is not in the latch word; after the reset, row 0 re-detects in 100 ms; the weapon needs a new edge | Bounded |
| Resume at speed (link blip, MCU reset) | Back-EMF preset → Release (with the folded CLR_FLT) → nFAULT wait; OCP at a zero preset → encoder-suspect branch | Sound (settled) |
| Crossed J2/J3 or motor bundles; swapped phase pair | Row 7 (both latched) / row 6a | No reversed drive |
| Weapon short, spinning / stopped / to GND | Row 4 / row 5 / row 8 | Latched; no masked short |
| Compute-board hang | ARM falls in 52–164 ms [S arm.out]; ≤ 2 NRST pulses per 10 s | Safe |
| Re-arm after a motor-MCU reset | Automatic re-toggle only without a latch; throttle-zero interlock | No operator-less spin-up (settled) |

## 3. §1 margins (outputs re-read; hardware unchanged)

* **DRV8316 VM dV/dt** [S hotplug.out]:
  * loaded bounce 0.80–2.26 V/µs;
  * 2.66 V/µs with C1 at its −40 °C ESR;
  * re-close ≤ 2.09 V/µs;
  * all ≤ the §1 claim of 2.75 V/µs and < 4 V/µs.
* **ARM** [S arm.out]:
  * armed at 2.50–2.95 V, against VT+ ≤ 2.15 V;
  * 7–10 edges to arm;
  * disarm in 52–164 ms, against the §1 "~30–200 ms";
  * pause tolerance ≥ 52 ms, against the §3.5 "~45–50 ms nominal" (conservative).
* **Voltage chain:** 16.8 + 1.4 = 18.2 V < 18.3 V (test) < 18.5 V (coast) < 19 V (BOVL) < 20 V (OVP minimum).  D1 32.4 V < 35 V (C1) < 40 V.
* **Row 1 "open bus decays ~0.2 V/ms":** ~95 mA / 374 µF = 0.25 V/ms.  Consistent.
* **Soft-start and spin-up:** 1.3–3.0 V/ms; 22 A peak and 14.1 V minimum against the 10.3 V worst-case logic cutoff [C §7, §9].
* **5 V budget:** 450 mA to the compute board [C §4].

## 4. Summary

| ID | Sev | One line |
|---|---|---|
| R25D-01 | MINOR | The round-24 braking pause is keyed on the explicit command.  An open switch during a brake is then masked whenever the 18.5 V coast (which has no restart rule), a row 1 "over-voltage" class, or a voltage-type regen limiter lets the brake resume on the open bus.  The drives run on drum energy until the brake ends, and row 1's "row 0 still catches it within ~100 ms" is wrong.  Fix: pause only while the weapon is under FOC with a regenerating torque command (a protection coast ends it); do not resume a brake after an over-voltage coast with \|I\| < 50 mA until pack current returns; the regen limit is a current limit |
| N1–N3 | NOTE | A zero-torque instant coast on a closed switch (harmless); the 18.5 V coast needs a rule (row 1); the round-24 fixes verified |

**Verdict: 0 BLOCKER, 0 MAJOR, 1 MINOR, 3 NOTE.**  The hardware and §1 margins are unchanged and consistent.  The only finding is firmware-contract text around the round-24 braking pause, and it is bounded and safe in every walked scenario.
