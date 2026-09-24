# Review round 28 / D: system-level review (rev L)

**Reviewer role:** adversarial system reviewer (power electronics and combat robotics).

**What I read:**
* DESIGN.md rev L, all of it.  I focused on the round-27 edits:
  * the Z-count mismatch rule [D l.615];
  * the §7.2 bounce window [D l.510];
  * the §3.2 1 nF / sustained-clamp wording [D l.183];
  * the §9 step 4 idle band and the step 6 regen-current log [D l.749, l.763].
* design/calcs.md.
* spice/arm.out, hotplug.out and spinup.out.
* review/CHANGES.md (rounds 1–27), round26_d_system.md and round27_d_system.md.
* Datasheets:
  * MT6701CT-STD.pdf v1.9: §7.3 ABZ, Figures 9–12, and the Z_PULSE_WIDTH / HYST / ZERO register tables (pp. 14–15, 29).
  * SMBJ20A: the clamp figures, re-used from round 27.

**Scripts:**
* I copied design/, spice/ and ref/ only to `/tmp/r28d/`, ran them there, then deleted the copy.
* `motor_board.py` printed "237 refs (205 placed components), 160 nets, 67 BOM lines / checks: OK".
* nets.md, netlist.csv, bom.csv, mcu_pinmap.md and calcs.md came out byte-identical to the package.

Apart from this file, nothing in the package was edited.

**Evidence tags:**
* **[D l.N]** = a DESIGN.md line.
* **[S file]** = a spice output.
* **[C §N]** = a calcs.md section.
* **[MT p.N]** = the MT6701 datasheet.

---

## 1. Findings

### R28D-01 (MINOR): the round-27 Z-count rule cannot see the fault it was added for, and one noise burst leaves a drive sensorless for the rest of the match

The text [D l.615] says:

> at every later Z check the count (mod 4096): a few counts is drift (correct it); a larger mismatch (a slipped or loose magnet or encoder) marks the encoder suspect → sensorless and report.

CHANGES.md records the change as "Z-count mismatch beyond drift → encoder suspect (slipped magnet)".

**(a) A slipped magnet gives no count mismatch.**
* The MT6701 counts the *magnet's* angle continuously.  It also emits Z at a fixed *magnet* angle (the ZERO register [MT p.29]).
* When the magnet slips on the shaft, A/B follow the magnet through the slip (the chip is rated to 55 k rpm).  Z still fires at the same magnet angle.
* So the count at Z stays constant modulo 4096.  Round 27's own N1 said the same: "a slipped magnet moves Z together with A/B".
* What the slip breaks is the link between the count and the *rotor* (the electrical offset).  A count-at-Z comparison cannot see that link.
* So R27D-N1 case 1 is unchanged.  A slip to a reversing offset drives the wheel backwards until the motor reaches observer speed.  At ~3–5 k rpm motor that is ~0.3 m/s at the wheel, ~40–50 ms at 1.5 A.
* The outcome is bounded, the same as round 27 accepted.  But the package now claims detection it does not have.

What the rule *does* catch, correctly:
* missed or extra A/B edges: an intermittent A or B line, harness noise, or a field so weak that the chip's output goes erratic (a magnet that has come *off*);
* a stuck or noisy Z line.

**(b) The chosen action cannot recover after a harmless count slip.**
* "The count itself is never zeroed" [D l.615].  A burst of N extra counts (e.g. weapon-bridge noise coupled into the J2/J3 harness) therefore shifts every later count-at-Z by N.
* The drive goes sensorless.  The return path needs "a Z matches the stored offset", and every later Z is still N counts off.
* The drive stays sensorless until a reset or re-alignment, and nothing in §8/§8.1 schedules either.
* Sensorless FOC is weak at the low speeds a pushing match runs at.  So one transient costs the rest of the match on that wheel, when the fix was one re-reference.
* The text itself calls Z "the absolute reference".  A count error is therefore corrected *at* Z, like drift.  Only *repeated* mismatches (e.g. > ~2 within a few seconds) indicate a bad line.

**(c) The Z edge moves by the Z pulse width when the direction reverses.**
* The Z pulse is programmable to 1, 2, 4, 8, 12 or 16 LSB, or 180° [MT p.15, p.29].  One LSB is one quadrature count (Figure 12: 1000 pulses = 4000 steps).
* A capture on the rising edge of Z lands at one end of the pulse when running forwards and at the other end when running backwards.  The difference is the pulse width.
* §9 step 5 programs "ABZ mode, 1024 PPR, rotation direction, power-up absolute ABZ output off" [D l.755] but not the Z width.
* With a 4–16 LSB pulse, every reversal exceeds "a few counts".  A combat drive reverses constantly, so each reversal would mark the encoder suspect.
* With 180°, the offset is 2048 counts.  That is 0° electrical at 6 pole pairs, but the mod-4096 count check still flags it.
* The Z electrical-offset measurement in §9 step 5 (spread < ~5° electrical ≈ 9 counts) would not reveal widths up to 8 LSB.

**Fix (text only):**
* In §9 step 5, program Z_PULSE_WIDTH = 1 LSB, or make the Z capture direction-aware (capture both edges and use the counter DIR bit).
* Reword the rule: "a Z-count mismatch beyond a few counts (missed or extra edges: intermittent A/B, harness noise, magnet lost) → re-reference the count at Z and report; repeated mismatches (e.g. ≥ 2 in ~5 s) → encoder suspect → sensorless".
* Drop "slipped magnet" from both the rule and CHANGES.md.
* Keep R27D-N1 as a documented, bounded residual.  If it should be closed, the missing check is a torque-sign one: below observer speed, commanded \|Iq\| ≥ ~0.5 A for ≥ ~30 ms with the encoder speed moving *against* the command → encoder suspect.  Row 6a already catches a wrong sign at alignment; this is the mid-match equivalent.

---

**NOTEs**

* **R28D-N1: §1 and calcs §7 still claim ≤ 2.75 V/µs "even with C1 at its −40 °C ESR limit", but §7.2 now quotes 2.82 V/µs there.**
  * The claims are at [D l.36] and [C §7].  §7.2 [D l.510] carries the round-27 extra case.
  * The 0–50 °C figure (≤ 2.33 V/µs) and the 4 V/µs abs max are unaffected.
  * Fix the wording, e.g. "≤ 2.35 V/µs over 0–50 °C, ≤ 2.82 V/µs at C1's −40 °C limit".
  * Also stale: DESIGN l.9 "rounds 11–26" and README "twenty-six".
* **R28D-N2: the armed brake time is ~0.5 s, not ~0.4 s.**
  * The claims are at [D l.524, l.620].
  * At top speed the ~10 A DC regen limit binds: 170 W at 17 V takes the drum from 64.5 J to 15.3 k rpm in 0.24 s.
  * Below that speed the 20 A phase limit binds: 0.106 N·m on J = 1.8e-5 takes 0.27 s more.
  * Total ≈ 0.52 s lossless.  Copper and windage losses shorten it slightly.
  * This is informational only.  The event limit applies to the disarmed free coast, which §9 step 6 measures.
* **R28D-N3: the round-27 regen log and clamp numbers verify.**
  * D1 at 10 A: 24.5 + 10 × 0.425 = 28.75 V.  ÷7.8 gives 3.69 V (3.75 V with worst-case tolerance) on PA3–PA5, under the 4.0 V abs max.
  * 4.0 V on the pins is reached at 14.3–15.8 A, consistent with the "~12–14 A" in §9 step 6 (VBR spread and the hot TVS coefficient).
  * The §9 step 6 check "INA239 ≥ ~−10 A combined" measures the real current into D1's future path.  This closes R27A-01 as intended.

---

## 2. Scenario walk-through (current text)

Scenarios walked in rounds 26/27 and unchanged by the round-27 edits are not repeated.  These are the round-27 interactions and a few fresh single-fault cases.

| Scenario | Path | Outcome |
|---|---|---|
| Magnet slips mid-match to a reversing offset | Count-at-Z stays consistent (R28D-01a).  Observer check above a few k rpm → sensorless.  The return needs a Z that matches the stored *electrical* offset, which fails, so the drive stays sensorless | Bounded (~50 ms, ~0.3 m/s), as R27D-N1 |
| Magnet comes off (field lost) | Erratic edges → Z-count mismatch or no edges → sensorless / "no edges, torque commanded" | Bounded |
| A-line open mid-match | B toggles against a constant A: the count dithers ±1 and the angle freezes.  Moving: Z-count mismatch → sensorless.  Stalled: "no edges" once the rotor settles | Bounded; no reversed drive |
| Harness noise adds N counts once | Z-count mismatch → sensorless.  With the current text there is no return (R28D-01b) | Degraded for the match, not unsafe |
| Drive reversal with the Z width > a few LSB | Every reversed Z is flagged (R28D-01c) | Nuisance; configuration-dependent |
| Brake, switch closed, drives also braking (combined 10 A) | Weapon share = 10 A − drive regen.  Bus ≤ 16.8 + 10 × 0.15 = 18.3 V on a cold pack.  Row 1 halves on an 18.5 V event | Non-latching (a second event needs R > 0.34 Ω) |
| Switch opened during a 10 A brake | ~26 V/ms → BOVL/18.5 V coast in ≤ ~0.45 ms → D1 ≤ 28.75 V, PA3–PA5 ≤ 3.75 V → looks open → row 0 hold ~0.1 s after the coast; DRV8316 OVP Hi-Zs the drives | Safe; sense pins within rating (N3) |
| Loaded bounce 0.8–1.3 ms, 0–50 °C | ≤ 2.33 V/µs at VM (round-27 extra sims) | Within the abs max |
| Mid-fight IWDG reset | Latch word honoured.  "ARM edge required" → the compute board holds ≥ 250 ms low → throttle-zero interlock.  Drives realign; a shove repeats alignment (row 6c), never a latch | No operator-less weapon restart |
| Weapon FET short (either side), spinning or stopped | Row 4 (second fast re-trip) / row 5 (resistance check) | Latched; no masked short |
| Crossed bundles or sensor cables after a pit repair | Row 7 latches both drives; §9 forward-move check | No reversed drive |

## 3. §1 margins (re-checked)

* **Timers:** 170 MHz / (2 × 3542) = 24.00 kHz and / (2 × 1771) = 48.00 kHz.  USART BRR 85 gives 2 Mbaud.
* **INA239:**
  * SOVL 0x76C0 = 30400 × 1.25 mA = 38.0 A.
  * BOVL 0x17C0 = 6080 × 3.125 mV = 19.0 V.
  * ADC_CONFIG 0xB480: 150 µs per conversion, AVG 1.
* **ARM** [S arm.out]: armed at 2.50–2.95 V vs VT+ ≤ 2.15 V, after 7–10 edges.  Disarm in 52–164 ms, inside the §1 range (~30–200 ms).  The pause tolerance is ≥ 52 ms (85 °C), consistent with the §3.5 ≤ 20 ms gap spec.
* **Soft-start** [S hotplug.out]: 1.28–2.95 V/ms, ≤ 0.005 V/µs at VM, Q7 ≤ 22.0 W / ≤ 57 mJ.
* **Re-close and bounce:** re-close ≤ 2.09 V/µs; bounce ≤ 2.26 V/µs [S hotplug.out], ≤ 2.33 V/µs to 1.3 ms (0 °C).  The §1 wording is stale at −40 °C (N1).
* **Voltage chain:** 18.3 V (§9) < 18.5 V (coast) < 19 V (BOVL) < 20 V (DRV8316 OVP minimum) < 28.75 V (D1 at 10 A) < 35 V (C1) / 40 V (DRV8316).
* **Spin-up** [S spinup.out]: 22.1 A peak and a 14.06 V minimum, vs the ≤ 10.3 V worst-case logic cutoff and the ≤ 10.1 V switch UVLO.
* **Supply:** 450 mA of 5 V left for the compute board [C §4].
* **Drive top speed:** 46.5 k rpm (duty-capped), inside the MT6701's 55 k rpm and the firmware's 50 k cap [C §10].

## 4. Summary

| ID | Sev | One line |
|---|---|---|
| R28D-01 | MINOR | The Z-count check cannot detect a slipped magnet (Z moves with A/B).  After a single count burst the drive never leaves sensorless.  The Z-edge position depends on direction by the Z pulse width, which is not programmed.  Fix: Z_PULSE_WIDTH = 1 LSB or direction-aware capture; re-reference on the first mismatch, suspect only on repeats; drop the "slipped magnet" claim (optionally add a torque-sign check) |
| N1 | NOTE | §1 and calcs §7 "≤ 2.75 V/µs at −40 °C" vs §7.2's 2.82 V/µs; round labels stale (11–26, "twenty-six") |
| N2 | NOTE | The armed brake from full speed is ~0.5 s, not ~0.4 s (informational) |
| N3 | NOTE | The round-27 D1 clamp / PA3–PA5 margin and the §9 regen-current log verify numerically |

**Verdict: 0 BLOCKER, 0 MAJOR, 1 MINOR, 3 NOTE.**  Every fight and pit scenario walked ends safe and bounded.  None leaves a masked short or re-arms without the operator.  The one reversed-drive case, a magnet slip, stays the bounded transient that round 27 accepted; the round-27 text only overstates its coverage.  The one match-affecting weakness is R28D-01(b)/(c), a text-only fix.
