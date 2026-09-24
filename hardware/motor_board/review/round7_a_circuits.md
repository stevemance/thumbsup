# Round 7 / A: circuits (rev G), re-verified from the datasheets

Scope: every circuit block, with priority on the rev G changes: D10 1N4148W + R32 1 MΩ in the Cdvdt network, UVLO R13/R14 =
100 k / 15 k, R19 10 k, and the rewritten `sim_hotplug.py` U13 model.  After that, a second pass over the weapon stage, the drives,
the sensors, the BQ76907, the buck, the MCU support and the ARM self-test.  No design file was edited.  All work was done on copies
in `/tmp/r7a/` (package in `/tmp/r7a/motor_board`, `tools/spice` beside it):

* `spice/sim_hotplug.py`, `spice/sim_arm.py`: unmodified copies, re-run and diffed against `hotplug.out` / `arm.out`.
* `spice/probe_r7.py`: the `sim_hotplug.py` circuit with options.  `model='hyst'` is a **latched** U13 comparator: on above
  V(EN_UVLOR) after ENTDLY 75 µs, 60 µA source until EN < V(EN_UVLOF), then the 2 Ω sink within ~2 µs.  Other options are an EN
  capacitor, a load current source, the gate hold resistance and the pack/lead values.
* `run1.py` (trip point, orig vs latched model), `run2.py` (re-close sweep around the trip, with/without D10), `run3.py` / `run5.py`
  (pack sag, trip and recovery under 22–25 A), `run4.py` / `run6.py` (BAT_IN ripple under weapon PWM, with/without an EN
  capacitor), `run7.py` (soft-start and reversed pack with the EN capacitor, IGATE 40 µA).

References: [LM] TI SNOSDE5A (LM74502), [DRV23] TI SLVSDJ3D, [DS] Diodes DS35124 (74LVC1G17), [LVC08] TI SCAS283, [HYG]
HYG015N04LS1C2, [D] DESIGN.md rev G, [N] design/motor_board.py, [C] design/calcs.md.

## Findings

| ID | Sev | Where | Finding | Evidence | Fix |
|---|---|---|---|---|---|
| R7A-01 | MINOR | [N] PSW_EN (R13/R14, no capacitor); [D §3.1] R13/R14 row "below a tired 4S pack under load (~11.5 V)"; [C] row 109 | **The switch UVLO is unfiltered.  It compares the instantaneous BAT_IN, including the weapon's 24 kHz input ripple, not the average.  Rev G raised the threshold, so in a tired-pack corner this can cut the robot's power mid-fight.**  At 20–30 A of weapon PWM the BAT_IN trough sits 0.6–1.1 V below the mean.  So the worst-case part (off at 10.14 V: V(EN_UVLOF) max, 5 µA sink, 1 % resistors) trips at a *mean* pack voltage of ~10.8–11.2 V.  The design claims margin against ~11.5 V.  The buck cut-off it is compared with is filtered: R4/R5/C10 τ = 4.5 ms, so it acts on the mean.  The switch is therefore now the binding limit, and it sits ~0.5–0.9 V above the buck's worst case.  Once tripped under load, the EN hysteresis (0.66–0.77 V at the bus) is smaller than the load's I × R_pack sag (2–4 V).  The switch then hiccups: off → pack recovers → on (75 µs) → load → off.  Q7 cycles through its linear region while carrying load current until the logic browns out and the load stops.  Result: MCU and compute-board reset, "ARM edge required", and a Bluetooth re-connect, i.e. the fight is lost.  Nominal packs are fine (14.1 V at 22 A per [C]).  The exposure is the tired, cold or high-IR corner, which the firmware fold-back ("toward ~12 V", [D §8]) must hold off. | [LM] 6.5: V(EN_UVLOF) 1.027/1.14/1.235 V, V(EN_UVLOR) 1.16/1.24/1.32 V, I(EN) 3/5 µA; 6.6: tUVLO_OFF 2 µs typ (no deglitch).  Off max = 1.235 × (1 + 101k/14.85k) + 5 µA × 101k = **10.14 V**.  `run4.py` (C1 ESR 20 mΩ, 150 nH lead): 16.8 V / 56 mΩ pack, 0/30 A square at 24 kHz: BAT_IN mean 15.92, min **14.99 V**; 13.6 V / 120 mΩ pack, 0/30 A: mean 11.60, min **10.59 V**; ESR 40 mΩ: min 10.46 V (EN trough 1.14 V bus-equivalent below the mean).  `run3.py` (latched model, max thresholds, 13.6 V / 150 mΩ pack, 25 A load held while VBAT > 6 V): one trip, then Q7 **81 W peak, ~80 W average** (the ideal load never stops; in the real board the buck/MCU and the DRV UVLOs end it within ms).  Same pack at typical thresholds: no trip (VBAT min 9.53 V). | Add **100 nF 16 V 0402 from PSW_EN to GND** (existing line C1525).  τ = (100k ∥ 15k) × 100 nF = 1.3 ms.  `run6.py`: EN ripple 1.02–1.14 V → **0.01 V** bus-equivalent.  `run7.py`: soft-start unchanged (0.005 V/µs, 16.5 W, 53.5 mJ; t90 9.0 → 10.2 ms); reversed pack unchanged (13.1 A C14 spike, EN −2.2 V, within the V(VS)-referred abs max).  Then state the UVLO margin on the mean (off ≤ 10.1 V worst vs the fold-back floor) and make the firmware fold-back floor explicit: hold the average VBAT ≥ ~11 V, because a trip under load is a reset, not a brown-out ride-through. |
| R7A-02 | MINOR | `spice/sim_hotplug.py` U13 model; [D §3.1] R15 row, [D §5], [D §7.2] "3.3 V/µs worst" | **The hot-plug model is still not faithful to the device in the hysteresis band, and it again hides the worst re-close, though only slightly.**  `bg` fades the 60 µA source out below the EN *midpoint*.  The device keeps sourcing until EN crosses V(EN_UVLOF) (it is latched on).  Between the two, the model's gate has no drive, and rev G's R32 (via D10) bleeds ~20 µA from it.  So the model FETs open about 0.02 V (EN) early: at a bus of **7.88 V**, not 7.74 V (min construction), and **9.15 V**, not 9.06 V (typ).  With a latched comparator, the worst re-close (min UVLO, C1 at 300 mΩ) is **3.46 V/µs** at 7.75 V (off 413 ms), not 3.30 V/µs.  The window is ~0.415 s (typ ~71 ms).  It is still under 4 V/µs (13 % margin, only at the −40 °C C1 corner).  The **0.968 V construction itself is right**: it gives a 7.72 V bus trip vs 7.74 V calculated (1 % resistors, no sink) and 7.739 V in the latched sim.  The sink-only-below-V(EN_UVLOF) change is also right. | `run1.py` (switch opened at 60 ms, C1 300 mΩ): orig model: Vgs < 3 V at 0.111 s / VBAT 9.149 V (typ) and 0.433 s / **7.880 V** (min), C13 bled to 10.5–11.8 V.  Latched model: 0.131 s / 9.057 V and 0.475 s / **7.739 V**, C13 18–19.5 V.  `run2.py` (latched, min UVLO, C1 300 mΩ): off 300 ms 3.296 V/µs; 400 ms 3.419; **413 ms 3.434 (D10) / 3.462 (no D10) V/µs**, 142 A, Q7 27 W; 420 ms: tripped, soft.  Calc: 1.027 × (1 + 99k/15.15k) = 7.74 V. | In `sim_hotplug.py` make U13 a latched comparator (as in `probe_r7.py`: state node, threshold V(EN_UVLOR) when off / V(EN_UVLOF) when on, 75 µs on / 2 µs off).  Add a re-close case at ~off 410 ms (min).  Restate 3.3 → **~3.5 V/µs** in §3.1, §5 and §7.2. |
| R7A-03 | MINOR | [D §4] table; [N] R13, R32, D4 comments and the power-entry header; [D §3.1] R1/D10/C13/R32/D4 row; [C] row 109 | **Stale or inconsistent power-entry figures in the files the board is drawn from.**  (a) [D §4] "switch FETs off below ~7.8 V (7.0–8.6)" is the rev F (R14 18 k) value; rev G is ~9.0 V (7.7–10.1).  (b) [N] R13: "off below ~9.0 V (**8.2**–10.0) … limits a quick re-close step to <= **8.6 V**" vs [D]/[C] 7.7–10.0 and ≤ ~8.9–9.1 V.  (c) [C] row 109 / [D §3.1]: max off 9.97 V and on ≤ 10.62 V omit the 1 % resistor tolerance that the minimum includes: they are **10.14 V / 10.8 V**.  (d) [N] header: "R15 bleeds the bus there within ~0.5 s" vs [D] ~0.1 s typ / ~0.4 s min.  (e) The D4 text ([D §3.1] and [N] D4): "during a pack sag C13 holds the gate while the source falls".  With D10 this cannot happen: a falling gate reverse-biases D10.  D4's remaining job is the TI clamp against VCAP − VS up to 13.9 V (GATE–SRC abs max 15 V).  (f) [N] R32: "takes <= 17 uA of the 60 uA gate drive near the top of the ramp".  In steady state it takes (VBAT + Vgs − 0.6 V)/1 MΩ ≈ **28 µA** at 16.8 V (≈ 31 µA at 19 V), continuously, against I(GATE) min 40 µA (see N-03). | [LM] 6.5 thresholds; arithmetic in R7A-01/-02; D10 orientation from nets.md: PSW_RG = D10.A, PSW_DV = D10.K; [LM] 6.5 charge-pump turn-off 11 / 12.4 / 13.9 V | Update the six texts (and re-run `calcs.py`). |

## Notes

| ID | Sev | Finding | Evidence / action |
|---|---|---|---|
| N-01 | NOTE | **D10 removes the soft-start for a re-close within ~20–40 ms after a UVLO trip.**  C13 is still charged (18–20 V) and isolated by D10, so it engages only once the gate reaches it, i.e. after the FETs are on.  The step is then Miller-limited and benign.  In the same window the rev F network (no D10) was worse at the trip edge. | `run2.py` (latched, typ): off 71/75/80 ms (trip at ~71 ms): **0.030–0.054 V/µs, Q7 62–75 W peak, 8–12 mJ** (no D10: 1.71 V/µs, 284 W at 71 ms; 0.005 V/µs later).  Min UVLO off 420 ms: 0.057 V/µs, 55 W, 12 mJ.  Soft (≤ 0.005 V/µs) from ~90 ms after the trip.  No change. |
| N-02 | NOTE | **Pack sag and recovery:** during a sag C13 stays above the falling gate (D10 off), so it neither holds the gate nor loads it.  On a fast recovery the gate must recharge C13 through R1/D10, and Vgs dips.  The dip is harmless: the FETs stay fully on while the current falls. | `run5.py` (25 A for 300 ms, then released): 16.8 V / 250 mΩ / 50 nH: Vgs 11.9 → **8.26 V**; 16.8 V / 200 mΩ / 150 nH: 8.99 V; 15 V / 200 mΩ: 9.04 V; Q7 ≤ 0.8 W.  `run3.py`: sag to 12.1 V, Vgs min 9.39 V. |
| N-03 | NOTE (UNVERIFIED) | **R32 is a permanent ~28 µA gate load.**  I(GATE) is specified only at Vgs = 5 V (40/60/77 µA).  The source's headroom near VCAP (VCAP − VS 11.6–12.4 V typ, 10.3 V min turn-on) is not specified, and D4 also shares the current near its knee.  The steady Vgs is therefore somewhat below the charge-pump level; it is very unlikely to be below ~8 V ([HYG] RDS(on) is specified at 4.5 V as well).  Soft-start at I(GATE) = 40 µA: t90 13.9 ms, Q7 10.6 W / 55.6 mJ (`run7.py`). | Measure Vgs(Q7) at 16.8 V at bring-up (§9 step 1).  R32 = 2.2 MΩ halves the load: τ 48 ms, still ≪ the 2 s re-close rule. |
| N-04 | NOTE (UNVERIFIED) | C13 22 nF 50 V **0402** X7R sits at ~28 V in steady state and 0–19 V during the ramp.  DC-bias loss in 0402 X7R is typically 20–40 % at those voltages, so the real ramp is ~2.5–3 V/ms.  That is inside the already-simulated 77 µA case (3.0 V/ms, 21.8 W). | Optional: 0603 50 V (C1622-class) for less derating. |
| N-05 | NOTE | U14 draws extra supply current while armed: its input sits at 2.5–2.95 V, i.e. VCC − 0.35…0.8 V, where [DS] ΔICC is ≤ 500 µA (at VCC − 0.6 V).  Plus R19's 0.33 mA.  Under 1 mA total on +3V3; harmless. | [DS] p.3 ΔICC; arm.out 2.50–2.95 V |
| N-06 | NOTE | No 1N4148W datasheet in `datasheets/` (generic part; C81598 SOD-123).  Ratings relied on: VR ≥ 75 V vs ≤ 45 V worst (C13 at gate + TVS level), IR ≤ 25 nA at 20 V / 25 °C, Cj ≤ 4 pF.  Standard 1N4148W values, UNVERIFIED for this vendor. | Add the CJ/LCSC PDF. |

## Re-verification of the requested items

* **D10 + R32, soft-start.**  `hotplug.out` reproduces byte-identically: 2.23 V/ms, ≤ 0.009 V/µs at VM, Q7 16.5 W / 53.5 mJ
  (21.8 W at 77 µA).  The latched model gives the same (`run7.py`: 0.005 V/µs, 16.5 W, 53.5 mJ, t90 9.0 ms).  D10 orientation is right:
  anode on R1/PSW_RG, cathode on C13/PSW_DV (nets.md l.71/74), KiCad SOD-123 pad 1 = K.
* **Turn-off speed.**  With D10 reverse-biased, the 2.3 A sink sees only the gate capacitance (Ciss 2 × 4.05 nF).  [LM] tUVLO_OFF is 2 µs
  typ at 4.7 nF.  R1 plus D10 give double isolation.  OK.
* **Reversed pack.**  With D10, C13 cannot source current from GND into the gate: 13.0–13.1 A C14 spike only, for gate holds of 300 Ω,
  3 kΩ and 100 kΩ (`hotplug.out`; `run7.py` also with the proposed EN capacitor).  D10 then sees VR ≈ 16.5 V, and with Cj ≤ 4 pF it
  injects < 10 mV into Ciss.  R32 has no path to the gate while D10 is reverse-biased.  OK.
* **D10/C13 during sag and recovery:** N-02; after a trip: N-01.
* **Does R32's bleed change anything else?**  Steady gate load (N-03, R7A-03f).  It makes the U13 model's hysteresis-band artefact
  worse (R7A-02).  With U13 off and a flat pack connected, it pulls PSW_S to ~0.6 V through the internal GATE–SRC switch and D10: µA only,
  with both body diodes reverse-biased.  It has no effect on the reverse, ARM or monitor paths.
* **UVLO 100 k / 15 k.**  Off 9.04 V typ (7.74 V min: 1 % R, no sink; 10.14 V max); on 9.8 V typ (≤ 10.8 V).  Against a nominal pack
  (14.1 V at 22 A) there is ample margin.  Against a tired or high-IR pack at 22–27 A there is margin only on the mean, and not on the
  ripple trough (R7A-01).  **Buck interplay:** buck off 9.2 V typ / 7.4–10.3 V on the 4.5 ms-filtered VBAT; the switch is now at the
  same level but unfiltered, so it is the one that acts first in a sag (R7A-01).  After a switch trip under load, the pack recovers
  above V(EN_UVLOR) at once, so the switch re-closes (hiccup) until the logic or the load drops out.
* **R19 10 k.**  Worst-case input leakage 3 × 5 µA ([LVC08]) + PD2 → ≤ 0.2 V, below VIL 0.8 V.  Load when armed 0.33 mA: [DS] VOH ≥
  VCC − 0.1 V at −100 µA and ≥ 2.2 V at −12 mA, so the 0.33 mA costs nothing.  Unpowered U14: IOFF, R19 holds the node low.  R19 does not load
  W_ARM (it sits on the output).  OK.
* **Sim models.**  The sink only below V(EN_UVLOF) is right.  The source "above the EN midpoint" is not (R7A-02).  The 0.968 V
  "min UVLO" construction is the true minimum (7.72 V vs 7.74 V) and the right worst case (the lowest bus at which the FETs are still on).
* **ARM self-test, §3.5 item 4.**  (a) Single edge: healthy W_ARM = 3.3 × 0.47/2.67 ≈ 0.58 V, so it stays low.  With C15/C16 swapped,
  3.3 × 2.2/2.67 − V_F ≈ 2.4 V > VT+ ≤ 2.15 V ([DS] 3 V: 2.00, 4.5 V: 2.74).  It stays above VT− for ~14 ms (τ 22 ms), so the rise and the
  latched "fell" flag catch it.  A shorted C15 also arms on (a).  (b) Healthy arms in 12 ms at 500 Hz (arm.out).  (c) C15 short: W_ARM held
  ~3 V, no fall: caught.  R41 open: only D9/U14 leakage (nA cold), no fall in 250 ms: caught (boot = cold).  U14 stuck high: caught.
  (d) C16 open: W_ARM_S is a copy of the clock, so it falls at the final falling edge, ~0 ms after the stop, below the 20 ms floor: caught.
  (In (c) its 13–30 ms fall can sit inside the window, so (d) is the step that catches it.)  Wrong values: R41 ≫ 47 k fails the 250 ms
  ceiling, C16 ≪ 2.2 µF fails the 20 ms floor.  Every claim in item 4 holds.

## VERIFIED OK

* `design/motor_board.py` (copy) regenerates `nets.md`, `netlist.csv`, `bom.csv`, `mcu_pinmap.md` byte-identically: "228 refs (196
  placed components), 157 nets, 65 BOM lines, checks: OK".
* `spice/sim_hotplug.py` → `hotplug.out` and `spice/sim_arm.py` → `arm.out`: byte-identical (`diff` clean).
* U13 LM74502 DDF pinout ([LM] Fig. 5-1: 1 EN/UVLO, 2 GND, 3 NC, 4 VCAP, 5 VS, 6 GATE, 7 OV, 8 SRC) vs [N]; OV to GND; C14 100 nF on
  VS; C12 220 nF VCAP–VS ≥ 0.1 µF and ≥ 10 × Ciss; D4 12 V gate–source (GATE–SRC abs max 15 V vs VCAP − VS ≤ 13.9 V); EN abs max met
  forward and reversed (EN ≥ V(VS) when VS < 0; sim −2.2…−4.2 V vs VS −16.8 V).
* Q7/Q8 back-to-back (Q7 D = BAT_IN, Q8 D = VBAT_SW, common S/G); body-diode directions block the plug-in surge (Q7) and a
  reversed pack (Q8); RS4/U7 after the switch.
* INA239: SHUNT_CAL 0x1000 = 819.2e6 × 1.25 mA × 1 mΩ × 4; SOVL 0x76C0 = 38.0 A; BOVL 0x17C0 = 19.0 V.  ALERT is wire-ORed on W_nFAULT.
* Weapon stage: VDS 0.13 V / 1.4–2.1 mΩ → 62–93 A; CSA 40 mV/A, ±35 A about VREF/2 = 1.65 V; straps as rev F (MODE 47 k, IDRIVE
  75 k, VDS 18 k, GAIN Hi-Z, CAL GND); INLx = CHxN AND W_ARM_S, fourth gate grounded; R47–R49 100 k.
* Buck: FB 0.765 × (1 + 56/10) = 5.05 V; nSHDN 390 k / 51 k with −1 / −4.2 µA: on 10.42 V, off 9.17 V typ; C10 τ 4.5 ms.
* Drives: DRV8316C SPI words re-derived (address << 9, even parity in B8): 0x0603, 0x1019, 0x0A4E, 0x0D10, 0x0F00, 0x1818, 0x087C,
  0x097D, 0x0606 all have consistent parity; CSA 0.15 V/A → ±8.7–9.9 A over AVDD 3.1–3.465 V; VREF/ILIM on its own AVDD.
* Sensors (TPS22945, SN74LVC3G17, 4.7 k / 1 k, NTC 2.2 k + BAV99), BQ76907 4S wiring and 22 µs input filter, D5, MCU support
  (VBAT_SNS 68 k / 10 k → 2.15 V at 16.8 V, 0.87 ms; NRST, BOOT0, VDDA/VREF+): unchanged since round 6 and re-checked against nets.md.
* U14 thresholds used in `sim_arm.py` (VT+ ≈ 2.15 V at 3.3 V interpolated, VT− 0.80–1.33 V) match [DS] p.3–4; armed 2.50–2.95 V.

**Verdict: 0 BLOCKER, 0 MAJOR, 3 MINOR (6 NOTE).**
