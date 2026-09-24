# Round 18 / A: hardware (rev L): the round-17 §8/§8.1/§9 text against the datasheets and the netlist

Scope: the hardware facts that the round-17 text relies on.  These are row 0 (the continuous switch-open monitor), row 1 (the BOVL
branch on the pack-current sign), row 5 (the stopped-drum test W_Vx < 25 mV and ΔV/ΔI), drive row 2 (TIM8/TIM20 OISx = 1),
drive row 7, DIAG_ALRT handling and the boot-order heartbeat.  Board area, prose and firmware preferences are out of scope.
This file is the only one I wrote in the package.

**Snapshot.**  I copied the package to `/tmp/r18a`.  `design/motor_board.py` prints "237 refs (205 placed components), 160 nets,
67 BOM lines, checks: OK".  The regenerated nets.md, netlist.csv, bom.csv and mcu_pinmap.md are byte-identical to the working
tree.  Round 17 changed text only, so I did not re-run the SPICE decks.

References:
* [D] DESIGN.md rev L; [N] nets.md; [C] calcs.md
* [DRV16] DRV8316C SLVSH07; [DRV23] DRV8323 SLVSDJ3D; [INA] INA239 SLYS027A
* [G4] STM32G474 DS12288 Rev 4; [S] spice/sim_weapon_spinup.py
* [RM] RM0440, TIMx_BDTR OSSI description.  This is ST's reference manual; it is not in `datasheets/`.

## Verification of the facts the round-17 text relies on

| Claim | Verdict | Evidence |
|---|---|---|
| Row 5: "W_Vx < ~25 mV ≈ 50 rpm, only ~4 ADC counts" | **Arithmetic correct** (see N-01 for what is measurable near 0 V) | 25 mV × 10/78 = 3.21 mV; 3.3 V/4096 = 0.806 mV/LSB → 3.98 LSB.  1800 KV → 25 mV ≈ 45 rpm |
| Row 5: BEMF ≪ the "~0.25–0.5 V test drop" | Correct | 2.5 A and 5 A × (0.10 Ω + ~7 mΩ of FETs and shunts) = 0.27 and 0.53 V |
| Row 5: ΔV/ΔI measurable as wired | **Yes, with V taken from duty × VBUS** (N-02) | ΔI through the CSAs: 2.5 A = 125 LSB at 20 mA/LSB.  Both low sides are on at the TIM1 peak sample, so both shunts of the pair carry the current (settled in R17A).  ΔV from TIM1 duty: 1/3542 per count = 4.7 mV at 16.8 V, so ΔV ≈ 0.27 V ≈ 57 counts.  Dead time is a constant offset for a current that does not change sign: at 2.5 A the FET Coss swings the node in ~20 ns, far below the ≥ 100 ns dead time, so the offset is the same at 2.5 A and 5 A and cancels |
| INA239 sign: positive = pack → board | Correct | [N] INA_INP (IN+) via R2 from VBAT_SW (pack side of RS4), INA_INN via R3 from VBAT |
| BOVL 0x17C0 = 19.0 V, SOVL 0x76C0 = 38 A | Correct (settled) | 6080 × 3.125 mV; unchanged |
| Row 1: "pack current ≥ ~0 A at the trip → switch open" | **Wrong** (R18A-01) | below |
| Row 0: RS4 current with the switch open | ≈ −0.2 mA | Only the back-fed BAT_IN load crosses RS4, flowing board → pack: R13 + R14 (115 kΩ), U13 45 µA.  Every other load is on VBAT [N] |
| Drive row 2: in 6x mode INH high (INL = +3V3) is Hi-Z; in 3x mode either level brakes | Correct | [DRV16] Table 8-3 p.20: INL = 1, INH = 1 → Hi-Z; INL = 1, INH = 0 → L.  Table 8-4 p.22: 3x with INL = 1, INH selects L or H.  So in 3x, OIS = 1 means all high sides on, also a brake |
| Drive row 2: "OISx = 1 so a break idles INH high" | **Only with OSSI = 1** (R18A-02) | below |
| The DRV_OFF pin overrides INH/INL | Correct | [DRV16] §8.4.2 p.53 |
| Drive row 7: swapped J2/J3 are seen as the other timer moving | Correct | [N] J2 → U9 → TIM3 (left), J3 → U10 → TIM2 (right) |
| DIAG_ALRT: a read clears the ALATCH-held flags and releases ALERT | Correct (settled R17A-03) | [INA] §7.3.6 p.16 |
| The first heartbeat after clocks + USART1 | No hardware conflict | USART1 on PC4/PC5, from PCLK2; nothing in that path depends on the later GPIO or SPI init |

## Findings

| ID | Sev | Where | Finding | Evidence | Fix |
|---|---|---|---|---|---|
| R18A-01 | **MAJOR** | [D] §8.1 weapon row 1 | **The sign of the pack current does not separate "switch open" from "regen over-voltage".  Which answer firmware gets depends on which INA239 shunt conversion it reads, and the conversion that is current at classification time (~0.3–0.5 ms) gives the wrong one for a real over-voltage.**<br><br>• **Switch closed, real over-voltage.**  At a full pack, reaching 19 V at the INA239 needs ≈ 30 A of regen ((19 − 16.8) V / 74 mΩ of pack, lead, Q7/Q8 and RS4).  The BOVL alert breaks TIM1, so the weapon coasts.  Its maximum BEMF is 25.6 k rpm / 1800 KV ≈ 14.2 V < 16.8 V, so it stops feeding the bus.  The ~374 µF bus then discharges into the pack with τ = 74 mΩ × 374 µF ≈ 28 µs.<br>• My step model (pack 16.8 V, 74 mΩ, 0.3 µH, 70 mA idle) gives these mean pack currents over successive 150 µs windows after the break: **−5.4 A, then +0.06, +0.07, +0.07 A**.  VBUS is 16.8 V from the second window on.<br>• The first post-event shunt conversion reads negative.  Every later one reads the positive idle current, which is "≥ 0" → row 0 hold → **drives off (DRV_OFF high) until an operator clear or a power cycle**.  The robot is dead for the rest of the match after a real over-voltage.<br>• **Switch open during regen.**  RS4 carries ≈ −0.2 mA after opening (±7 mA offset, ±15 mA p-p noise [INA] p.5 / Table 8-2).  So "≥ 0" is a coin toss.  The last shunt conversion *before* the BUSOL flag still averages the pre-opening regen (negative): at 10 A the bus climbs 17.5 → 19 V in ~55 µs.  Reading the "at the trip" value instead therefore turns a switch-open into an "over-voltage" restart with the switch open.<br>• What does separate the two is the **magnitude**: with the switch open RS4 current is exactly ~0 whatever the motors do, because there is no pack path.  VBUS separates them too: with the switch closed it is back at the pack voltage (≤ ~17 V) within ~0.15 ms.  With the switch open it decays only by P/(C·V) ≈ 1.2 W / (374 µF × 19 V) ≈ 0.17 V/ms while the drives are idle | [N] RS4/U7 wiring; [C] pack + lead 70 mΩ, ~374 µF; [D] §3.1, §8 weapon-safety row; step model in this round (numbers above) | Replace the sign test.  **Switch open** ⇔ \|I\| < ~50 mA in the first **two** shunt conversions that *started* after the alert (the row 0 band; the switch-closed case gives ≥ 5 A or the ~60–80 mA idle), preferably also with the first post-event bus conversion still > ~18.5 V.  **Otherwise over-voltage** (a large negative current from the cap discharge or drive regen, or a positive idle or drive current, with VBUS back at the pack voltage).  State which conversions are used.  §9 step 3 already injects BOVL with a lowered limit; add one run with the switch closed and one with the + lead opened under drum braking, and check the classification of each |
| R18A-02 | MINOR | [D] §8.1 drive row 2 ("TIM8/TIM20 OISx = 1 so a break … idles INH high"); §8 boot order (DBGMCU note) | **OISx only takes effect with OSSI = 1, and §8 sets OSSI = 1 only for TIM1.**<br><br>• With OSSI = 0 a break (MOE = 0) *releases* the output to the GPIO logic, which forces Hi-Z [RM, BDTR.OSSI].  The DRV8316 INHx input then falls through its internal 70–130 kΩ pull-down ([DRV16] RPD, p.10).<br>• In 6x mode (a chip reset back to defaults) INL = 1, INH = 0 is **L, low side on = brake** (Table 8-3 p.20).  That is exactly the state B17-09 set out to avoid.<br>• The same applies to a TIM8 break from L_nFAULT, to the CLL lockup break and to the DBGMCU freeze | [RM] TIMx_BDTR OSSI; [DRV16] p.10, p.20 | Add "OSSI = 1" to TIM8/TIM20 in the §8 timers row, next to OISx = 1.  With OSSI = 1, MOE = 0 in 3x mode is a high-side brake, so the "halted core leaves the drives braking" note still holds |
| R18A-03 | MINOR | [D] §8.1 weapon row 5 ("W_Vx < ~25 mV … average") | **A signed average of the line-to-line W_Vx has nulls at speeds where the window spans whole electrical periods.  A turning drum can then pass as "stopped", and the check can latch a healthy weapon.**<br><br>• With a 10 ms boxcar (the R17A suggestion), 100 Hz electrical = 857 rpm (7 pole pairs) averages to 0, although the BEMF is 0.48 V peak.  Every n × 100 Hz nulls in the same way, and near-nulls cover a band around each (sinc).<br>• At 857 rpm the BEMF changes at up to 2π·100·0.48 ≈ 0.3 V/ms.  Across the two ~1 ms steps that is a ΔV error up to ~0.3 V, or **±0.12 Ω on ΔI = 2.5 A**, against a 0.107 Ω reference.  The "< half" rule (0.053 Ω) is then met by a healthy motor → weapon latch, operator clear.  A real short can pass in the same way | 7 pole pairs [D] §8; KV 1800, R 0.10 Ω [S]; ΔI 2.5 A [D] row 5 | Define "stopped" as a **magnitude**: the max over the three pairs of \|line-to-line\| (short averages ≤ ~1 ms), below the threshold for a window ≥ one electrical period at the threshold speed (≥ ~200 ms: 50 rpm is 5.8 Hz electrical).  Or use the Clarke-vector magnitude, which is constant for a turning drum.  In both cases also require the catch-spin listener to report no rotation.  Never use a signed mean over a long window |

## Notes

| ID | Sev | Note |
|---|---|---|
| N-01 | NOTE | **What the W_Vx channels resolve near 0 V.**  With the bridge idle, the phases sit near GND (78 kΩ dividers; FET IDSS may lift the common mode by a few to tens of mV, and it varies with temperature).  A turning drum's BEMF swings ± around that level.<br>• A single-ended ADC channel has up to **±4 LSB** of offset ([G4] Table 68 p.145).  A negative offset or a negative phase voltage reads as code 0, so the "calibrate the offsets at the §7.16 boot test" step cannot see a negative offset.<br>• With clipping at code 0, the peak line-to-line value that is still visible is 0.29–0.58 of the true peak, depending on the instant.<br>• So the nominal 25 mV (≈ 45 rpm) can mean up to ~150 mV of real BEMF, about 270 rpm.  That is harmless: at 270 rpm (31.5 Hz electrical) the BEMF changes ~30 mV between the steps, ±12 mΩ (~11 %) on ΔV/ΔI, well inside the "< half" rule.  Just do not quote 50 rpm as a guarantee.<br>• §9: set the threshold ≥ ~4 LSB above the measured stopped reading, and confirm that a hand-turned drum (~100 rpm) is seen |
| N-02 | NOTE | **Where ΔV comes from.**  The W_Vx dividers cannot supply the ΔV: τ = 8.7 kΩ × 1 nF = 8.7 µs, sampled once per 41.7 µs period at a fixed phase, so the reading is a pulse-response sample, not the average.  ΔV must be (duty difference) × VBUS (INA239 VBUS or VBAT_SNS), which is what the "cancels the dead-time offset" wording implies.  Say so explicitly.  Apply the step as a differential duty around 50 % on the two legs rather than d / 0 %: at 2.5 A a d / 0 % pulse is only ~0.9 µs, near the gate-drive transition times at IDRIVE 60/120 mA.  Let the current loop settle before taking each value (the weapon L/R is not in the package; measure the settling at §9 step 6) |
| N-03 | NOTE | Row 1's "more than ~3 within 10 s → held" and "restart once VBUS < 18 V" are consistent with the hardware once R18A-01 is fixed.  With the switch closed, VBUS returns below 18 V within ~0.1 ms of the break |

## Independent re-checks (no finding)

* **Row 0 averaging and suspension** (R17A-02 fix): the physics is consistent.  RS4 is the only pack path, and a coasting motor's rectified current into a bus held by the pack is zero unless BEMF > VBUS.
* **DRV8316 words** in §8/§8.1 (0x0603, 0x0606, 0x087C, 0x097D, 0x0A4E, 0x0C90, 0x0D10, 0x0F00, 0x1019, 0x1818): unchanged since round 17, where they were verified to have even parity.
* **Boot order.**  With OSSI = 1 on TIM8/TIM20 (R18A-02), the INH pins are driven high from timer enable until MOE.  The DRV_OFF pin is held high by R50 and firmware until the drives are commanded, so the drives stay Hi-Z; nothing changes.

**Verdict: 0 BLOCKER, 1 MAJOR, 2 MINOR, 3 NOTE.**  All fixes are text only: §8.1 row 1 (magnitude, not sign, and name the
conversions), the §8 timers row (OSSI = 1 on TIM8/TIM20) and §8.1 row 5 (a magnitude-based stopped test).  No circuit change is needed.
