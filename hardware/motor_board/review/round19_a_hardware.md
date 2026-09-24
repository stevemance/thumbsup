# Round 19 / A: hardware (rev L): the round-18 §3.3/§8/§8.1/§9 text against the datasheets and the netlist

Scope: the hardware facts that the round-18 text relies on.  That text covers the boot order (per-chip Release, then MOE
re-arm), TIM8/TIM20 OISx = 1 with OSSI = 1, the drive-table nFAULT exemption for the DRV_OFF pin, weapon row 1 "looks
open", the row 0 plausibility gate, the row 5 stopped-drum test and ΔV/ΔI.  Board area, prose and firmware preferences are
out of scope.  This file is the only one I wrote in the package.

**Snapshot.**  I copied the package to `/tmp/r19a`.  `design/motor_board.py` prints "237 refs (205 placed components), 160
nets, 67 BOM lines, checks: OK".  The regenerated nets.md, netlist.csv, bom.csv and mcu_pinmap.md are byte-identical to the
working tree.  `calcs.py` reproduces calcs.md (the only difference is a trailing blank line).  Round 18 changed text only,
so I did not re-run the SPICE decks.

References:
* [D] DESIGN.md rev L; [N] nets.md
* [DRV16] DRV8316C SLVSH07; [INA] INA239 SLYS027A; [G4] STM32G474 DS12288 Rev 4
* [PINS] ref/STM32G474RxTx_pins.xml
* [RM] RM0440, "Using the break function" and "Debug mode".  This is ST's reference manual.  It is not in `datasheets/`,
  so those statements are quoted from the manual, not from a file in the package.

## Verification of the facts the round-18 text relies on

| Claim | Verdict | Evidence |
|---|---|---|
| The DRV_OFF pin Hi-Zs all six FETs regardless of INHx/INLx, and it "can trigger fault condition resulting in nFAULT getting pulled low" | Correct as quoted.  **The datasheet does not say which fault, or whether it is latched** (see R19A-01) | [DRV16] §8.4.2 p.53 |
| CTRL4 bit 7 DRV_OFF "1h = Hi-Z FETs"; 0x0C90 / 0x0D10 have even parity | Correct | [DRV16] Table 8-21 p.65.  0x0C90: 2 + 2 ones.  0x0D10: 3 + 1 ones |
| L_nFAULT = PB7 = TIM8_BKIN; W_nFAULT = PC13 = TIM1_BKIN; R_nFAULT = PC15 (no break) | Correct | [N] l.67, 110, 162; [PINS] PB7 lists TIM8_BKIN, PC13 lists TIM1_BKIN |
| OISx = 1 plus OSSI = 1 drives INH high on MOE = 0 (break, CLL lockup, debug freeze).  In 3x mode that is a high-side brake.  In 6x mode (INL = +3V3) INH high is Hi-Z | Correct | [RM] BDTR.OSSI and "Debug mode" (a counter stopped by DBG_TIMx_STOP disables the outputs as if MOE = 0, so OSSI = 1 → idle level); [DRV16] Table 8-3 p.20, Table 8-4 p.22 (settled in R18A) |
| Row 1: with the switch closed the bus is back near the pack voltage within ~0.15 ms | Correct | τ = 74 mΩ × 374 µF ≈ 28 µs.  After the break the weapon BEMF is ≤ 25.6 k / 1800 ≈ 14.2 V < 16.8 V, so it stops feeding the bus |
| Row 1: an open bus decays only ~0.2 V/ms, so VBUS stays > ~18 V over two conversions | Correct, with margin | 1.2–1.9 W / (374 µF × 19 V) = 0.17–0.27 V/ms.  Two shunt + bus pairs that *started* after the alert end ≤ ~0.9 ms later (150 µs conversions, AVG = 1 reset default [INA] p.5), so VBUS ≥ 19 − 0.25 ≈ 18.75 V.  D1 (SMBJ20A, V_BR ≥ 22.2 V) does not conduct there |
| Row 1: \|I\| < ~50 mA separates open from closed | Correct in combination with the VBUS clause | Open: RS4 carries ≈ −0.2 mA (BAT_IN loads only), offset ±5 µV = ±5 mA at 1 mΩ [INA] p.1/p.5.  Closed: +idle (~60–100 mA) plus drive current.  Drive regen could null \|I\| with the switch closed, but VBUS is then ≈ the pack OCV ≤ 16.8 V < 18 V.  So the AND is robust |
| Row 0 plausibility: "C1 alone would fall ~27 V in 100 ms" | Correct | 0.1 A × 0.1 s / 374 µF = 26.7 V |
| Row 5: 25 mV ≈ 50 rpm; up to ~270 rpm with a ±4-count offset gives ~11 % error | Correct | 25 mV × 1800 KV = 45 rpm.  With clipping at code 0, up to ~150 mV (≈ 270 rpm) of real BEMF can hide under the threshold (R18A N-01).  At 31.5 Hz electrical the BEMF changes ~30 mV between ~1 ms steps, vs ΔV ≈ 0.27 V → 11 % |
| Row 5: ΔV from differential duty × VBUS | Correct | TIM1 ARR 3542 → 4.7 mV per count at 16.8 V; ΔV ≈ 57 counts.  Dead time is the same offset for both same-polarity steps.  The drum's own acceleration from the DC steps adds little: J ≈ 1.8·10⁻⁵ kg m² (64 J at 25.6 k rpm), Kt ≈ 5.3 mNm/A → ≤ ~1.5 rad/s over a 2 ms pair → ≤ ~8 mV BEMF, ~2 % of ΔV |
| Row 5: "calibrate the offsets at the §7.16 boot test" makes a max-based test work at ~4 LSB | **Not by itself** (R19A-02) | below |

## Findings

| ID | Sev | Where | Finding | Evidence | Fix |
|---|---|---|---|---|---|
| R19A-01 | MINOR | [D] §8 boot order (l.597), §8 watchdog row (l.606), §8.1 drive-events preamble (l.672) | **The MOE re-arm for TIM8 can fail silently when L_nFAULT is still low, and the text only re-arms after a Release.**<br><br>• TIM8's break input is L_nFAULT (PB7), and the break is level-sensitive: [RM] "MOE cannot be set while the break input is active, and BIF cannot be cleared".  §8 itself relies on this (l.606: clear the break flags "after … the DRV8316 fault clear … so MOE can be set").<br>• Round 18 changed the order.  The DRV8316 sequence (including CLR_FLT) now runs with the DRV_OFF **pin high**, and the pin is released afterwards.  [DRV16] §8.4.2 says the pin itself can raise a fault that pulls nFAULT low.  It does not say which fault or whether it is latched.  If it persists after the pin goes low (a status bit that only CLR_FLT clears), nothing in the boot order clears it.  L_nFAULT then stays low, TIM8 MOE never sets, and **drive L stays in the OSSI idle (high sides on = brake) while drive R runs**.  The robot can only turn.  The same can happen after a Release (CTRL4 bit, "bench-verify whether it pulls nFAULT low").<br>• The exemption covers nFAULT "while the pin is high or within ~1 ms after firmware raised it".  It says nothing about nFAULT that is still low after the pin is **lowered**.<br>• The pin is also lowered without a Release: command-timeout recovery ("DRV_OFF high … stay stopped until commanded again"), supply-row restarts ("DRV_OFF high, restart both after 20 ms") and the SPI3-fault retry.  If the pin pulls L_nFAULT low, each of these clears TIM8 MOE.  The text re-arms MOE only "after a Release", so drive L stays braked after the first command timeout or supply event.  §9 step 2 checks nFAULT once after Release, but not these paths | [DRV16] §8.4.2 p.53, Table 8-8 p.48 (most faults list "CLR_FLT … (bit)" recovery); [N] L_nFAULT → U1.60 PB7 = TIM8_BKIN; [RM] break function | Text only.  (a) After **every** lowering of the DRV_OFF pin and after every Release, wait for L_nFAULT (and R_nFAULT) high, up to a few ms.  If one is still low, run the §8 fault recovery (CLR_FLT) once and wait again.  Then clear BIF and set MOE on TIM8/TIM20.  If nFAULT stays low, treat it as a drive event (row 2 for that chip), not as a silent brake.<br>(b) Extend the exemption to "until ~1 ms after the pin was lowered or the Release was written".<br>(c) In §9 step 2/3, add: after a command-timeout coast and resume, both drives run again, and L_nFAULT high after the DRV_OFF pin toggles.  Record whether the pin-induced fault needs CLR_FLT |
| R19A-02 | MINOR | [D] §8.1 weapon row 5 ("the largest weapon line-to-line \|W_Vx\| over a ≥ ~200 ms window … below ~25 mV") | **The maximum of raw 24 kHz samples is dominated by ADC noise at this threshold.  The stopped test would often fail on a stopped drum, time out after 2 s, and skip the resistance check (reported, but the standstill-short protection is then absent).**<br><br>• The threshold is ~4 LSB: 25 mV × 10/78 = 3.2 mV, and 1 LSB = 0.806 mV, which is 6.28 mV at the motor.<br>• [G4] Table 68 p.145 gives single-ended SNR ≥ 65 dB and ENOB ≥ 10.4.  That is ≈ 0.8 LSB rms per sample in a quiet lab, before any coupling from the 48 kHz drive nodes onto the 78 kΩ weapon dividers (Hi-Z phases).<br>• A 200 ms window at 24 kHz is 4800 samples per channel and three line-to-line pairs.  I ran a Monte Carlo with σ = 0.8 LSB and quantisation.  The median max is **31 mV** (min 25 mV) with the phases a few LSB above code 0, and 19 mV when clipped at code 0.  At σ = 1 LSB it is 38 / 25 mV.  So the statistic sits at or above 25 mV with the drum perfectly still.<br>• R18A-03 proposed "short averages ≤ ~1 ms" before the max.  The text adopted the max but dropped the averaging.  A 1 ms (24-sample) mean leaves a 5.8 Hz (50 rpm) BEMF intact and brings the noise max to ~4–6 mV | [G4] Table 68 p.145 (SNR, ENOB, E_O ≤ 4 LSB); [N] W_VA/W_VB/W_VC dividers R22–R27 68 k/10 k, C41–C43 1 nF (τ 8.7 µs: no useful filtering at 24 kHz); Monte Carlo in this round | Text only: "max over the window of the **~1 ms averaged** \|line-to-line W_Vx\|".  In §9 (step 4 or 6), measure that statistic on a stopped drum on the running robot (drives switching) and set the threshold ≥ ~4 LSB (~25 mV) above it.  Confirm that a hand-turned drum (~100 rpm) exceeds it (the R18A N-01 suggestion, not yet in §9) |

## Notes

| ID | Sev | Note |
|---|---|---|
| N-01 | NOTE | **The row 0 plausibility gate covers only a stopped drum.**  With C2 shorted (INA239 ≈ 0 A, all config read-backs pass) and the weapon **motoring**, the second suspension clause does not apply (the estimate from actively driven channels is amperes, not ≈ 0).  The gate does not apply either (the drum is not stopped), so row 0 matures in 100 ms and holds the whole robot.  After each operator clear it re-fires until the drum has coasted down (10–40 s), and only then does the INA239-failure path take over.  A physical fact closes this: with the switch open, a motoring load of ≥ ~1 A collapses the bus at ≥ ~7 V/ms (374 µF), so an estimate ≥ ~1 A with VBUS steady for 100 ms proves the pack path.  In that case take the INA239-failure path too.  Availability only (the hold is safe) |
| N-02 | NOTE | R18A-02 asked for OSSI = 1 in the §8 "STM32 timers/ADC" row.  It now appears in §3.3 (l.214) and §8.1 drive row 2 (l.677) but not in the timers row, which is where a firmware writer configures TIM8/TIM20.  Consider repeating "TIM8/TIM20: OISx = 1, OSSI = 1, BKP active low (TIM8), BKE = 1 / BKINE = 0 (TIM20)" there |
| N-03 | NOTE | Row 1 "first two shunt/bus conversions that *started* after the alert" assumes ADC_CONFIG AVG = 1 (the reset default; §8 does not state it).  With averaging the reported values span the event.  Firmware can identify the conversions with DIAG_ALRT CNVRF: the first CNVRF after the alert may straddle the event, so use the 2nd and 3rd.  That is ≤ ~0.9 ms at 150 µs + 150 µs, consistent with the VBUS margin above |

## Independent re-checks (no finding)

* **Boot order with OSSI = 1.**  The INH pins are timer-driven high from CCxE until MOE.  The DRV_OFF pin (R50 pull-up,
  PC14 analog at reset) and the CTRL4 coast bit hold both chips Hi-Z until the Release.  Between the Release and MOE the
  drives briefly high-side brake a stopped motor, which is harmless.
* **Debug freeze.**  With DBG_TIMx_STOP and OSSI = 1 the drive outputs go to OISx = 1 (brake) and the weapon INL goes low
  (coast).  This matches the §8 note.
* **Row 1 over-voltage on a closed switch** needs ≈ 30 A of weapon regen at a full pack.  Drive regen alone cannot reach
  19 V through ~74 mΩ.  So after the weapon coasts, VBUS is ≈ OCV and the "looks open" test cannot be met.
* **Row 5 current steps** are within the hardware.  The DRV8323 3x mode gives per-phase Hi-Z through CHxN for the third
  phase.  Both low sides of the pair conduct at the TIM1 peak, so both CSAs read.  A real phase short under the
  current-regulated step shows as a small duty, and the 30 A comparator still backs it up.

**Verdict: 0 BLOCKER, 0 MAJOR, 2 MINOR, 3 NOTE.**  Both fixes are text only: §8/§8.1 (wait for nFAULT high and re-arm
TIM8 MOE after every DRV_OFF-pin lowering and every Release, with CLR_FLT if needed) and §8.1 row 5 (average ~1 ms before
the max; set the threshold from a measured stopped-drum floor in §9).  No circuit change is needed.
