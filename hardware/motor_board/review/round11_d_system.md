# Review round 11 / D: system-level review (rev K), gate = ready for schematic capture

Reviewer role: power electronics and combat robotics, looking at the whole package fresh.  No
design file was edited.  Out of scope: board area and chassis fit, the compute board's own design
beyond §3.5, and firmware-contract detail except where the hardware makes a safety function
impossible (those items are NOTEs).

Inputs: DESIGN.md rev K (read end to end), design/calcs.md, design/nets.md, spice/*.out,
spice/sim_hotplug.py (model check), review/CHANGES.md (round 10 → rev K), review/round10_d_system.md,
review/round10_a_hardware.md (for the origin of the rev K fault-kick numbers).

Evidence tags: **[D §x]** DESIGN.md, **[C §x]** calcs.md, **[N]** nets.md, **[S …]** spice output,
**[R11 sim]** my own throw-away run of the package's `sim_hotplug.py` model with changed parameters
(in `/tmp/r11`; nothing was added to the package; see the appendix).

---

## 1. Focus items

### 1.1 Rev K DRV8316 VM filters (R302/R402 0.1 Ω + ~16 µF)

Checked and found sound as hardware:

* **Netlist.**  [N] L_VM = R302.2, C300/C301 (100 nF), C302/C308/C309/C310 (4 × 10 µF), C303.2 (the CP
  capacitor's VM end) and U3 pins 9/10/11; R_VM is the same for U4.  R302.1/R402.1 are on VBAT.  The
  charge-pump capacitor is referenced to the filtered node, which is correct.  No other load is on L_VM/R_VM.
* **Damping.**  The series R302 with 5–20 nH of trace and 16 µF gives Z0 = √(L/C) ≈ 18–35 mΩ, so
  Q ≈ Z0/R ≤ 0.35: overdamped.  No local resonance.
* **Stability with the drive as a constant-power load.**  The worst-case incremental resistance is
  −V²/P = −16.8² / (8 A × 16.8 V) ≈ −2.1 Ω at an 8 A peak, and ≈ −11 Ω at the 1.5 A traction limit.
  The filter's source impedance is ~0.1 Ω, far below either.  Middlebrook criterion met.
* **Own switching ripple (not in the sim).**  τ = 1.6 µs is much shorter than the 20.8 µs PWM
  period, so R302 carries the drive's bus current within each cycle.  VM ripple ≈ I_bus × 0.1 Ω =
  0.1–0.2 V at 1–2 A.  The edge step is 2 A / 16 µF ≈ 0.13 V/µs.  Harmless.  This closes the open
  point in R10D-01's fix column.
* **Regen/OVP.**  Drive regen of ≤ 2 A lifts L_VM ~0.2 V above VBAT.  Firmware coasts at an 18.5 V
  VBAT, so L_VM stays ≤ ~18.7–19.3 V (the last figure at an 8 A peak), below the DRV8316 OVP minimum
  of 20 V.
* **Pulse duty.**  The loaded-bounce re-close puts (VBAT − L_VM) ≈ 3–4 V across R302, i.e. ~35 A for a few µs
  (< 1 mJ).  The phase-to-ground fault puts ~100 A through it for ~1 µs (~1 mJ) [D §7.21].  Both
  are trivial for a 2512 thick film.
* **Sim numbers.**  They reproduce [S hotplug.out]: bounce ≤ 2.25 V/µs (0 °C bound), 2.65 V/µs
  (−40 °C), and worst re-close 2.06 V/µs.  §1, §3.1, §3.3, §5, §7.2 and calcs §7 agree.
* **Side benefit (worth writing down).**  R302/R402 also act as a fuse if a DRV8316 fails VM-to-GND,
  which is the likely failure mode of an over-ramped VM.  The fault would draw 16.8 / (0.1 + ~0.075) ≈ 95 A,
  i.e. ~0.9 kW in the 2512, which opens it within about a millisecond.  The robot then loses one drive.
  Before rev K the same fault was a bus short, and per [D §7.14] U13 would retry into it until Q7 failed.

### 1.2 Weapon fast trip (§7.21, §8)

The hardware can do everything the plan needs:

* The three weapon CSA pins reach COMP3/COMP1/COMP6 non-inverting inputs.
* DAC3_CH1/DAC4_CH2 are internal-only.
* The comparators feed TIM1's asynchronous BRK.  The break drives CHxN low (OSSI = 1), and the U6
  AND gate then pulls INLx low.
* At the fault currents (130–145 A × 2 mΩ = 0.26–0.29 V), the CSA inputs stay inside ±0.3 V
  differential.
* The drive timers are independent, so a weapon trip does not stop the drives.

The realistic chain (0.7–1.0 µs) plus R302/R402 gives ≤ ~2 V/µs at VM for comparator-covered
faults (round-10 sims).  The residuals in §7.21 (phase-to-ground shorts are seen only by the 4 µs
VDS trip, ~7–8 V/µs; an open D1) are stated with numbers.  They are not cheaply fixable: the
round-10 table shows that even 0.22 Ω leaves ~5.6 V/µs, and there is no fast sensor for the
high-side current.

The remaining points are about how the trip is set and when it latches (R11D-01, -02, -03, -05).
They are NOTEs because firmware sets the threshold and the latch policy.

### 1.3 Safety-chain walk-through (rev K)

| Phase | Result |
|---|---|
| Power-on | DRV8316 nSLEEP rises with +3V3 while R50 holds DRVOFF high.  A freshly woken DRV8316 is in 6x mode with its buck enabled, but DRVOFF overrides that.  In reset, R47–R49 hold INL low and R40 holds ENABLE low.  The soft-start is ≤ 0.01 V/µs at L_VM.  OK |
| Arming | No change.  OK |
| Fight, normal | Weapon ripple at L_VM is now filtered by τ = 1.6 µs.  The drive's own ripple is 0.1–0.2 V (§1.1).  OK |
| Fight, weapon fault | Comparator-covered faults give ~1–2 V/µs at VM.  Phase-to-ground shorts are an accepted residual.  Threshold and latch policy: R11D-01/02 |
| Contact bounce / re-close | ≤ 2.25 V/µs (0 °C bound) and 2.65 V/µs (−40 °C) at VM.  If the bounce drags VM to ~4.5 V and resets a DRV8316, the 100 Hz NPOR read-back recovers it.  In the ≤ 10 ms before that, a reset DRV8316 in 6x mode with INL tied high only brakes on the PWM off-times.  Benign |
| Brown-out / regen disconnect | Unchanged; D1 is the clamp.  L_VM tracks VBAT within I × 0.1 Ω.  OK |
| Signal loss / hangs | Unchanged.  OK |
| Power-off | +3V3 collapses, which sleeps the DRV8316s and takes U6 low; R40 pulls ENABLE low.  L_VM follows VBAT down with a 1.6 µs lag.  OK |

---

## 2. Findings

| ID | Sev | Area | Finding | Evidence / numbers | Fix |
|---|---|---|---|---|---|
| R11D-01 | NOTE | Fight availability: fast-trip threshold vs the first-trip latch | §8 now recommends **~25 A (0.65 V)** as the working threshold.  R10D-02 proposed that only "once the nuisance margin is measured".  At the 20 A FOC limit a returning phase already sits at 1.65 − 0.80 = **0.85 V**, which is 0.20 V (5 A) above a 25 A threshold.  CSA offset takes ±80 mV (±2 A) of that, leaving **~3 A** for PWM ripple plus current-loop overshoot.  The comparator sees the instantaneous current, not the centre-sampled average.  Ripple estimate at 24 kHz, M ≈ 0.5 (mid spin-up), with the 2822's per-phase inductance unpublished: ΔI_pp ≈ (⅔V_dc − v_ref) × t_active / L_ph ≈ 3 V × 14.6 µs / L_ph.  That is **5.8 A p-p (±2.9 A) at 7.5 µH** and **±5.5 A at 4 µH**.  So a 25 A threshold may nuisance-trip during ordinary 20 A spin-ups, and §7.21 then latches the weapon off for the rest of the fight | [D §8] weapon fast-trip row; [D §7.21] "first large trip latches the weapon off"; [C §1] 40 mV/A; round10_d §3 (CSA offset ±2 A) | Make **30 A (0.45 V) the default**.  Lower it only after §9 step 4 has measured the nuisance margin at a 20 A spin-up (measure L_ph of the real motor too).  Record the chosen value and the measured margin in §8 |
| R11D-02 | NOTE | Contradiction on weapon trip latching (§7.21 vs §8) | §7.21 says "the first large trip latches the weapon off (no retries)".  §8's Watchdog/faults row says "more than ~3 DRV8323 OCP retries (4 ms cadence) … within a second → latch".  On this board a weapon VDS OCP only fires for faults the comparators cannot see (phase-to-ground) or failed to stop, because the comparators act at 0.7–1.0 µs and the VDS deglitch is 4 µs.  Each firmware re-enable after one therefore repeats a **~500 A pulse** (near the FETs' 600 A pulse rating) and a **~7–8 V/µs kick at both DRV8316 VM pins** (2× the 4 V/µs abs max).  With nFAULT on BKIN and AOE = 0 the DRV8323's own 4 ms auto-retry cannot re-drive the bridge, so the choice is firmware's.  The two sections disagree | [D §7.21]; [D §8] Watchdog/faults and DRV8323RH rows; round10_a (7.5 / 8.2 V/µs VDS-only at the filtered VM) | In §8, say that on the **weapon** any comparator trip or VDS OCP (nFAULT releasing after ~4 ms) latches the channel off at once.  The 3-per-second counter stays for the drives (DRV8316 recoveries) and for W_nFAULT events that no comparator saw and that did not look like VDS OCP |
| R11D-03 | NOTE | Unfiltered W_nFAULT break input now that BKF = 0 is required | Rev K requires TIM1 **BKF = 0** because the comparator and pin sources share one BRK filter.  That also removes all filtering from W_nFAULT (PC13).  This open-drain line has a 10 k pull-up (R42) and runs from U2 at the bridge and U7 at RS4 to the MCU [N W_nFAULT: R42, TP9, U1.2, U2.28, U7.3; no capacitor].  Any coupled glitch below V_IL clears MOE and coasts the weapon.  By my estimate (0.2 pF of coupling × ~20 V of edge ringing into ~10 pF of line ≈ 0.4 V dip) a trip is unlikely, but it cannot be tuned out in firmware any more.  A capacitor at PC13 costs no protection: <br>• the DRV8323 Hi-Zs its own bridge on VDS OCP/GDF; <br>• INA239 alerts come ≥ 150 µs after a conversion; <br>• an open-drain driver discharges 1 nF in ns, so faults still assert at once; only the release is slowed (10 k × 1 nF = 10 µs) | [D §8] fast-trip row "BKF = 0"; [N] W_nFAULT; R42 10 k [motor_board.py l.263] | At capture, add a **0402 footprint at PC13, W_nFAULT to GND** (fit 1 nF, or DNP until the bench shows a need).  It gives the pin path its own glitch filter without slowing the comparators |
| R11D-04 | NOTE | Rev K filter parts: no bring-up check; silent single faults not listed | These parts are new.  A wrong value, a 0 Ω, or a missing or tombstoned C309/C310 is invisible in operation and in §9 (step 1's scope check at switch-on shows ≤ 0.01 V/µs whether the filter is there or not).  R11 sim of the worst loaded bounce (0.3 ms, stiff pack, C1 at 100 mΩ): **2.21 V/µs as designed → 3.49 V/µs with R302 = 0**, and **2.99 V/µs with only 8 µF**.  Round 10's table puts the comparator-covered weapon short back at ~5 V/µs without the resistor.  So the filter's margin disappears silently.  (For the record: an open C1, e.g. a can broken off in a hit, stays at 3.04 V/µs in the same bounce because R302 does the work, so C1-open is not a VM hazard) | [R11 sim]; [D §7.16]; [D §9] steps 1, 6; round10_d A.2 | §9 step 2: with one drive running at a known bus current (≥ 1 A), measure VBAT − L_VM across R302/R402 (expect ~0.1 V/A).  Visually check the 4 × 10 µF per drive.  Add R302/R402 and C302/C308–C310 (and the U4 equivalents) to the §7.16 list.  Optionally note in §7 that R302/R402 are the de facto fuse for a shorted DRV8316 (§1.1) |
| R11D-05 | NOTE | Documentation consistency around the fast trip | (a) §9 step 4 ends "that normal switching does not false-trip (**blanking set**)", but §8 says "**blanking off by default** … a TIM1_OC5 window would be a blind spot".  (b) §9 step 4 runs the trip test after "Raise to 16.8 V" on the step-1 bench supply (1.5 A / 0.2 A limit).  A locked-rotor trip at 25–30 A phase needs ~30 A pulses and a few amps of average bus current, so a current-limited supply will sag or hiccup into U13's UVLO.  Step 6 already says "4S pack or a supply good for ≥ 25 A peaks".  (c) §3.2's VDS row and calcs §6 still say "a hardware comparator trip on all three CSAs" covers 20 A to the VDS trip.  The R10D-02 correction (30–60 A peak by vector angle) went into §8 only.  (d) The kick figures are on different averaging bases: §3.3, CHANGES and calcs §7 say "~1 V/µs", which round10_a gives as the 200 ns average.  On the 50 ns basis used for the unfiltered 9–11 V/µs it is ≤ 2.2 V/µs rising, plus a 3.6 V/µs blip at turn-off that round10_a attributes to a model glitch.  §7.21's "~1–2 V/µs" is the honest range | [D §9] step 4 vs [D §8]; [D §9] steps 1, 4, 6; [D §3.2], [C §6] vs [D §8]; round10_a R10A-01 | (a) "blanking off; if a nuisance trip appears, raise the threshold first".  (b) In step 4: "on the pack (or a ≥ 30 A-peak supply)".  (c) Carry the 30–60 A wording into §3.2 and calcs §6.  (d) Quote "≤ ~2 V/µs (50 ns average)" in §3.3/calcs §7 |

---

## 3. Checked and found consistent (no finding)

* **BOM count:** bom.csv has 67 lines and 198 designators, matching §1.  R302/R402 are C25466
  (UNI-ROYAL 25121WF100LT4E, 0.1 Ω 1 % 1 W 2512) in bom.csv and BOM.md.
* **Hot-plug sim model:** the rev K model has R302/R402 and 16 µF + 200 nF behind 5 nH, the right
  topology for the claims.  The DRV8316 load current is not modelled; §1.1 covers it analytically.
* **Break output sequence in FOC:** with CHxN held high by an inactive-high CCxNP, the asynchronous
  break level is CCxNP (high).  OISxN = 0 applies after the (zero) dead time plus ~2 clocks, which
  round 10 already counted (tens of ns).  CLL keeps the clock running.  Fine.
* **Power-on with a DRV8316 at default registers:** DRVOFF (R50 up) overrides the 6x-PWM / INL = 1
  default.  The default buck output goes into R300 22 Ω / C307 with no load.  Benign.
* **Weapon bus ripple in C1:** ~8 A rms during 20 A spin-ups against a 2.8 A rms rating.  With
  ~0.5 s bursts, about 5–10 % of a match, the match-average I² is under the rating.  Not a finding.
* **Accepted residuals** §7.2, §7.14, §7.16, §7.20 and §7.21 still hold with rev K's numbers.

---

## 4. Summary

| ID | Sev | One line |
|---|---|---|
| R11D-01 | NOTE | The ~25 A recommended fast-trip threshold leaves ~3 A for PWM ripple (est. ±3–5.5 A) at the 20 A limit.  With the first-trip latch, a nuisance trip ends the weapon for the fight.  Default to 30 A; lower only after measuring |
| R11D-02 | NOTE | §7.21 (latch on the first large trip) contradicts §8 (3 OCP retries/s).  On the weapon every VDS OCP is a ~500 A, 7–8 V/µs-at-VM event, so it must latch at once |
| R11D-03 | NOTE | BKF = 0 leaves W_nFAULT (10 k pull-up, long run) unfiltered.  Add a 0402 C footprint at PC13 (1 nF, fit or DNP); it costs no protection |
| R11D-04 | NOTE | Rev K filter parts have no bring-up check and are missing from §7.16.  Without R302 the worst bounce goes 2.2 → 3.5 V/µs (sim), and weapon-short protection is lost.  Measure VBAT − L_VM at a known current |
| R11D-05 | NOTE | Doc drift: §9 "blanking set" vs §8 "blanking off"; step 4 trip test needs the pack, not the 1.5 A bench supply; §3.2/calcs §6 still overstate comparator coverage; kick figures quoted on mixed averaging bases |

**Verdict: 0 BLOCKER, 0 MAJOR, 0 MINOR, 5 NOTE: ROUND CLEAN.**

---

## Appendix: R11 sim (throw-away, `/tmp/r11/r11.py`, not added to `spice/`)

This imports `spice/sim_hotplug.py` unchanged and calls `run()` with modified parameters.  Peak
dV/dt is at the DRV8316 VM node (vm2).

| Case | VM before | Peak dV/dt | I peak |
|---|---|---|---|
| 0.3 ms bounce, 20 A, stiff, C1 40 mΩ (reproduces hotplug.out) | 4.7 V | 1.67 V/µs | 216 A |
| same, C1 open (ESR 1 kΩ) | 4.3 V | 3.04 V/µs | 195 A |
| same, nominal lead, C1 open | 4.3 V | 1.84 V/µs | 115 A |
| 0.3 ms bounce, stiff, 0 °C C1 100 mΩ, **R302 = 1 mΩ** | 4.7 V | 3.49 V/µs | 213 A |
| same, **8 µF local** (C309/C310 missing) | 4.7 V | 2.99 V/µs | 199 A |
| switch closure, nominal, C1 open | — | 0.00 V/µs (soft-start) | 13 A |
| re-close after 300 ms, min UVLO, C1 open | 2.6 V | 0.00 V/µs (bus already below UVLO) | 23 A |

For reference, the designed 0 °C / 100 mΩ bounce is 2.21 V/µs [S hotplug.out].
