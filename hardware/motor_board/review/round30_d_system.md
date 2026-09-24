# Review round 30 / D: system-level review (rev L)

**Reviewer role:** adversarial system reviewer (power electronics and combat robotics).

**What I read:**
* DESIGN.md rev L, all of it, with the focus on the round-29 edits in the §8 timer-inputs row [D l.615]:
  * the Z-count mismatch is now held as a candidate and adopted only when the next Z confirms it;
  * a second *confirmed* mismatch since reset marks the encoder suspect and re-references;
  * the torque-sign slip check is gone.  A slipped magnet is left to the observer check as a bounded residual.
* §8.1 drives resume [D l.674–678] and the drive table, because they consume the encoder state.
* design/calcs.md (§8, §9, §10).
* spice/arm.out and spice/hotplug.out.
* review/CHANGES.md (rounds 1–29) and round29_d_system.md.

**Scripts and edits:** none run, no copy made.  Nothing edited apart from this file.

**Evidence tags:** [D l.N] = a DESIGN.md line; [C §N] = a calcs.md section; [S file] = a spice output.

**Numbers used below:**
* λ = Kt / (1.5 × 6 pole pairs) = 2.73 mN·m/A / 9 ≈ 0.30 mWb [C §10].
* 1 m/s at the wheel = 442 rpm wheel = 12.6 k rpm motor, so ω_e ≈ 7.9 krad/s and the back-EMF is ≈ 2.4 V phase peak.
* 1024 PPR × 4 = 4096 counts per motor revolution = 683 counts per electrical revolution.  So 30° electrical ≈ 57 counts and 180° ≈ 341 counts.

---

## 1. Findings

### R30D-01 (MINOR): the round-29 candidate/confirm rule never flags an A/B line that keeps losing edges

**The rule [D l.615]:** "a larger mismatch (missed or extra A/B edges: a broken line, harness noise, a magnet come off) is held as a candidate reference and adopted when the next Z confirms it (a noise pulse on Z is then ignored); a second confirmed mismatch since reset marks the encoder suspect".

**The gap.**  Each Z after a candidate can do one of three things:
* confirm the candidate → adopt it;
* match the old reference → drop the candidate (a Z glitch);
* match neither.  **The rule does not say what happens then.**

"Match neither" is the signature of the fault the check is meant to catch: an intermittent A or B contact (a chafed wire, a fretting SH connector) that drops edges on every revolution while the wheel turns.
* Each Z lands at a new offset, so no candidate is ever confirmed.
* The reference is never corrected, and the confirmed-mismatch count stays at 0.
* So the Z check neither corrects the angle nor declares the encoder suspect.
* Before round 29, every mismatch re-referenced and the second one declared the encoder suspect.  Round 29 lost this case.

**Consequence (single fault, realistic in a combat harness):**
* The electrical angle error grows with every revolution the wheel turns.
* Torque fades towards zero as the error approaches 90°.  Past 90° the torque reverses.  With a speed loop, that is positive feedback up to the current limit.
* The observer check stops it once the motor exceeds a few thousand rpm (> 30° disagreement → sensorless).  That is the same ~0.3 m/s, ~40–50 ms bounded residual already accepted for a slipped magnet.
* **Below observer speed, in a pushing exchange,** the wheel loses torque progressively without any report.  That is the match-deciding case, and the one the Z check exists for.

The ambiguity also means two implementers could build different behaviour from the same text.

**Fix (text only).**
* Treat a Z that matches neither the reference nor the pending candidate as a second mismatch → encoder suspect → sensorless and report.  Re-reference to that Z, as the rule already does for a confirmed second mismatch.
* One way to word it: "two consecutive Zs off the reference that disagree with each other → encoder suspect".
* The cases the round-29 rule was written for still behave as intended:
  * A single Z glitch is followed by a Z that matches the reference, so it is still ignored.
  * A one-time burst of lost edges is still adopted by the confirming Z.
* Continuous noise on the Z line also ends up suspect under this rule.  That is correct: the encoder cannot be trusted then.

### R30D-02 (MINOR): drives resume can take its angle from a Z offset the observer has already shown to be wrong, and at speed that can latch the drive

**The rule.**  Drives resume [D l.676] takes a turning rotor's angle "from the stored Z offset (not while 'Z offset stale' is reported, nor before §9 step 5 has stored one: then the no-encoder branch)".

**The gap.**  Nothing excludes a drive that the **observer check** has switched to sensorless [D l.615].  That is exactly the slipped-magnet case that round 29 now leaves to the observer:
* A magnet that has slipped carries Z with it, so the stored Z offset is wrong by the slip angle.
* The encoder still counts, so the "encoder counting, rotor turning" branch is selected.

**Chain.**  It needs one fault (the magnet slips mid-match) plus a routine event: a contact-bounce supply restart, a link timeout and recovery, or a per-drive row 2 recovery.  All three route through drives resume, and none resets the MCU, so the sensorless state is still in memory.
1. The resume presets V_q = ω·λ at the slipped angle.
2. The DRV8316 leaves Hi-Z with a voltage error of 2·E·sin(Δθ/2) against the back-EMF E.
   * At 1 m/s, E ≈ 2.4 V.  A 180° error is ~4.8 V and a 40° error is ~1.6 V, across a ~0.1–0.15 Ω phase.
   * §8.1 itself says a 15° error at top speed already gives ~10 A.
   * So the 16 A OCP trips within ~0.1 ms.
3. The resume repeats once, then drive row 2 recovers and resumes again.
4. With "a valid encoder angle", **more than ~3 OCPs in a second latch that drive** [D l.678].

**Result:**
* **At speed:** one wheel is latched until the operator clears it, which is a match-losing nuisance from a fault the design otherwise handles gracefully in sensorless mode.
* **At low speed:** no OCP, but the drive comes back in encoder mode with a reversed or offset angle until the observer catches it again.  That is bounded, but it repeats the residual on every resume.

**Fix (text only).**  A drive that the observer check (or the Z check) has marked encoder-suspect:
* uses the no-encoder resume branch (coast to the safe-resume speed, then a preset of 0, with OCP retries that never latch);
* and is not treated as "a valid encoder angle" for the resume-OCP latch;
* until it has returned to encoder mode through a Z that matches the stored offset.

In short, extend the existing "Z offset stale" exclusion to "encoder suspect".

---

**NOTEs**

* **R30D-N1: while a candidate is pending, the angle stays wrong for up to one more motor revolution.**
  * This applies after a real burst of lost edges.
  * One revolution is 4096 counts, ~12.6° of wheel, ~4.8 mm.
  * If the error reverses torque, the rotor is driven back through the same Z position.  The direction-aware capture then reads the same count, which confirms the candidate at once.
  * If the error is near 90°, the rotor stalls and the "no encoder edges, torque commanded" report applies.
  * Bounded.  This is the price of rejecting Z glitches, and it is acceptable.
* **R30D-N2: an A/B line that breaks outright is also caught only indirectly.**
  * The count then dithers ±1 on the other channel, and Z keeps arriving at the same count, so the first confirmed mismatch adopts it.
  * With a frozen angle, FOC cannot spin the rotor.  It settles within half an electrical period, and the "no encoder edges, torque commanded" report (with the compute board's optional sensorless restart) covers it.
  * No reversed drive beyond the fixed-vector cogging while the robot is shoved.  Unchanged by round 29; no action.
* **R30D-N3: removing the torque-sign check is correct.**
  * Every push or back-drive scenario from R29D-01 is now free of nuisance trips.
  * A reversing slip under a speed or torque command is positive feedback, so it accelerates the wheel into the observer band by itself.  The ~0.3 m/s, ~40–50 ms residual holds.
  * A ~90° slip gives zero torque, a stall and the no-edges report.
  * The §9 step 6 tests no longer need a back-driven case.

---

## 2. Scenario walk-through (rev L as it stands)

Weapon, power-entry and ARM rules are unchanged since round 28.  Their walks (rounds 26–29) were re-checked against the current text and still hold; they are summarised in the last rows.

| Scenario | Path | Outcome |
|---|---|---|
| Out-pushed, wheels back-driven under a forward command, 0–0.4 m/s | No torque-sign check any more; the Z counts stay consistent | No nuisance (R29D-01 closed) |
| Speed-loop stop through the observer band | No check on it | No nuisance |
| Single Z glitch | Candidate held; the next real Z matches the reference → dropped | Correct |
| One burst of lost A/B edges | Candidate confirmed at the next Z → adopted (≤ 1 motor rev wrong, N1) | Bounded |
| Intermittent A/B contact losing edges every rev | Zs match neither the reference nor the candidate → never confirmed, never suspect; the angle drifts | **Silent torque loss below observer speed; bounded reversal above it (R30D-01)** |
| A or B line broken outright | Frozen count, stall, "no edges, torque commanded" (N2) | Bounded, reported |
| Magnet slips mid-match | Observer check at ~0.3 m/s → sensorless; the Z electrical check keeps it there | Bounded residual (~40–50 ms) |
| Slipped magnet, then bounce or link recovery at speed | Resume takes the Z-offset angle → wrong preset → OCP × 3/s → drive latched | **Match-losing latch (R30D-02)** |
| Slipped magnet, then an MCU reset, rotor still | Alignment gives the true offset; the first Z → "Z offset stale"; runs on the alignment | Correct |
| Crossed bundles or sensor cables, swapped phase pair | Row 7 / row 6a latch; §9 forward-move check | No reversed drive |
| Mid-fight IWDG reset | Latch word; "ARM edge required" + throttle zero; drives resume | No operator-less weapon restart |
| Weapon phase short, spinning / stopped | Row 4 / row 5 | Latched; no masked short |
| Contact bounce under load; switch opened under throttle or braking | Row 2 supply budget / rows 0 and 1 → hold (not a latch) | Safe, non-nuisance (unchanged) |
| Radio loss / compute-board hang | ARM decays in 52–164 ms [S arm.out]; command timeout coasts the drives | Safe |

## 3. §1 margins (re-checked)

* **Timers:** 170 MHz / (2 × 3542) = 24.00 kHz and / (2 × 1771) = 48.00 kHz.
* **INA239:** SOVL 0x76C0 × 1.25 mA = 38.0 A; BOVL 0x17C0 × 3.125 mV = 19.0 V.
* **ARM** [S arm.out]: armed 2.50–2.95 V vs VT+ ≤ 2.15 V; disarm in 52–164 ms; gap tolerance ≥ 52 ms vs the ≤ 20 ms spec.
* **Soft-start** [S hotplug.out]: 1.28–2.95 V/ms, ≤ 0.005 V/µs at VM, Q7 ≤ 22.0 W / ≤ 56.9 mJ.
* **Re-close and bounce at VM** [S hotplug.out]: re-close ≤ 2.09 V/µs; bounce ≤ 2.26 V/µs, 2.66 V/µs at C1's −40 °C limit.  With the round-27 cases (≤ 2.33, 2.82 at −40 °C) all are under 4 V/µs, as §1 states.
* **Voltage chain:** 18.3 V < 18.5 V coast < 19 V BOVL < 20 V DRV8316 OVP minimum < ~28.7 V D1 at 10 A < 35 V C1 / 40 V DRV8316.
* **Spin-up:** 22 A peak and a 14.1 V bus, vs the ≤ 10.3 V logic cutoff and the ≤ 10.1 V switch UVLO [C §7, §9].
* **5 V rail:** 450 mA left for the compute board [C §4].
* **Drive speed:** 46.5 k rpm vs the 50 k firmware cap and the 55 k MT6701 rating [C §10].
* **Encoder:** 4096 counts per motor revolution, 116 736 per wheel revolution [C §8].  The alignment step of 171 counts is 90° electrical.

All hold.

## 4. Summary

| ID | Sev | One line |
|---|---|---|
| R30D-01 | MINOR | The round-29 candidate/confirm Z rule never flags an A/B line that keeps losing edges: successive Zs match neither the reference nor the candidate, so the count is never corrected or marked suspect.  The result is silent torque loss below observer speed.  Fix: a Z off both the reference and the candidate counts as the second mismatch → suspect and re-reference |
| R30D-02 | MINOR | Drives resume takes a turning rotor's angle from the stored Z offset even for a drive the observer has switched to sensorless (a slipped magnet), so a routine bounce or link recovery at speed gives a wrong preset → OCP × 3 in a second → drive latched.  Fix: extend the "Z offset stale" exclusion to encoder-suspect drives (no-encoder branch, OCPs never latch) |
| N1 | NOTE | A pending candidate leaves the angle wrong for ≤ 1 motor rev (~4.8 mm); self-limiting |
| N2 | NOTE | An A/B line that breaks outright is caught by the stall / no-edges report, not the Z check; bounded |
| N3 | NOTE | Removing the torque-sign check is correct; the slip residual holds by positive feedback into the observer band |

**Verdict: 0 BLOCKER, 0 MAJOR, 2 MINOR, 3 NOTE.**
* Every fight and pit scenario walked ends safe and bounded.  None leaves a masked short, re-arms without the operator, or reverses a drive beyond the accepted ~40–50 ms residual.
* Both MINORs are in the encoder-state handling that round 29 touched or relies on, and both are text-only fixes.
