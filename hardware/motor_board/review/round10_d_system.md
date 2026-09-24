# Review round 10 / D: system-level review (rev J), gate = ready for schematic capture

Reviewer role: power electronics and combat robotics, looking at the whole package fresh.  No
design file was edited.  Out of scope: board area and chassis fit, the compute board's own design
beyond §3.5, and firmware-contract detail except where the hardware makes a safety function
impossible.

Inputs: DESIGN.md rev J (read end to end), design/calcs.md, design/nets.md, design/mcu_pinmap.md,
spice/*.out, review/CHANGES.md (round 9 → rev J), review/round9_d_system.md.  Datasheets checked:
DRV8323 (SLVSDJ3D: CSA, logic inputs, sleep), HYG015N04LS1C2 (gate charge), STM32G474 (DS12288:
comparator timing, pin I/O structure), and the ST pin database in `ref/`.

Evidence tags: **[D §x]** DESIGN.md, **[C §x]** calcs.md, **[N]** nets.md, **[S …]** spice output,
**[DS …]** datasheet, **[R10 sim]** my own throw-away ngspice run with the package's
`tools/spice/ngspice_shared.py` (it re-uses the round-9 fault model; it reproduces round 9's numbers,
see the appendix; nothing was added to the package).

---

## 1. Safety-chain walk-through (rev J)

| Phase | Result |
|---|---|
| Power-on | Unchanged from rev I.  R47–R49 hold INL low, R40 holds W_EN low and R50 holds DRV_OFF high, so every enable is defined in reset.  OK |
| Arming | Unchanged; the self-test window rationale has been added (R9D-04).  OK |
| Fight, normal | Unchanged.  OK |
| Fight, weapon fault | The rev-J fast trip is wired correctly: PA0 = COMP3_INP, PA1 = COMP1_INP and PB11 = COMP6_INP, all confirmed in `ref/`.  PB11 is also ADC1_IN14, so the ADC plan still holds.  **However, the claimed ~0.5 µs Hi-Z cannot be reached with this gate driver and these FETs.**  The realistic chain takes ~0.8–0.9 µs, which leaves 9–11 V/µs at VM for a hard short (R10D-01).  The trip also covers motor over-current only on the returning phases (R10D-02) |
| Brown-out, regen disconnect | D1 is documented as the real clamp, INA239 conversions are ≤ 150 µs, and an open D1 is listed.  OK |
| Signal loss / hangs | Unchanged.  OK |
| Power-off | Unchanged: +3V3 collapse takes DRV8316 nSLEEP and U6 low, and R40 pulls W_EN low.  All bridges end off or asleep.  OK |

---

## 2. Findings

| ID | Sev | Area | Finding | Evidence / numbers | Fix |
|---|---|---|---|---|---|
| **R10D-01** | MINOR | Fight fault: the fast trip does not close R9D-01 | **§7.21 says the comparator Hi-Zs the bridge "within ~0.5 µs (sim: ≤ 3.8 V/µs at VM)".  This hardware cannot reach 0.5 µs.**  Latency budget from the start of a hard phase-to-phase short (100 nH, ~170–200 A/µs): <br>• the current reaches 30 A in ~0.18 µs; <br>• the DRV8323 CSA adds ~0.13–0.33 µs of lag (t_SET is 600 ns to 1 % at G = 20; UGB 10 MHz / noise gain ~21); <br>• the comparator, asynchronous break and U6 add ~0.05 µs (COMP t_D ≤ 31 ns); <br>• the DRV8323 input-to-gate delay t_PD is **150 ns** (typical, no maximum given); <br>• the 120 mA IDRIVE sink must pull ~35–40 nC off the gate (V_GS ~11 V down to the high-current plateau) before the current starts to fall: **~0.3 µs**, then Miller (8.5 nC, ~70 ns). <br>So the FET current starts to fall at **~0.8–0.9 µs**, not 0.5 µs.  With that chain modelled (R10 sim), VM reaches **9.0–11.2 V/µs** for a 100 nH short at 130–144 A.  It reaches 5.9–6.9 V/µs at 300 nH and 3.7–4.1 V/µs at 1 µH.  The trip therefore cuts the kick by ~3× from the 31–36 V/µs of round 9, but a weapon-lead short can still exceed the DRV8316 VM 4 V/µs absolute maximum by 2–3×.  Faults that only the VDS trip covers (phase-to-GND, 4 µs) remain at 32 V/µs.  The hardware can supply the fix cheaply: the R10 sim shows that **decoupling each DRV8316 VM feed from the bus** brings every comparator-covered case under 4 V/µs | [D §7.21] "within ~0.5 µs (sim: ≤ 3.8 V/µs at VM)"; [DS DRV8323] t_PD 150 ns, t_SET 600 ns @ G = 20, V_SLEW 10 V/µs, UGB 10 MHz; [D §3.2] IDRIVE 60/120 mA; [DS HYG015N04] Qg 59 nC @ 10 V, 27 nC @ 4.5 V, Qgd 8.5 nC; [DS G474] COMP t_D 16.7/31 ns; [R10 sim] table A.1 | (1) Correct §7.21/§8: state the realistic trip time (~0.8–1 µs from fault onset) and the kick it leaves (~9–11 V/µs for a hard short).  (2) **Before capture, evaluate a series element in each DRV8316's VM branch** (§6.6 already gives them their own branch from C1).  R10 sim with the existing 2 × 10 µF local: 0.1 Ω → **2.2 / 1.6 V/µs** (100 / 300 nH, realistic trip) and 11 V/µs for the VDS-only 4 µs case (from 32).  0.1 Ω plus 16 µF local → **1.0 / 0.8 V/µs**, 5.8 for the 4 µs case.  Cost: 0.1 V drop and ≤ 0.1–0.4 W at the drives' 1–2 A input current; one 1206/2010 resistor per drive, plus two 10 µF 1206 each for the 16 µF variant.  It needs a proper sim (drive switching ripple with R in series; stability of the local L-C-R).  The alternative with no series R is ≥ 24 µF effective local MLCC per DRV8316 (sim 3.4 / 2.6 V/µs).  (3) If neither is adopted, list "a hard weapon short can exceed the DRV8316 VM ramp limit" as an accepted residual in §7.21, with the numbers |
| R10D-02 | NOTE | Weapon over-current coverage of the fast trip (the R9D-02 band) | **Only the "returning" phases are detected.**  A positive-shunt comparator sees a phase only while current flows from the motor into that phase's low side.  With a stationary current vector (a jammed drum under FOC or a stuck observer), the returning phases carry between 0.5× and 1× of the peak phase current, depending on the angle.  A 30 A threshold therefore trips at **30–60 A peak phase current**.  At the worst angle that is the hot VDS trip level (62 A).  The limitation is documented (§8: "the other polarity relies on the FOC limit and the VDS trip").  But §3.2 (VDS row) and calcs §6 say the band from 20 A to the VDS trip is covered by "a hardware comparator trip on all three CSAs", which overstates it.  No pin can add the other polarity: PA0 is also COMP1_INM, but COMP INP must be a pin and no free pin carries a threshold.  A rotating vector (I/f start, spinning drum) does reach 30 A on every phase within one electrical cycle | [D §8] weapon fast-trip row; [D §3.2]; [C §6]; `ref/` pin DB (PA0: COMP1_INM, COMP3_INP; PA1: COMP1_INP; PB11: COMP6_INP); min over θ of max(cos θ, cos(θ ± 120°)) = 0.5 | State "30–60 A peak phase current depending on the vector angle" in §3.2/calcs §6.  Consider a ~24–25 A threshold (20 A limit + ripple; ~48–50 A worst angle) once the nuisance margin is measured (R10D-03) |
| R10D-03 | NOTE | Fight availability: nuisance trip of the required fast trip; no bring-up test | Now that the comparators are the primary weapon-fault protection, a false trip latches the weapon off ("first large trip latches, no retries").  The SOx pins have no filter [D §3.2].  The shunt ESL drives SPx to +3.2 / −1.4 V for a few ns every edge [S bridge.out, 60 mA, 3 nH], far outside the CSA's ±0.3 V differential and ±0.15 V common-mode input range [DS DRV8323 §7.5].  The output's overload recovery is unspecified.  The threshold sits 1.2 V from VREF/2, so an edge glitch is unlikely but unquantified.  **§9 has no step that proves the required trip works, measures its latency or measures its nuisance margin.**  The INA239 limits are tested by injection in step 3; the comparators are not mentioned | [D §7.21], [D §8] weapon fast-trip row; [D §9] steps 3, 6; [S bridge.out] | §9 step 6: (a) with a low DAC threshold (e.g. 5 A), check that the trip fires, and measure on a scope the time from SOx crossing to GHx/GLx falling; (b) at 20 A spin-up, raise the threshold in steps to find where nuisance trips stop, and record the margin.  Optional at capture: 0 Ω series plus a DNP 0402 C at the MCU end of W_SOA/B/C (100 Ω / 470 pF–1 nF if needed), costing ~0.1 µs.  Otherwise use COMP blanking from TIM1 OC5 around the switching edges |
| R10D-04 | NOTE | Firmware must-haves the hardware timing depends on (firmware contract) | The fast trip is only as fast as the following settings allow: <br>(a) **TIM1 OSSI = 1** so the break *drives* CHxN low.  With OSSI = 0 the pins go Hi-Z and INL falls only through R47–R49 100 kΩ × ~10–15 pF (U6 + pin + trace): **~1.4–2 µs** to the LVC08's 0.8 V V_IL.  That more than doubles the trip time. <br>(b) **BKF = 0** on BRK.  In RM0440 the pin and comparator sources are ORed before the BRK digital filter, so a filter chosen for nFAULT glitches also delays the comparators; confirm this in RM0440. <br>(c) Enable the comparator break sources only after U2 is awake.  In sleep the CSAs are disabled [DS DRV8323 §8.4.1.1], so SOx sits far below the 0.45 V threshold and holds BRK active.  The same applies around the ENABLE fault-clear pulse. <br>(d) "Latch on the first trip" needs the source identified: the break flag is shared with nFAULT/ALERT, and the comparator VALUE bit clears once the bridge is off.  Use the COMP EXTI lines. <br>(e) Use internal-only DAC channels: DAC3_CH1 for COMP1/COMP3 and DAC4_CH2 for COMP6.  The alternatives DAC1_CH1 and DAC2_CH1 have outputs on PA4 (W_VA) and PA6 (W_NTC) | [N] W_INLx_M: R47–R49 only; [DS DRV8323] INx V_IL 0.8 V, R_PD 100 k; [DS SN74LVC08A]; [D §8] DRV8323RH row "Break (MOE = 0) with OISxN = 0"; `ref/` PA4 DAC1_OUT1 | Add (a)–(e) to the §8 weapon fast-trip row |
| R10D-05 | NOTE | Stale text after the pin swap | §3.2 phase-voltage bullet: "PA4/PA5/PA2 … these TT pins".  PA2 (now W_VC) is **FT_a**; PA4 is TT_a and PB11 (now W_SOC) is TT_a [DS G474 pin table].  The swap moved the divider to a *more* tolerant pin, so this is harmless | [D §3.2]; DS12288 pin table (PA2 FT_a, PA4 TT_a, PB11 TT_a) | "PA4/PA5 (TT) and PA2 (FT)" |

---

## 3. Checked and found consistent (no finding)

* **Pin swap applied everywhere:** in [N] W_SOC = U1.33 (PB11) and W_VC = U1.14 (PA2).  The pin map
  lists PB11 COMP6_INP and PA2 ADC1_IN3.  The §3.4 ADC table (ADC1 injected PB11, regular PA2) and
  the §6.8 keep-away list both match.  PB11 is ADC1_IN14 and ADC2_IN14 per `ref/`.
* **Comparator plumbing exists on the G474:** COMP1/3/6 INMSEL can take a DAC channel.  TIM1_AF1 has
  BKCMP1E–7E, and COMP6's polarity is set in COMP_CSR (TIM1 has BKCMPxP only for COMP1–4).  With
  the trip condition "SOx < threshold", the comparator output is low on a fault, the same sense as
  the active-low nFAULT/ALERT on BKIN.
* **The DAC threshold and the CSA use the same reference:** the DRV8323 VREF = +3V3 and the G474
  VREF+ = +3V3A via R60 0 Ω.  0.45 V (30 A) sits 0.2 V above the CSA's 0.25 V linear floor, and CSA
  offset is ±4 mV × 20 = ±80 mV ≈ ±2 A.
* **ADC kickback on the shared comparator pins:** no RC on SOx.  The pins' normal range at ≤ 20 A
  is 0.85–2.45 V, so charge sharing with the ADC sample capacitor cannot reach the 0.45 V threshold,
  and the comparator hysteresis covers the rest.
* **Shunt input limits with the fast trip:** 130–145 A × 2 mΩ = 0.26–0.29 V is inside the CSA's
  ±0.3 V differential range and the ±1 V SPx/SNx absolute maximum.  Only VDS-only faults (≈ 500 A)
  reach 1 V, and those bypass or saturate the shunt path anyway (already in §7.21).
* **Power-on/off, dynamic ARM, hot-plug and brown-out:** no change since rev I, and nothing new was
  found.  Q7 avalanche, the D1 role, the open-D1 fault and the U6 stuck-high brake are all in §7.

---

## 4. Summary

| ID | Sev | One line |
|---|---|---|
| R10D-01 | MINOR | The fast trip cannot Hi-Z in ~0.5 µs.  The CSA lag, 150 ns t_PD and the 120 mA gate discharge give ~0.8–0.9 µs, which leaves 9–11 V/µs at the DRV8316 VM for a hard weapon short (sim).  A 0.1 Ω series element (± 16 µF) in each DRV8316 VM branch brings it to 1–2 V/µs (sim).  Adopt it or document the residual |
| R10D-02 | NOTE | Single-polarity comparators trip at 30–60 A peak phase current depending on the vector angle, so §3.2/calcs §6 overstate the coverage of the 20–62 A band.  Quantify it; consider a ~25 A threshold |
| R10D-03 | NOTE | Required fast trip with a first-trip latch-off: no bring-up test of its function, latency or nuisance margin, and the SOx pins are unfiltered while SPx overshoots the CSA input range each edge.  Add the §9 test; optional 0 Ω + DNP C footprints |
| R10D-04 | NOTE | §8 must require OSSI = 1 (otherwise R47–R49 add ~1.5–2 µs) and BKF = 0, comparators enabled only while U2 is awake, EXTI source identification, and internal-only DAC channels |
| R10D-05 | NOTE | §3.2 still calls PA2 a TT pin; it is FT_a (harmless) |

**Verdict: 0 BLOCKER, 0 MAJOR, 1 MINOR, 4 NOTE. Not clean.**

---

## Appendix: R10 sim (throw-away, `/tmp/r10`, not added to `spice/`)

This is the round-9 lumped fault model: 16.8 V pack, 70 mΩ / 300 nH lead, C1 330 µF with 20 mΩ ESR
and 5 nH, D1 (BV 23.3 V), 12 µF bridge MLCC behind 5 nH, HS_A and LS_B as conductances
(2.7 mΩ hot) with body diodes, a phase-to-phase short (L + 5 mΩ), a 2 mΩ shunt, and VM fed through
10 nH (‖ 2 Ω) into 8 µF (3 mΩ, 0.5 nH) + 200 nF + a 20 mA load.  The FETs turn on at 10 µs and
ramp off over 100 ns starting at t_clr.

**Check against round 9** (100 nH, t_clr 0.3 / 0.5 / 1.0 µs): 63 / 91 / 153 A and
1.4 / 3.8 / 12.6 V/µs, against round 9's 63 / 91 / 154 A and 2.0 / 3.8 / 12.7.

**A.1: realistic trip chain.**  t_clr = the time the short current, low-passed by a one-pole CSA
(τ = 130 or 330 ns), crosses 30 A, + 0.05 µs (comparator, break, U6) + 0.15 µs (t_PD) + 0.30 µs
(gate discharge to the plateau).

| Short L | CSA τ | CSA crosses 30 A | FET current starts to fall | Peak I | VM min–max | VM dV/dt (50 ns avg) |
|---|---|---|---|---|---|---|
| 100 nH | 130 ns | 0.30 µs | 0.80 µs | 130 A | 14.4–19.7 V | 9.0 V/µs |
| 100 nH | 330 ns | 0.42 µs | 0.92 µs | 144 A | 13.8–20.5 V | 11.2 V/µs |
| 300 nH | 130 ns | 0.68 µs | 1.18 µs | 66 A | 15.1–19.0 V | 5.9 V/µs |
| 300 nH | 330 ns | 0.86 µs | 1.36 µs | 75 A | 14.8–19.4 V | 6.9 V/µs |
| 1 µH | 130 ns | 1.97 µs | 2.47 µs | 41 A | 16.0–18.4 V | 3.7 V/µs |
| 1 µH | 330 ns | 2.17 µs | 2.67 µs | 44 A | 15.9–18.6 V | 4.1 V/µs |

**A.2: VM-branch mitigation.**  A series R between the plane inductance and the DRV8316's local
capacitance, and/or more local MLCC (3 mΩ) or a 47 µF polymer (30 mΩ, 3 nH).  Cases: realistic trip
(100 nH at 0.86 µs, 300 nH at 1.27 µs) and a VDS-only fault (100 nH at 4 µs).

| R series | Local MLCC | + polymer | 100 nH, 0.86 µs | 300 nH, 1.27 µs | 100 nH, 4 µs (VDS only) |
|---|---|---|---|---|---|
| 0 | 8 µF (as designed) | – | 10.1 V/µs | 6.4 | 31.8 |
| 0 | 16 µF | – | 5.3 | 3.9 | 22.2 |
| 0 | 24 µF | – | 3.4 | 2.6 | 17.1 |
| 0 | 8 µF | 47 µF | 4.8 | 3.1 | 18.9 |
| 0.1 Ω | 8 µF | – | **2.2** | **1.6** | 11.0 |
| 0.1 Ω | 16 µF | – | **1.0** | **0.8** | 5.8 |
| 0.22 Ω | 8 µF | – | 1.0 | 0.8 | 5.6 |
| 0.1 Ω | 8 µF | 47 µF | 1.5 | 0.9 | 5.5 |

Model limits: lumped; the real DRV8323 turn-off profile, FET avalanche and the drive ICs' own
switching current through the series R are not modelled.  The trip-chain delays come from typical
datasheet values: t_PD has no maximum, and the gate charge is at 10 V from the FET's typical curve.
Before a VM series element is adopted, it needs a simulation with the DRV8316's 48 kHz input
ripple (≈ 1–2 A) and a check that the local L-C-R is damped.
