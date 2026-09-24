# Review round 22 / D: system-level review (rev L)

Reviewer role: adversarial system reviewer (power electronics and combat robotics).  I read DESIGN.md rev L end to end,
design/calcs.md, spice/*.out, the weapon spin-up model (spice/sim_weapon_spinup.py), review/CHANGES.md (rounds 1–21),
round21_d_system.md and R21A-01.  The package minus datasheets/ and review/ was copied to `/tmp/r22d/`, run, and deleted.
`design/motor_board.py` printed "237 refs (205 placed components), 160 nets, 67 BOM lines / checks: OK".  `design/calcs.py`
regenerated calcs.md byte-identical.  Round 21 changed text only, so no SPICE deck was re-run.  Nothing in the package was
edited apart from this file.

Evidence tags: **[D l.N]** = DESIGN.md line, **[S file]** = spice output, **[C §N]** = calcs.md, **[N]** = design/nets.md.

---

## 1. Findings

| ID | Sev | Area | Finding | Evidence / numbers | Fix |
|---|---|---|---|---|---|
| R22D-01 | MAJOR | §8.1 row 0, the round-21 "positive torque, negative power → coast at once" clause | **The new instant coast fires in normal operation with the switch closed, and it has no exit.  So the weapon drops out, and stays out, while the operator holds throttle.**<br><br>**1. The trigger has no pack-current gate.**  The rule is "a weapon with a positive torque command but negative electrical power is instead coasted at once … and the coasting-drum rules then apply" [D l.652].  Unlike the rest of row 0, it does not depend on the INA239 reading \|I\| < 30 mA or on any persistence.<br><br>**2. The same signature appears with the switch closed.**  A drum held at full throttle settles at its voltage limit.  From there it only needs a small bus dip to regenerate:<br>• The package's own spin-up model [S spinup.out, sim_weapon_spinup.py] settles at 25.6 k rpm, with a phase current of 2.7 A against windage and 15.24 V on the bus.<br>• The only voltage headroom is I·R = 2.7 A × 0.1 Ω = **0.27 V**.  A bus dip of **≥ 0.28 V** therefore turns the weapon current, and its electrical power, negative.<br>• Normal driving produces that dip on the 70 mΩ pack + lead.  Two drives reversing at speed swing the bus current by ~4.5 A (−1.1 → +1.1 A per motor at 1.5 A phase) = **0.31 V**.  A late-match pack at 120–150 mΩ reaches 0.28–0.45 V for 2.3–3 A of drive load.<br>• A contact bounce also produces it: the bus falls to the drum's back-EMF for the length of the bounce.  The package calls impact bounces common (R20A-01).  With the drum at top speed and little bus load, a bounce may cause no break at all (the drum holds the bus near 14 V, so there is no U2 UVLO, no ALERT, and row 2 never runs).<br><br>**3. Once it fires, nothing restarts the weapon.**<br>• The "coasting-drum rules" are row 0, which needs \|I_pack\| < 30 mA for 100 ms.  With the switch closed the pack carries the idle and drive current, so row 0 never holds — and never releases either.<br>• No weapon row or restart rule covers this coast.  Row 6's catch-spin restart belongs to comparator trips only [D l.658].<br>• The weapon therefore stays coasted while ARM and the throttle are held.  A literal implementation leaves it off until the operator disarms and re-arms, if that even clears a state no text defines.<br><br>**Result: a match-losing nuisance with no fault present.**  The drum stops responding at top speed after a drive reversal or a bump | [D l.652, 658]; [S spinup.out] 25 573 rpm; model steady state computed here: i = 2e-9·ω²/Kt = 2.70 A, V_bus 15.24 V, headroom 0.27 V → 0.28 V bus dip; drive bus current at top speed ≈ 1.5·(0.81·V/√3)·1.5 A / V ≈ 1.1 A per motor [C §10] | Gate the instant coast on the pack path.  The coast needs the INA239 \|I\| < ~30 mA on the first two conversions after the sign change (≤ ~0.3 ms), **and** firmware's signed estimate (idle + drives + weapon) differing from it by more than ~0.5 A.  With the switch closed, the weapon's regen shows up in the pack current.<br><br>Define the exit: if row 0 has not confirmed within its 100 ms window, restart with a catch-spin inside the continuous ARM, counted like row 6.<br><br>Alternatively, drop the instant coast and apply R21D-02's fix instead: suspend row 0 only while the **net** estimate is within tolerance of zero.  That catches the throttle-held switch-open case within ~100 ms.<br><br>§9 step 6: with the drum at full throttle, reverse both drives at speed, and bounce the + lead (0.3 ms) → the weapon keeps running, or restarts within ~0.1 s |
| R22D-02 | MINOR | §8.1 "drives resume" steps (2)–(4) | **The round-21 resume claims "no current step", but the mechanism that makes it true is not required.  Its OCP fallback also contradicts itself.**<br><br>**(a) The back-EMF voltage feed-forward is not stated.**<br>• Step 3 claims the chip "leaves Hi-Z with its outputs already at the back-EMF" [D l.676].  Step 2 only asks for "FOC at **zero current**" [D l.675].<br>• While the chip is Hi-Z, the phase current is truly zero, so the current PI sees no error, and a reset integrator stays at 0 V.  The DRV8316 CSA only reads while its low-side FET is on, so during Hi-Z it gives nothing better than an offset.<br>• At Release, a standard zero-current FOC without an ω·λ feed-forward therefore applies a 0 V dq vector.  At 48 kHz that is a PWM-averaged 3-phase short: the brake R21A-01 quantified at **12–31 A at top speed, against the 10 / 16 / 22 A OCP**.  The current rises at 0.4–1.5 A/µs, so it trips inside the first 20.8 µs control period, before the loop can react.<br>• The claim holds only if the voltage command is pre-set to V_q = ω_e·λ (λ_phase ≈ 0.26 mWb) from the encoder speed, with the integrators held (feedback ignored) until the Release.  R21A-01's proposal said "applies the BEMF-matched voltage"; the adopted text dropped that clause.<br><br>**(b) The OCP fallback contradicts itself.**  Step 4 says "else classify that chip through this table, first match".  If both chips OCP at a top-speed resume — the usual case after a link blip, where both wheels turn — that fallback matches drive row 1 ("both DRV8316s at once" → Supply → supply budget).  The same step says an OCP in a resume window is "never toward row 1 or the supply budget".<br><br>§9 step 6's top-speed resume test would expose (a) at bring-up.  That is why this is MINOR: the text is wrong, but the bench catches it | [D l.673–677, 612 (CTRL4 OCP latched)]; R21A-01 numbers (λ, L 5–20 µH, 12–31 A); [C §10] 46.5 k rpm | Step 2: "…FOC at zero current **with the voltage command pre-set to the back-EMF (V_q = ω_e·λ from the encoder speed, integrators held) until the Release**".  Step 4: "…else classify through this table, skipping row 1 for OCPs raised inside the resume window" |
| R22D-03 | MINOR | "drives resume" step (2) and §8 timer inputs: "the observer's catch of a turning rotor" | **A coasted DRV8316 gives the observer nothing to catch, so a sensorless drive cannot learn its speed during a coast.**<br>• The drive outputs have no voltage sense: L_A = J_LA + U3 OUTA only [N l.34] (R_A the same [N l.77]).  The only phase dividers are the weapon's (R22–R27).  With the chip Hi-Z the CSAs read only an offset.<br>• In sensorless mode — a pulled encoder cable (§8 timer inputs, a case the design tests), or both drives after row 7 — step 2's "with no valid angle and the motor turning, wait until it is slow" cannot be evaluated [D l.675].  The same applies to "unless the encoder or the observer shows the rotor moving" before an alignment [D l.614].<br>• Firmware either waits for an observation that never comes (the drive stays coasted), or assumes the drive stopped and releases at speed.  Releasing at speed means R22D-02's OCP chain, then drive row 2, then > 3/s, which latches the drive.<br>• Realistic chain: one encoder cable lost (single fault), then any link blip or bounce while rolling (a normal fight event) | [N l.34, 77]; [D l.614, 675, 764] | State what a sensorless drive does while coasted.  For example:<br>(i) Wait a fixed time measured in §9 step 6 (coast-down from top speed to ~0.8 m/s).<br>(ii) Or catch the rotor with brief zero-vector probes after the Release.  All low-side FETs on for ~2–3 µs, then read the CSAs: ≤ ~4.5 A at 1.5 A/µs, below the 10 A OCP minimum.<br>§9: an encoder-unplugged resume at speed |
| R22D-04 | MINOR | §8.1 drive row 6 (a) → row 7 (round-21 ordering) | **"Own encoder stayed still and the other moved" also describes a dead encoder during a shove.  Row 7 then puts the healthy drive into sensorless for the rest of the match.**<br>• Row 6 (a) sends that pattern to row 7 [D l.686].  Row 7 is sticky: both drives go sensorless until an operator clear, and it is stored in the latch word [D l.688].<br>• The design's own lost-encoder path produces the pattern [D l.614]: a cable cut while moving → sensorless until stopped → align at standstill.  The dead encoder gives 0 counts.<br>• Standstill in a fight is usually being pinned or pushed.  "Still" is < ~17 counts = 1.5° of motor shaft, which is 0.02 mm at the tyre and well inside the planetary's backlash (1–3° at the output ≈ 28–85° at the motor).  So the other encoder "moves" readily.<br>• Result: row 7 fires on one cut cable plus a shove.  The **healthy** drive loses encoder mode (and odometry) for the match, and the report says "crossed", a wrong diagnosis that sends the pit crew to the wrong wires.<br>• Together with R22D-03, both drives are then sensorless with no speed information during any later coast | [D l.614, 686–688]; 4096 counts × 1.5°/360° ≈ 17 counts; 116 736 counts per wheel rev [C §8] | Require a crossed-cable **signature** for (a): the other encoder moves by ~0.5–2× the expected 171 counts, in step with both alignment steps and with the expected step-to-step sign pattern, on **two consecutive** alignments.  Anything else with a still own encoder goes to (b): higher current, then sensorless for that drive only |
| R22D-N1 | NOTE | Resume step (2) BKE = 0 on TIM8 | While BKE = 0, CLL (lockup → break) does not act on TIM8 for the ≤ ~10 ms window.  The DRV8316's own OCP and the 20 ms IWDG still bound it.  It takes a second fault; no change needed | [D l.606, 675] | — |

---

## 2. Scenario walk-through (rev L after round 21)

| Scenario | Path | Outcome |
|---|---|---|
| Drum impacts, flurries | Row 6 catch-spin; > 5/s → 1 s off; row 4 needs two fast re-trips | Safe, bounded, no latch |
| Jammed / locked drum | Rows 6, 10 retry; row 5 passes at a stopped restart | No latch |
| Weapon phase–phase short, spinning / stopped | Row 4 / row 5 | Latched: no masked short |
| Weapon phase–GND short | Row 8 VDS OCP (SOVL masking implausible, R21D-N1) | Latched |
| Bounce under weapon spin-up load | Row 2 supply, restart after 20 ms steady; one-chip DRV8316 reset left to resume (R21D-04 closed) | Bounded |
| Bounce or drive reversal with the drum at saturated top speed, throttle held | Weapon power < 0 with torque > 0 → coast at once; the switch is closed, so row 0 never confirms; no exit | **R22D-01** |
| Switch opened, drum at speed, throttle held | Coast at once → row 0 hold in ~100 ms (R21D-02's intent met) | Safe |
| Switch opened, drum coasting, driving | Row 0 hold; plausibility counts a motoring weapon only | Safe |
| Switch opened while braking | Row 1 "looks open" → row 0 | Safe |
| One corrupted INA239 read | Needs ≥ 3 consecutive polls; a rewrite-fixed mismatch is only reported (R21D-03 closed) | Non-nuisance |
| C2 short / R2–R3 open | Plausibility / cross-check → INA239 hold (operator clear) | Weapon off, drives on |
| Radio blip at top speed, encoders good | Timeout → DRV_OFF high; ARM falls → new edge + throttle zero; drives resume on link recovery | Sound **if** the resume pre-sets the BEMF voltage (**R22D-02**) |
| Same, with one encoder lost earlier | Resume cannot see that drive's speed | **R22D-03** |
| Encoder cable pulled, robot pushed at the next alignment | Row 6 (a) → row 7, both drives sensorless | **R22D-04** |
| Encoder cable pulled, robot still | Row 6 (b) → higher current → sensorless, report (R21D-01 closed) | Sound |
| Pit: J2/J3 or motor bundles crossed | Row 6 (a) → row 7 report | Sound (no drive until cleared) |
| Pit: swapped phase or encoder pair | Two clean wrong-sign alignments → row 6a latch | No reversed drive |
| DRV8316 short / unpowered / deaf | Row 2 (> 3/s latch, INH high) / row 3 / row 4 | Sound |
| MCU reset mid-match, ARM held | New ARM edge required; the compute board's ≥ 250 ms low + toggle; throttle-zero interlock; reset within 2 s of a weapon event latches | No operator-less spin-up |
| Compute-board hang / heartbeat loss | ARM stops (52–164 ms [S arm.out]); ≤ 2 NRST pulses per 10 s | Safe, bounded |
| Power cycle with latches | Board latches lost; the compute board mirrors the weapon latch; the switch-open hold is not persisted | Sound |

## 3. Checked and found sound

* **Round-21 fixes.**
  * **Row 6 ordering** (a/b/c) is bounded: ≤ ~5 repeats, then sensorless.  Row 7 is reachable; see R22D-04 for the one false path.
  * **INA239 confirmation**: 3 polls at 100 Hz = 30 ms.  A reset INA239 is rewritten on the first mismatch.
  * **Pending supply restart**: drive row 2 defers to resume, so the event is counted once.
  * **Latch word**: now lists the INA239 hold.
  * **The resume sequence order** (the chip stays coasted while the pin goes low, BKE off, MOE, then Release) removes R21A-01's high-side brake window.  It does so provided R22D-02's feed-forward is applied.
* **No operator-less re-arm.**  Every automatic weapon restart stays inside a continuous ARM.  An ARM fall, reset, link recovery or clear needs a new edge and throttle zero.  The operator-clear holds (latches, "supply unstable", the INA239 hold, row 7) are never cleared by firmware.
* **No reversed drive.**  Row 6a handles swapped phase or encoder pairs.  The §9 forward-move check covers crossed bundles with "fixed" sensor cables.
* **§1 margins** (hardware unchanged since round 16; outputs re-read):
  * DRV8316 VM: loaded bounce 0.8–2.26 V/µs, 2.66 V/µs at C1's −40 °C ESR, re-close ≤ 2.09 V/µs, all against 4 V/µs [S hotplug.out].
  * Q7: 16 / 22 W peak, 54–57 mJ.
  * ARM: armed 2.50–2.95 V against VT+ ≤ 2.15 V; 7–10 edges to arm; disarm in 52–164 ms [S arm.out].
  * Spin-up: 22.1 A pack peak, 14.06 V minimum, against the buck's 10.3 V worst-case cutoff [S spinup.out, C §9].
  * Voltage chain: D1 clamp 32.4 V < 35 V (C1) < 40 V (DRV8316).  BOVL 19 V < the 20 V minimum OVP.  LiPo 16.8 V + 1.4 V of regen = 18.2 V < the 18.3 V test limit < the 18.5 V coast.
  * SOVL 38 A > the 32 A budget.
  * MT6701: 46.5 k rpm (duty cap) against its 55 k rpm rating.
  * 5 V rail: 450 mA left for the compute board.
* **Scripts**: the netlist checks pass and calcs.md regenerates unchanged.

## 4. Summary

| ID | Sev | One line |
|---|---|---|
| R22D-01 | MAJOR | The round-21 instant coast (weapon torque > 0, power < 0) has no pack-current gate and no exit.  A drum at its voltage limit (0.27 V of headroom in the package's own model) regenerates on a ≥ 0.28 V bus dip from a drive reversal or a bounce with the switch closed, so the weapon coasts and never restarts.  Fix: gate it on the INA239 ≈ 0 against a non-zero estimate, and restart via catch-spin if row 0 does not confirm |
| R22D-02 | MINOR | The "no current step" at Release needs a back-EMF voltage feed-forward (integrators held) that the text does not require.  Plain zero-current FOC releases into a 12–31 A brake at top speed.  Step 4's table fallback also puts a two-chip resume OCP into row 1 / the supply budget, which the same step forbids |
| R22D-03 | MINOR | The drive outputs have no voltage sense, so a coasted, sensorless drive has no observer.  "Wait until slow" and "observer shows the rotor moving" cannot be evaluated after a lost encoder.  Fix: a fixed measured wait, or zero-vector probing |
| R22D-04 | MINOR | Row 6 (a) → row 7 also matches a dead own encoder plus a shove (the "still" limit of 17 counts is inside the gearbox backlash).  The healthy drive then goes sensorless for the match, with a wrong "crossed" report.  Fix: require a step-correlated signature on two consecutive alignments |
| R22D-N1 | NOTE | BKE = 0 during resume suspends CLL on TIM8 for ≤ ~10 ms (second-fault only) |

**Verdict: 0 BLOCKER, 1 MAJOR, 3 MINOR, 1 NOTE.**  All findings are firmware-contract text; no hardware change is needed.
