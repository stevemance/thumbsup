# Review round 17 / D: system-level review (rev L)

Reviewer role: adversarial system reviewer (power electronics and combat robotics).  I read DESIGN.md rev L end to end,
design/calcs.md, spice/hotplug.out, arm.out, bridge.out and spinup.out, review/CHANGES.md (rounds 1–17) and
round16_d_system.md, plus the SMBJ20A datasheet.  The package was copied to `/tmp/r17d/` and nothing in it was edited
apart from this file.

**Snapshot note.**  While I was working, the round-17 A/B fixes landed in DESIGN.md:
* row 5 now runs only with the drum stopped (W_Vx < ~25 mV) and uses ΔV/ΔI;
* row 0 now uses a ≥ 100 ms mean and is suspended on any negative motor power or a near-zero pack-current estimate;
* the INA239 row, the boot heartbeat, TIM8/TIM20 OISx = 1, and "disarm, then persist the latch copy" were also updated.

I re-copied the package and reviewed that **current** text.  My own findings on the old row 5 (a slow drum's
BEMF false-latching the check) and the old row 0 (a robot shoved backwards nulling the pack current) duplicate
R17A-01/B17-01 and R17A-02/B17-N3, and both are already fixed, so they are not repeated below.

Evidence tags: **[D l.N]** = DESIGN.md line, **[S file]** = spice output, **[C §N]** = calcs.md, **[TVS]** = SMBJ20A_BORN.pdf.

---

## 1. Findings

| ID | Sev | Area | Finding | Evidence / numbers | Fix |
|---|---|---|---|---|---|
| R17D-01 | MINOR | §8.1 row 1 (BOVL) with the pack disconnected during commanded regen | **Row 1 restarts with no limit, so a pack disconnect (switch or XT30) during a commanded weapon brake or reversal turns into a BOVL → coast → restart → regen → BOVL loop.  D1 absorbs every overshoot, and row 0 cannot stop the loop.**<br>• With no pack connected, 10 A of regen charges the ~374 µF bus at 27 V/ms.<br>• BOVL (19 V) acts 0.3–0.45 ms after the crossing [D l.617].  By then the bus has passed D1's breakdown (22.2–24.5 V), and D1 clamps ~10 A for 0.1–0.26 ms: **~30–70 mJ per cycle** (0.8 ms latency per §7.21: ~160 mJ).<br>• Row 1 restarts once VBUS < 18 V.  At ~1–2 W of board load that takes ~25–50 ms, and the brake command is still active, so regen resumes.  That is ~20–35 cycles/s, i.e. **~0.5–2.5 W average in D1**.  D1's RθJA is 100 °C/W [TVS], so the steady rise is 50–250 K.<br>• Each cycle takes ~60–90 mJ out of the drum, so a full-speed drum (64 J) needs ~700–1000 cycles, i.e. tens of seconds: D1 gets close to steady state.  Each cycle also trips the DRV8316 OVP (20 V min), so the drives keep cycling through drive row 1.<br>• Row 0 suspends itself "while any motor's electrical power is negative" [D l.651].  The regen bursts come < 100 ms apart, so if a suspension restarts the ≥ 100 ms mean, row 0 never matches.  The text does not say whether it restarts the mean or only drops the suspended samples.<br>• Row 1 names "switch open" as a cause [D l.652] but treats it like a full pack.  A D1 that overheats fails short, and the next switch closure then drives U13 into the short (§7.14: Q7 likely fails) | [D l.651, 652, 617, 589 (§7.21 BOVL 0.3–0.8 ms), 619 (regen ~10 A)]; [TVS] BV 22.2–24.5 V, VC 32.4 V, RθJA 100 °C/W, PD 5 W only with a 75 °C lead; [S spinup.out] 64.5 J, J = 1.8e-5 kg m²; 374 µF [D l.109] | Use the INA239's signed current, which separates the two BOVL causes.  With the pack connected, a BOVL comes with I ≈ −(regen) A.  With the pack gone, I ≈ 0.  **BOVL with pack current ≥ ~−0.1 A → switch open**: take the row 0 hold at once, with no restart.  Also bound row 1: a second BOVL within ~1 s → hold the weapon coasted until the pack current shows the pack is connected again.  In row 0, say that suspended samples are excluded from the mean and do not restart it |
| R17D-02 | MINOR | §8.1 row 0 suspension: "any motor's electrical power is negative (commanded or back-driven regen)" | **A coasting drum's diode rectification is also "back-driven regen", and with the switch open it is exactly what holds the bus up.  If firmware counts it, row 0 is suspended for its own main case**: the switch is opened with the drum coasting after disarm (§7.5), so the robot stays drivable on drum energy for seconds while it is being handled.  This re-opens R16D-01's second half.<br>• While the weapon coasts, the CSAs still measure the body-diode currents (low-side shunts) and W_Vx measures the phase voltages.  A firmware that computes power from measurements, which the "back-driven" wording invites, gets a negative value.<br>• With the switch **closed**, a coasting drum never rectifies: its BEMF is ≤ ~14.2 V (25.6 k rpm / 1800 KV), below the pack.  So excluding coasting channels loses nothing | [D l.651, §7.5 l.519]; [S spinup.out] 25 573 rpm; [C §10]/§1 1800 KV | Add to row 0: "only channels whose bridge is actively driven (FOC/six-step outputs enabled) count; a coasting (Hi-Z) channel never suspends the monitor, because its rectified current into an open-switch bus is the signature" |
| R17D-03 | MINOR | Row 0 hold vs the compute board's persistent weapon-latch copy (§3.5, §8.1 latch word) | **Row 0's hold is "stored in the latch word … until the operator clears it", and the compute board persists "the weapon latch" across power cycles.  If the switch-open hold is reported as a weapon latch, it is persisted after nearly every end-of-match switch-off with the drum still coasting (the 10–40 s coast, §7.6).**<br>• The next power-up then refuses to arm until the operator clears it.  That makes "clear" a routine reflex at every power-up, and the persistent copy exists for real short latches (rows 4/5/8/9/12), which that reflex then masks.<br>• The text does not say whether the row-0 hold is a weapon latch in the heartbeat or a flag of its own.  Opening the switch is the normal way to turn the robot off, and a fresh power-up is by definition the switch being closed again | [D l.346–347, 643–645, 651]; [D §7.5, §7.6] | Report row 0 as its own "switch-open hold" flag: not mirrored, not persisted by the compute board, and cleared by a fresh power-up (BORRSTF, invalid word).  While the board stays powered it is still cleared only by the operator, as now.  The compute board persists only the latches from rows 4/5/7/8/9/11/12 and the MCU-reset latch |
| R17D-04 | MINOR | §8 timer inputs: swapped J2/J3 sensor cables | **The one-at-a-time alignment "catches" swapped sensor cables but says nothing about what happens next.  The generic return rule can then put a drive back into encoder mode on the *other* motor's encoder.**<br>• With the cables swapped, aligning L moves the L motor, but L's input (R's encoder) sees nothing.  The drive therefore falls to "too little motion → retry → run sensorless and report", and R does the same.<br>• "Return to encoder mode only after edges resume and a Z matches the stored offset" [D l.614] is then satisfied in normal driving.  Each input sees the other motor's edges.  While turning, the two rotors' relative phase sweeps, so a Z lands inside the ±30° window within seconds.<br>• Once back in encoder mode the drive commutates on the other rotor.  Any differential motion drifts the angle by 360° electrical per ~0.8 mm of differential travel (R16D-04), which gives wrong-signed torque.<br>• The observer plausibility check only runs "above a few thousand rpm" (≲ 0.2 m/s), and the per-Z count check is self-consistent (the same encoder), so slow manoeuvring, turning in place and shoving at low speed are unprotected: **reversed drive torque at low speed**.<br>• Swapping identical SH cables at a pit repair is realistic.  The report arrives at power-up, when crews are rushed | [D l.614 (alignment, 10 % tolerance, return-to-encoder rule, plausibility "above a few thousand rpm")]; R16D-04 numbers (0.8 mm per electrical rev) | Define the action.  Other-encoder motion ≥ ~50 % of the expected ~171 counts, while the aligning drive's own encoder stays still → "sensor cables swapped".  Both drives are then **locked to sensorless** (never return to encoder mode) until a clean re-alignment after an operator clear.  10–50 % → retry the alignment.  More generally, a drive whose alignment failed never re-enters encoder mode on a Z match alone |
| R17D-N1 | NOTE | Row 5 stopped-drum gate | 25 mV line-to-line at the phase is **~4 LSB** at the dividers' 6.3 mV/LSB [C §2], and a drum at 50 rpm has a 170 ms electrical period (7 pole pairs, 5.8 Hz).<br>• The gate needs offset-calibrated line-to-line readings (at boot the strap test already needs W_Vx ≈ 0) averaged over ≥ one period.<br>• It also needs a timeout, or an offset makes "the check waits for it to stop" wait for ever: a weapon that never restarts.<br>• A more sensitive alternative below the catch-spin speed is a brief low-side brake.  Its current is E/R, 0.28 A at 50 rpm with R ≈ 0.1 Ω, i.e. 14 CSA LSB, and it stops the drum.  At < 1 k rpm the brake current is ≤ ~5.6 A (0.56 V / 0.1 Ω), far from the "never short-brake at speed" case | [D l.656, 618]; [C §1, §2] | — |
| R17D-N2 | NOTE | Row 5 scope | "Every restart with the drum stopped" leaves out the **first** start after arming.  A short present at arm time then gets one 0.5 s row-10 stall at 20 A before the first restart runs the check.  This is bounded, but "every start" costs ~3 ms | [D l.656, 661] | — |
| R17D-N3 | NOTE | Row 5 reference after a pit repair | The stored ΔV/ΔI belongs to one motor and harness, just as the Z offset does.  After a weapon motor or lead change, re-measure it (§9 step 6).  A lower-R spare (e.g. a higher-KV motor) can fall below half and latch, and a higher-R one can hide a partial short | [D l.656, 752] | — |

---

## 2. Scenario walk-through (current rev L text)

| Scenario | Path | Outcome |
|---|---|---|
| Drum impacts (single, flurries) | Row 6 → catch-spin after 50–100 ms; > 5/s → 1 s off; row 4 needs two consecutive fast re-trips within 200 µs of the first vector; row 5 only at a stopped drum | Safe, no latch |
| Bounce 0.1 ms, 20 A | 9.3 V floor [S], slope < 5 V/ms, possible SOVL → row 3 fold-back with ramp-back over 0.5 s | Bounded, no latch |
| Bounce 0.3–3 ms, heavy load | U2 UVLO break; post-event VBUS < 10 V or slope ≥ 7–10 V/ms → row 2 supply → restart after 20 ms steady; row 0 needs a ≥ 100 ms mean | Safe, no hold |
| Bounce, light load | No break (bus holds) or row 7 (counted; > 5 in 10 s → latch) | Accepted residual (R16) |
| Bounce ≥ ~5 ms / chattering | BOR → supply budget (> 20/min → operator hold) | Bounded |
| Pushing, being pushed back | Drives regenerate → row 0 suspended (negative motor power) | Fixed in R17A-02 |
| Jammed drum | Row 10: 0.5 s at the limit, 1 s coast, retry; row 5 check at stop passes on a healthy motor | Retries, no latch |
| Wheel in the air | Duty cap 46.5 k rpm < 50 k encoder cap < 55 k MT6701 | Sound |
| Weapon phase–phase short, spinning | Row 6 → two fast re-trips → row 4 latch; or FOC regulates it → row 10 stall → the drum brakes on the short → stopped → row 5 latch | ≤ 0.5 s at 20 A, then latched |
| Weapon phase–phase short, stopped | Row 5 at the restart (first start: N2) | Latched |
| Weapon phase–GND short | VDS OCP → row 8 | Latched |
| Drive short | DRV8316 OCP → drive row 2 → > 3/s latch, coasted, INH high (OISx = 1) | Sound |
| Unpowered / deaf DRV8316 | Rows 3 / 4 (≥ 3 confirmed reads) | Sound |
| SPI3 fault / INA239 fault | Hold with retry; INA239-only → weapon off, drives on VBAT_SNS; destructive DIAG_ALRT read now feeds the classifier | Sound |
| Compute-board reboot | ARM decays 52–164 ms [S arm.out]; command timeout; new session, self-test at zero throttle, ARM edge + throttle zero | Sound |
| Radio drop | ≤ 0.5 s → ARM stop + command stop; throttle-zero on recovery | Sound |
| Switch opened mid-match, drum driven | Motoring collapses the bus → row 2 restarts → supply budget (5/s) → 1 s hold → row 0 hold | Bounded, safe |
| Switch opened while braking / reversing the drum | Row 1 restarts without limit; row 0 suspended each burst | **R17D-01** |
| Switch opened, drum coasting disarmed | Row 0 fires after ~100 ms, **if** the coasting weapon's rectification does not count as negative power | **R17D-02**; persisted as a weapon latch? **R17D-03** |
| Switch opened, drum stopped | Bus reaches the 9.2 V buck cutoff in ~20–35 ms, before row 0's 100 ms; board off, latch word lost | Safe |
| Regen near the thresholds, pack connected | Negative current → row 0 suspended; 18.5 V coast / 19 V BOVL → restart below 18 V | Sound |
| Pit repair | Phase swap → sign latch; J2/J3 swap → detected, but the action is undefined and the Z-match return re-enters encoder mode (**R17D-04**); weapon wire swap → visual check (§9); motor swap → re-measure the row 5 reference (N3) | See findings |
| Power cycle with latches | Board latch lost (fresh power-up); compute board disarms, persists and refuses until the operator clears it | Sound for real latches; row 0 (R17D-03) |
| MCU reset / IWDG | Latch word honoured; boot coasts both DRV8316s, releases only unlatched drives, aligns one at a time; ARM edge + throttle zero | Sound |

## 3. Checked and found sound

* **§1 / §5 margins** (hardware unchanged since round 16; I re-read the outputs):
  * DRV8316 VM: loaded bounce 0.80–2.26 V/µs, 2.66 V/µs at −40 °C ESR, re-close ≤ 2.09 V/µs, closure ≤ 0.005 V/µs, all against 4 V/µs [S hotplug.out].
  * Q7: 16.5 / 22.0 W, 53.8–56.9 mJ.
  * Reversed pack: 13.1 A with D10.
  * ARM: 2.50–2.95 V, 7–10 edges, disarm 52–164 ms.
  * Spin-up: 22.1 A pack peak, 14.06 V minimum bus.
  * Bridge at 60 mA / 6 nH: VDS 29.4 V, SHx −4.58 V.
  * D1 clamp 32.4 V against 35 V (C1) and 40 V (DRV8316).
  * SOVL 38 A against a power budget ≤ 32 A.
* **No operator-less re-arm into a latch.**  Every automatic restart stays inside a continuous ARM.  An ARM fall, reset, link recovery or clear needs a new edge and throttle zero.  Clearing is operator-only.  The compute board now disarms before persisting a latch (no flash write while armed).
* **Row 0 (current text):**
  * Idle ≥ ~60–80 mA against the 30 mA threshold.
  * INA239 static error ≤ ~7 mA (R17A).
  * A 100 ms mean against bounces of ≤ a few ms.
  * With the drum stopped the board powers down before the monitor matures.
* **Row 5 (current text):** the ΔV/ΔI of two same-polarity steps cancels the dead-time offset.  At < 50 rpm the BEMF (≤ 28 mV) is ≤ ~10 % of the 0.25–0.5 V test drop.  The gate itself: N1.
* **TIM8/TIM20 OISx = 1.**
  * In 3x mode a break brakes either way, and a DRV8316 on its own fault is already Hi-Z.
  * In 6x mode (a reset chip) INH high is Hi-Z.
  * A CLL lockup gives a ≤ 20 ms high-side brake, then the IWDG reset and the R50 pull-up coast.

## 4. Summary

| ID | Sev | One line |
|---|---|---|
| R17D-01 | MINOR | A pack disconnect during a commanded weapon brake gives an unlimited BOVL → restart loop that dumps ~30–70 mJ per cycle into D1 (≈ 0.5–2.5 W, RθJA 100 K/W) for tens of seconds; row 0 is suspended by each burst.  Fix: BOVL with pack current ≥ ~0 = switch open → row 0 hold; bound row 1 |
| R17D-02 | MINOR | "Back-driven regen" suspends row 0; a coasting drum rectifying into an open-switch bus is exactly that, so the §7.5 case can be masked.  Count only actively driven channels |
| R17D-03 | MINOR | If the row-0 hold is reported as a weapon latch, the compute board persists it after most end-of-match switch-offs, and routine clears then mask real short latches.  Make it a separate flag, cleared by a fresh power-up |
| R17D-04 | MINOR | The swapped J2/J3 case is detected but has no action; the Z-match return rule can re-enter encoder mode on the other motor's encoder and give wrong-signed torque at low speed.  Lock both drives to sensorless on detection |
| R17D-N1..N3 | NOTE | Row 5 gate resolution (4 LSB) and a timeout, or a low-side-brake BEMF probe; run row 5 at the first start too; re-measure the row 5 reference after a motor or lead change |

**Verdict: 0 BLOCKER, 0 MAJOR, 4 MINOR, 3 NOTE** (against the current text, with R17A/B applied).  The hardware and the §1
margins are clean.  The round-16/17 §8.1 procedure ends safe and bounded in every walked scenario except the four MINOR
edges above.  All four are firmware-contract text fixes; no hardware change is needed.
