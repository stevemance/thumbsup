# Round 4 (C): MCU plan and firmware contract, rev D

Scope: DESIGN.md rev D §3.3 (48 kHz drives), §3.4 (timers/ADC plan), §3.5 (J1), §8 (firmware contract), §9, plus the
MCU-facing nets in `design/motor_board.py`.  No design file was edited.

`python3 design/motor_board.py` was run on a temp copy: `222 refs (190 placed components), 155 nets, 60 BOM lines,
checks: OK`.  The regenerated `mcu_pinmap.md`, `nets.md`, `netlist.csv`, `bom.csv` and `calcs.md` are byte-identical to
the committed ones.

Sources:

* **ES0430 Rev 8 (March 2023)**: full text this time, from a distributor mirror
  (rxelectronics.sg/datasheet/9f/stm32g474rct3.pdf).  The sections used are §2.7.3, §2.7.5–2.7.9 and Table 2
  (REV_ID Z = 0x2001, Y = 0x2002, X = 0x2003).  Round 3's "partially verified" 2.7.9 items are now verified.
* **DS12288 Rev 4** (`datasheets/STM32G474RET6.pdf`):
  * Table 54 (VIL/VIH/VHYS);
  * Table 58 (NRST);
  * Table 66 (fADC, tLATR/tLATRINJ, CADC);
  * VBOR table;
  * Table 15 (IINJ);
  * pin table (PD2 = FT, PC5 = TT_a).
* **stm32g4xx_hal_driver master**:
  * `stm32g4xx_ll_adc.h`: l.1409–1540 (JEXTSEL list), l.1073–1117 (EXTSEL list), l.1626–1630 (JEXTEN), l.2250–2259 (DUAL modes);
  * `stm32g4xx_ll_tim.h`: l.905–965 (MMS, MMS2, SMS, TS).
* **ST community**, "How to trigger ADC1 with TIM1_CH4?" (community.st.com/…/17251).  An ST-community expert states that
  the TIMx_CHy ADC trigger is the channel **output** signal (the signal that goes to the pin).  It needs CC4E = 1 and
  MOE = 1, and CCR4 = ARR gives no trigger.
* TI **SLVSH07** (DRV8316C Table 8-20, §8.3.9.1, Table 8-6), **SLVSDJ3D** (DRV8323 tSET, tPD), **SN74LVC08A**
  (Δt/Δv, §7.3.2).
* **RM0440**: st.com still times out and the mirrors return 403.  Anything that depends on it is marked **UNVERIFIED**.

---

## Timing reference (numbers used below)

Assumptions:
* TIM1, TIM8 and TIM20 count at 170 MHz (PSC = 0), centre-aligned.
* TIM1 ARR = 3542 (23.998 kHz, period 41.67 µs, half-period 20.835 µs).
* TIM8/TIM20 ARR = 1771 (47.996 kHz, period 20.83 µs).  The ratio is exactly 2 : 1 only if ARR1 is even and ARR8 = ARR1 / 2.
* t = 0 is the TIM1 valley.  With reset-mode slaving, the TIM8 valleys fall at t = 0 and t = 20.83 µs, and the TIM8 peaks at t = 10.42 and 31.25 µs.

Injected group (3 ranks × (12.5 + 12.5) cycles at 42.5 MHz):
* The whole group takes 75 cycles = **1.76 µs**.
* Relative to the trigger, rank 1 samples during 0–0.29 µs, rank 2 during 0.59–0.88 µs and rank 3 during 1.18–1.47 µs.
* Add tLATR, which is ≤ 2.125 ADC cycles (50 ns).

Drive (DRV8316C, 3x mode, DLY_TARGET = 1.2 µs, CSA tSET ≤ 1 µs):
* With the low-side centre at c, the INH-low window is c ± (1−D)·10.42 µs.
* At the OUT pin that window is delayed by 1.2 µs.
* Valid samples lie in [c − (1−D)·10.42 + 2.2, c + (1−D)·10.42 + 1.2] µs.
* **At D = 88 % the valid window is [c + 0.95, c + 2.45] µs, 1.50 µs wide.**  All three ranks (1.47 µs) fit only if the trigger is at c + 0.95 µs (±0.03 µs).  The §8 figure "duty ≤ ~88 %" is therefore correct, with no spare margin, **but only if the trigger is at c + 0.95 µs**.

Weapon (DRV8323, tPD 150 ns, tSET 600 ns at 20 V/V):
* The low-side window is c_w ± (1−D_w)·20.83 µs.
* c_w is the TIM1 peak (t = 20.83 µs) with PWM mode 1, or the TIM1 valley with PWM mode 2.

---

## Findings

| ID | Sev | Where | Issue | Evidence | Fix |
|---|---|---|---|---|---|
| **R4C-01** | **MAJOR** | §3.4 "Injected groups trigger on TIM1_CC4, which fires on both the up- and down-count match = 48 kHz (the drives use every sample; the weapon uses the one centred in its low-side-on interval)"; §8 STM32 row; calcs.md l.95 | **Geometry makes this impossible, independent of the edge mechanics.**<br><br>**1. Where the two triggers can sit.** The two CC4 matches of a centre-aligned counter are symmetric about a TIM1 extreme, at t = CCR4 and t = 41.67 − CCR4.  They are evenly spaced (48 kHz) only when CCR4 = ARR/2, i.e. at t = 10.42 and 31.25 µs.<br><br>**2. Why that fails for both loads.** With in-phase slaving these two instants are the TIM8/TIM20 *peaks*, which are the drive low-side centres in PWM mode 1.  The weapon low-side centre is at a TIM1 *extreme* (t = 0 or 20.83 µs), always exactly 10.42 µs away from either trigger.<br><br>**3. Numbers with CCR4 = ARR/2.**<br>• Drive: the best case is a trigger exactly at c.  The +0.95 µs offset cannot be applied, because the up-count trigger moves later and the down-count trigger moves earlier.  This gives (1−D)·10.42 ≥ 2.2 − 0.05, so **D ≤ 79 %** instead of 88 %: about 1 m/s of top speed lost.<br>• Weapon: the up-count sample needs 20.83 − (1−D)·20.83 + 0.75 ≤ 10.47, i.e. D ≤ 53 %.  The down-count sample (31.30–32.77 µs) needs (1−D)·20.83 ≥ 11.94, i.e. **D ≤ 43 %**.  Weapon current control therefore fails above ~45 % duty (~11 k rpm of 25.6 k).<br><br>**4. Moving CCR4 toward ARR** to centre the weapon puts both triggers around the TIM1 peak.  That is a TIM8 valley, so the drives in mode 1 get no low-side sample at all.  With the drives in mode 2 they get two samples ~2δ apart and none in the other half-period, so the drive loop is effectively 24 kHz.<br><br>**Answers to the round's questions:**<br>• JEXTEN = 11 (both edges) exists (`LL_ADC_INJ_TRIG_EXT_RISINGFALLING`).<br>• TIM1_CH4 is a JEXTSEL source with no instance restriction (all five ADCs).<br>• TIM1_CH4 is **not** a regular trigger (R3C-01).<br>• Because the trigger is the OC4 output signal (see R4C-02), a PWM-mode OC4 does give two edges per centre-aligned period.<br>• The "both edges" part works.  What cannot work is the placement. | `ll_adc.h` l.1422, l.1630; community thread (trigger = channel output); SLVSH07 Table 8-6 / §8.3.9.1 (1.2 µs fixed delay); DRV8323 tSET 600 ns (20 V/V), tPD 150 ns; DESIGN §8 "≥ 1 µs after it opens + DLY_TARGET; duty ≤ ~88 %" | **Option A (recommended; no hardware change):**<br><br>**1. Move the drive low-side centres onto the TIM1 extremes.** Run TIM8/TIM20 in **PWM mode 2** (INH high around the TIM8 peak).  The drive low-side centres are then at the TIM8 valleys, t = 0 and 20.83 µs.  The weapon stays in PWM mode 1, with its low-side centre at t = 20.83 µs, so every second drive sample point coincides with the weapon centre.<br><br>**2. Take the injected trigger from TIM8.** Injected ← **TIM8_TRGO2**, with MMS2 = OC6REF, OC6M = PWM mode 2, CCR6 ≈ 155–162 counts (≈ 0.95 µs minus tLATR; trim on a scope) and JEXTEN = rising.<br>• This gives one trigger per TIM8 period, at every TIM8 valley + 0.95 µs, i.e. 48 kHz, evenly spaced.<br>• TIM8_TRGO2 is an injected source on all five ADCs (`ll_adc.h` l.1489, no instance note).<br>• It is derived from OC6REF, so it is not gated by MOE (R4C-02).<br><br>**3. Resulting duty limits.**<br>• Drives: ≤ 88 %, as now.<br>• Weapon: samples in [c_w + 0.95, c_w + 2.47] µs, which needs (1−D_w)·20.83 + 0.15 ≥ 2.47, so **D_w ≤ 88.6 %**.<br><br>**4. Regular trigger.** Keep the regular group on TIM1_TRGO2 (OC6REF), placed per R4C-04.<br><br>**Option B:** injected ← TIM1_TRGO2 with **MMS2 = 1101 "OC4REF rising or OC6REF falling"** (`ll_tim.h` l.932).<br>• OC4 PWM mode 2 with CCR4 ≈ 160 gives a trigger at valley + 0.95 µs.<br>• OC6 PWM mode 2 with CCR6 = ARR − 160 gives a trigger at peak + 0.95 µs.<br>• The regular group then needs another source: TIM8_TRGO2 or TIM20_TRGO2 (both regular sources on ADC1/2), or TIM1_TRGO after a one-shot trigger-mode start of TIM8/TIM20.<br><br>**Not recommended:**<br>• TIM1 at 48 kHz doubles the weapon switching loss (~1.1 → 2.2 W per switching FET at 20 A).<br>• TRGO/TRGO2 = update samples exactly at the centre, which limits the drives to D ≤ 79 %.<br><br>Update §3.4, the §8 STM32 row and calcs.md l.95. |
| **R4C-02** | **MAJOR** | §3.4 injected ← TIM1_CC4; §8 "Break (MOE = 0) with OISxN = 0 → coast", TIM1 BKIN = W_nFAULT (DRV8323 nFAULT + INA239 ALERT) | **The TIMx_CHy ADC triggers are the channel output (OC4 after CC4E/MOE gating), not OC4REF.**  TIM1_CC4 therefore needs CC4E = 1 **and MOE = 1**.  Every weapon break forces the TIM1 outputs to their idle state and so stops the injected trigger of **all five ADCs**:<br>• an SOVL (38 A) trip;<br>• a BOVL (19 V regen) trip;<br>• a DRV8323 fault;<br>• any firmware coast done with MOE = 0.<br><br>This also applies with AOE = 0, until firmware sets MOE again.<br><br>**Consequences:**<br>• The drive FOC loops lose their current samples, and their ISR if it runs on JEOS, exactly during a pack over-current or regen over-voltage event, while PWM continues at the last duty.<br>• ES0430 §2.7.7 (> 1 ms without a conversion → the next result is wrong) then also applies at restart.<br>• (The round-3 VERIFIED line "CC4E = 0 still lets the compare generate events" is wrong for the ADC trigger.) | ST community thread above ("the ADC is triggered by exactly the same signal which goes to the TIM_CHx pin"; needs CC4E and MOE; CCR4 = ARR gives no trigger).  RM0440 wording **UNVERIFIED**.  TRGO2 = OCxREF is internal (`ll_tim.h` l.923–934: "OCxREF signal is used as trigger output 2"). | Do not use a TIMx_CHy trigger for anything that must survive a break.  R4C-01 Option A or B fixes this: TRGO2/OC6REF on TIM8 or TIM1 is pre-output-stage and ignores MOE.  Add to §8: "ADC triggers come from TRGOx (OCxREF), never from TIMx_CHy, so a weapon or drive break does not stop current sampling."  If TIM8_TRGO2 is used, TIM8 must also never be stopped (the §2.7.7 1 ms rule now applies to TIM8). |
| **R4C-03** | **MINOR** | §3.4 "ES0430: all concurrently converting ADCs use the same synchronous clock (CKMODE = HCLK/4)"; §8 "CKMODE = HCLK/4" | **Only half of ES0430 §2.7.9 workaround 3 is followed.**<br>• ADC1/2 (dual) against ADC3/4/5 is an "other combination".  With a synchronous clock at a division ratio ≥ 2 it needs the same clock config **and** "trigger them with the same timer using the same clock prescaler division ratio (or its integer multiple) as the ADC prescaler".<br>• The timers run at 170 MHz (PSC = 0, which the 48 kHz / 3542-count plan implies).  The ADC prescaler is /4, so the condition is not met.<br>• This is the configuration in which mjbots measured periodic ~8-LSB errors. | ES0430 Rev 8 §2.7.9 (Description, both Notes, Workarounds 1–3); DS12288 Table 66: fADC ≤ 52 MHz with all ADCs on at VDDA ≥ 2.7 V, so HCLK/1 or /2 is not allowed and synchronous mode must be /4. | Use **workaround 2**:<br>• asynchronous clock, CKMODE = 00, **PRESC = 0000 (/1)**;<br>• ADC12SEL = ADC345SEL = **PLLP = 42.5 MHz** (HSI16 /4 × 85 = 340 MHz VCO; PLLR /2 = 170 MHz; PLLP /8 = 42.5 MHz).<br><br>Why this option:<br>• There is no condition on the timer prescaler, so the PWM keeps 170 MHz resolution.<br>• The trigger jitter is ±0.5 ADC cycle (12 ns).<br><br>Alternative: keep HCLK/4 and run the trigger timer with PSC = 3.  At 42.5 MHz, ARR8 = 442 and ARR1 = 884 (48.08 / 24.04 kHz), which leaves 442 duty steps per half-period.  Update §3.4 and §8. |
| **R4C-04** | **MINOR** | §3.4 "Regular groups … trigger on TIM1_TRGO2 (OC6REF) at a fixed weapon PWM phase"; §8 | **Nothing keeps the regular group out of the injected slots, and at 48 kHz injected there are twice as many slots.**  If an injected trigger lands during an ADC1/2 regular conversion, three problems follow:<br><br>(a) **Skewed start.** ADC1/2 start injected after tLATRINJ = 3.125 cycles; ADC3/4/5 (idle) start after tLATR = 2.125.  The ADC12 and ADC345 conversions are then one ADC clock (23.5 ns) out of phase, which is exactly the concurrency ES0430 §2.7.9 describes, on all 9 currents.<br><br>(b) **Channel 0 converted (Rev Y).** On **Rev Y (REV_ID 0x2002)**, ES0430 §2.7.8 case 1 applies: "injected conversion triggered while regular conversion is ongoing" converts channel 0 and returns 0.  Case 2 also applies: the master's first injected and the slave's first resumed regular conversion.  The result is a zero weapon-current reading in rank 1.<br><br>(c) **Resampling kick on the 1 nF nodes.** The aborted regular channel is resampled after the injected group (RM0440 wording **UNVERIFIED**).<br>• On the 1 nF W_Vx nodes (source 68k‖10k = 8.7 kΩ, τ = 8.7 µs), each sampling kicks the node by CADC/(1 nF) = 0.5 % of ΔV.<br>• ΔV is up to ~2 V from the previous channel, so the kick is ≈ 10 mV ≈ 12 LSB ≈ 80 mV at the phase.<br>• A second kick within ~2 µs does not recover.<br>• The 247.5-cycle rank 4 (5.8 µs) is the one most likely to be hit. | DS12288 Table 66 (tLATR CKMODE = 11: 2.125; tLATRINJ: 3.125; CADC 5 pF); ES0430 §2.7.8 (Rev Y "A", Z/X "−"), §2.7.9; DESIGN §3.4 (1 nF on W_Vx, 68k/10k) | State the allowed OC6 window in §8.<br>• With Option A the injected groups occupy t = 0.95–2.76 and 21.78–23.60 µs.<br>• The regular group takes 7.9 µs, or 8.7 µs with 24.5-cycle ranks 1–3.<br>• So TIM1 OC6 must fall at **t ∈ [2.9, 12.9] µs or [23.7, 33.8] µs**.<br><br>Add: "on Rev Y parts also insert a dummy first injected rank or confirm no collision (ES0430 §2.7.8)".  Use circular DMA for the regular CDR (§2.7.8 case 4). |
| **R4C-05** | **MINOR** | §2 "what ST's motor SDK, SimpleFOC and moteus-class firmware already run on"; §3.3 48 kHz FOC; §8 (no CPU budget) | **The CPU budget is tight and unstated.**<br><br>At 48 kHz the injected ISR has 3542 cycles.  Estimates for a lean float C loop on the M4F with CORDIC (zero-overhead sin/cos ≈ 30–40 cycles):<br>• ISR entry/exit + FPU stacking ≈ 40 cycles.<br>• 9 JDR reads + offsets/scaling ≈ 60 cycles.<br>• Per drive with the encoder (angle/PLL, Clarke/Park, 2 PI, inverse Park, SVPWM, CCR writes, limits) ≈ 450–650 cycles, plus ≈ 300–500 when its flux observer runs (hand-over near top speed).<br>• Weapon sensorless FOC + observer ≈ 900–1300 cycles, every other ISR.<br><br>Resulting load:<br>• **Peak ISR ≈ 2.1–2.9 k cycles (60–82 %)**.<br>• **Average ≈ 45–60 %** before UART/SPI/telemetry.<br>• With both drive observers active: **peak 2.7–3.9 k, i.e. 77–110 %**.  That is infeasible at the worst corner.<br><br>SimpleFOC (loopFOC in the main loop, float, no ISR-locked sampling) and a stock MCSDK dual-motor project will not reach 48 k + 48 k + 24 k on this part (**UNVERIFIED** vendor figures).  Flash at 170 MHz runs with 8 wait states; the ART only partly hides that. | Cycle counts are estimates.  Budget = 170 MHz / 48 kHz = 3542 cycles/ISR. | Add a §8 row:<br>• one injected-JEOS ISR (the drives every call, the weapon on alternate calls), running from **CCM SRAM**, bare-metal/LL;<br>• CORDIC used by that ISR only, or context saved if another ISR uses it;<br>• measure with DWT_CYCCNT at bring-up (§9 step 5), with a ≤ 70 % peak budget.<br><br>Fallbacks, in order:<br>1. decimate the drive observers to 24 kHz;<br>2. drive current loop at 24 kHz on 48 kHz PWM (averaging both samples);<br>3. weapon six-step above base speed.<br><br>Reword §2 so it does not imply that off-the-shelf SimpleFOC runs this. |
| **R4C-06** | **MINOR** | U6 SN74LVC08A inputs on W_ARM (C16 100 nF / R41 1 M, τ = 100 ms); §3.5 item 4; §8 W_ARM row | **The EXTI side is clean, but the AND gate is not.**<br><br>*PD2 (FT), EXTI side:*<br>• Armed, W_ARM ≈ 2.9–3.0 V.<br>• Ripple at 500 Hz is 29 mV with R41 alone (C16 alone supplies the low half-cycle).<br>• Worst-case datasheet leakage adds 3 × 5 µA from the LVC08 inputs, 0.15 µA from PD2 and the BAT54 IR.  That gives ≤ ~180 mV ripple, so min ≈ 2.75 V > **VIH = 0.7·VDD = 2.31 V**.<br>• Released, it reaches **VIL = 0.99 V** in ≤ 107 ms.<br>• VHYS is 200 mV (typ).<br>• A single clean edge is expected: the node is 100 nF, so impedance is low above a few Hz.  EXTI needs no external Schmitt.<br><br>*U6 (LVC08), gate side:*<br>• U6 has **no Schmitt inputs**, and TI specifies Δt/Δv ≤ 8 ns/V ("slow or noisy input … use a Schmitt-trigger device … to avoid excessive currents and oscillations").<br>• W_ARM decays at ~15 V/s (≈ 67 ms/V) through the gate threshold.<br>• In FOC mode CHxN is held **static high**, so while W_ARM crosses ~1.2–1.6 V every INLx can oscillate while INH is PWM-ing.<br>• When a hung compute board stops W_ARM_CLK, the gate is the first thing to act.  The MCU's command timeout (100–250 ms) comes later, and the MCU's Schmitt threshold may trip after the gate's. | DS12288 Table 54 (FT: VIL 0.3·VDD, VIH 0.7·VDD, VHYS 200 mV typ, Ileak ±150 nA); SN74LVC08A §5.3 Δt/Δv 8 ns/V, §7.3.2, II ±5 µA; netlist W_ARM = C16, D9.2, R41, TP6, U1.55, U6.2/5/10 | Hardware (one part):<br>• replace U6 with a Schmitt-input quad AND, e.g. **SN74HCS08** (TI HCS family; check LCSC stock/pinout, **UNVERIFIED**);<br>• or buffer W_ARM through a Schmitt gate before U6.<br><br>Firmware mitigation, if hardware is kept:<br>• set the **weapon** command timeout to ≤ 50 ms, shorter than W_ARM's ≥ 70 ms decay to the gate threshold;<br>• §3.5: the compute board sends an explicit weapon-stop frame whenever it stops W_ARM_CLK.<br><br>Then CHxN is already low when the gate input goes slow. |
| **R4C-07** | **MINOR** | §8 boot order "a fresh low→high ARM edge has been seen since this reset"; §3.5 item 4 | **There is no re-arm handshake after an MCU reset.**<br>• After a brown-out or IWDG reset, W_ARM is still high (τ 100 ms).<br>• The MCU needs a new edge, which requires W_ARM_CLK to stay idle for **≥ ~110–150 ms**, until W_ARM < VIL = 0.99 V (worst case).<br>• The compute board stops toggling only while the heartbeat is missing, and its heartbeat timeout is unspecified.<br>• A motor MCU that reboots and resumes its heartbeat in < 100 ms leaves the weapon **disabled for the rest of the match** with no indication.<br><br>This is safe, but a silent loss of function. | DS12288 VIL; R41/C16 τ = 100 ms; DESIGN §8 | Add to §8 and §3.5:<br>• the motor MCU reports "ARM edge required" in its status/heartbeat frame;<br>• on that flag, the compute board holds W_ARM_CLK low for ≥ 250 ms and then resumes;<br>• specify the heartbeat rate (e.g. 100 Hz) and the compute board's heartbeat timeout (e.g. 50 ms). |
| R4C-08 | NOTE | §3.4 "slaved to TIM1 through ITR0 (reset-synchronised, in phase)" | Mechanics, which firmware has to get right:<br>• TIM1 MMS = update (with RCR = 0 the UEV comes at both extremes; with RCR = 1 only at the valley; either works).<br>• TIM8/TIM20: SMS = reset, TS = ITR0.  TIM20's ITR0 = tim1_trgo is still **UNVERIFIED** (RM0440 Table 250 not retrieved).<br>• The phase stays locked, lagging by ~2 timer clocks (≈ 12 ns) of TRGI resync.<br>• Each reset also generates a TIM8 UEV (preload transfer, RCR reload, UIF), so set URS = 1.<br>• The 2 : 1 lock needs **ARR1 even and ARR8 = ARR1/2 exactly** (3542/1771).<br>• An equivalent option is SMS = trigger (start once): the timers share the APB2 timer clock and stay locked with no periodic resets.<br>• Option A additionally needs the drives in PWM mode 2 (R4C-01). | `ll_tim.h` l.905, 943–946, 965 | Add these five lines to §8. |
| R4C-09 | NOTE | §3.3 "(10 updates per electrical cycle at speed)"; §3.4 "Each regular group takes ~7.9 µs"; §8 regular VREFINT | Three small documentation points:<br>• **Updates per electrical cycle.** At 16.8 V no-load (5.9 kHz electrical) it is 48/5.9 = **8.1** updates per electrical cycle.  "10" is the 14 V figure (calcs.md l.137 says so).<br>• **Regular group time.** With ranks 1–3 at 24.5 cycles, the regular group takes 3 × 37 + 260 = 371 cycles = **8.7 µs**, not 7.9 µs.<br>• **VREFEN.** §8 does not mention VREFEN (ADC12_CCR), which VREFINT needs, or its ≤ 12 µs start-up (carried over from R3C-02). | DS12288 VREFINT table; DESIGN §3.3/§3.4 | Edit the three sentences. |
| R4C-10 | NOTE | §8 DRV8316C CTRL3 0x0A4E | CTRL3 bit 4 is **PWM_100_DUTY_SEL** (reset 0 = 20 kHz bootstrap refresh at 100 % duty; 1 = 40 kHz).  0x0A4E leaves it at 0.  This is harmless while firmware caps duty at 88 %.  If firmware ever uses 100 % (e.g. six-step or overmodulation), set it to 1 so the refresh stays clear of the 48 kHz sample slots, or say in §8 that 100 % is never used. | SLVSH07 Table 8-20 | Optional one-line note. |

---

## VERIFIED OK

**Header change (netlist).**
* J1.7 = SPARE1 → NC.
* J1.19 = W_ARM_CLK = C15.1 + R18 (100 k pull-down).
* **W_ARM** = C16, D9.2 (K2), R41, TP6, **U1.55 PD2** (pin type **FT**, EXTI-capable, no analog function) and U6 1B/2B/3B.
* The charge-pump level is valid for EXTI (see R4C-06 for the numbers).

**Pull-ups.**
* **R16 10 k on NRST.**
  * *Against the internal pull-up:* R16 sits in parallel with RPU 25–55 k, giving 7.1–8.5 k.  There is no conflict.
  * *Against an RP2040 pin in reset (~50 k pull-down):* NRST sits at 2.8–2.9 V, above VIH(NRST) = 0.7·VDD = 2.31 V.  Without R16 it would be 1.5–1.8 V, which is indeterminate.
  * *Internal reset pulse:* the internal pulse generator, the SWD probe and an open-drain RP2040 each sink only 0.33 mA extra.  With C67 = 100 nF, the value in DS12288 Figure 27, the pin still goes below VIL(NRST).  (Rule 5 of §3.5 — NRST open-drain only — is required.  A push-pull high from the compute board would block IWDG/software resets, per Figure 27 note 2.)
* **R17 10 k on MB_RX (PC5, TT_a, 3.6 V tolerant).**
  * With an RP2040 pull-down in reset, MB_RX idles at ≥ 2.75 V, above VIH = 2.31 V, so there are no false start bits.
  * A 3.3 V drive from the compute board is within TT limits.

**§8 register values.**

| Frame | Addr | Data | Ones | Parity |
|---|---|---|---|---|
| 0x0603 | 0x03 | 0x03 | 4 | even |
| 0x1019 | 0x08 | 0x19 | 4 | even |
| **0x0A4E** | **0x05** | **0x4E** | **6 (P = 0)** | **even** |
| 0x1915 | 0x0C | 0x15 | 6 (P = 1) | even |
| 0x087C | 0x04 | 0x7C | 6 | even |
| 0x097D | 0x04 | 0x7D | 8 (P = 1) | even |
| 0x0606 | 0x03 | 0x06 | 4 | even |

* **CTRL3 0x4E** (SLVSH07 Table 8-20) decodes as:
  * b6 reserved = 1 (reset value);
  * PWM_100_DUTY_SEL = 0;
  * OVP_SEL = 1 (22 V);
  * OVP_EN = 1;
  * SPI_FLT_REP = 1 (SPI faults **not** on nFAULT);
  * OTW_REP = 0 (OTW **not** on nFAULT, so it is polled).

  This matches the §8 text.
* **DLY_TARGET 0x5 = 1.2 µs** is TI's value for 200 V/µs (Table 8-6).
* **INA239 limits.**
  * **SOVL** 0x76C0 = 30400 × 1.25 µV = 38.0 mV = **38.0 A** at 1 mΩ.  This is inside ±40.96 mV (ADCRANGE = 1) and below 32767.
  * **BOVL** 0x17C0 = 6080 × 3.125 mV = **19.0 V**.
* **BOR level 4:** DS12288 VBOR4 falling is 2.76 / 2.81 / 2.86 V, so "~2.8 V" is correct.  It is an option byte, programmed once (§8, §9 step 2).

**ADC trigger facts** (from `ll_adc.h`).
* TIM1_CH4, TIM1_TRGO2, TIM8_TRGO2 and TIM20_TRGO2 are injected sources with no instance restriction.
* TIM1_TRGO2 and TIM8_TRGO2 are also regular sources.
* JEXTEN = both edges exists.
* DUAL = 00001 "combined regular simultaneous + injected simultaneous" exists (`LL_ADC_MULTI_DUAL_REG_SIM_INJ_SIM`).

**ES0430 §2.7.9 (full text now).**
* ADC1 and ADC2 in any dual mode other than alternate-trigger "do not impact one another whatever the clock source".  The dual-simultaneous choice for ADC1/2 is correct.
* ADC1/2 against ADC3/4/5 still needs workaround 2 or 3 (R4C-03).
* §2.7.3 (interleaved only) and §2.7.5 (10/8/6-bit) do not apply to this plan.
* §2.7.6 applies to Rev Z only.

**Dual-mode behaviour.**
* Injected simultaneous may interrupt regular simultaneous on both ADCs together, so ADC1/2 stay in lockstep with each other.  The problems are with ADC3–5 and Rev Y (R4C-04).
* The injected sequences are the same length on all five ADCs (3 ranks), and no pin is on both ADC1 and ADC2 in the same rank.

**Timing figures.**
* The injected group takes **1.76 µs**, and the regular group 7.9–8.7 µs.
* **fADC = 42.5 MHz ≤ 52 MHz** ("all ADCs operation, VDDA ≥ 2.7 V").
* Drive **D ≤ 88 %** holds exactly, with ~30 ns spare, **if** the trigger is at the low-side centre + 0.95 µs (Option A gives that).
* Weapon DRV8323 CSA tSET is 600 ns at 20 V/V, so the settling side of the weapon window is not limiting.

**Command link / heartbeat.**
* Timeout 100–250 ms, CRC + sequence number, coast on loss, and the compute board gating W_ARM_CLK on the MCU heartbeat are sound as a structure.
* Two gaps remain: the reset re-arm handshake (R4C-07) and the timeout ordering against the W_ARM decay (R4C-06).

**Other §8 items.**
* USART1 BRR = 170 MHz / 2 Mbaud = 85, exact.
* SPI3 /32 = 5.31 MHz, which is within the DRV8316C (tSCLK ≥ 100 ns) and INA239 (≤ 10 MHz) limits.
* The OPAMP5, VREFBUF-off, UCPD dead-battery and DBGMCU lines are unchanged from round 3 and still correct.

---

**Verdict: 0 BLOCKER, 2 MAJOR (R4C-01, R4C-02), 5 MINOR (R4C-03…07), 3 NOTE.**  Every fix is firmware or documentation except R4C-06's optional U6 swap.

Sources:
[ES0430 Rev 8 mirror](https://www.rxelectronics.sg/datasheet/9f/stm32g474rct3.pdf),
[stm32g4xx_hal_driver](https://github.com/STMicroelectronics/stm32g4xx_hal_driver),
[ST community: How to trigger ADC1 with TIM1_CH4?](https://community.st.com/stm32-mcus-products-25/how-to-trigger-adc1-with-tim1-ch4-17251),
[mjbots: STM32G4 ADC performance part 2](https://blog.mjbots.com/2023/07/24/stm32g4-adc-performance-part-2/),
[RM0440](https://www.st.com/resource/en/reference_manual/rm0440-stm32g4-series-advanced-armbased-32bit-mcus-stmicroelectronics.pdf) (not downloadable).
