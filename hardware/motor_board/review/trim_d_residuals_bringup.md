# Trim D: residual risks (§7), bring-up (§9), §1/§5 wording

Scope: DESIGN.md §7 items touched in rounds 12–30 (7.2, 7.4, 7.5, 7.6, 7.16, 7.17, 7.18, 7.21), all
of §9 (steps 0–6), and the §1 and §5 sentences those rounds touched.  The hardware has not changed
since round 11, so every change here is to text.

**How I judged each item.**
* **KEEP** anything a builder checks on the bench: rails, straps, safety paths, ARM timing, the fast
  trip, the VM filter and R302, regen and over-voltage, switch-open, contact bounce, wiring and
  direction after pit repairs, and the calibrations the firmware cannot run without (idle current,
  CCR6, Z offset, λ, the row 5 reference, coast-down and safe-resume speed).
* **CUT** tests that only exercise one branch of a firmware rule (deaf chip, latch persistence
  across resets, alignment-shove handling, open-switch-while-braking-with-stick-held, and so on).
  They belong in a firmware test plan once firmware exists.  **SIMPLIFY** means merging duplicates
  and shortening wording.
* **Step numbers 0–6 are kept**, and so is what each step contains, because §7/§8 cite them:
  step 0 (R302), step 2 (straps, nFAULT/CLR_FLT bench check, "no motors"), step 4 (idle current,
  t_split), step 5 (Z offset, Z pulse width, λ), step 6 (row 5 reference, coast-down, safe-resume
  speed, top-speed resume, DRV8316 VM scope).

**Numbers checked against sources.**
* `spice/hotplug.out`:
  * closure 0.002–0.005 V/µs and 1.28–2.95 V/ms;
  * Q7 16.5/22.0 W, 53.8–56.9 mJ;
  * reversed pack 13.1 / 102–147 A;
  * re-close 0.059–0.664 and 1.83–2.09 V/µs;
  * bounce 0.80–2.26 V/µs (0 °C), 2.66 V/µs (−40 °C).
* The 2.33 / 2.82 V/µs figures for bounces up to ~1.3 ms are **not** in `hotplug.out`.  They come
  from the round 27 extra runs, reproduced in round28_a (table at l.56–59), and are labelled that
  way below.
* `spice/arm.out`: 12.0–12.1 ms / 7 edges to arm at 500 Hz; disarm 52–134 ms stuck low, 67–164 ms
  stuck high.
* 74LVC1G17 VT+ ≤ 2.00 V at 3 V.
* DRV8323 four-level inputs 0 / 1.2 V (45–47 k) / 2 V Hi-Z; seven-level inputs 0.5 V (18 k),
  1.1 V (75 k), 1.65 V Hi-Z (SLVSDJ3D EC table, Fig. 8-23/8-24); t_RETRY 4 ms typ only.
* SMBJ20A: VBR 22.2–24.5 V, VC 32.4 V at 18.6 A.  A linear clamp model gives 28.7 V at 10 A, so the
  68 k/10 k sense pins read 3.69 V (3.75 V with 1 % resistors).
* AP2112K ±1.5 %, so VDD = 3.25–3.35 V.
* **STM32 (DS12288 Rev 4):**
  * TT_xx input abs max 4.0 V (Table 14);
  * operating VIN on TT_xx is −0.3 … **VDD + 0.3 V** (Table 17 "General operating conditions"),
    i.e. 3.55–3.65 V here;
  * injected current on TT_xx is −5/**0** mA, and note 3 says positive injection is not possible
    (Table 15; Table 53: TT_a positive injection 0);
  * PA3, PA4, PA5 are all TT_a.

**Two errors found in the current text.**
* **§9 step 4 "a bench-supply dip below ~5 V" to measure a U2 UVLO cannot work on this board.**
  The switch UVLO opens Q7/Q8 near 9 V (≤ 10.1 V) and the buck UVLO drops the logic at 9.2–10.3 V,
  both long before VM reaches U2's own UVLO.  Cut.  Use the W_EN-wake nFAULT time instead (it is
  the §8.1 row 7 case).
* **"PA3–PA5 at ~3.7 V" is only compared with the 4.0 V abs max.**  3.7 V is **above** the
  VDD + 0.3 V operating limit (3.55–3.65 V).  It is acceptable (transient, no injection path), but
  the text must say so (new §7.4 text).  Also, §9 step 6 says "PA3–PA5 reach 4.0 V at ~12–14 A".
  The linear clamp model gives 4.0 V at ~14.5 A (1 % dividers, VBR max) to ~16 A (nominal).
  Replaced by "≥ ~14 A".

---

## 1. Disposition table

### §1 and §5

| Item | Verdict | Reason |
|---|---|---|
| §1 Environment row (≤ 2.75 V/µs, 2.82 at −40 °C, round 28) | SIMPLIFY | One figure per temperature case, with its source.  2.75 is a leftover of the pre-round-27 wording |
| §1 Battery, Safety rows | KEEP | They match hotplug.out / arm.out (0.005 V/µs, 52–164 ms) |
| §5 power-switch-closure row | SIMPLIFY | Correct but run-on.  Split it into closure / reversed / re-close / bounce, and label the ~1.3 ms figures as reruns that are not in the file |
| §5 ARM row | KEEP | Matches arm.out |

### §7 residual risks

| Item | Verdict | Reason |
|---|---|---|
| §7.2 re-close / loaded bounce | SIMPLIFY | Keep the physics and the limit margins.  Drop the nested round-27 parentheses (the numbers stay, once) |
| §7.4 regen with pack disconnected | SIMPLIFY + FIX | Add the TT_a fact: inside the 4.0 V abs max, above the VDD + 0.3 V operating limit, no injection path, transient; say why that is accepted |
| §7.5 switch vs coasting drum | SIMPLIFY | Keep the powered-by-drum warning and the bounded re-close; point to §8.1 row 0 instead of restating it |
| §7.6 free coast after disarm | KEEP (minor wording) | A real inspection item, measured in §9 step 6 |
| §7.16 silent single faults | SIMPLIFY | Keep every fault; turn the run-on into a list; cut the boot-test description down to what the reader needs (the §8 boot order and §8.1 row 11 cite it) |
| §7.17 board is not pack protection | KEEP | Real; idle 95–113 mA matches calcs |
| §7.18 LiHV | SIMPLIFY | One sentence |
| §7.21 phase short / fast trip | SIMPLIFY + FIX | Point the latch rules to §8.1 instead of restating them.  **State plainly** that the phase-to-ground residual (~7–8 V/µs) exceeds the DRV8316 4 V/µs abs max; the current text only calls it "a damaged-harness event" |

### §9 bring-up

**Step 0**

| Item | Verdict | Reason |
|---|---|---|
| Stake C1/L1/J2/J3; J1 pin-1 mirror; DNP set; inspect bottom; weigh | KEEP | Build checks |
| R302/R402 1 A force / 4-wire | KEEP, SIMPLIFY | The only way to see a shorted filter resistor.  Shorter wording |

**Step 1**

| Item | Verdict | Reason |
|---|---|---|
| Bench supply, 1.5 A first closure, rails, LED, < 60 mA | KEEP | Basic power-up |
| Reverse polarity as a step | KEEP | Checks the D10 / soft-start protection |
| UVLO sweep (9.2 / 10.4 / ~9 V) | KEEP | Hardware thresholds |
| Scope VBAT + VM ramp 8–13 ms | KEEP | Confirms the soft-start sim |

**Step 2**

| Item | Verdict | Reason |
|---|---|---|
| SWD, device ID/UID/rev, BOR | KEEP | Counterfeit / errata check (§7.12) |
| U2 strap voltages | KEEP, SIMPLIFY | Datasheet levels; the only way to find the §7.16 strap faults |
| DRV8316 write + read-back, BUCK_UV, NPOR, AVDD | KEEP | Hardware bring-up of the SPI and the chips |
| nFAULT after lowering DRV_OFF with the chip coasted (decides the optional CLR_FLT) | KEEP, SIMPLIFY | The register map does not document this chip behaviour, and §8.1 depends on it |
| "Alignment reports no motion — expected" aside | CUT | Noise |
| INA239 ID/V/I vs supply | KEEP | |
| Sensor VS short → +3V3/nSLEEP stay up | KEEP | Hardware protection check (TPS22945) |
| Cell voltages vs meter | KEEP | |

**Step 3**

| Item | Verdict | Reason |
|---|---|---|
| ARM rise ≤ 15 ms at 500 Hz; single edge does not arm; stuck high/low/unplugged → 30–200 ms, warm | KEEP | Core hardware interlock (sim 12 ms, 52–164 ms) |
| Halt the compute board → W_ARM_S falls; boot self-test passes | KEEP | Dynamic-ARM purpose |
| Weapon Hi-Z with W_ARM low and TIM1 running | KEEP | The AND gate |
| MCU reset with ARM high → no restart | KEEP | Safety rule, cheap |
| Transmitter off → stop | KEEP, merged | Merged with "stop command frames" (same failsafe, two layers) |
| SOVL/BOVL trip the break | KEEP | Hardware path |
| 10 min armed soak, zero "W_ARM_S fell" | KEEP | Real RF/noise test |

**Step 4**

| Item | Verdict | Reason |
|---|---|---|
| Idle current (row 0 term) | KEEP, SIMPLIFY | Needed calibration.  Drop the "band ≤ half" rule-tuning sentence; add "compute board attached" (RS4 sees its load) |
| Charge pumps | KEEP | |
| Fast trip scope ≤ ~1 µs, locked rotor; no false trip at 20 A on a pack | KEEP | Required protection (§7.21) |
| t_split via "bench-supply dip below ~5 V" (U2 UVLO) | CUT | **Physically impossible here**: the switch UVLO (~9 V) and the buck UVLO (9.2 V) act first |
| t_split via a "lowered VDS trip or brief phase short" VDS OCP | SIMPLIFY | Deliberately provoking a 62–93 A VDS OCP is risky and needs a strap change.  Use the W_EN wake time (easy, ~1 ms) and the datasheet 4 ms t_RETRY; confirm t_RETRY from any VDS OCP logged later |

**Step 5**

| Item | Verdict | Reason |
|---|---|---|
| MT6701 off-board programming (incl. Z width 1 LSB, power-up train off) | KEEP | Needed; §8 cites it |
| CCR6 trim | KEEP | Needed calibration |
| Duty 0–10 % delay-comp check | KEEP | Cheap scope check of a chip feature |
| Open-loop: direction, pole pairs, CSA offsets | KEEP | |
| Z offset (spread < 5°) | KEEP | Needed calibration |
| λ measurement | KEEP | Needed for the resume preset |
| Current sampling at the duty cap | KEEP | Merged with CCR6 |
| ISR cycle count (§8 CPU budget says "measure at bring-up") | ADD (one clause) | §8 asks for it; §9 never did |

**Step 6, weapon**

| Item | Verdict | Reason |
|---|---|---|
| No drum, 5 → 20 A; scope SHx, VDS, DRV8316 VM | KEEP | Checks the bridge sim; §6.6 cites it |
| Drum fitted: stopped-drum max \|W_Vx\| + phase-pair ΔV/ΔI | KEEP, SIMPLIFY | Calibration §8.1 row 5 needs; drop the hand-turn aside |
| Coast-down time | KEEP | §7.6, event rules |
| Full-pack regen: VBUS < 18.3 V, current ≥ −10 A | KEEP, SIMPLIFY | Real over-voltage margin.  Fix the PA3–PA5 figure (≥ ~14 A, not 12–14) |
| "Brake hard into a full pack, switch closed → row 1 restart, no hold" | MERGE | Into the regen test: "no switch-open report" |
| "Brake to a stop and reverse, drives idle and driving → no switch-open / INA239 report" | MERGE | Same test, same log |

**Step 6, drives**

| Item | Verdict | Reason |
|---|---|---|
| Power-cycle / reset at a marked position, incl. ~180° | KEEP | Checks the two-step alignment against its real dead zone |
| Unplug a sensor at standstill with torque (no-edges flag) | MERGE | With the spinning unplug: one connector pull, two states |
| Unplug a sensor while spinning → sensorless | KEEP | Realistic pit failure |
| Stall against a wall 5 s → no fault | KEEP once | It appeared twice (drives list and classifier list) |
| Link timeout + recover → drives resume; repeat at top speed (no step, no OCP) | KEEP | Checks the back-EMF preset; §8.1 cites the top-speed test |
| Encoder unplugged: safe-resume speed + coast-down time | KEEP, SIMPLIFY | §8.1 needs these numbers |
| Shove during re-alignment → repeats, no latch | CUT | Tests a firmware nuisance-latch branch; no hardware content |
| "After a Release, check the drive runs normally" | MERGE | Into the per-drive-coast test (same Release) |
| Hold R_nCS high from boot → both drives latched | CUT | Only exercises §8.1 drive row 4 |
| Lift one end of R402 → right drive latches | CUT | Needs desoldering on a finished board; only exercises drive row 3 |
| Per-drive coast (CTRL4 0x0C90) at speed: Hi-Z, nFAULT, other drive runs | KEEP | Bench check of an undocumented chip feature that §8.1 relies on |
| Short a sensor VS ~100 ms while spinning → recovery | CUT | The hardware part is step 2; the recovery is the sensor-unplug test again |
| Swap two drive phase wires → sign check latches | KEEP | Realistic pit-repair error |
| Swap J2/J3 cables; swap motor bundles → "left/right crossed" | KEEP, SIMPLIFY | Realistic pit-repair errors |
| Forward-move eye check after drive rewiring; weapon direction eye check after weapon rewiring | KEEP | Only defence against silent reversal |

**Step 6, fault classifier and switch-open**

| Item | Verdict | Reason |
|---|---|---|
| Timed pack-lead interruptions 0.1/0.3/1/3 ms under drum load | KEEP, SIMPLIFY | Contact bounce is real.  Two durations (~0.3, ~1 ms) and **scope the DRV8316 VM**: this is the only bench check of the §7.2 bounce margin |
| Repeated locked-rotor trips → row 6 cool-down, no latch | CUT | Step 4 covers the trip hardware; the rest is firmware counting |
| Hard phase short with the drum spinning → latch on 2nd re-trip | CUT | Destructive to the bridge/harness; step 4 covers the trip chain |
| Phase short with the drum stopped → row 5 latch | KEEP, SIMPLIFY | Safe (a wire across two leads) and checks the stored reference |
| Drum jammed → row 10 retries | KEEP | Real arena event; thermal protection of a jammed drum |
| Power cycle / IWDG reset with a latch set | CUT | Firmware persistence test |
| Reconnect radio with stick up → no spin-up | KEEP | Safety interlock, cheap |
| Push against wall 5 s (2nd copy) | CUT | Duplicate |
| Switch open with the drum spinning → coast everything | KEEP | Real pit-crew event |
| Repeat while driving both wheels / with throttle held | MERGE | One test: drum under throttle and wheels driving (the hardest case covers the others) |
| Open switch while braking, stick held → 18.5 V coast / row 1 → hold | CUT | Tests a rule chain (rounds 24–25), not hardware; the regen and switch-open tests already cover both halves |
| Log max \|I\| with the switch open and the drives switching | KEEP | Sets the 30 mA row 0 threshold; logged during the same test |

### Outside my scope (not changed; wording for consistency)

These are outside §7/§9/§1/§5, but they carry the same over-claim or refer to text changed above.
The wording is suggested so the owner of §3/§8 can align it.

* **§3.2 "Phase voltage sense" bullet** (l.183–186) says "below the 4 V abs max of PA4/PA5 (TT)" and
  "≤ ~3.75 V at the pins".  Suggested last sentence: "A *sustained* D1 clamp is limited by the §8
  regen current limit (≤ ~10 A → ≤ ~3.75 V at the pins: inside the 4.0 V abs max, briefly above
  the VDD + 0.3 V operating limit, §7.4)."
* **§8 Power budget row**: replace "keeping the 4.0 V-rated sense pins PA3–PA5 at ~3.7 V nominal,
  ≤ ~3.75 V worst case" with "keeping the TT_a sense pins PA3–PA5 at ≤ ~3.75 V: inside their 4.0 V
  abs max, briefly above VDD + 0.3 V (§7.4)".
* **§8.1 rows 7/8**: "the measured VDS-OCP retry time" / "the measured t_RETRY" should read "the
  datasheet t_RETRY (4 ms typ; confirmed when a VDS OCP is logged, §9 step 4)".

---

## 2. Replacement text (ready to paste)

### 2.1 §1 table: replaces the whole `| Environment | … |` row (l.36)

```markdown
| Environment | Indoor arena, ambient 0–50 °C | The DRV8316 VM filters (R302/R402 0.1 Ω + ~16 µF) keep the simulated switch-closure, re-close and loaded contact-bounce steps at the DRV8316 VM pins ≤ ~2.3 V/µs with C1 down to 0 °C (~2.8 V/µs only at C1's −40 °C ESR limit), under the 4 V/µs abs max (§5, §7.2).  Not covered: a weapon phase-to-ground short (§7.21) |
```

### 2.2 §5 table: replaces the whole `| Power-switch closure (…) | … |` row (l.434)

```markdown
| Power-switch closure (`sim_hotplug.py`, `hotplug.out`) | Behavioural LM74502 + Q7/Q8 model (charge pump, hysteretic EN/UVLO gating the 60 µA gate source and 2 Ω sink, C18, EN sink, D4, D10/C13/R32) with a realistic load (buck as constant power above its UVLO, ~66 kΩ of dividers, R15).  **Closure:** VBAT ramps ~2.2 V/ms (1.3–3.0 V/ms over the 40–77 µA gate current); VM dV/dt 0.002–0.005 V/µs in every case (stiff or 300 nH lead, C1 at 40 or 300 mΩ, 12 V pack) vs the 4 V/µs limit; Q7 16 W peak (22.0 W at max gate current), 54–57 mJ; the 9–23 A peak current is C14 ringing with the lead, upstream of the FETs.  **Reversed pack:** only the 13 A C14 spike with D10, whatever U13's unpowered gate hold; 102–147 A without D10 if that hold is weak.  **Re-close** (at the DRV8316 VM pins): typical thresholds 0.06–0.7 V/µs within ~0.1 s; minimum threshold with C1 at 300 mΩ 1.8–2.09 V/µs up to ~0.4 s; soft (≤ 0.005 V/µs) after that.  **Contact bounce, 20 A load, 0.1–0.8 ms:** 0.8–2.26 V/µs with C1 up to its aged 0 °C bound, 2.66 V/µs at its −40 °C ESR.  Longer bounces to ~1.3 ms (round 27/28 reruns, not in `hotplug.out`): ≤ 2.33 V/µs at 0 °C, 2.82 V/µs at −40 °C.  Without the R302/R402 filters these were up to ~3.75–4.3 V/µs |
```

### 2.3 §7.2: replaces the whole item 2 (l.507–514)

```markdown
2. **Re-closing the power switch early, or a contact bounce under load, is not soft-started.**
   Re-closing within ~0.1 s (typical thresholds) to ~0.4 s (minimum threshold, unloaded) of
   opening finds Q7/Q8 still on.  A bounce of ~0.1–1.3 ms at the XT30/switch while the weapon draws
   20 A collapses the bus faster than the C18-filtered UVLO reacts (~1–2 ms), so the switch
   re-closes hard onto a bus at ~4–10 V.  That is below the DRV8316 UVLO: the drives reset and come
   back through "drives resume" (§8.1).  At the DRV8316 VM pins, behind R302/R402:
   * re-close ≤ 2.1 V/µs;
   * loaded bounce ≤ ~2.3 V/µs with C1 at its aged 0 °C bound (~100 mΩ);
   * ~2.7–2.8 V/µs only at C1's −40 °C ESR limit, outside the environment;
   * all vs the 4 V/µs abs max.  Sources: `spice/hotplug.out` for 0.1–0.8 ms, round 27/28 reruns
     to 1.3 ms.

   The weapon bridge and U2 see the unfiltered step (no ramp limit on them).  No C18 value closes
   the window without bringing back the ripple trip (review/round8_c18_sweep.md).  §9 step 6
   scopes a real bounce.
```

### 2.4 §7.4: replaces the whole item 4 (l.517–519)

```markdown
4. **Regen with the pack disconnected:** a spinning drum can pump VBAT up (64 J vs a 600 W TVS).
   The INA239 BOVL (19 V) trips the weapon break (coast) within ~0.3–0.45 ms; firmware also coasts
   above 18.5 V, never brakes the drum hard, and limits combined regen to a **current** of ~10 A
   (§8 Power budget).  Until the coast acts, D1 clamps: ~28.7 V at 10 A (SMBJ20A linear clamp
   model).  That puts the 68 k/10 k sense pins PA3–PA5 at ~3.7 V (≤ 3.75 V with 1 % resistors).
   * PA4/PA5 (1 nF, τ ≈ 9 µs) follow the clamp; PA3 (100 nF, τ 0.87 ms) follows only partly.
   * **These are TT_a pins.**  3.7 V is inside the 4.0 V absolute maximum (DS12288 Table 14) but
     above the VDD + 0.3 V ≈ 3.55–3.65 V operating limit (Table 17).  TT_a pins have no clamp
     diode to VDD, so no current flows into them (positive injection "not possible", Table 15).
   * **Accepted:** it only happens when the pack disconnects during a brake, lasts < ~0.5 ms, and
     the ADC just reads full scale meanwhile.
   * The 4.0 V abs max is reached only at ≥ ~14 A of clamp current, which is why the regen limit is
     a current limit, measured in §9 step 6.  Staying inside the operating range in every case
     would need ≤ ~6–8 A of regen (VDD and divider tolerance).
```

### 2.5 §7.5: replaces the whole item 5 (l.520–523)

```markdown
5. **Power switch vs a coasting drum:** opening the switch while the drum spins leaves the board
   powered through the motor's body-diode rectification until the drum slows to ~19 k rpm; the
   power LED stays lit meanwhile.  Firmware detects the open switch (pack current ≈ 0 with the bus
   up, §8.1 row 0), coasts the weapon and stops the drives.  Re-closing while the drum still holds
   the bus up is not soft-started.  This case is not simulated, but the step is bounded by the
   drum's rectified BEMF, so it is no larger than the simulated quick re-close (≤ 2.1 V/µs at the
   DRV8316 VM pins).  Tell the pit crew and inspectors.
```

### 2.6 §7.6: replaces the whole item 6 (l.524–526)

```markdown
6. **Weapon stop after disarm is a free coast** (hardware Hi-Z; no braking without ARM):
   estimated 10–40 s.  **Measure it at bring-up** (§9 step 6) against the event's limit (e.g.
   60 s).  A commanded stop while armed brakes at the ~10 A regen limit in ~0.5 s.
```

### 2.7 §7.16: replaces the whole item 16 (l.550–565)

```markdown
16. **Single faults that silently remove a protection** (none is visible in operation):
    * **ARM:** C15 short, R41 open/high, C16 open or U14 stuck high → ARM is no longer dynamic.
      The compute board's timed boot self-test catches all four.  W_ARM_S feeds both the hardware
      gate and the firmware check, so a U14 output fault defeats both; the command-link timeout
      remains.
    * **U6** gate stuck high → one weapon phase enabled without ARM.  No torque at standstill; a
      partial brake (~30–50 A) on a coasting drum.  Safe, not detectable.
    * **Power entry:** D10 short → the soft-start's reversed-pack protection is lost; Q7 short →
      no soft-start; Q8 short → no reverse-polarity protection.  Not detectable.
    * **R302/R402** shorted, or the local VM caps missing → the DRV8316 loses its VM ramp margin
      (loaded bounce ~2.3 → ~3.5 V/µs).  §9 step 0 measures the resistors.
    * **U2 straps:**
      * open R44 (MODE) → 1x PWM, where the disarm state (INL low) *brakes* instead of coasting;
      * shorted R44 → 6x PWM, where INH turns a high side on without ARM;
      * open R46 (VDS) → trip at 0.6 V, 250–430 A: the shoot-through backstop is gone;
      * open R45 (IDRIVE) → 120/240 mA gate drive (sim: VDS 39 V, SHx −9.2 V, over the limits);
      * an open GAIN pin with leakage → CSA gain error.

      **Measure the four strap voltages at bring-up (§9 step 2).**  The firmware boot test (§8 boot
      order, §8.1 row 11) also catches a 6x-mode strap.  It runs only with the drum stopped (all
      W_Vx ≈ 0).  A ≥ 30 µs INH pulse on one phase with INL = 0 must leave that phase's W_Vx at
      ~0 V (6x mode reads ~VBAT/7.8; sample by software trigger inside the pulse, τ ≈ 8.7 µs) and
      draw no current, and the idle CSA offsets must sit at VREF/2.  A failure latches the weapon
      off.
```

### 2.8 §7.17: no change (KEEP)

### 2.9 §7.18: replaces the whole item 18 (l.569–570)

```markdown
18. **LiPo 4.20 V/cell only.**  LiHV (4.35 V/cell, 17.4 V full) plus the regen rise reaches
    ~18.1–18.6 V at the 10 A regen limit (~18.8 V at 20 A).  Braking a full LiHV pack therefore
    runs into the 18.5 V coast (and at 20 A the 19 V BOVL), with no margin.
```

### 2.10 §7.21: replaces the whole item 21 (l.575–590)

```markdown
21. **Weapon phase short and the fast trip.**  A phase short reaches up to ~500 A before the
    DRV8323's fixed 4 µs VDS trip acts (near the FETs' 600 A pulse rating).  When the bridge turns
    off, the loop current dumps onto the shared bus: 6–36 V/µs at the DRV8316 VM pins without the
    R302/R402 filters (review round 9/10 sims, not in spice/).  So the weapon **requires the
    comparator fast trip** (§8).
    * All three weapon CSA outputs reach a comparator (PA0 → COMP3, PA1 → COMP1, PB11 → COMP6)
      feeding TIM1's main break.
    * The bridge turns off 0.7–1.0 µs after the current passes the threshold: CSA lag
      0.13–0.33 µs, comparator + break ~0.05 µs, driver 0.15 µs, gate discharge at 120 mA ~0.4 µs.
      With the filters, the DRV8316 VM then sees ~1–2 V/µs (round 10 sims).
    * §9 step 4 scopes the trip.  Latching and restart rules: §8.1 rows 4–6 and 8.

    **Residual:** a phase-to-*ground* short bypasses the shunts, so only the 4 µs VDS trip acts.
    That gives ~7–8 V/µs at the filtered VM, **above the DRV8316's 4 V/µs abs max**: a
    damaged-harness event that may take the drive ICs with it.
    * R302/R402 then carry ~100 A for ~1 µs (~1 mJ).  The datasheet gives no µs pulse rating; the
      estimated ~3 K film rise is unverified but far from any limit.
    * If a DRV8316 fails shorted, R302/R402 act as its fuse.
    * D1 is the real clamp when the pack disconnects during regen (§7.4); an open D1 is a silent
      single fault.
```

### 2.11 §9: replaces the whole section from `## 9. Bring-up checklist` to the end of the file (l.715–785)

```markdown
## 9. Bring-up checklist

Steps 0–4 are hardware and first firmware; steps 5–6 need motors.  Several later steps store a
calibration that §8 needs (marked **store**).

0. **After assembly (unpowered).**
   * Stake C1, L1 and J2/J3 with adhesive.
   * Check J1 pin 1 against the compute-board socket (mirror image).
   * Fit or leave the DNP set as intended (C110–C112, C114–C116; the §7.15 cell-monitor option).
   * Inspect the bottom side (it faces the compute board); weigh the board.
   * **R302 / R402** (a short is invisible in operation, §7.16): measure each with a 4-wire
     milliohm meter, or force 1 A from a floating current-limited supply between TP10 (VBAT) and
     an L_VM (R_VM) capacitor pad.  R302 is the only DC path; read the voltage on the resistor's
     own two pads, not through the forcing probes.  Expect 0.10 V (100 mΩ).

1. **First power, no motors.**  Floating bench supply on the battery holes, 12 V.
   * Current limit 1.5 A for the first closure (the soft-start draws ~0.8 A for ~8–13 ms; a lower
     limit makes U13 hiccup; keep ≥ 1.5 A whenever the compute board and its hold-up cap are
     attached), then 0.2 A.  Check 5.0 V, 3.3 V, the power LED, current < 60 mA.
   * **Reverse polarity** as a *step* (switch the reversed, current-limited supply on): no
     current beyond the input-capacitor spike.
   * **UVLO sweep:** sweep the supply down.  The 5 V rail drops out near 9.2 V and returns near
     10.4 V; the switch FETs open near 9 V.
   * **Soft-start:** switch a stiff 16.8 V source on and scope VBAT and a DRV8316 VM pin: a clean
     ~8–13 ms ramp.

2. **MCU, drivers, monitors (bench supply, no motors or sensors).**
   * **MCU:** SWD flash; read the STM32 device ID/UID/revision (§7.12; reject rev Z); program the
     BOR option byte (level 4).
   * **U2 strap pins** against AGND (§7.16): MODE ~1.2 V, IDRIVE ~1.1 V, VDS ~0.5 V, GAIN ~2.0 V
     (open).  An open IDRIVE/VDS strap reads ~1.65 V, an open MODE strap ~2.0 V.
   * **DRV8316, U3 then U4:** write the §8 sequence and read it back: BUCK_UV clear and NPOR = 1
     after CLR_FLT, AVDD 3.1–3.47 V.  Run "drives resume" (§8.1; with no motors it only releases,
     with no wait) and check that L_nFAULT/R_nFAULT go high with the DRV_OFF pin low (a coasted
     chip, or the pin high, may hold nFAULT low, SLVSH07 §8.4.2).
   * **Bench check (§8.1):** record whether nFAULT stays low after the pin is lowered while the
     chip is still coasted.  This decides the optional CLR_FLT in drives resume step 2.
   * **INA239:** DEVICE_ID, bus voltage and current against the bench supply.
   * **Sensor VS:** short each sensor connector's VS to GND.  +3V3 and nSLEEP must stay up
     (scope).
   * **Cells:** with a pack, read the four cell voltages from the compute board over I²C and
     compare them with a meter at the balance plug.

3. **Safety paths.**  Scope TP6 W_ARM, TP7 W_EN, TP8 DRV_OFF, TP9 W_nFAULT; read W_ARM_S from the
   heartbeat.
   * **ARM:** W_ARM rises above ~2.2 V within ~15 ms of W_ARM_CLK toggling at 500 Hz (sim 12 ms).
     A single edge does not arm.
   * **Disarm:** holding W_ARM_CLK high or low, or unplugging the header, drops W_ARM_S within
     ~30–200 ms (sim 52–164 ms; repeat with the board warm).  Halting the compute board's main loop
     (debugger) stops the toggling and W_ARM_S falls.
   * The compute board's timed boot self-test passes.
   * With W_ARM low and TIM1 running, the weapon phases are Hi-Z.
   * An MCU reset with ARM held high does not restart the weapon (a new ARM edge is needed).
   * **Failsafe:** transmitter off → the weapon disarms and the drives stop within ~0.5 s + the
     command timeout.  Stopping command frames alone stops everything within the timeout.
   * The INA239 SOVL and BOVL trip the TIM1 break (inject with a temporarily lowered limit).
   * **Armed soak:** 10 minutes armed with the transmitter and the robot radio on, drum idle.
     Expect **zero** "W_ARM_S fell" events.

4. **Full voltage and the weapon fast trip.**  Raise the supply to 16.8 V.
   * **Store:** with the compute board attached (RS4 carries its load too), record the minimum
     idle pack current, the idle term of the §8.1 row 0 estimate.  Expect ~95–113 mA.
   * **Charge pumps:** U2 VCP ≈ VM + 11 V; DRV8316 CP.
   * **Weapon fast trip** (on a pack, not the bench supply): lock the motor, raise the current
     limit past the comparator threshold, and scope the trip (CSA edge → bridge Hi-Z, ≤ ~1 µs).
     Then run at the 20 A limit and confirm no false trips.
   * **Store t_split** (§8.1 rows 7/8): scope W_nFAULT after a W_EN wake (expect ~1 ms low).  Set
     t_split between that and the DRV8323's 4 ms (typ) VDS-OCP retry, ~3 ms.  Log the W_nFAULT low
     time of any VDS OCP seen later to confirm t_RETRY.

5. **Drives, one motor at a time.**
   * **Program each MT6701 off-board first:** ABZ mode, 1024 PPR, rotation direction, Z pulse
     width 1 LSB, power-up absolute ABZ output off.  Its EEPROM needs 4.5–5.5 V.
   * **Open-loop spin** at a 1 A limit: check encoder direction, pole pairs and the CSA offsets
     (L_SOC through OPAMP5 separately).
   * **Store CCR6:** sweep it at a fixed drive current and take the middle of the flat plateau of
     the measured current (the sampling instant has no pin).  Confirm sampling still holds at the
     duty cap.
   * **Delay compensation:** sweep the duty 0–10 % on a scope to check it on short pulses.
   * **Store the Z electrical offset:** repeat over several Z passes; spread < ~5°.
   * **Store the flux constant λ** for the §8.1 resume preset: closed-loop FOC at a few speeds,
     no load, λ ≈ (V_q − I·R)/ω.  Cross-check with 60 / (√3·2π·KV·pole pairs).
   * Then closed-loop FOC.  Measure the ISR cycle counts (§8 CPU budget).

6. **Full system** (4S pack, or a supply good for ≥ 25 A peaks).

   **Weapon, no drum:** 5 A limit.  Scope SHx and VDS at the FETs, and a DRV8316 VM pin (dV/dt
   well under 4 V/µs, §6.6).  Raise the limit in steps to 20 A.  Confirm the pole count (14 poles
   assumed).

   **Weapon, drum fitted:**
   * **Store the §8.1 row 5 threshold and reference:** the stopped-drum max \|W_Vx\| (the row 5
     threshold) and the three phase-pair ΔV/ΔI values.  Re-measure after any weapon motor or lead
     change.
   * **Measure the free coast-down time** after disarm (§7.6).
   * Spin the drum slowly and check its direction by eye.

   **Regen:** on a freshly charged pack, brake the drum at the chosen regen limit and reverse it,
   with the drives idle and then driving.  Log INA239 VBUS and current.
   * VBUS peak < 18.3 V (below the 18.5 V coast).
   * Pack current ≥ ~−10 A, weapon and drives combined (this sets the D1 clamp current if the
     pack ever disconnects mid-brake, §7.4).
   * No switch-open and no INA239-failure report.
   * Otherwise lower the regen limit.

   **Contact bounce:** with the drum at speed, interrupt the pack + lead for ~0.3 ms and ~1 ms (a
   MOSFET in the lead).  Scope a DRV8316 VM pin: < 4 V/µs (sim ≤ ~2.3 V/µs at 0 °C, §7.2).
   Everything restarts and nothing latches.

   **Switch open:** open the power switch with the drum spinning under throttle and both wheels
   driving.
   * The weapon coasts and the drives stop within ~0.1 s.
   * The heartbeat reports "switch open" (not "INA239 failed").
   * Log the largest \|I\| reading while open with the drives switching.  It must stay well under
     the 30 mA §8.1 row 0 threshold.

   **Weapon faults:**
   * A wire across two weapon phase leads with the drum stopped → the restart resistance check
     refuses to start and latches (§8.1 row 5).
   * Jam the drum at the current limit → the stall cut-out coasts and retries, no latch (§8.1
     row 10).
   * Reconnect the radio with the weapon stick up → no spin-up until the stick returns to zero.

   **Drives:**
   * **Start angle:** power-cycle and MCU-reset with the rotor at a marked position, including
     ~180° from the last aligned position → the aligned start angle is correct.
   * Push against a wall for 5 s → no fault.
   * **Sensor unplug:** unplug a sensor at standstill with torque commanded → the heartbeat's
     no-edges flag.  Unplug it while spinning → that drive goes sensorless and reports.
   * **Link recovery:** let the command link time out and recover → both drives resume with no
     braked wheel.  Repeat at top speed: no current step, no OCP (the §8.1 back-EMF preset).
   * **Store the safe-resume speed** (§8.1 no-encoder branch): with the encoder unplugged, find the
     wheel speed below which a resume without a valid angle is safe (expect ~0.5 m/s), and the
     coast-down time to reach it.
   * **Per-drive coast** of a live chip at speed (CTRL4 0x0C90): its phases go Hi-Z, note its
     nFAULT behaviour, and the other drive keeps running.  After the Release (0x0D10) it drives
     normally.

   **Wiring checks.**  Run these once at bring-up:
   * swap two drive phase wires → the alignment sign check latches that drive (it must not run
     backwards);
   * swap the J2/J3 sensor cables, and separately the left/right motor bundles → "left/right
     crossed", with both drives latched until cleared.

   **After every pit repair that touches a motor lead or sensor cable:**
   * after drive rewiring, command a short forward move and check it by eye (or with the compute
     board's IMU): crossed bundles plus "fixed" sensor cables would drive backwards;
   * after weapon rewiring, spin the drum slowly and check its direction by eye (a swapped weapon
     phase pair reverses it silently).
```

---

## 3. Tests cut from §9 (move them to the firmware test plan when firmware exists)

These exercise firmware branches, not hardware, and are better run by fault injection in firmware
(forced register values, simulated SPI failures) than by modifying the board:

* shove during a re-alignment;
* R_nCS held high (deaf U4);
* lifted R402 (unpowered U4);
* sensor VS short while spinning;
* repeated locked-rotor trips (row 6 cool-down);
* phase short with the drum spinning (second fast re-trip);
* latch kept across a power cycle / IWDG reset;
* switch opened while braking with the stick held.
