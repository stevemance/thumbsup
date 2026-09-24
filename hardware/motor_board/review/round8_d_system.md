# Review round 8 / D: system-level review (rev H), gate = ready for schematic capture

Reviewer role: power electronics and combat robotics, looking at the whole package fresh.  No design
file was edited.  Out of scope: board area and chassis fit, the compute board's own design, and
firmware-contract detail except where the hardware makes a safety function impossible.

Inputs: DESIGN.md rev H (read end to end), design/calcs.md, design/nets.md, design/bom.csv,
spice/*.out and the models `sim_hotplug.py`, `sim_arm.py` and `sim_weapon_bridge.py`,
review/CHANGES.md, review/round7_d_system.md.  Datasheets checked: LM74502 (SNOSDE5A), DRV8323
(SLVSDJ3D), DRV8316C (SLVSH07), LMR16006 (SNVSA24), HYG015N04LS1C2.

Evidence tags: **[D §x]** DESIGN.md, **[C §x]** calcs.md, **[N]** nets.md, **[B]** bom.csv,
**[S …]** spice output or model, **[DS …]** datasheet, **[R8 sim]** my own throw-away ngspice
check (netlist in the appendix; not added to the package).

---

## 1. Safety-chain walk-through (rev H)

| Phase | Result |
|---|---|
| Power-on | Soft-start, and the MCU stays in reset until the buck is up.  R47–R49 hold INL low, R40 holds W_EN low (sleep), R50 holds DRV_OFF high.  The DRV8316 nSLEEP, INL and DRVOFF all come from +3V3, so they rise together, and t_WAKE (1 ms) is over by the time DRVOFF is high.  OK |
| Arming | ≥ 7 software edges, a qualified rising edge and the boot self-test.  OK |
| Fight | See the new items R8D-01 (weapon ripple on the DRV8316 VM) and R8D-02 (switch opening under load) |
| Brown-out | The switch UVLO and the logic cutoff are documented and the 12 V fold-back is a requirement.  Opening the switch under load is not analysed (R8D-02) |
| Signal loss / hangs | Compute-board and motor-MCU hangs are covered (heartbeat, IWDG, CLL, permission refresh).  OK |
| Faults | nFAULT/ALERT reach the break inputs.  Two more silent strap faults exist (R8D-03) |
| Power-off | If +3V3 collapses first, it takes nSLEEP (DRV8316), U6/U14 (INL, then the DRV8323 internal pull-downs) and the MCU down with it, so every bridge ends up off or asleep.  OK |
| Cross-board | A default pin state on the compute board shifts the motor MCU's bus-voltage reading (R8D-04) |

---

## 2. Findings

| ID | Sev | Area | Finding | Evidence / numbers | Fix |
|---|---|---|---|---|---|
| **R8D-01** | MINOR | Fight: shared bus, DRV8316 VM ramp limit | **Nobody has assessed what the weapon's switching does to the DRV8316 VM pins.**  The package checks the DRV8316's 4 V/µs "power supply voltage ramp (VM)" absolute maximum only for power-switch closure (≤ 0.01 V/µs).  But the drive ICs share VBAT with a 20 A hard-switched bridge at 24 kHz.  `sim_weapon_bridge.py` models VBAT as an ideal source, so it cannot show bus ringing.  I modelled the bus as: pack + 300 nH lead → C1 (330 µF, 20 mΩ, 5 nH) → plane L1 → bridge MLCCs (3 × 10 µF ≈ 12 µF effective) → plane L2 → the DRV8316 decoupling (2 × 10 µF ≈ 8 µF + 2 × 100 nF).  The bridge draws 0↔20 A pulses with 71–142 ns edges.  **Without reverse recovery the ripple is 0.75 V p-p and 1.2–1.3 V/µs.  With a 10 A / 20 ns body-diode recovery spike, the 1 ns derivative reaches 3.7–4.0 V/µs when the drive IC sits close to the bridge (3 nH + 5 nH), and 2.1–2.4 V/µs at 5 nH + 10 nH.**  A cold C1 (300 mΩ) gives about 3 V p-p on the bus.  The model is crude (a lumped current source, and the recovery charge is a guess), but in the tight-layout case the margin to an absolute maximum is somewhere between 0 and 3×, and it is hit 48 000 times a second | [DS DRV8316C] abs max "Power supply voltage ramp (VM) 4 V/µs"; [S sim_weapon_bridge.py] `vbat vb 0 16.8` (ideal); [D §6.1, §6.6]; [C §7] "≤ 0.01 V/µs" covers closure only; [R8 sim] | **§6: new layout rule.**  Feed U3/U4 VM from C1 on their own branch (a star at C1), not from the weapon bridge's pour or its MLCC node, and keep ≥ ~10 nH of plane between the bridge caps and the drive ICs; C1 stays close to both.  **§9 step 6:** at 20 A weapon current, scope U3/U4 VM (short ground spring, ≥ 200 MHz bandwidth) and confirm the edge rate is < ~2 V/µs.  Optional: a third 10 µF per drive IC (C_VM) if the measurement is marginal |
| **R8D-02** | MINOR | Power-off under load, unprotected node | **When the switch opens under load, the lead's energy lands on BAT_IN, and nothing is sized or clamped for it.**  The switch UVLO is designed to trip under load: a tired pack under 20–30 A ([D §8] power budget, [D §3.1] R13/R14).  U13 then sinks the gate at 2.4 A and opens Q7/Q8 within ~2 µs (t_UVLO_OFF).  The pack + lead inductance (100–300 nH) keeps driving current into BAT_IN, where the only parts are C14 (100 nF **50 V** 0603) and U13's VS pin.  C14 absorbs ½LI²: at 22 A and 300 nH (73 µJ) BAT_IN peaks at ~39 V; at 30 A and 300 nH (135 µJ), ~53 V.  After that, Q7 avalanches (BV ≥ 40 V, ~44–48 V hot) into C1 through Q8's body diode, which clamps BAT_IN at about VBAT + BV + 0.8 V ≈ **55–60 V**.  That is over C14's rating, at U13's 60 V recommended maximum, and 5–10 V under its 65 V absolute maximum.  The same happens when the UVLO interrupts a hard VBAT short (it does, ~1–2 ms after C18): at ~200 A, ½LI² ≈ 6 mJ goes into Q7 avalanche (EAS 370 mJ, so the FET is fine) and BAT_IN ≈ 45 V.  **C14 is also the one ceramic on the unswitched node.**  A flex crack in it shorts the pack through the leads, and only the external switch can stop that (every MLCC on VBAT is at least cut off by the UVLO).  §6.10's crack rule covers 1206/2512 parts only | [N] BAT_IN = C14, U13.VS, Q7.D, R13; [B] C14 100 nF 50 V 0603 C14663; [DS LM74502] VS abs max 65 V, recommended ≤ 60 V, t_UVLO_OFF 2 µs, 2.4 A sink; [DS HYG015N04LS1C2] BVDSS ≥ 40 V, EAS 370 mJ; [D §6.10] | C14 → **100 nF 100 V** (0805 or 1206 X7R, soft-termination if stocked), placed parallel to the board edge and away from the holes per §6.10.  §3.1: note that switch opening under load avalanches Q7 (by design) and that BAT_IN reaches ~VBAT + 45 V.  Optional: a bidirectional TVS (SMBJ26CA class) on BAT_IN.  It must be bidirectional because of the reversed pack, and it adds another unprotected part that fails short, so the 100 V capacitor is the better cheap fix |
| **R8D-03** | MINOR | Undocumented single points of failure (DRV8323 straps) | **Two more strap opens silently remove weapon protection, and nothing checks the strap levels.**  §7.16 lists MODE (R44) and GAIN only.  **R46 (VDS) open** → Hi-Z = **0.6 V** VDS trip → 250–430 A at 1.4–2.4 mΩ.  That removes the only hardware shoot-through / hard-short backstop, which is designed for 62–93 A.  The FETs' IDM is 600 A, so a shoot-through then runs for the full 4 µs deglitch near IDM, on every 4 ms retry.  **R45 (IDRIVE) open** → Hi-Z = **120 / 240 mA**.  The bridge sim at 150 mA with a 6 nH loop gives **VDS 39.3 V (40 V part) and SH −9.2 V (limit −7 V)**, which slowly overstresses the driver and FETs.  Neither fault can be seen in operation.  R7D-06 proposed measuring the strap pin voltages at bring-up; §9 does not include it | [DS DRV8323] 7-level table: Hi-Z → IDRIVE 120/240 mA, VDS 0.6 V; strap voltages 18 k→AGND 0.5 V, 75 k→AGND 1.1 V, Hi-Z 1.65 V; [S bridge.out] 150 mA / 6 nH row; [D §3.2] straps; [D §7.16] | §7.16: add R45 and R46 opens.  **§9 step 0/2:** with W_EN high, measure the pins against the datasheet levels: IDRIVE ≈ 1.1 V, VDS ≈ 0.5 V, MODE ≈ 1.2 V, GAIN ≈ 2 V (Hi-Z).  Repeat after any repair near U2 |
| **R8D-04** | MINOR | Cross-board: a protection input depends on the compute board's pin state | **VBAT_SNS goes to the header unbuffered, so the compute board's pin loads the node the motor MCU uses for protection.**  R63/R64 (68 k / 10 k, 8.7 kΩ source) feed both PA3 and J1 pin 11 with no series resistor.  Every RP2040 GPIO resets with its ~50–80 kΩ pull-down **enabled**; it stays on until the compute firmware calls `adc_gpio_init`, and whenever the Pico resets or reboots.  That makes the motor MCU read **10–15 % low**: 16.8 V reads as ~14.4–15.2 V.  So the firmware **18.5 V coast** [D §8 weapon safety] really fires at **~20.6–21.7 V**.  That is above the DRV8316's OVP minimum (20 V) and at the SMBJ20A's standoff.  The 12 V fold-back acts at ~13.5–14 V real (lost performance), and FOC voltage compensation is wrong.  If the compute board is unpowered (its diode or regulator has failed), its ESD clamp pulls the node to ≤ ~0.5 V.  The INA239 BOVL (19 V, measured directly) still protects in hardware, so this is not a BLOCKER | [N] VBAT_SNS = R63.2, R64.1, C68, J1.11, U1.17 (PA3); [D §3.4], [D §3.5] pin 11 "÷7.8"; [D §8] "coast if VBAT_SNS > 18.5 V"; RP2040 datasheet PADS_BANK0 PDE reset = 1 | Add a series resistor (e.g. 10–47 kΩ) in the J1 pin 11 branch, after C68, so the header side cannot load PA3.  The compute board then reads through it into its own high-impedance ADC; the error from a 50 k pull-down through 47 k is ~0.5 %.  §3.5: J1.11 is an ADC input with pulls disabled.  §8: take the 18.5 V coast from the INA239 VBUS (or cross-check VBAT_SNS against it and trust the higher value) |
| R8D-05 | NOTE | Accepted residual §7.14 misdescribed | §7.14 says a hard VBAT short is "limited only by the pack, leads and FETs".  In fact the switch UVLO opens it ~1–2 ms after the bus collapses (C18), and then **retries**.  EN recovers with BAT_IN, and the soft-start ramps Q7's gate into the short.  Q7 then conducts ~100 A at ~9–10 V VDS (~1 kW) for ~1 ms until the UVLO trips again, every few ms.  That is outside a PDFN 5×6's 1 ms SOA when hot, so Q7 will probably fail **short**.  After that, forward current flows through Q8's body diode whatever its gate does, and the pack dumps into the short.  The conclusion (a fuse is the only real protection) is unchanged | [DS LM74502] EN hysteresis, ENTDLY 75 µs; [D §3.1] C13/R1/D10; [D §7.14] | Rewrite §7.14 to describe the hiccup and the likely Q7 short, and recommend the inline fuse for fight builds rather than calling it optional |
| R8D-06 | NOTE | Contradictions left after round 7 | (a) §7.2 still gives the worst re-close as "3.3 V/µs"; §3.1 R15, §5 and hotplug.out give **3.44 V/µs**, and §7.5 gives ≤ 3.4.  (b) Self-test step (c) in §3.5 passes "20–250 ms", while §1 and §9 step 3 say ~30–200 ms and §3.2 gives ~30 ms as the worst-case pause tolerance.  A board that disarms at 20–29 ms passes the self-test but has no margin for the 20 ms gap the compute board is allowed.  The only effect is nuisance disarms, so this is not a safety issue (R7D-05 was only partly applied).  (c) §6.2 says "join analog/logic ground to power ground at one place near C1", but §6.2 also calls for a solid L2 GND plane and §3.3/§6.5 join each DRV8316's AGND island at its own pad.  One GND net cannot show a single-point join, so pick one strategy before layout (and add net-ties if it is the single point) | [D §3.1, §5, §7.2, §7.5]; [S hotplug.out] 3.444 V/µs; [D §1, §3.2, §3.5, §9]; [D §3.3, §6.2, §6.5] | (a) → 3.44 V/µs.  (b) Pass window → 30–250 ms.  (c) Say "solid L2 plane; each IC's analog island joins at its own pad; the power-return region is kept out from under the MCU/CSA/header" and drop "one place near C1" |
| R8D-07 | NOTE | Bring-up hold-up interaction | The compute board's 470 µF (§3.5, added in rev H) plus C29/C30 charges from the buck at its cycle-by-cycle limit (1.2 A typ; LMR16006 has no hiccup, so it still starts): ~3–4 ms at ~0.7 A net.  During the soft-start this adds ~0.7 A of Q7 current from 10.4 V upward, which `sim_hotplug.py` does not model (constant 2.5 W).  My estimate is ≤ ~10 mJ and < 10 W extra in Q7, inside the stated ≥ 2× SOA margin.  §9 step 1 says 1.5 A for the first closure, which is enough with the compute board attached, but the 0.2 A setting afterwards will not start the stack | [DS LMR16006] §8.3.5 (cycle-by-cycle limit, no hiccup); [S sim_hotplug.py] `bbuck … 2.5 /`; [D §3.5] item 4, [D §9] step 1 | §9 step 1: keep ≥ 1.5 A whenever the compute board is attached |

---

## 3. Checked and found consistent (no finding)

* **Reverse pack**: EN/UVLO and OV stay within V(VS) to 65 + V(VS) (R13/R14 divide BAT_IN to GND,
  and OV sits at GND, 16.8 V above VS).  SRC ≤ VS holds.  The INA239 is behind Q8.
* **D4 vs the charge pump**: VCAP − VS regulates between 10.3 and 13.9 V, so D4 (11.4–12.6 V) can
  conduct.  Its current is limited by the 40–77 µA gate source, which is below the ≥ 162 µA
  charge-pump capability.  C12 (25 V) sees ≤ 13.9 V.
* **Unpowered-MCU back-feed**: R_nFAULT goes to PC15, which is not FT, through R401 from
  R_AVDD.  That is ≤ 0.27 mA, and only while the DRV8316 is awake, which needs nSLEEP = +3V3.
  Negligible.
* **+3V3 lost with VM up** (LDO failure): DRV8316 nSLEEP low puts it to sleep, the DRV8323 INL
  internal pull-downs and W_EN pull-down put it into Hi-Z and sleep, and the drives coast.  Fail-safe.
* **DRV8316 reset mid-run** (6x default with INL = 1): INH = 0 gives a low-side brake and INH = 1
  gives Hi-Z, so the worst case is a brief brake until the 100 Hz read-back.  The MCU always
  resets before the DRV8316's VM UVLO (buck cutoff 9.2 V vs ~4.5 V), so it cannot happen from
  a sag.
* **Coupling into W_ARM_CLK** from a 16.8 V phase edge through ~1 pF: ~17 pC per edge × 48 k/s
  gives ≈ 0.8 µA into R41, i.e. ≈ 40 mV on W_ARM.  It cannot arm.
* **D9 single faults** (either diode short or open), C16 open, and R42 open all fail safe.  With
  R42 open, the open-drain faults still pull the break input low; only the release fails.
* **Pack-current thermal** in Q7/Q8/RS4 for a realistic grinding load (~20 A pack): ~2 W in the
  pair.  C1 ripple while grinding at 20 A phase and M ≈ 0.9 is ~5.7 A rms, about 0.65 W, which
  is tolerable for seconds.
* §5 against spice/*.out: hotplug, arm, bridge and spin-up figures match (except R8D-06a).
  §1 counts match bom.csv: 65 lines, 191 parts.

---

## 4. Summary

| ID | Sev | One line |
|---|---|---|
| R8D-01 | MINOR | Weapon switching ripple on the shared bus was never checked against the DRV8316's 4 V/µs VM limit; a rough sim gives 1.2–1.3 V/µs steady and up to ~4 V/µs recovery spikes in a tight layout.  Add a star-feed layout rule and a §9 VM scope check |
| R8D-02 | MINOR | The switch opening under load (the designed UVLO trip, or a bus short) kicks BAT_IN to ~40–60 V: over C14's 50 V rating and at U13's 60 V recommended maximum, and C14 is an unprotected pack-short part.  Use a 100 V C14 and document the Q7 avalanche |
| R8D-03 | MINOR | An open R46 (VDS OCP → 250–430 A) or R45 (IDRIVE → 120/240 mA, 39 V VDS / −9 V SH) is silent and undocumented.  Add both to §7.16 and measure the strap pin voltages in §9 |
| R8D-04 | MINOR | VBAT_SNS goes to the compute board unbuffered; the RP2040's default pull-down makes the motor MCU read 10–15 % low, so the 18.5 V firmware coast moves to ~21 V.  Add a series resistor on the header branch and/or use the INA239 VBUS |
| R8D-05 | NOTE | §7.14: the UVLO does interrupt a hard short, then hiccups Q7 through its linear region and probably fails it short.  Recommend the fuse |
| R8D-06 | NOTE | Stale 3.3 vs 3.44 V/µs; self-test window 20–250 vs 30–200 ms; grounding strategy stated two ways |
| R8D-07 | NOTE | The compute board's 470 µF is not in the hot-plug load model (small effect); keep the bench limit ≥ 1.5 A with the stack attached |

**Verdict: 0 BLOCKER, 0 MAJOR, 4 MINOR, 3 NOTE. Not clean.**

---

## Appendix: R8D-01 bus-ripple check (throw-away, not added to `spice/`)

```
vpack p0 0 16.8 ; rpack p0 p1 0.07 ; lpack p1 p2 300n ; rsw p2 vb1 0.005
c1 vb1 - 330u, ESR 20 mOhm, ESL 5 nH            (C1)
l1 vb1 vbr {3|5|10} nH (2 ohm damping)           (plane C1 -> bridge)
cm vbr - 12u, 1 mOhm, 0.3 nH                      (C25/C26/C31 effective)
ib vbr 0 pulse(0 20A, tr 71|142 ns, 50 % duty, 24 kHz)
irr vbr 0 pulse(0 {0|10} A, 20 ns)                (body-diode recovery)
l2 vbr vm {5|10|20} nH (2 ohm damping)           (plane bridge -> DRV8316)
cd vm - 8u, 3 mOhm, 0.5 nH ; cdh vm 0 200n        (C302/C308 effective, C300/C301)
```
Results: without recovery, 1.2–1.3 V/µs, 0.74 V p-p.  With 10 A recovery (1 ns derivative):
3.7–4.0 V/µs at 3 + 5 nH, 2.1–2.4 V/µs at 5 + 10 nH, and 1.4–1.6 V/µs at 10 + 20 nH.
Averaged over 20 ns: 3.1–3.2 / 1.8 V/µs.  C1 at 300 mΩ gives 2.9–3.2 V p-p.
