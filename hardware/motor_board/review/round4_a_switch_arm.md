# Round 4 / A: high-side power switch (U13 LM74502 + Q7/Q8) and dynamic ARM

Reviewer scope: the rev D power switch (DESIGN §3.1, netlist `design/motor_board.py` lines 92–119) and the dynamic ARM
(DESIGN §3.2 "Dynamic ARM", netlist lines 238–247).  No design file was edited.  Datasheets were read with
`pdftotext -layout` and rendered where the text lost a figure.  Simulations are in `/tmp/r4a/spice/`:
`sim_hotplug.py` (unchanged copy), `sim_hotplug_nopor.py` (gate sink off below POR), `sim_psw_sag.py` (GATE–SRC
during a pack sag), `sim_arm.py`, `sim_arm_fix.py` and `sim_arm_r41.py` (ARM charge pump).  The ngspice runs used
KiCad's libngspice (`hardware/tools/spice/ngspice_shared.py`).  The main netlists are summarised in the appendix.

References: [LM] SNOSDE5A (LM74502), [HYG] HYG015N04LS1C2 V1.0, [BAT] Nexperia BAT54S (1 July 2022),
[LVC] SCAS283 (SN74LVC08A), [ST] DS12288 Rev 4 (STM32G474), [D] DESIGN.md rev D, [N] motor_board.py.

## Findings

| ID | Sev | Where | Finding | Evidence | Fix |
|---|---|---|---|---|---|
| **R4A-01** | **MAJOR** | [D §3.2] Dynamic ARM, [N] C15/C16/R41, [D §8] W_ARM row, [D §9] step 3 | **The ARM hold time is not ~130 ms.  It depends on which level the clock stops at, and on temperature.  One edge is enough to arm.**  (a) *Stuck high*: C15 (1 µF) is 10 × C16.  With the clock held high, C15 discharges through D2 into W_ARM, so W_ARM decays with R41·(C15+C16) = 1.1 s instead of R41·C16.  (b) *Stuck low or floating*: D2 is reverse-biased by W_ARM, and its reverse leakage (BAT54S ~25 µA typ at 85 °C) is added to R41's 3 µA.  (c) *One edge*: C15 and C16 share charge 10:1, so a single rising edge takes W_ARM to 2.9 V (91 % of the swing) within µs.  The circuit therefore works as an edge detector with a 0.1–1.4 s hold, not as a frequency detector.  Consequences: **false disarms** — a compute-board loop that stops with the pin low drops W_ARM below PD2's VIH within 35 ms at 25 °C, ~15 ms at 60 °C and ~4 ms at 85 °C.  §8 then latches a full weapon stop ("re-arm needs an explicit restart and a new ARM edge").  RP2040 flash-erase stalls (tens of ms on XIP) or BT-stack hiccups are enough.  **Slow disarm**: a hung compute board with the pin high keeps ARM for up to 1.4 s, and a board that sets the pin high once and hangs gets ≥ 2.0 V for 0.4 s.  That same single edge satisfies the §8 "fresh low→high edge" rule.  The §9 step 3 pass limit (< 0.8 V within ~150 ms, stuck high) will fail. | sim_arm.py §2, time from the stop to below 2.31 V / 2.0 V / 0.8 V: **25 °C stuck high 316 / 464 / 1368 ms**; 25 °C stuck low 28 / 42 / 123 ms; 60 °C stuck high 164 / 225 / 500 ms; **60 °C stuck low 15 / 20 / 45 ms**; 85 °C stuck high 42 / 57 / 115 ms; **85 °C stuck low 3.8 / 5.2 / 10.4 ms**.  §4, 500 Hz with one pause parked low, minimum W_ARM: 20 ms → 2.52 V, 35 ms → 2.15 V, 50 ms → 1.83 V.  §5, one rising edge then held high: peak 2.92 V, ≥ 2.0 V for 397 ms, > 0.8 V for 1301 ms.  [BAT] Fig. 2: IR ≈ 0.2–0.5 µA at 25 °C, ≈ 20–30 µA at 85 °C, ≈ 250 µA at 125 °C (low VR).  [ST] Table 54: VIH = 0.7 VDD (2.31 V) for FT pins.  [LVC] 6.3: VIH 2.0 V, VIL 0.8 V. | Rebalance so C15 ≪ C16 and R41 dominates the diode leakage: **C15 470 nF, C16 2.2 µF, R41 47 kΩ** (sim_arm_fix.py).  Results: W_ARM 2.78–2.96 V at 500 Hz; rise to 2.31 V in 14–16 ms (~8 edges, so a single edge gives only ~0.6 V); below VIL 0.8 V in **99–157 ms whether stuck high or stuck low, over 25–85 °C**.  With today's values the same run gives 10–1368 ms.  Also add a compute-board requirement to §3.5 item 4: "no gap between W_ARM_CLK edges longer than 10 ms".  Correct the §3.2, §9 step 3 and netlist-comment numbers; test both stuck levels at bring-up. |
| R4A-02 | MINOR | [N] R41 1 MΩ, U6 pins 2/5/10, PD2 | **By datasheet limits, input leakage can hold W_ARM up.**  Three LVC08 inputs sit on W_ARM, each specified at II ±1 µA (25 °C) / ±5 µA (−40…85 °C), and PD2 adds ±150 nA.  A sourcing leakage of 1 µA holds W_ARM at 0.83 V (above VIL) and 3 µA holds it at 2.83 V (**armed**) indefinitely with the clock stuck low.  Real CMOS leakage is typically nA (UNVERIFIED on these parts).  At 85 °C the BAT54S leakage happens to sink more than this, so the worst case is cold. | [LVC] 6.7: "II VI = 5.5 V or GND … ±1 (25 °C), ±5 (−40…85 °C) µA".  [ST] Table 54: Ilkg ±150 nA (FT).  sim_arm.py §3 (25 °C, clock low): 1 µA → 0.83 V, 3 µA → 2.83 V, 15 µA → clamps high. | R41 ≤ 47 kΩ, which R4A-01's values already use: 15 µA × 47 k = 0.71 V < VIL 0.8 V. |
| R4A-03 | MINOR | [N] U6 SN74LVC08A inputs on W_ARM | **A slow RC edge drives a non-Schmitt gate.**  W_ARM crosses the LVC threshold at ~1.4–150 V/s (an RC decay with τ ≈ 0.01–1.1 s, depending on temperature and on the level the clock stopped at).  That is 0.007–0.7 s/V, against the LVC08's recommended limit of Δt/Δv ≤ 8 ns/V.  During every disarm (and during ripple near the threshold) the three INLx outputs can oscillate, and U6 draws ΔICC (up to 500 µA per input) through the linear region.  PD2 has hysteresis; U6 has none.  Each chatter burst is a train of enable pulses into U2's low-side drivers while the weapon is being disarmed. | [LVC] 6.3: "Δt/Δv Input transition rise or fall rate … 8 ns/V"; 6.7 ΔICC 500 µA.  sim_arm.py §2 decay rates. | Put an SN74LVC1G17 Schmitt buffer (SOT-23-5, +3V3) between W_ARM and U6/PD2.  U6's inputs then see clean edges; PD2 can read either side. |
| R4A-04 | MINOR | [N] C15 (0402 1 µF), R41 (0402) | **Two latent single faults make ARM static and silently undo E3-01.**  **C15 shorted** (the usual failure of a flex-cracked MLCC): W_ARM_CLK is DC-coupled through D2, so a pin stuck high holds W_ARM at 3.22 V forever.  **R41 open**: with the pin stuck high, W_ARM is still 1.82 V after 10 s at 25 °C.  Neither is visible in normal toggling (C15 short gives 3.18–3.21 V, which looks healthy).  The other D9/C16 faults fail safe (see VERIFIED OK). | sim_arm.py §6: c15_short stuck high → 3.22 V, "below 0.8 V in inf ms"; sim_arm_r41.py: R41 open, 25 °C stuck high → 1.82 V at 10 s. | Boot self-test in the firmware contract (§3.5 item 4 / §8): the compute board holds W_ARM_CLK high for ≥ 0.5 s, then low, and the motor MCU reports PD2 over the UART at each step.  Arming is refused unless W_ARM falls in both states.  Optionally make C15 two capacitors in series. |
| R4A-05 | MINOR | [N] C13 22 nF PSW_DV→GND, U13 GATE/SRC | **GATE–SRC can exceed U13's 15 V abs max during a pack sag.**  The Cdvdt topology is TI's (Fig. 8-2: RG + Cdvdt to GND), but it fixes the gate's *absolute* voltage.  When the pack sags under the weapon load, SRC (≈ BAT_IN) falls with it and C13 holds the gate, so GATE–SRC rises by ≈ 0.73 × ΔV_pack.  If the GATE pin has an internal path to VCAP, the gate is clamped near VCAP and the rise stays under ~0.6 V.  SNOSDE5A does not show such a path (UNVERIFIED), and `sim_hotplug.py` assumes it (its `dgc` diode).  TI recommends a GATE–SRC Zener "in case output is expected to drop to the level where it can exceed external FET VGS(max)".  The FETs themselves (±20 V) are fine. | sim_psw_sag.py, 20 A load, BAT_IN sagging over 50 ms, max GATE–SRC with / without a GATE→VCAP path: 16.8→14.1 V: 12.9 / **14.3 V** (CP cut-off 12.4 V typ), 14.4 / **15.8 V** (13.9 V max); 16.8→12 V: 12.9 / **15.7 V**, 14.4 / **17.2 V**.  [LM] 6.1: "GATE to SRC 0 … 15 V"; 6.5 charge-pump turn-off 11–13.9 V; 9.3.3 / 9.4 Zener text; 9.2.2.2: "maximum VGS LM74502 can drive is 13.9 V". | 13 V Zener (BZT52C13 / MMSZ5243B class, SOD-123) with cathode on PSW_G and anode on PSW_S, at the FETs.  It conducts at most the 60 µA gate current when the pump sits at its 13.9 V maximum, and clamps GATE–SRC below ~13.7 V. |
| R4A-06 | MINOR | [N] R13/R14 470k/100k; [D §3.1], §4, §9 step 1; calcs.md "Switch UVLO", "Drain with the buck off" | **The EN/UVLO sink current is left out, so the documented switch thresholds are low by 1.4 V typ (2.35 V worst).**  I(EN/UVLO) = 3 µA typ / 5 µA max flows through R13 (470 k).  Thresholds: off **7.9 V typ (5.9–9.4)**, on **8.5 V typ (6.6–9.9)**; documented as 6.5 / 7.1 V (5.9–7.0).  Effects: (a) the switch UVLO now overlaps the buck UVLO (off 7.4–10.3 V), so at a deep sag the switch may open first and the whole bus collapses (the weapon empties C1 at ~50 V/ms), rather than only the 5 V rail; (b) after the switch opens, the bus reaches UVLO sooner (benign for the re-close window); (c) §9 step 1 "FETs open near 6.5 V" will read ~7.9 V.  Whether the sink is a constant current is UNVERIFIED: it is specified only at V(EN) = 12 V, but §8.3.4 calls it an "internal sink current of 3 uA". | [LM] 6.5: "I(EN/UVLO) Enable sink current V(EN/UVLO) = 12 V … 3 typ, 5 max µA"; thresholds 1.027/1.14/1.235 V falling, 1.16/1.24/1.32 V rising.  Calculation: V = Vth × 5.7 + I × 470 k. | Either document the corrected numbers (§3.1, §4, §9, calcs, `sim_hotplug.py`) or lower the divider impedance: e.g. 200 k / 43 k keeps ~6.5 V off with ≤ 1 V of sink error. |
| R4A-07 | NOTE | `spice/sim_hotplug.py` LM74502 model | **Critique of the model; none of it changes the rev D conclusions.**  (1) VCAP is an ideal VS + 12 V source: no C12, no 162–600 µA pump limit, no VCAP UVLO.  So the T_DRV_EN delay (Eq. 1: 75 µs + 220 nF × 6.5 V / 300 µA ≈ 4.8 ms typ, ~10 ms at 162 µA / 7.5 V) is missing.  That is timing only and makes early bounce harmless.  (2) The `dgc` GATE→VCAP diode is assumed (see R4A-05).  (3) No EN sink current (R4A-06).  (4) The gate sink is active even while VS < POR.  I re-ran the closure cases with the sink gated on VS > 3.9 V: peak VM dV/dt 0.003 V/µs, ramp 2.58 V/ms, the same energies, so the Cgd kick does not turn Q7 on.  (5) The gate top is fixed at 12 V; the spec is 10.3–13.9 V.  (6) The buck is modelled at 2.5 W; the §4 budget is ~3.3 W in (2.85 W out / 0.85).  The re-run reproduces `spice/hotplug.out` line for line. | `/tmp/r4a/spice/hotplug_rerun.out` = `spice/hotplug.out`; `hotplug_nopor.out`. | Optional: add C12 with a current-limited pump and T_DRV_EN, drop `dgc` (or run both), and add the 3 µA EN sink. |
| R4A-08 | NOTE | J1.19 ESD, compute board absent | A +8 kV HBM zap (150 pF / 1.5 kΩ) on the unstacked header pin pumps W_ARM to 8–12 V for 60–170 ms.  That is above the LVC08 input abs max (6.5 V) and "arms" the gate path; a negative zap is clamped by D1.  The pin is exposed only while the stack is apart (normally unpowered).  With R4A-01's values, the zap's charge lands mostly on the 2.2 µF: ≈ 0.6 V by hand calculation (not simulated). | sim_arm.py §8: +8 kV → 11.9 V (no clamp) / 8.2 V (clamp to 3.3 V); −8 kV → 0.9 V. | None beyond R4A-01. |
| R4A-09 | NOTE | U13 UVLO turn-off under load | If UVLO ever opens the switch while current is flowing (only on a pack sagging to ~8–9 V, see R4A-06), the ~2 µs turn-off dumps the pack lead's ½LI² (150 nH, 20 A: 30 µJ) into C14 alone.  BAT_IN then rings to ≈ Voc + 24 V (≈ 36 V; ~45 V if C14 has lost half its value to DC bias).  Q7 sees V_DS ≈ 28–38 V (40 V part; avalanche-rated, µJ ≪ 370 mJ EAS) and VS stays under 65 V.  No action needed; noted because nothing else clamps BAT_IN. | ΔV = I·√(L/C); [HYG] EAS 370 mJ; [LM] VS 65 V abs max. | — |

## Answers to the scope questions

**Power switch**

* **Pins.**  [N] U13: 1 EN/UVLO = PSW_EN, 2 GND, 3 NC, 4 VCAP = PSW_CAP, 5 VS = BAT_IN, 6 GATE = PSW_G,
  7 OV = GND, 8 SRC = PSW_S.  This matches [LM] Table 5-1 and Fig. 5-1; OV "connect to ground when OV feature is not used".  Q7 D = BAT_IN, Q8 D = VBAT_SW,
  common S/G: the TI back-to-back arrangement (Fig. 9-1).
* **VCAP.**  [LM] 9.2.2.4: C_VCAP ≥ 10 × Ciss(eff).  Ciss = 4050 pF × 2 = 8.1 nF → ≥ 81 nF; 220 nF chosen (TI's own value),
  ≥ 0.1 µF ROC, 25 V vs ≤ 13.9 V.  OK.
* **Cdvdt topology.**  TI Fig. 8-2 (page 12, rendered) returns Cdvdt **to GND** through RG, and the design matches.  Derivation: once
  Q7 conducts, the output follows the gate.  The only gate capacitances that draw current are C13 (to GND) and Q7's Cgd (to BAT_IN, fixed),
  so dV/dt = I_GATE/(C13 + Cgd) ≈ 60 µA/22 nF = 2.7 V/ms (1.8–3.5 V/ms over 40–77 µA).  I = C_bus·dV/dt ≈ 380 µF × 2.7 = 1.0 A.
  The sim gives 2.67 V/ms.  Returned to SRC instead, C13 would sit in parallel with Cgs, only delay turn-on, and leave the ramp
  set by Cgd (~0.03–1.6 nF): 0.04–2 V/µs, i.e. no soft-start.
* **Vgs.**  Static ≤ 13.9 V ([LM] 9.2.2.2), under the U13 limit (15 V) and the FET limit (±20 V).  Dynamic: see R4A-05.
* **3.9 V POR.**  POR (≤ 3.9 V rising) is far below EN/UVLO (≥ 6.6 V), so it never governs.  At VS = 3.9 V, EN = 0.68 V, which
  may already exceed V(ENF) (0.32–0.94 V): the part is then in the UVLO state with the charge pump on and the gate off.  That is harmless and
  shortens T_DRV_EN on a slow bench ramp.
* **UVLO thresholds.**  See R4A-06: 7.9 / 8.5 V typ, not 6.5 / 7.1 V.
* **Gate sink on UVLO.**  2.37 A peak, 0.4–2 Ω, t_UVLO_OFF 2 µs typ.  R1 (4.7 k) keeps C13 off the gate: C13 drains
  (≤ 2.6 mA) into SRC with τ = 103 µs and lifts the FET gate only ~5 mV above SRC.  OK.
* **Reverse polarity.**  VS = −16.8 V (≥ −65 V); EN = −2.95 V (≥ V(VS), [LM] 6.1); OV = 0 V (within V(VS)…65 + V(VS));
  Q8's body diode blocks, and the INA239, TVS, C1 and R15 are all downstream.  SRC is pulled to BAT_IN + V_F(body, µA) by Q7's
  body diode, against a table limit of V(VS) + 0.3 V.  This is inherent to TI's own Fig. 9-1 topology, so it is accepted.
* **Q7 SOA.**  The ramp is a triangle: 16.4 W peak, 53 mJ, ~6.3 ms (21.5 W peak at the 77 µA maximum), with E = C·V²/2 independent of the ramp rate.
  [HYG] Fig. 3: at 16.8 V the 10 ms / DC lines sit at ≈ 4–5 A (Tc = 25 °C), against ~1 A here.  Derating
  to Tc = 100 °C ((175 − 100)/150 = 0.5) still leaves ≥ 2× margin, and a triangle is gentler than a rectangle.
  Hot-spotting (Spirito) is UNVERIFIED: Q7 runs at Vgs ≈ 2.3 V, well below its ZTC, and the Huayi SOA is calculated, not measured.
* **Load current during the ramp.**  Q7 is a source follower whose gate is set by C13, so load current raises
  Q7's Vgs slightly but cannot stall the ramp.  The DRV8316/DRV8323 start-up currents (UVLO ~4.5 V) are mA.  The buck at ~10.4 V is bounded
  by its 1.7 A output limit (≤ ~0.85 A at the input), which adds ≤ 5.4 W at V_DS 6.4 V: Q7 < 12 W there, under the 16.4 W peak.
  Nothing mid-ramp is large enough to stall it.
* **Weapon sag.**  The gate is held (C13 plus a pump that only sources); nothing droops.  The risk goes the other way (R4A-05).
* **Regen.**  The LM74502 has no reverse-current comparator and OV is grounded, so the gate stays on and regen returns to the pack
  through Q8 (D→S) and Q7 (S→D), as §8 intends.  SRC sits I·R_DS above VS (17 mV at 10 A) against a "SRC ≤ V(VS)" table
  limit.  That is inherent to the topology and accepted.
* **Switch bounce.**  Bounce in the first ~5–10 ms happens before T_DRV_EN, so the gate is not yet on: harmless.  Bounce during or after
  the ramp is the documented re-close residual (§7.2; re-run: 1.35–2.43 V/µs for 10–300 ms off).
* **Pack connected, switch open.**  BAT_IN is held by 570 kΩ + C14 and U13 is in shutdown (EN ≈ 0).  Nothing is powered except U8 from the
  balance lead.  OK.
* **Loss of VS under current.**  BAT_IN is tied to the bus through the on FETs and follows it down; U13 stays enabled until UVLO,
  then sinks the gate.  The lead-inductance energy appears across the external switch contacts, not on the board.  See R4A-09 for
  the UVLO-under-load case.

**Dynamic ARM**

* **BAT54S pinout.**  [BAT] Table 2: 1 = A1, 2 = K2, 3 = K1/A2.  [N]: 1 = GND, 2 = W_ARM, 3 = ARM_AC.  D1 clamps ARM_AC ≥ −V_F
  and D2 rectifies into W_ARM.  OK.
* **Level vs frequency and source impedance.**  sim §1 (25 °C): mean 3.106 / 3.108 / 3.108 V at 500 Hz / 1 kHz / 10 kHz with a 50 Ω source;
  3.06 V with a 1 kΩ source.  Ripple 33 / 16.5 / 1.8 mVpp.  Rise to 2.31 V in 9 µs (50 Ω) or 164–314 µs (1 kΩ).  At 85 °C: 2.99–3.25 V.
  At 125 °C it fails (0.33–3.05 V): keep D9 away from the bridge.
* **Fall times, leakage, the "130 ms" claim, false disarms, single faults.**  See R4A-01 to R4A-04.
* **Crosstalk.**  sim §7, compute board absent (only R18): a 3.3 V aggressor at 1 MHz / 400 kHz through 1 pF gives
  ≤ 52 mV on W_ARM; through 5 pF, 0.46 V; through a gross 20 pF, 1.19 V at 85 °C.  With the compute board holding the pin low: 0.31 V at 20 pF.
  The header neighbours of pin 19 are 17 (BMS_ALERT, quasi-static), 18 (NC) and 20 (GND); MB_TX (pin 5) is far away on the header.
  The §6.8 routing rule is enough as long as the trace coupling stays below a few pF.

## VERIFIED OK

* U13 pin map, OV→GND and NC per [LM] Table 5-1; back-to-back common-source arrangement per [LM] Fig. 9-1.
* C12 220 nF ≥ 10 × Ciss(Q7+Q8) and ≥ 0.1 µF; C14 100 nF ≥ 22 nF; C13 50 V (≤ ~31 V abs on PSW_DV); R1 isolation.
* Cdvdt to GND as in [LM] Fig. 8-2; ramp 2.7 V/ms (1.8–3.5), ~1.0 A inrush, E(Q7) = C·V²/2 = 53 mJ.
* Static gate drive ≤ 13.9 V vs 15 V (U13) / ±20 V (FET).
* POR below UVLO; T_DRV_EN ≈ 4.8 ms typ (Eq. 1) only delays closure.
* UVLO gate sink: 2 µs, fast thanks to R1.
* Reverse polarity: VS, EN, OV within [LM] 6.1; Q8 body diode blocks; INA239/TVS/C1 downstream.
* Q7 soft-start SOA (≥ 2× margin at Tc 100 °C by the calculated curve; Spirito UNVERIFIED).
* No load can stall the ramp; buck and driver start-up currents are small.
* Regen passes (no reverse blocking, OV grounded); weapon sag does not droop the gate.
* Early bounce is harmless; the switch-open / pack-connected state is dead; loss of VS is benign.
* `spice/sim_hotplug.py` re-run reproduces `hotplug.out` exactly; the result also holds with the gate sink off below POR.
* BAT54S pinout; ARM level ≥ 2.99 V at 500 Hz–10 kHz, 25–85 °C; ripple ≤ 33 mV; source impedance up to 1 kΩ is fine.
* Unplugged or floating W_ARM_CLK behaves like stuck low (R18).
* D1 short → permanently disarmed.  D1 open → W_ARM decays to 0.5–0.8 V even while toggling (sim §6).  C16 leaky or short → disarmed.
  D2 short or C16 open → W_ARM follows the clock (−0.08…2.92 V), so INLx is chopped only while toggling, and it falls below VIL ~1.25 s after a stuck-high stop.  None of these arms a
  static line.
* Negative ESD is clamped by D1.
* Crosstalk from adjacent 1 MHz / 400 kHz lines is negligible at ≤ 1 pF.

## Appendix: models used

* BAT54: `d(is=2e-7 n=1.0 rs=1.5 cjo=10p m=0.4 vj=0.35 eg=0.69 xti=2 bv=30 ibv=10u)`.  Fitted to [BAT] Fig. 1/2:
  V_F(1 mA) ≈ 0.22 V (≤ 0.32 V max); IR ≈ 0.2 µA at 25 °C and ≈ 26 µA at 85 °C (the curve shows ~25 µA).
* ARM netlist: source (50 Ω / 1 kΩ) → W_ARM_CLK; R18 100 k + 5 pF; C15; D1 GND→ARM_AC; D2 ARM_AC→W_ARM; C16; R41; 20 pF of inputs; an optional
  leakage current source.  "Floating" opens the source after the stop.  HBM is 150 pF at ±8 kV through 1.5 kΩ.
* Switch sag: pack source → BAT_IN (5 mΩ) with C14.  The charge pump is a 300 µA source into C12 up to 12.4 or 13.9 V, with a 5 µA sink above.  The 60 µA
  gate source is enabled by EN > 1.19 V and VCAP − VS > 6.5 V and cannot pull the gate above VCAP.  The GATE→VCAP diode is optional.  C13 through R1 to GND; the
  same VDMOS as `sim_hotplug.py`; 380 µF bus; a 20 A load while BAT_IN sags over 50 ms.

**Verdict: 0 BLOCKER, 1 MAJOR, 5 MINOR (3 NOTE).**
