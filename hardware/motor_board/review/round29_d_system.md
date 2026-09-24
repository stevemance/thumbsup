# Review round 29 / D: system-level review (rev L)

**Reviewer role:** adversarial system reviewer (power electronics and combat robotics).

**What I read:**
* DESIGN.md rev L, all of it.  I focused on the round-28 edits in the §8 timer-inputs row [D l.615]:
  * Z-edge capture with the direction bit, or Z_PULSE_WIDTH = 1 LSB (§9 step 5 [D l.755]);
  * the first Z-count mismatch re-references the count, and a second one marks the encoder suspect;
  * the torque-sign slip check below observer speed.
* design/calcs.md (§8 odometry, §10 drive motor).
* spice/arm.out, hotplug.out, spinup.out and bridge.out.
* review/CHANGES.md (rounds 1–28) and round28_d_system.md.

**Scripts:** none run.  No copy was made.  Nothing in the package was edited apart from this file.

**Evidence tags:**
* **[D l.N]** = a DESIGN.md line.
* **[C §N]** = a calcs.md section.
* **[S file]** = a spice output.

---

## 1. Findings

### R29D-01 (MAJOR): the torque-sign slip check fires in ordinary pushing, and drops the drive to sensorless just when sensorless is weakest

**The rule [D l.615]:**

> below observer speed, encoder speed moving against the commanded torque for ~30 ms also marks the encoder suspect.

The action is "sensorless and report".  The way back is: "Return to encoder mode only after edges resume and a Z matches the stored offset."

**Problem 1: the rule's signature is also normal combat.**  With a correct encoder, the wheel moves against the commanded torque whenever something outside the motor drives it.
* **Being shoved backwards while driving forward.**
  * The design already lists this as normal: row 0 [D l.653] names "a back-driven drive when the robot is shoved backwards".
  * The drives are deliberately traction-limited to ~0.8–1 A [C §10].  So any opponent with more traction, or a wedge that unloads our wheels, back-drives them.
* **The speed band is where pushing happens.**
  * The observer takes over "above a few thousand rpm" of motor speed [D l.615].
  * 3 k rpm / 28.5 × π × 43.2 mm = **0.24 m/s** at the wheel, and 5 k rpm gives **0.40 m/s**.
  * Pushing exchanges run at 0–0.4 m/s.
* **30 ms is shorter than the event.**
  * Example: a net 2 N shove on the two robots (~0.9 kg) accelerates us backwards at ~2.2 m/s².
  * Reaching 0.24 m/s then takes ~110 ms, all of it with speed and acceleration against our torque.
  * A slow grind stays in the band indefinitely.
* **Braking can also trip it.**  If "speed against torque" means signs, every deceleration through the band that takes more than 30 ms trips it.
  * Crossing 0.24 m/s at the traction limit (12.7 m/s² with both wheels at 1 A) takes 19 ms, which passes.
  * A speed loop braking at ≤ ~8 m/s² takes more than 30 ms, which trips.

**Problem 2: the consequence is bad for a match.**
* Below observer speed, sensorless means the I/f start [D l.201].
* While the robot is being pushed backwards against a forward command, an I/f vector loses synchronism with the rotor.  Torque then averages near zero.  So the robot stops resisting exactly when it is being pushed.
* The way back is a Z pulse that "matches the stored offset".  That comparison needs an independent electrical angle, which only the observer gives, and only above observer speed.
* A robot held in the push, or pinned, therefore stays sensorless.  It gets its encoder drive back only after it breaks free and accelerates past ~0.3 m/s.

**Problem 3: bring-up will not catch it.**
* §9 step 6 tests "push against a wall for 5 s", where the wheel is stalled, with no motion and no trigger.
* It also tests "shove the robot during a re-alignment", which is outside FOC.
* No listed test back-drives a wheel under a forward command.

**What the check is for.**  It covers a slipped magnet at a reversing offset.
* R27D-N1 / R28D-01 already accepted this as a bounded residual: the observer check catches it at ~0.3 m/s, after ~40–50 ms.
* So the check buys little and costs a nuisance that no fault is needed to trigger.

**Fix (text only).** Pick one:

1. **Drop the torque-sign check** and keep the slip as the documented bounded residual (R27D-N1).
2. **Base the check on the back-EMF sign, not the motion sign.**
   * In the FOC frame, the q-axis voltage residual Vq − R·Iq − (L·dIq/dt) equals ω·λ when the angle is right.  It equals −ω·λ when the offset is ~180° out.
   * An external push leaves the residual matching the encoder speed.  A reversed offset makes it opposite.
   * So the check becomes: residual sign opposite the encoder speed, with |ω·λ| above the residual's uncertainty, for ~30 ms → encoder suspect.
   * Numbers:
     * λ = Kt / (1.5 × 6 pole pairs) ≈ 0.30 mWb.
     * At 0.1 m/s at the wheel (1.26 k rpm motor, ω_e ≈ 790 rad/s), ω·λ ≈ 0.24 V.
     * Against that, R·Iq is 0.10–0.15 V at 1 A (~0.1–0.15 Ω phase), known to ~±30 %.
     * So the check works down to a few cm/s, well below observer speed.
   * λ is already stored at §9 step 5.

Whichever is chosen, add a §9 step 6 test: drive forward at the current limit while the robot is pushed backwards slowly (by hand or by a second robot).  Expect no encoder-suspect report.

---

**NOTEs**

* **R29D-N1: a single noise pulse on the Z line is now trusted for up to one motor revolution.**
  * The first "larger mismatch" re-references the count at that Z [D l.615].
  * That is right when A/B lost edges, but wrong when the Z pulse itself was the glitch.
  * The design names harness noise as a cause.  The CH3 input filter (≤ 0b0011, ~47 ns) does not stop a longer glitch.
  * After a bogus re-reference, the angle is wrong by an arbitrary amount until the next real Z.  That Z then mismatches, counts as the second event, and sends the drive to sensorless.
  * **Bounded:**
    * The real Z comes within one motor revolution: 4096 counts, 12.6° of wheel, ~4.8 mm of travel.
    * A reversing error moves the wheel backwards into that Z within the revolution.
    * An error near 90° gives near-zero torque on that wheel until the robot moves it, e.g. by turning on the other wheel.
  * **Cheap improvement (optional):**
    * On a first mismatch, keep the old reference and hold the new one as a candidate.  The next Z decides: 4096 counts after the candidate → A/B lost edges → adopt it; consistent with the old reference → the Z was a glitch → ignore it.
    * Or treat any mismatch above ~90° electrical (~170 counts) as suspect at once.  A few missed edges cannot reach that.
* **R29D-N2: two wording points in the rule.**
  * "a second one within the match": the MCU has no notion of a match.  Say "since reset" or "within ~N s".
  * State that the suspect-marking mismatch re-references the count as well.  Otherwise every later Z stays off by the error, and the "a Z matches the stored offset" way back never succeeds after a pure count error (the round-28 (b) issue, reached after two bursts instead of one).
* **R29D-N3: the round-28 capture fix verifies.**
  * The G474 allows a TIM3/TIM2 CH3 capture alongside encoder mode on CH1/CH2.
  * Mod 4096 is consistent even before the 32-bit extension (65536 = 16 × 4096).
  * At the capped 46.5 k rpm the Z pulse is 1 LSB = 1 / (4096 × 775 s⁻¹) ≈ 315 ns, far wider than the ~47 ns filter.

---

## 2. Scenario walk-through (current text)

Scenarios walked in rounds 26–28 whose rules are unchanged are not repeated.

| Scenario | Path | Outcome |
|---|---|---|
| Out-pushed, wheels back-driven under a forward command, 0–0.3 m/s | Torque-sign check → encoder suspect → sensorless (I/f) below observer speed; no way back until > ~0.3 m/s | **Nuisance, match-affecting (R29D-01)**; not unsafe |
| Speed-loop stop through 0.24 m/s at < ~8 m/s² | If "against" means the speed sign: trips (R29D-01) | Nuisance |
| Spinner hit knocks the robot back at > 0.4 m/s | Above observer speed: the observer check passes, the encoder is fine.  Deceleration then passes through the band against the command (same as the braking case) | As above |
| Magnet slips to a reversing offset mid-match | Torque-sign check ≤ ~30 ms, or the observer at ~0.3 m/s → sensorless; the Z electrical check fails, so it stays sensorless | Bounded, safe; no reversed drive beyond ~30–50 ms |
| A/B line intermittent | First Z mismatch re-references (correct), second → sensorless | Bounded |
| Glitch on the Z line | Bogus re-reference until the next real Z (≤ 1 motor rev, ~4.8 mm) → second mismatch → sensorless (N1) | Bounded |
| Reversal at a Z edge | Direction-aware capture / 1 LSB width: no false mismatch (N3) | OK |
| Encoder cable cut at standstill with torque commanded | No edges → no torque-sign trigger; "no edges, torque commanded" report | As before |
| Mid-fight IWDG reset | Latch word honoured; "ARM edge required" + throttle-zero interlock; drives resume with the back-EMF preset, or align (a shove repeats row 6c, never a latch) | No operator-less weapon restart |
| Weapon phase short, spinning / stopped | Row 4 / row 5 | Latched; no masked short |
| Switch opened under throttle or while braking | Row 0 / row 1 → hold, not a latch | Safe (unchanged) |
| Crossed bundles or sensor cables | Row 7 latches both drives; §9 forward-move check | No reversed drive |

## 3. §1 margins (re-checked, unchanged since round 28)

* **Timers:** 170 MHz / (2 × 3542) = 24.00 kHz; / (2 × 1771) = 48.00 kHz.
* **INA239:** SOVL 0x76C0 = 38.0 A; BOVL 0x17C0 = 19.0 V.
* **ARM** [S arm.out]: armed at 2.50–2.95 V vs VT+ ≤ 2.15 V; disarm in 52–164 ms; pause tolerance ≥ 52 ms vs the ≤ 20 ms gap spec.
* **Soft-start** [S hotplug.out]: 1.28–2.95 V/ms, ≤ 0.005 V/µs at VM, Q7 ≤ 22.0 W / ≤ 57 mJ.
* **Re-close and bounce:**
  * [S hotplug.out]: re-close ≤ 2.09 V/µs, bounce ≤ 2.26 V/µs.
  * Round-27 extra cases: ≤ 2.33 V/µs at 0 °C, 2.82 V/µs at −40 °C.
  * All under the 4 V/µs abs max, and §1 now states them correctly.
* **Voltage chain:** 18.3 V (§9) < 18.5 V coast < 19 V BOVL < 20 V DRV8316 OVP minimum < 28.75 V (D1 at 10 A) < 35 V C1 / 40 V DRV8316.  PA3–PA5 reach 3.69 V nominal / 3.75 V worst.
* **Spin-up** [S spinup.out]: 22.1 A peak, 14.06 V minimum vs the ≤ 10.3 V logic cutoff and the ≤ 10.1 V switch UVLO.
* **5 V:** 450 mA left for the compute board [C §4].
* **Drive top speed:** 46.5 k rpm vs the 50 k firmware cap and the 55 k MT6701 rating [C §10].

## 4. Summary

| ID | Sev | One line |
|---|---|---|
| R29D-01 | MAJOR | The round-28 torque-sign slip check ("encoder speed against commanded torque for ~30 ms below observer speed") also matches a wheel back-driven by a shove, and possibly a gentle stop.  It drops the drive to sensorless I/f exactly in a pushing exchange, with no way back until > ~0.3 m/s.  Fix: drop it (the slip is an accepted bounded residual) or use the q-axis back-EMF sign (Vq − R·Iq vs ω·λ), which a push cannot fake; add a §9 back-driven test |
| N1 | NOTE | A Z-line glitch is trusted by the first-mismatch re-reference for ≤ 1 motor rev (~4.8 mm); bounded; optional candidate-and-confirm |
| N2 | NOTE | "within the match" undefined; say that the suspect mismatch also re-references |
| N3 | NOTE | Direction-aware Z capture / 1 LSB width and mod-4096 verify |

**Verdict: 0 BLOCKER, 1 MAJOR, 0 MINOR, 3 NOTE.**
* Every fight and pit scenario walked ends safe and bounded.  None leaves a masked short, re-arms without the operator, or reverses a drive beyond the accepted ~30–50 ms slip transient.
* The one defect is R29D-01.  The round-28 slip check's signature is shared with normal pushing, so it causes a nuisance in a fault-free, match-deciding situation.  The fix is text only.
