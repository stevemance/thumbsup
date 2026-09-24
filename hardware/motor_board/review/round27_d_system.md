# Review round 27 / D: system-level review (rev L)

**Reviewer role:** adversarial system reviewer (power electronics and combat robotics).

**What I read:**
* DESIGN.md rev L, all of it (including the round-26 edits: CLR_FLT after the Release word, the §9 step 4 idle-current pass ≥ ~100 mA, the ≤ ~10 A regen current limit tied to the TVS clamp).
* design/calcs.md.
* spice/arm.out, hotplug.out and spinup.out.
* review/CHANGES.md (rounds 1–26) and round26_d_system.md.
* Datasheets:
  * DRV8316C (SLVSH07): OVP auto-recovers and releases nFAULT when the condition clears; hysteresis 0.7–0.9 V at OVP_SEL = 0.
  * DRV8323: VM UVLO 5.4–5.8 V falling.
  * MT6701: its ABZ output has no field-strength status.

**Scripts:** I copied the package without datasheets/ and review/ to `/tmp/r27d/`, ran the scripts there, then deleted the copy.
* `motor_board.py` printed "237 refs (205 placed components), 160 nets, 67 BOM lines / checks: OK".
* The regenerated calcs.md, nets.md, netlist.csv and bom.csv are byte-identical to the package.
* **Extra run:** I imported `sim_hotplug.py` unchanged and swept loaded contact bounces from 0.8 to 2.0 ms (stiff pack, C1 at 100 and 300 mΩ).
  * Some runs added a second constant load of 2.5 A that continues below the model's 5 V weapon cutoff, down to the DRV8316 UVLO (~4.2 V). It stands for the drives plus the buck.
  * Results are in N2.

Apart from this file, nothing in the package was edited.

**Evidence tags:**
* **[D l.N]** = a DESIGN.md line.
* **[S file]** = a spice output.
* **[C §N]** = a calcs.md section.

---

## 1. Findings

**No BLOCKER, MAJOR or MINOR findings.**

**NOTEs:**

* **R27D-N1: a magnet that slips or comes loose mid-match is caught only once the motor passes the observer speed.  The result is bounded.**
  * The only encoder-integrity checks that work while the rotor is moving are these two [D l.615]:
    * the observer comparison, above a few thousand rpm;
    * the Z check.
  * The Z check does not help here: a slipped magnet moves Z together with A/B, so the count at Z stays consistent.
  * **Case 1: the magnet slips to a fixed new offset.**
    * Any slip over ~15° mechanical is a random electrical offset (6 pole pairs), so there is about a 50 % chance of reversed torque (cos δ < 0).
    * With reversed torque the wheel runs backwards until the motor reaches the observer's range.  At ~3–5 k rpm that is 0.24–0.4 m/s at the wheel.
    * At 1.5 A the wheel force is 4.3 N [C §10] on a ~0.45 kg robot, so this takes about 40–50 ms.  The drive then goes sensorless.
    * The drive stays sensorless afterwards: the Z-vs-stored-offset test on return fails.
    * An offset near ±90° gives no torque and no edges, and the existing "no encoder edges, torque commanded" report covers it.
  * **Case 2: the magnet rattles loose** and makes edges without the rotor moving.  None of the rules catch this below observer speed, so that drive stays weak or twitching until a reset.  After a reset, alignment sends it to sensorless.
  * Neither case is unsafe.
  * Optional (text only):
    * Treat a Z-count mismatch of more than a few counts as "encoder suspect" (sensorless and report), not as drift to correct.  Quadrature with the ICxF filter does not drift by more than a count or two between Z pulses.
    * Or extend the no-edges report to "no net motion with torque commanded".
* **R27D-N2: the hard re-close window after a loaded bounce runs to ~1.2–1.3 ms, not just the simulated 0.1–0.8 ms.  The margins still hold.**
  * C18 (τ 1.3 ms) takes EN from 2.19 V to the ~1.17 V threshold in ≈ 1.3 ms, so bounces up to that length re-close with the FETs on [D l.510 cites 0.1–0.8 ms].
  * The extra run, at the DRV8316 VM pins:

    | Bounce | C1 100 mΩ (aged, 0 °C) | C1 300 mΩ (−40 °C limit) |
    |---|---|---|
    | 0.8–1.2 ms, sim as-is | 2.25–2.27 V/µs | 2.70–2.73 V/µs |
    | Same, +2.5 A load below 5 V (VM before 3.8–3.9 V) | 2.33 V/µs | 2.79–2.82 V/µs |
    | ≥ 1.4 ms (the switch UVLO has opened) | soft, 0.07 V/µs | soft, 0.09 V/µs |

  * Everything stays under the 4 V/µs abs max.
  * Only the −40 °C column, which is outside the 0–50 °C environment, passes the §1 "≤ 2.75 V/µs" wording [D l.36], by 0.07 V/µs.
  * The model's 5 V weapon-load cutoff is realistic: U2's UVLO (5.4–5.8 V) Hi-Zs the bridge at about that level.
  * Optional: say "0.1–~1.3 ms" in §7.2.
* **R27D-N3: a TIM8 break "brakes" if a DRV8316 OVP clears before the SPI owner raises DRV_OFF.  The result is a sub-ms, self-limiting brake.**
  * The scenario is a bounce during a weapon brake with the switch closed:
    * The bus rises ~26 V/ms, and both DRV8316s go to OVP (20–22 V).
    * L_nFAULT triggers the TIM8 break: INH idles high, and in 3x mode that means high sides on [D l.215].
    * On re-contact the bus returns to the pack in ~30 µs.  The OVP auto-recovers (0.8 V hysteresis), which is before the ~0.5 ms classification.
    * The left chip therefore applies a high-side brake until DRV_OFF goes high.  The right chip, on TIM20, resumes FOC with a wound-up integrator.
  * At speed the brake reaches the 16 A latched OCP and the chip Hi-Zs itself.
  * Drive row 1 (both chips at once, OVP within 1 ms of BOVL) [D l.682] already takes the event as supply, and "drives resume" step 4 clears the OCP without counting it.
  * The outcome is one supply count and no latch.  No change needed.  It is listed because the "a timer break brakes" choice has this one visible consequence.
* **R27D-N4: U4 nCS stuck low (short to GND) makes the whole of SPI3 fail.**
  * CTRL2 sets U4's SDO to push-pull, so a permanently selected U4 fights every U3 and U7 read.  The "two or three devices failing → SPI3 fault" hold then stops drives and weapon.
  * It is safe but it is a total loss.  Drive row 4 covers only an open or stuck-high nCS.
  * This needs a trace shorted to ground by impact, which §9 bring-up would otherwise catch.  Not worth new policy; noted for completeness.

---

## 2. Scenario walk-through (current text)

Scenarios verified in round 26 are unchanged and not repeated.  The round-26 edits were re-checked against the text:
* The optional CLR_FLT now comes after the Release word in both step 2 and step 3.
* The step 4 idle pass is ≥ 100 mA.
* The regen current limit ties to the D1 clamp.

| Scenario | Path | Outcome |
|---|---|---|
| Throttle re-applied to a spinning drum on a tired or cold pack (200 mΩ, 22 A step → ~5 V/ms on VBAT_SNS) | Row 2 is evaluated only at break time, so a load step alone raises no event | No nuisance |
| Comparator trip coinciding with its own current surge | A ≥ 5 V/ms slope needs a ≥ ~60 A pack step through 70 mΩ, so it stays row 6 | Non-latching |
| Brake into a cold pack: bus 16.8 + 10 A × 150 mΩ = 18.3 V (can reach 18.5 V) | Row 1 over-voltage → restart at 5 A.  A second trip would need R > 0.34 Ω | Cannot reach the 3-in-10-s latch |
| Disarmed drum coasting, switch closed | 25.6 k rpm / 1800 KV ≈ 14.2 V line-line peak < pack + 2 diode drops, so the drum cannot feed the pack and cannot fake row 0 | No false hold |
| Weapon low-side FET fails short | Disarmed: a partial brake on a coasting drum.  Armed: a shoot-through through RS1 → comparator trip → two fast re-trips → row 4 latch | Latched; no masked short |
| Weapon high-side FET fails short | Every low-side on-time → comparator → row 4.  At standstill, the row 5 check's PWM does the same | Latched |
| DRV8316 internal FET short | R302/R402 open as the fuse → drive row 3 latches that drive; the other continues | Bounded |
| Mid-match magnet slip or loss | N1 | Bounded; no sustained reversed drive |
| Loaded bounce 0.8–1.3 ms | N2: ≤ 2.33 V/µs (0 °C), ≤ 2.82 V/µs (−40 °C) | Within the abs max |
| Bounce during a weapon brake | OVP on both drives → N3 transient → drive row 1 supply | Non-latching |
| J1 partially unplugged by an impact | W_ARM_CLK R18 pull-down → disarm in 52–164 ms [S arm.out]; UART loss → command timeout coasts the drives | Safe |
| NRST held by the compute board | DRV_OFF R50 pull-up (coast), INL R47–R49 pull-down (weapon Hi-Z), W_EN pull-down | Safe |
| Parity of every DRV8316 word | 0x0603, 0x0606, 0x087C, 0x097D, 0x0A4E, 0x0C90, 0x0D10, 0x0D94, 0x0C14, 0x0F00, 0x1019, 0x1818: all even parity over 16 bits | ✓ |

## 3. §1 margins

* **Timers:**
  * 170 MHz / (2 × 3542) = 24.00 kHz and 170 MHz / (2 × 1771) = 48.00 kHz, an exact 2:1.
  * USART BRR 85 gives 2 Mbaud.
* **INA239:**
  * ADC_CONFIG 0xB480 decodes to MODE Bh, VBUSCT = VSHCT = 010 (150 µs), AVG 0.
  * SOVL 38.0 A and BOVL 19.0 V.
* **ARM** [S arm.out]:
  * Armed at 2.50–2.95 V vs VT+ ≤ 2.15 V, after 7–10 edges.
  * Disarm in 52–164 ms, against the §1 range (~30–200 ms) and the §3.5 re-arm hold (≥ 250 ms) and self-test window (20–250 ms).
* **Soft-start** [S hotplug.out]:
  * 1.28–2.95 V/ms and ≤ 0.005 V/µs at VM.
  * Q7 ≤ 22.0 W and ≤ 57 mJ.
* **Re-close and bounce:** re-close ≤ 2.09 V/µs; loaded bounce ≤ 2.26 V/µs (2.66 V/µs at −40 °C), extended in N2.
* **Voltage chain:**
  * 18.0 V (braking) < 18.3 V (§9 check) < 18.5 V (coast) < 19 V (BOVL) < 20 V (OVP minimum).
  * D1 clamps at ≤ 28.7 V with ≤ 10 A of regen.
* **Spin-up** [S spinup.out]: 22.1 A peak and a 14.06 V minimum, vs the ≤ 10.3 V worst-case logic cutoff.
* **Supply:** 450 mA of 5 V left for the compute board [C §4].

## 4. Summary

| ID | Sev | One line |
|---|---|---|
| — | — | No BLOCKER, MAJOR or MINOR findings |
| N1 | NOTE | A magnet that slips or rattles mid-match is caught only above observer speed.  A reversal is bounded (~0.3 m/s, ~50 ms), and a rattling magnet leaves the drive weak until a reset.  Optional: treat a Z-count mismatch as "encoder suspect" |
| N2 | NOTE | The hard re-close window runs to ~1.3 ms.  Extra sims: ≤ 2.33 V/µs at 0 °C and 2.82 V/µs at −40 °C, still under 4 V/µs |
| N3 | NOTE | The TIM8 idle-high break brakes the left drive for < 0.5 ms if an OVP auto-recovers first.  Self-limiting (OCP), and drive row 1 absorbs it |
| N4 | NOTE | A U4 nCS stuck low (push-pull SDO) turns into a full SPI3 hold.  Safe, but a total loss |

**Verdict: 0 BLOCKER, 0 MAJOR, 0 MINOR, 4 NOTE.**  Every fight and pit scenario walked ends safe, bounded and non-latching where it should be.  None leaves a masked short, re-arms without the operator, or drives in reverse (beyond N1's bounded transient).  The §1 margins check out numerically.
