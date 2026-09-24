# Review round 26 / D: system-level review (rev L)

**Reviewer role:** adversarial system reviewer (power electronics and combat robotics).

**What I read:**
* DESIGN.md rev L, all of it.  I re-read §8.1 rows 0–1 at the end because the file changed during the review: the stale "(only its explicit braking command pauses it, above)" in row 0 now reads "(only its regenerating torque command pauses it, above)".  I had drafted a MINOR for that leftover; it is fixed, so it is dropped.
* design/calcs.md and spice/hotplug.out, arm.out, spinup.out.
* review/CHANGES.md (rounds 1–25) and round25_d_system.md.
* Datasheets: SMBJ20A_BORN.pdf (VBR 22.2–24.5 V, Vc 32.4 V at 18.6 A) and STM32G474RET6.pdf (PA3/PA4/PA5 are TT_a: 4.0 V abs max, VDD + 0.3 V operating; PA2 is FT_a).

**Scripts:**
* I copied the package without datasheets/ and review/ to `/tmp/r26d/`, ran `design/motor_board.py` and `design/calcs.py` there, then deleted the copy.
* `motor_board.py` printed "237 refs (205 placed components), 160 nets, 67 BOM lines / checks: OK".
* The regenerated calcs.md, nets.md, netlist.csv and bom.csv are byte-identical to the package.
* I did not re-run the SPICE decks, because the hardware has not changed since round 16.  The .out files were re-read.

Apart from this file, nothing in the package was edited.

**Evidence tags:**
* **[D l.N]** = a DESIGN.md line (current numbering).
* **[S file]** = a spice output.
* **[C §N]** = a calcs.md section.

**Numbers used:**
* C_bus ≈ 374 µF.
* Idle ≈ 0.1 A [C §9].
* Regen limit ~10 A pack-side [D l.619].
* Drive bus load 0.5–2.1 A [D l.653].
* Drum J = 1.8e-5 kg·m², 25.6 k rpm, 64.5 J [S spinup.out].
* 2822 1800 KV → Kt = 5.3 mN·m/A.
* Divider 68k/10k = ÷7.8.

---

## 1. Findings

**No BLOCKER, MAJOR or MINOR findings.**  The round-25 changes check out numerically and are consistent across §8, §8.1 and §9.

**NOTEs:**

* **R26D-N1: row 0 stays paused while a brake's regen is smaller than the drive load.  This is still bounded, and short in practice.**
  * With the switch open, the pause lasts only while regen is smaller than the load.  With the fold-back [D l.609], the bus then settles near ~12 V and the drives run on drum energy.
  * At the 10 A pack limit the brake returns ~170 W, far above the drives' ~45 W, so the bus rises and a protective coast ends the pause.
  * Below 60 % speed the brake becomes phase-limited: 20 A × 5.3 mN·m/A = 0.106 N·m.  Regen then falls under 45 W at ω ≈ 425 rad/s (~16 % speed).
  * That tail takes J·ω/T = 1.8e-5 × 425 / 0.106 ≈ **72 ms** and holds ~1.6 J.  The bus then collapses and the board browns out or holds.
  * A long masked window needs the regen limit already halved twice or three times (2.5 A ≈ 42 W, or 1.25 A).  That takes repeated closed-switch over-voltage coasts, which the §9 < 18.3 V calibration is meant to prevent.  The drum energy bounds the window at ≲ 3 s.
  * No change needed.
* **R26D-N2: while the switch is open during a brake, D1 is the clamp for ≤ ~0.8 ms.  The worst-case bus sits ~0.3 V under the TT-pin abs max.**
  * Regen into the open bus rises at (10 − 0.1) A / 374 µF ≈ 26 V/ms.  The BOVL break acts after 0.3–0.8 ms [D l.589], so D1 conducts ≤ 10 A.
  * The SMBJ20A's slope is (32.4 − 24.5) / 18.6 ≈ 0.42 Ω, so a part at VBR max clamps at ≈ 24.5 + 4.2 = **28.7 V**.
  * The energy is ≤ 10 A × 28.7 V × 0.8 ms ≈ 0.23 J, well inside the part's 600 W 10/1000 µs rating.
  * Downstream parts at 28.7 V:
    * PA4/PA5 (1 nF, they follow the bus) see 28.7 / 7.8 = **3.68 V**, and a phase node one diode above sees ~3.77 V.  That is above the 3.6 V operating range but below the **4.0 V abs max** for TT pins.
    * PA3 (VBAT_SNS) is also TT, but its 0.87 ms filter holds it lower.
    * The DRV8316 OVP (20–22 V) Hi-Zs the drives, as intended [D l.619].
  * All of this is within limits.  The assumption doing the work is that pack-side regen stays ≤ ~10 A: at D1's 18.6 A rating point the bus is 32.4 V → 4.15 V on the pins, over the abs max.
  * Suggested (text only): note the ≤ 10 A regen-limit dependency next to the §3.2 "TVS-level spike" sentence [D l.183–185].
* **R26D-N3: the row 0 margins depend on the measured idle current, and §9 does not state an acceptance value.**
  * Row 0 needs idle ≫ 30 mA (the hold threshold) and above the ~50 mA "estimate within 50 mA of zero" suspension band.
  * If the measured idle fell below ~50 mA, row 0 would be suspended permanently whenever the drives are idle.  That is exactly the pit case: drum coasting, drives off.
  * The package's own numbers give ~100–120 mA with the compute board fitted [C §9], roughly 2× margin, so the design is fine as it stands.
    * The §9 step 1 bench figure of "< 60 mA at 12 V" has no firmware running and no compute board, so it is not the operating idle.
  * Suggested: §9 step 4 should accept the idle only if it is ≥ ~2 × the suspension band (≥ ~100 mA; otherwise narrow the band).
* **R26D-N4: VBUS "> ~8 V" in row 0 sits inside the logic-cutoff spread (7.4–10.3 V) [D l.113].**
  * On a board whose buck turns off near the 7.4 V minimum, a switch opened with the drum already below ~14 k rpm leaves the logic alive at a 7.4–8 V bus, where row 0 is not evaluated.
  * The drives could then run on ~19 J of drum energy, for ≲ 0.5 s at 40 W.
  * This needs a worst-case part plus a slow drum at the moment the switch opens.  It is bounded and harmless.
  * Optional: gate row 0 at ~7 V.
* **R26D-N5: the round-25 changes were verified by walking the scenarios below.**
  * The pause is keyed on a regenerating FOC command and ends at any protective coast.
  * The brake is withheld after a coast while |I| < 50 mA.
  * The regen limit is a current limit [D l.609].
  * The 18.5 V coast is handled as row 1 [D l.618].
  * The instant coast needs a positive command.
  * The row 1 sentence and the §9 expectation [D l.769] match.
  * The numbers behind the rules:
    * row 1 open-bus decay 0.1 A / 374 µF = 0.27 V/ms ✓;
    * drives pulling: 1.3–5.6 V/ms ✓;
    * the closed-switch dump τ ≈ 374 µF × 74 mΩ ≈ 28 µs ✓;
    * "C1 alone would fall ~30 V in 100 ms" = 26.7 V ✓;
    * three shunt conversions ≈ 0.9 ms ✓.

---

## 2. Scenario walk-through (current text)

| Scenario | Path through §8 / §8.1 | Outcome |
|---|---|---|
| Weapon brake to stop, switch **closed**, drives idle | Paused while regen is commanded.  The bus is 16.8 + 10 A × 70–120 mΩ = 17.5–18.0 V, under the 18.5 V coast (§9 checks < 18.3 V).  At the end, the torque goes ≥ 0 and the pack current steps to ≥ +idle.  No instant coast (the command is negative) | Clean |
| Same, drives driving or regenerating | Drive regen suspends row 0.  Drive motoring adds to the pack current.  The cross-check is off (drum not stopped or motoring) | Clean |
| Invertible-drum reversal, switch closed | The decel is paused.  The reverse spin-up draws ≥ idle + copper loss | Clean |
| Speed-loop deceleration (throttle lowered), switch closed | Now paused too.  The PI torque crosses zero at ≳ 200 A/s, so its dwell in ±30 mA is ≪ 1 ms | Clean |
| Brake into a full or cold pack that hits 18.5 V, switch closed | Handled as row 1: after the dump the reading is +idle → over-voltage → restart at half the regen limit (the brake gate passes because \|I\| ≈ idle > 50 mA).  More than ~3 in 10 s latches | Bounded.  Halving stops repeats |
| **Switch opened during a brake, drives idle** | Rise ~26 V/ms → D1 clamp (N2) → BOVL/18.5 V coast → looks open (\|I\| ≈ 0.2 mA, VBUS > 18 V) → pause ended, brake withheld → row 0 hold ~100 ms after the coast | Safe; hold with the stick still held |
| **Switch opened during a brake, drives pulling** | Rise ~21 V/ms → coast.  The bus falls 1.3–5.6 V/ms, so the class may be over-voltage (one count).  The restart is gated because \|I\| < 50 mA → row 0 hold in 100 ms | Safe; no brake resume on the open bus; one count, no latch |
| Switch opened in a brake's tail or a gentle decel (regen < load) | Pause held → the drives run on drum energy → the brake ends (≤ ~72 ms at the phase limit), then collapse or the instant coast, then the hold | Bounded (N1) |
| Switch opened under throttle, fast drum | The bus sags to the drum's BEMF; FOC saturates; power ≤ 0 and \|I\| < 50 mA ×3 (~0.9 ms) → instant coast → hold at 100 ms (the estimate ≥ idle) | Safe |
| Switch opened under throttle at spin-up (slow drum) | C1 falls ~59 V/ms under 22 A → bus below every UVLO → BOR.  Everything Hi-Z (INL pulled down, DRV_OFF pulled up; +3V3 loss also drops the DRV8316 INL = phase Hi-Z).  A re-close is a fresh power-up with the throttle-zero interlock and the ARM edge | Safe |
| Switch opened, drum coasting (disarmed) in the pit | Body-diode feed never suspends row 0; estimate = idle → hold in 100 ms; power LED on until ~19 k rpm | Safe; re-close is not soft but ≤ 2.1 V/µs [S hotplug.out] |
| Switch opened while shoved or while the drives brake | Drive regen suspends row 0 while it lasts.  Drive regen into the open bus trips the DRV8316 OVP or BOVL → looks open → drives at zero torque → hold | Bounded |
| Switch opened 50 ms and re-closed mid-match, drum spinning | Instant coast → pack current returns at re-close → catch-spin restart.  The row 0 run is broken before 100 ms | Auto-recovers; no hold |
| Opened for > 100 ms mid-match, drum spinning | Hold → operator clear (disarm, new edge, throttle zero for the weapon) | Intended; no operator-less restart |
| Opened for > 100 ms, drum stopped | C1 falls ~27 V/100 ms → brown-out.  On re-close: fresh power-up, re-arm needs the edge and throttle zero | Auto-recovers the drives; weapon only after operator throttle |
| Contact bounce 0.1–3 ms under spin-up, switch closed | Row 2 supply (≥ 1 ms bounces may also give an instant coast that restarts when current returns); VM ≤ 2.26 V/µs [S hotplug.out] | Bounded, non-latching |
| Contact bounce during a brake, switch closed | Rise into D1 (≤ 0.23 J), DRV8316 OVP, looks open → current returns → supply restart | Non-latching.  Four such within 10 s with the over-voltage class could latch; that needs a loose connector *and* repeated braking (not a single fault) |
| Pushing match, wheels stalled, switch closed | The pack current is idle + copper loss, far from ±30 mA.  The no-edges flag is a report only | No fault |
| MCU reset during a row 0 hold | Hold not persisted → drives may resume ≤ 100 ms on drum energy → row 0 re-holds.  The weapon needs a new ARM edge (≥ 250 ms low) | Bounded |
| Drive resume at speed, crossed cables or bundles, swapped phase | Back-EMF preset, row 7 (both latched), row 6a | No reversed drive (settled) |
| Weapon short spinning / stopped / to GND | Row 4 / row 5 (the row 10 stall retry also passes through row 5) / row 8 | Latched; no masked short |
| +3V3 or LDO collapse | DRV8316 INL = 0 → Hi-Z, nSLEEP low; U6 outputs low → weapon Hi-Z; W_EN pulled down | Fail-safe |
| Compute-board hang | ARM falls in 52–164 ms [S arm.out] | Safe (settled) |

## 3. §1 margins (outputs re-read; hardware unchanged)

* **DRV8316 VM dV/dt** [S hotplug.out]: loaded bounce 0.80–2.26 V/µs; 2.66 V/µs at C1's −40 °C ESR; re-close ≤ 2.09 V/µs.  All within the §1 "≤ 2.75 V/µs" and under 4 V/µs.
* **Soft-start:** 1.28–2.95 V/ms, ≤ 0.005 V/µs at VM.  Q7: 22.0 W peak / 57 mJ max.  374 µF × 2.2 V/ms = 0.82 A in 7.6 ms.  Matches the §1 "~0.8 A in ~8 ms".
* **ARM:** armed at 2.50–2.95 V vs VT+ ≤ 2.15 V; 7–10 edges to arm; disarm in 52–164 ms.  Matches §1.
* **Spin-up:** 22.1 A peak and 14.06 V minimum at the 20 A limit, vs the ≤ 10.3 V worst logic cutoff [S spinup.out, C §9].
* **Voltage chain:** 16.8 + ~1.2 V = 18.0 V (braking at 10 A) < 18.3 V (test) < 18.5 V (coast) < 19 V (BOVL) < 20 V (OVP minimum).  D1 at ≤ 10 A regen ≤ 28.7 V, under 35 V (C1) and 40 V (DRV8316) (N2).
* **INA239 limits:** 0x76C0 × 1.25 µV / 1 mΩ = 38.0 A; 0x17C0 × 3.125 mV = 19.0 V.  ✓
* **5 V budget:** 450 mA for the compute board [C §4].

## 4. Summary

| ID | Sev | One line |
|---|---|---|
| — | — | No BLOCKER, MAJOR or MINOR findings |
| N1 | NOTE | The row 0 braking pause while regen < load is bounded: ≈ 72 ms tail at the phase limit; longer only after repeated regen halvings |
| N2 | NOTE | An open-switch brake clamps in D1 at ≤ 28.7 V (10 A): 3.68 V on the TT pins vs 4.0 V abs max.  This relies on the ≤ 10 A regen limit |
| N3 | NOTE | Row 0 needs the measured idle ≳ 2 × the 50 mA suspension band; state it as a §9 step 4 acceptance |
| N4 | NOTE | The row 0 VBUS > 8 V gate sits inside the 7.4–10.3 V logic-cutoff spread (tiny, bounded window) |
| N5 | NOTE | The round-25 changes verified by the scenario walk |

**Verdict: 0 BLOCKER, 0 MAJOR, 0 MINOR, 5 NOTE.**  Every walked fight and pit scenario ends safe and bounded, with no masked short, no operator-less spin-up and no reversed drive.  The one stale round-25 leftover I found (the "explicit braking command" in row 0's suspension clause) was fixed in DESIGN.md while this review was in progress.
