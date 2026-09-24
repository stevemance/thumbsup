# Review round 9 / D: system-level review (rev I), gate = ready for schematic capture

Reviewer role: power electronics and combat robotics, looking at the whole package fresh.  No design
file was edited.  Out of scope: board area and chassis fit, the compute board's own design beyond
§3.5, and firmware-contract detail except where the hardware makes a safety function impossible.

Inputs: DESIGN.md rev I (read end to end), design/calcs.md, design/nets.md, design/bom.csv,
spice/*.out, review/CHANGES.md, review/round8_c18_sweep.md, review/round8_d_system.md.
Datasheets checked: LM74502 (SNOSDE5A), DRV8316C (SLVSH07), DRV8323 (SLVSDJ3D), and the ST pin
database in `ref/` (for comparator inputs).

Evidence tags: **[D §x]** DESIGN.md, **[C §x]** calcs.md, **[N]** nets.md, **[S …]** spice output,
**[DS …]** datasheet, **[R9 sim]** my own throw-away ngspice check using the package's
`tools/spice/ngspice_shared.py` (netlist in the appendix; nothing was added to the package).

---

## 1. Safety-chain walk-through (rev I)

| Phase | Result |
|---|---|
| Power-on | Soft-start, reverse block and UVLO are unchanged and consistent.  Every enable has a defined level in reset: R47–R49 hold INL low, R40 holds W_EN low, R50 holds DRV_OFF high.  The LM74502 pinout matches [N].  OK |
| Arming | Dynamic ARM, a qualified edge and the timed self-test.  The pass window is still 20–250 ms (R9D-04) |
| Fight, normal | Round-8 bus-ripple rule (§6.6) and §9 step 6 are in place.  OK |
| Fight, weapon fault | **New:** clearing a weapon fault dumps the fault loop's energy onto the shared bus, and the drive ICs see far more than 4 V/µs (R9D-01).  **New:** between the 20 A firmware limit and the 62–93 A VDS trip, only firmware limits phase current; the INA239 does not cover this band at low duty (R9D-02) |
| Brown-out | Documented; the 12 V fold-back is required.  OK |
| Pack disconnect during regen | BOVL is slower than the bus rises, so D1 is the real clamp and its failure is silent (R9D-03) |
| Signal loss / hangs | Heartbeat, IWDG, CLL, permission refresh and NRST pulse are all present.  OK |
| Power-off | Same as round 8: all bridges end off or asleep.  OK |

---

## 2. Findings

| ID | Sev | Area | Finding | Evidence / numbers | Fix |
|---|---|---|---|---|---|
| **R9D-01** | MINOR | Fight fault: a weapon fault propagates to both drive ICs over the shared bus | **When a weapon over-current or phase short is cleared, the bus at the DRV8316 VM pins swings at 6–36 V/µs, against the 4 V/µs absolute maximum.**  A weapon phase-to-phase short (a cut motor lead is a normal fight failure) runs for the 4 µs VDS deglitch, reaching ~180–400 A depending on the short's inductance.  During that time the bus sags through C1's ESR.  The DRV8323 then turns every weapon FET off (Hi-Z).  The current in the fault loop keeps flowing through the opposite body diodes **back into VBAT**, so the bus rebounds.  At the DRV8316 VM pins (§6.6 star feed from C1: 10 nH of plane, 2 × 10 µF ≈ 8 µF effective), the sim gives: <br>• 100 nH short, ~370 A: VM goes 7 → 29 V, **~31–36 V/µs** rising (50 ns average) and 4.6–6.4 V/µs falling during the fault. <br>• 300 nH, ~190 A: 16–20 V/µs. <br>• 1 µH, ~65 A: **5.6–7.6 V/µs**. <br>So even an ordinary VDS trip at the 62–93 A threshold exceeds the limit.  The results hold for a nominal or stiff pack, C1 ESR 20–40 mΩ and a 100–500 ns turn-off.  Doubling the plane inductance barely helps (31 V/µs).  The TIM1 break stops re-tries in hardware, but §8 lets firmware re-enable up to ~3 times a second.  VM stays below 40 V (peak 24–34 V, D1 conducting), but a weapon-side fault can plausibly damage **both** drive ICs, leaving the robot immobile.  §7.21 accepts the weapon-FET stress of a phase short but does not mention this collateral path, and §6.6 cannot fix it: the source is C1's own node | [DS DRV8316C] abs max "Power supply voltage ramp (VM) 4 V/µs"; [D §3.2] VDS 4 µs deglitch, auto-retry; [D §6.6]; [D §7.21] "~500 A before the 4 µs VDS trip"; [D §8] "~3 DRV8323 OCP retries … within a second"; [R9 sim] tables in the appendix | (1) **§7.21**: add that clearing a weapon short or VDS trip kicks the shared bus by 10–20 V at tens of V/µs, a stress on U3/U4.  (2) Make the **on-chip comparator fast trip a requirement, not an option**: COMPx → TIM1_BKIN2 at ~30 A.  The sim with the fault cleared after 0.3 / 0.5 / 1.0 µs gives 63 / 91 / 154 A and **2.0 / 3.8 / 12.7 V/µs**.  Full coverage needs the pin swap in R9D-02.  (3) §8: latch the weapon off on the **first** VDS OCP whose peak exceeded the CSA range, rather than retrying 3×.  (4) Optional, sim first: more local VM bulk per DRV8316 (sim: 50 µF + 20 nH alone gives 7.2 V/µs; combined with the fast trip it should stay under 4) |
| **R9D-02** | MINOR | Undocumented safety single point of failure: weapon phase current | **Between the 20 A limit and the 62–93 A VDS trip, only firmware limits weapon phase current.  DESIGN says the INA239 backs this up, which is wrong at low duty.**  §3.2 says "(the 20 A limit is firmware + INA239)" and calcs §6 repeats it.  The INA239 measures **pack** current, which is about I_phase² × R_loop / V_bus at stall.  With R_loop ≈ 50–95 mΩ (motor line-line, 2 FETs, shunt, leads) and a jammed or stalled drum at 45 A phase, the pack draws only **~6–11 A**.  The 38 A SOVL trips only at **~80–110 A phase**, which is above the VDS trip.  A firmware current-loop fault (a bad CSA offset after a wake, a misplaced sample, a corrupted limit) with the drum jammed, which is the usual fight situation at spin-up, therefore runs 20–60 A through the 20 A motor and the FETs.  At 60 A that is ~8.6 W of conduction per FET when hot, and only the firmware stall cut-out and TH1 stop it.  §7.21 calls the comparator option "not relied on", and PA2 (W_SOC) has no comparator input, so even the option covers only two of the three shunts | [D §3.2] strap table, VDS row; [C §6] "the 20 A limit is firmware + INA239 SOVL"; [D §8] power budget, stall cut-out; [D §7.21]; ST pin DB: PA0 = COMP3_INP, PA1 = COMP1_INP, PA2 = COMP2_INM only, **PB11 = COMP6_INP and ADC12_IN14**, PA2 = ADC1_IN3 | **Zero-cost pin swap before capture: W_SOC ↔ W_VC (PA2 ↔ PB11).**  W_SOC is only used on ADC1 (injected ranks 2–3) and PB11 is ADC1_IN14.  W_VC is only used on ADC1 (regular rank 1) and PA2 is ADC1_IN3.  The ADC plan is therefore unchanged, and all three weapon low-side CSAs get a comparator input (COMP3/COMP1/COMP6 with a DAC threshold and POLARITY as needed → TIM1_BKIN2, CPU-independent once configured).  Check that PA2 has the same tolerance class for the W_VC divider spike.  Then §8 requires the ~30 A comparator trip and §3.2/calcs §6 are corrected to "firmware + on-chip comparators; the INA239 covers pack current only".  It does not catch a phase-to-GND short that bypasses the shunts (the VDS trip remains the backstop).  Otherwise, at minimum, correct the text and list the gap in §7 |
| R9D-03 | NOTE | Pack disconnect during regen: D1 is the real clamp, and an open D1 is silent | §7.4/§8 say the INA239 BOVL (19 V) coasts the drum "within one conversion".  With the pack disconnected during a controlled 10 A regen (weapon reversal, or a loose XT30 while braking), the bus capacitance (~360 µF: C1 plus the effective MLCCs) rises at **~28 V/ms**.  At the §4b example conversion times (280 µs shunt + 280 µs bus), BOVL detection takes ~0.3–0.8 ms, which would carry the bus to **~27–41 V**.  D1 (SMBJ20A, V_BR 22.2–24.5 V) clamps it at ~26–28 V for ≤ ~0.8 ms (≈ 0.2 J, inside its rating), and the DRV8316 OVP drops the drives briefly.  So D1, not BOVL, holds the bus, and **an open D1 is an undocumented silent single fault** that takes the bus toward the DRV8316's 40 V.  The VBAT_SNS ADC is no faster: C68 gives τ = 0.87 ms | [D §7.4], [D §4b] INA239 row, [D §3.1] D1; [C §2]; [DS INA239] VBUSCT options 50 µs–4.12 ms | §8: VBUSCT/VSHCT ≤ 150 µs with AVG = 1 (detection ≤ ~0.3 ms, bus ≤ ~26 V).  §7.4: say D1 is the first clamp; add "D1 open" to §7.16.  Optional hardware: C68 100 nF → 10 nF (τ 87 µs, still ~13× attenuation of the 24 kHz ripple) plus **COMP2 on PA3 (COMP2_INP)** → TIM1_BKIN2 as a CPU-independent over-voltage trip |
| R9D-04 | NOTE | Contradiction left from round 8 | §3.5 self-test step (c) still passes "within 20–250 ms".  §1 and §9 step 3 say ~30–200 ms, and §3.2 gives ~30 ms as the worst-case pause tolerance.  R8D-06(b) was not applied (CHANGES round 8 does not list it).  A board that disarms in 20–29 ms passes the self-test but gives nuisance disarms under the allowed 20 ms gap.  Not a safety issue | [D §3.5] item 4 (c); [D §1], [D §3.2], [D §9] step 3; [S arm.out] 52–164 ms nominal | Pass window → 30–250 ms |
| R9D-05 | NOTE | Single-fault consequence misstated | §7.16: "a U6 gate stuck high → one weapon phase enabled without ARM (no torque from one phase)".  That is true at standstill.  With the drum **coasting** after a disarm, though, INL_x = 1 with INH_x low turns LS_x on, and the other phases' low-side body diodes close a half-wave short across the line-line BEMF (~14 V peak at 25.6 k rpm, 7 pole pairs ≈ 3 kHz).  The current is then limited mainly by the motor inductance: order 30–50 A peak (estimate, L_ll 10–20 µH).  That is a partial brake, which is safe (the drum stops sooner) and within the FETs' burst capability, but it is neither "no torque" nor the free coast that §7.6 relies on for stop time | [D §7.16]; [D §3.2] 3x PWM: INL = 1, INH = 0 → low side on; [D §7.6] | Reword §7.16: "…brakes a coasting drum through one low side and the body diodes (tens of A, safe direction); no drive torque" |

---

## 3. Checked and found consistent (no finding)

* **Round-8 fixes present:** C14 is 100 nF 100 V 0805 (C28233) [N, BOM].  The strap-pin voltage check
  is in §9 step 2, and the open R45/R46 cases are in §7.16.  §7.14 describes the hiccup and recommends
  the fuse.  §6.2 is a single solid L2 plane.  3.44 V/µs is used throughout.  R33 is in the header
  branch, and its < 6 % residual loading is stated in the netlist.  The 18.5 V coast comes from the
  INA239 VBUS.
* **LM74502 pinout** (DDF: 1 EN/UVLO, 2 GND, 3 NC, 4 VCAP, 5 VS, 6 GATE, 7 OV, 8 SRC) matches [N].
  The "SRC ≤ V(VS)" absolute maximum can be exceeded by one body-diode drop (Q7) after the switch
  opens with the bus up.  This is TI's own back-to-back common-source topology, so it is not a finding.
* **Small caps on switched/derived nodes vs the new transients:** C18 (16 V) sees ≤ 7.6 V at a
  58 V BAT_IN.  C10 (16 V) sees ≤ 3.7 V at the 32 V clamp.  C13 (50 V) sees ≤ ~44 V (gate =
  VBAT + 12 V at the clamp), and R1 × C13 = 100 µs keeps it from following µs spikes.  C12 sees
  ≤ 13.9 V.  OK.
* **§9 step 1 "< 60 mA" at 12 V:** the DRV8316 draws 6–10 mA in standby with its buck on (SLVSH07
  I_VMS) × 2, plus a blank MCU, the LDO, the LED, R15 and the dividers: ≈ 30–40 mA.  Consistent.
* **R50 open:** during reset DRV_OFF floats to the DRV8316's internal pull-down, so the drives
  **brake** instead of coasting until firmware drives PC14.  That is the safe direction; no finding.
* **BOM counts:** 66 lines, 192 designators, 6 DNP outside the CSV, which matches §1 and BOM.md.
* **Bus capacitor ripple** (C1 2.8 A rms rating vs ~8–9 A rms at 20 A phase, M ≈ 0.5): about
  1.3–1.6 W in C1 during 0.5 s spin-up bursts.  This is thermal-mass limited and already assessed in
  round 8 at 5.7 A rms while grinding.  OK for bursts; the stall cut-out bounds grinding.

---

## 4. Summary

| ID | Sev | One line |
|---|---|---|
| R9D-01 | MINOR | Clearing a weapon short or VDS trip drives the DRV8316 VM at 6–36 V/µs (sim) vs the 4 V/µs abs max, so a weapon-lead fault can take out both drives.  Document it in §7.21, require a ≤ 0.5 µs comparator trip (sim: ≤ 3.8 V/µs), and latch off on the first big OCP |
| R9D-02 | MINOR | The INA239 does not back up the 20 A weapon limit at low duty (SOVL ≈ 80–110 A phase at stall), so 20–62 A is firmware-only.  Swap PA2 ↔ PB11 (W_SOC ↔ W_VC; ADC plan unchanged) so all three CSAs get comparators, require the trip, and fix §3.2/calcs §6 |
| R9D-03 | NOTE | During regen with the pack disconnected, BOVL latency lets the bus rise to D1 (~26–28 V).  D1 is the real clamp and its open failure is silent.  Use a short INA239 conversion time; optionally C68 → 10 nF with COMP2 on PA3 |
| R9D-04 | NOTE | Self-test pass window is still 20–250 ms; the design value is 30–250 ms (R8D-06b not applied) |
| R9D-05 | NOTE | §7.16: U6 stuck high brakes a coasting drum through body diodes (safe), it is not "no torque" |

**Verdict: 0 BLOCKER, 0 MAJOR, 2 MINOR, 3 NOTE. Not clean.**

---

## Appendix: R9 sim (throw-away, `/tmp`, not added to `spice/`)

```
vpack p0 0 16.8 ; rpack p0 p1 {0.07|0.02} ; lpack p1 p2 {300n|50n} ; rsw p2 c1 5m
lc1 c1 c1a 5n ; rc1 c1a c1b {20m|40m} ; cc1 c1b 0 330u            (C1)
dtvs 0 c1 (bv 23.3, rs 0.5)                                        (D1)
lb c1 br 5n || 2 ohm ; cm br - 12u, 1 mOhm, 0.3 nH                  (bridge MLCCs)
HS_A br->a, LS_B b->s as ramped conductances (2.7 mOhm hot RDS + 2 mOhm shunt), on at 10 us,
  off after the deglitch {4 us | 0.3–1 us} with a {100 | 500} ns ramp; body diodes on all four
  FETs involved (LS_A 0->a, HS_B b->br, ...); short a->b: {100n|300n|1u} + 5 mOhm
l2 c1 vm {10n|20n} || 2 ohm ; cd vm - {8u|24u|50u}, 3 mOhm, 0.5 nH ; cdh vm 0 200n ; 20 mA load
```

| Short L | C1 ESR | Pack | Peak I | VM min–max | VM rise after clear (V/µs, 50 ns avg) |
|---|---|---|---|---|---|
| 100 nH | 20 mΩ | nominal | 370 A | 7.3–29.1 V | 31–32 |
| 100 nH | 40 mΩ | stiff | 365–374 A | 9.4–34.0 V | 35–36 |
| 300 nH | 20–40 mΩ | both | 173–200 A | 10.6–26.8 V | 16–20 |
| 1 µH | 20–40 mΩ | both | 63–70 A | 14.5–20.5 V | 5.6–7.6 |
| 100 nH, fault cleared after 0.3 / 0.5 / 1.0 µs | 20 mΩ | nominal | 63 / 91 / 154 A | – | 2.0 / 3.8 / 12.7 |
| 100 nH, 20 nH plane + 50 µF local | 20 mΩ | nominal | 409 A | 9.2–17.9 V | 7.2 |

Model limits: lumped; FET avalanche and the real DRV8323 turn-off profile are not modelled; one
bridge-node sample at the turn-off instant is a numerical glitch and is ignored (VM is continuous
through it).  The conclusion (well above 4 V/µs unless the fault is cleared within ~0.5 µs) is
insensitive to the plane inductance, the pack model and C1 ESR over the ranges shown.
