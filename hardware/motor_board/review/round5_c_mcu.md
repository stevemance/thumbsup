# Round 5 (C): MCU timer/ADC plan and firmware contract, rev E

Scope: DESIGN.md rev E §3.3 (drive timing inputs), §3.4 (timers and ADC plan), §8 (firmware contract), checked against
round 4 (`round4_c_mcu.md`) and `CHANGES.md`.  No design file was edited.

Sources (all fetched or extracted this round):

* **RM0440 Rev 7** (Feb 2022), full PDF from the WeActStudio GitHub mirror (st.com still refuses the download).  Used:
  * Table 252 (TIM1/8/20 internal trigger connection), p.1081;
  * Table 65 "Interconnect 19" (ADC trigger assignment, ADC12 and ADC345), p.387;
  * §28.3.3 centre-aligned counting, p.1093;
  * slave-mode reset mode, p.1161;
  * TIMx_CR1 URS/UDIS/DIR, p.1169;
  * §28.3.31 ADC triggers;
  * §28.3.34 Debug mode;
  * ADC §21.4.x (trigger rules, Table 162, JQDIS);
  * OPAMP5 pin table.
  
  Round 4's RM0440 items that were UNVERIFIED are now checked against this manual.
* **ES0430 Rev 8** (rxelectronics.sg mirror), §2.7.1–2.7.9, §2.10.1, §2.12.1–2.12.4, full text.
* **DS12288 Rev 4** (`datasheets/STM32G474RET6.pdf`):
  * Table 66 (fADC, tLATR, tCONV, TTRIG);
  * Table 45 (LSI 29.5–34 kHz);
  * OPAMP table (TS_OPAMP_VOUT ≥ 200 ns, SR);
  * tS_vrefint ≥ 4 µs.
* **SLVSH07** (`datasheets/DRV8316C.pdf`):
  * §7.5 tPD, tDEAD and tSET;
  * §8.3.9.1 delay compensation and Figures 8-21/8-22;
  * §8.3.11 CSA ("when the low-side FET … is conducting"; sense-FET architecture);
  * §9.2.1.1.4.
* **SLVSDJ3D** (`datasheets/DRV8323.pdf`): tPD 150 ns, H/W dead time 100 ns, tSET 600 ns at 20 V/V.
* **stm32g4xx_hal_driver master**: `stm32g4xx_ll_adc.h` l.985, 1412, 1489, 5340–5360; `stm32g4xx_ll_tim.h` l.904–965.
* `ref/STM32G474RxTx_pins.xml` (PF0 = ADC1_IN10, PF1 = ADC2_IN10, PC3 = OPAMP5_VINP, PB7/PD2 = TIM8_BKIN, PC13 = TIM1_BKIN).

---

## Numeric timing diagram (rev E values)

Basis:

* 170 MHz timer clock, PSC = 0.
* TIM1: 2 × 3542 = 7084 clocks, **41.671 µs** (23 997.7 Hz).
* TIM8/TIM20: 2 × 1771 = 3542 clocks, **20.835 µs** (47 995.5 Hz).
* ADC clock 42.5 MHz, so one cycle is 23.53 ns.
* tLATR (CKMODE = 00) is 1.5–2.5 cycles = **35–59 ns** (DS12288 Table 66); the jitter is one ADC cycle.
* t = 0 is the TIM1 valley.

```
t (µs)   0        0.95   2.78          10.42         20.835   21.78  23.61        31.25          41.67
TIM1     valley ------------------- up ------------- PEAK -------------------- down ---------- valley
         (weapon HS centre, PWM1)                    (weapon LS centre)
TIM8/20  valley --- up ---------- PEAK ------------- valley --- up ---------- PEAK ---------- valley
         (drive LS centre, PWM2)                     (drive LS centre)
TRGO     reset TIM8/20 (MMS=update)                  reset TIM8/20                              reset
TRGO2(8) |--CCR6--^ inj ADC1-5 [0.95..2.78]          |--CCR6--^ inj [21.78..23.61]
                    rank1 0.95-1.29 (sampling)                 (weapon uses this one)
                    rank2 1.54-1.88
                    rank3 2.12-2.48
REG window        [2.74 ............ 12.99] = TIM1 OC6 PWM2 edge  |  [23.58 ........ 33.83] = OC6 PWM1 edge
REG group          +8.73 µs (3 x 37 + 260 cycles) +<=59 ns latency
```

The sampling intervals above span CCR6 = 155–162 and both latency extremes.  The injected group is 75 cycles
(1.765 µs).  Busy intervals: [0.947, 2.776] and [21.782, 23.611] µs.  Regular trigger windows, recomputed:

* the trigger must come after the injected group ends: t_r + 1.5 cycles ≥ 2.776;
* the group must finish before the next injected trigger: t_r + 2.5 cycles + 8.729 ≤ 21.782;
* the result is **[2.74, 12.99] µs and [23.58, 33.83] µs**.  §3.4's [2.9, 12.9] / [23.7, 33.8] lies inside with ≥ 90 ns of
  margin.  VERIFIED, but only for CCR6 = 155–162 (see R5C-05).

Drive low-side windows (DRV8316C, 3x PWM, DLY_TARGET T = 1.2 µs, CSA tSET ≤ 1 µs).  The INH-low interval is
±h around the valley, with h = (1 − D) × 10.42 µs.

* **i < 0 (current into the phase):** the LS FET conducts from −h + T to +h + T.
* **i > 0 (current out of the phase):** during both dead times the current is in the **LS body diode**.  The LS FET
  channel conducts only from −h + T + tDEAD to +h + T − tDEAD.

| D | h | valid, i < 0 | valid, i > 0 (tDEAD 0.5 typ) | valid, i > 0 (tDEAD 0.75 max) |
|---|---|---|---|---|
| 0.80 | 2.08 | [0.12, 3.28] | [0.62, 2.78] | [0.87, 2.53] |
| 0.83 | 1.77 | [0.43, 2.97] | [0.93, 2.47] | [1.18, 2.22] |
| 0.86 | 1.46 | [0.74, 2.66] | [1.24, 2.16] | [1.49, 1.91] |
| **0.88** | 1.25 | **[0.95, 2.45]** (the only case §3.4/§8 considered) | **[1.45, 1.95], 0.50 µs** | **[1.70, 1.70], 0 µs** |

Weapon (DRV8323RH, external shunts, tPD 150 ns, dead time 100 ns, tSET 600 ns typ at 20 V/V):

* At D_w = 88 % the LS window is peak ± 2.50 µs.
* Valid samples lie in ≈ [peak − 1.1, peak + 2.65] µs.
* The rank-3 sample ends at most at peak + 2.48 µs, which is **OK with 0.17 µs of margin**.  The limit is D_w ≈ 89 %.

---

## Findings

| ID | Sev | Where | Issue | Evidence | Fix |
|---|---|---|---|---|---|
| **R5C-01** | **MAJOR** | §3.4 "Duty limit ~88 % on all three channels"; §8 DRV8316C row ("≥ 1 µs after it opens + DLY_TARGET; duty ≤ ~88 %"); round 4 timing basis | **The 88 % drive cap ignores the DRV8316C dead time, and the CSA reads nothing during it.**<br><br>**1. Why dead time matters.** The DRV8316C CSA is a sense-FET mirror of the LS FET.  It measures the phase current only "when the low-side FET … is conducting".  When the phase current flows out of the phase (i > 0), the LS **body diode** carries it for tDEAD after the HS turns off, and again for tDEAD before the HS turns on.  With delay compensation the *OUT edges* sit at INH + T, so the LS **channel** conducts only from −h + T + tDEAD to +h + T − tDEAD.<br><br>**2. Numbers at 88 %.**<br>• tDEAD = 500 ns (typ, 200 V/µs): the valid window for i > 0 is **[1.45, 1.95] µs = 0.50 µs**.<br>• tDEAD = 750 ns (max): the window is **0 µs**.<br>• Rank 1 (ends 1.27–1.31 µs) is still settling.  Rank 3 (2.12–2.48 µs) samples after the LS has turned off (≤ 1.95 µs).  Only rank 2 is valid.<br><br>**3. Affected phases.**<br>• Drive L (ADC5: A rank 1, B rank 2, C rank 3): L_SOA and L_SOC are wrong for i > 0 near the cap.<br>• Drive R: R_SOC (rank 1) is wrong.<br>• At the SVPWM sector boundaries **two** phases sit at the cap together, so choosing the two lowest-duty phases does not avoid the problem.<br><br>**4. Result.** At top speed (the high-modulation corner the design is sized for) the drive FOC gets corrupted current samples.  That corner cannot be seen at the low-speed bring-up.<br><br>**5. Delay-compensation limit.** tPD + tDEAD is 1.15 µs typ but up to **1.05 + 0.75 = 1.8 µs max**.  The compensation can only *add* delay, so on a slow part (or a hot one) the 1.2 µs target is not reached.  The window then moves later by up to 0.6 µs, differently for each current direction. | SLVSH07 §8.3.11 / §8.3.11.1 (sense FET, "when the low-side FET … is conducting"); §7.5 tDEAD 500/750 ns and tPD 650/1050 ns at 200 V/µs; tSET 1 µs; §8.3.9.1 and Fig. 8-21/8-22 (the OUT edge is aligned, not the FET switching); §9.2.1.1.4 ("target = tpd + tdead").  Timing diagram above. | **Re-derive the cap with dead time** (the full sampling window after settling):<br>• the valid length is 2h − 2·tDEAD − tSET;<br>• 3 ranks need 1.47 µs + 1 ADC cycle of jitter.<br><br>Resulting cap:<br>• **Drive L: D ≤ ~83 % (typ tDEAD) / ~81 % (max)**.<br>• Drive R, which only needs ranks 1–2: ≤ 86 % / 84 %.<br><br>Keep the group centred on **valley + T + tSET/2 = +1.7 µs**.  That centre does not depend on D or tDEAD, so CCR6 ≈ 156 is right: keep the lower end of the 155–162 range.<br><br>Recover the lost headroom (about 6–8 % of line voltage) with bottom-clamped (flat-bottom) SVPWM.  The cap only limits the *maximum* duty, and the minimum is set by tMIN_PULSE 600 ns (2.9 %).  The line voltage is then limited by D_max − D_min ≈ 0.80, compared with 0.76 for a symmetric 12–88 %.<br><br>Optionally set **DLY_TARGET 0x8 (1.8 µs) ≥ worst-case tPD + tDEAD**, so the delay really is constant, and then re-trim CCR6 (≈ +102 counts; the regular windows move with it, R5C-05).<br><br>Update §3.4, the §8 DRV8316C row and calcs §10 (top speed at the new cap).  The weapon is unaffected: its shunts see diode current, and it is OK to ~89 %. |
| **R5C-02** | **MINOR** | §8 CPU budget: "fallback: drives at 32 kHz (still ≥ 6 updates per electrical cycle at 14 V)" | **The 32 kHz fallback breaks the §3.4 timer scheme.**<br>• §3.4 needs the TIM8/TIM20 period to be exactly half the TIM1 period (ARR 1771 vs 3542).  The weapon's current samples come from the TIM8 valley that coincides with the TIM1 peak.<br>• At 32 kHz, TIM8 would be 2656 clocks.  The TIM1 update resets (every 3542 clocks) would truncate every period.<br>• The TIM8 valleys would no longer land on the TIM1 peak, so the weapon would lose its low-side-centre samples.<br>• The regular non-overlap windows would be void.<br><br>(The 6.5 updates per electrical cycle at 14 V arithmetic is correct.) | §3.4; RM0440 reset mode p.1161; 170 MHz / 64 kHz = 2656.25 | Replace the fallback with ones that keep 48 kHz PWM and sampling:<br>1. drive current loops at 24 kHz on alternate ISRs, averaging both samples;<br>2. drive observers at 24 kHz;<br>3. weapon observer at 12 kHz.<br><br>If lower drive PWM is ever wanted, it must be 24 kHz (TIM8 = TIM1 period, drives sampled at the TIM1 valley).  That needs a second injected trigger at the TIM1 peak for the weapon, so it is a different §3.4. |
| **R5C-03** | **MINOR** | §8 Watchdog row "IWDG ~20 ms, refreshed only from the control loop"; boot order "start the IWDG first" | **Refreshing only from the control loop leaves the failsafe unwatched, and the boot phase unspecified.**<br><br>(a) If "control loop" means the 48 kHz JEOS ISR, a hung **main loop** keeps the IWDG fed while the motors run at the last command.  The main loop holds UART parsing, the 100–250 ms command timeout, the DRV8316 readback, OTW and fault counters.<br>• Only the compute board's heartbeat → W_ARM_CLK/NRST path catches it.  That removes the weapon in 100–160 ms, but the drives only on an NRST pulse.<br><br>(b) Started "first", the IWDG must survive the pre-timer boot, which has no control loop:<br>• clocks;<br>• t_READY 1 ms;<br>• DRV8316 ×2 and INA239 SPI setup;<br>• W_EN wake (~1 ms nFAULT);<br>• ADC calibration and regulator start-up.<br><br>That is probably < 20 ms, but the contract forbids the only refresh points.<br><br>LSI is 29.5–34 kHz, so 20 ms nominal is 18.8–21.7 ms. | DS12288 Table 45; DESIGN §8 command-link and watchdog rows | State the rule precisely:<br>• the main loop refreshes the IWDG only when the ISR tick counter **and** each main-loop task checkpoint have advanced since the last refresh (task-flag watchdog);<br>• the command-timeout check runs in the ISR (or SysTick), not the main loop;<br>• boot refreshes explicitly between steps.<br><br>Also:<br>• the HardFault/NMI handlers force safe outputs at once (TIM1/TIM8 MOE = 0, DRV_OFF high) instead of waiting ≤ 22 ms for the IWDG;<br>• debug builds set DBGMCU_APB1FZR.DBG_IWDG_STOP, otherwise every breakpoint resets. |
| **R5C-04** | **MINOR** | §8 W_ARM_S row: "EXTI both edges … firmware still ignores pulses < 1 ms.  On ARM low: full weapon stop …; re-arm needs an explicit restart and a new ARM edge" | **The rule is ambiguous in exactly the case it exists for.**<br><br>*Read one way:* "ignore pulses < 1 ms" also applies to a low pulse.<br>• U6 hardware Hi-Zs the weapon during the pulse, but firmware keeps CHxN high and its current controllers integrating.<br>• When W_ARM_S returns, the hardware re-enables the bridge **without** the "explicit restart and new ARM edge" that the next sentence requires.<br>• The controllers have wound up meanwhile.<br><br>*Read the other way:* the stop is delayed 1 ms to debounce, which is pointless given U14's Schmitt edges.<br><br>U14 plus the 2.2 µF node make genuine < 1 ms lows implausible, so any that appears is EMI or a fault and should be handled conservatively. | DESIGN §8 W_ARM_S row, §2 interlock (INLx = CHxN AND W_ARM_S) | Say it explicitly:<br>• **falling edge acts immediately and latches**: CHxN low, controllers reset, "ARM edge required" set;<br>• the **rising edge is qualified**: high for ≥ 1 ms, and a fresh edge since the latch or reset.<br><br>Also re-sample the PD2 level in the ISR each cycle as a backup to the EXTI. |
| **R5C-05** | **MINOR** | §3.4 regular windows "t ∈ [2.9, 12.9] or [23.7, 33.8] µs"; §3.4 "CCR6 ~155–162"; §8 STM32 row | **The windows are only valid for one CCR6, and R4C-04's Rev Y items were dropped.**<br><br>(a) The absolute windows are correct for CCR6 = 155–162 (recomputed: [2.74, 12.99] / [23.58, 33.83]).  Two changes would silently invalidate them:<br>• a re-trim of CCR6 (R5C-01, or a different DLY_TARGET → +0.6 µs);<br>• 12.5-cycle regular ranks.<br><br>(b) R4C-04's Rev Y guidance was not carried into rev E (CHANGES.md lists only the windows).  ES0430 §2.7.8 (Rev Y, REV_ID 0x2002) still has live cases:<br>• **case 3**: the first conversion after ADSTP/JADSTP, e.g. any reconfiguration or offset re-measurement that stops the ADC;<br>• **case 4**: the first conversion after a DMA end-of-transfer in **one-shot** DMA mode, which is the HAL default for `HAL_ADCEx_MultiModeStart_DMA` with a normal-mode channel;<br>• **cases 1/2**: a collision during start-up, before TIM8 is phase-locked or while CCR6 is being trimmed.<br><br>Each gives a zero weapon or drive current sample. | ES0430 §2.7.8 (Rev Y "A", Z/X "−") and its workarounds; DS12288 Table 66; timing diagram above | (a) Write the windows relative to the injected trigger:<br>• t_r ∈ [t_inj + 1.85 µs, t_inj + T8 − t_reg − 0.06 µs], with t_inj = CCR6 / 170 MHz;<br>• t_reg = 8.73 µs, or 7.88 µs with 12.5-cycle ranks 1–3.<br><br>(b) Add to §8:<br>• regular results by **circular** DMA or read in the JEOS/EOS ISR;<br>• never ADSTP/JADSTP without ADDIS → ADEN (hardware dummy conversion);<br>• start TIM1 only after TIM8/TIM20 are armed (R5C-N1), so there is no collision at start-up;<br>• on Rev Y, discard the first injected and regular results after every (re)start. |
| R5C-N1 | NOTE | §3.4/§8 "reset-slaved to TIM1 through ITR0 (URS = 1)" | **The mechanics work, but TIM1's MMS and the start sequence are still not written down** (R4C-08 asked for them).<br><br>*What is verified:*<br>• **TIM20 ITR0 = tim1_trgo** (also TIM8), now verified.<br>• With **TIM1 MMS = 010 (update)** and RCR = 0, TRGO fires at *both* TIM1 extremes, i.e. every 3542 clocks.  Both are TIM8 valleys, so every reset coincides with TIM8's own underflow (CNT → 0, then up-counting).  In steady state the reset therefore changes neither direction nor phase.  TIM8 lags TIM1 by the fixed TRGI resync delay (a few timer clocks, ~10–20 ns).  You do not need exactly one reset per TIM1 period.  RCR = 1 gives one (at whichever extreme the RCR phase lands on, also a TIM8 valley).<br>• RM0440 says a slave-mode reset makes the "counter restart counting from 0".  It does not say what DIR does if a reset lands mid-down-count.  That can only happen at start-up or after an ARR/CNT write, and the next reset re-locks it (DIR behaviour **UNVERIFIED**).<br>• URS = 1 only suppresses UIF/DMA; the preload transfer still happens (TIMx_CR1 URS/UDIS).  OC6REF (PWM mode 2) is inactive on both sides of the reset, so there is no spurious TRGO2.<br>• Gated mode is wrong here.  Trigger mode (SMS = 0110 with MMS = enable) also locks, since both timers use the same clock and an exact 2 : 1 ratio, but it does not self-heal. | RM0440 Table 252; §28.3.3 p.1093 ("…by using the slave mode controller… the counter restarts counting from 0"); p.1161; CR1 URS/UDIS p.1169; `ll_tim.h` l.905, 928, 943–947, 965 | Add to the §8 STM32 row:<br>• TIM1 CR2 MMS = 010 (update), MMS2 = 1001 (OC6REF);<br>• TIM8/TIM20 SMS = **1000 (combined reset + trigger)**, TS = ITR0, MSM = 0 (ES0430 §2.12.1 only concerns MSM = 1 + OPM);<br>• TIM8/TIM20 CNT = 0 and CEN left to the trigger; then start TIM1 with UG, which starts and aligns the drives in one step.<br><br>Also: never use OCREF_CLR on TIM8/TIM20 (e.g. a COMP-based current limit), because ES0430 §2.12.4 breaks it in reset slave mode. |
| R5C-N2 | NOTE | §3.3 line 195 "48 kHz PWM/FOC (10 updates per electrical cycle at speed)" | The text is stale.  R4C-09 was fixed in §4 and calcs (8.2 at 16.8 V, 9.8 at 14 V), but not in §3.3. | DESIGN.md l.195 vs l.352, calcs.md l.136 | "8–10 updates per electrical cycle". |
| R5C-N3 | NOTE | §8 STM32 row, boot "offsets" | **ES0430 §2.7.7 (> 1 ms since calibration or the previous conversion) applies at boot and after every debug halt** (DBGMCU freezes the trigger timers).  Calibration comes before the ≥ 1 ms DRV8316 t_READY and the other setup, so the first injected and regular results are suspect. | ES0430 §2.7.7; DS12288 TTRIG ≤ 1 ms | Discard the first few samples of each group after start or resume before accumulating offsets.  Also, with JQDIS = 1, set JQDIS **before** writing JSQR, because setting it flushes JSQR (RM0440 ADC_CFGR bit 31). |

---

## Answers to the round's questions

1. **Timer relationships.**
   * *Resets and phase.*  With TIM1 MMS = update, the reset arrives on every TIM8 valley, where TIM8's counter is already 0.  In steady state it disturbs neither direction nor phase (lag ≈ resync delay).  Details and the recommended SMS = combined reset + trigger are in R5C-N1.  One reset per TIM1 period is not needed.
   * *TIM20 ITR0.*  **TIM20 ITR0 = tim1_trgo**, VERIFIED in RM0440 Table 252.
   * *TIM8_TRGO2.*  TIM8_TRGO2 = OC6REF with OC6 in PWM mode 2 rises once per TIM8 period, at valley + CCR6.
   * *Injected trigger source.*  **JEXTSEL = 10 is tim8_trgo2 on both ADC1/2 and ADC3/4/5** (RM0440 Table 65; `LL_ADC_INJ_TRIG_EXT_TIM8_TRGO2`, no instance note).
   * *Regular trigger source.*  EXTSEL = 10 is tim1_trgo2 for the ADC1/2 regular group.
2. **Sampling instants.**
   * *Weapon at 88 %:* works (0.17 µs margin, limit ≈ 89 %).
   * *Drive at 88 %:* does **not** work once the DRV8316 dead time is included (R5C-01).  The cap is ~81–83 % for drive L and 84–86 % for drive R.
   * *CCR6:* ≈ 156 is the correct centre.
3. **Regular windows.**
   * They were recomputed and are correct (above).  There is no overlap for CCR6 = 155–162.
   * The 247.5-cycle rank fits: the group is 8.73 µs within a 19.0 µs injected-free gap.
   * VREFINT gets 5.82 µs, which meets tS_vrefint ≥ 4 µs.
   * The windows need to be tied to CCR6 (R5C-05).
4. **ES0430.**
   * *Workaround 2.*  Workaround 2 ("same clock source for all ADC instances running concurrent conversions and prescaler division ratio one") has **no condition on the trigger or on dual mode**.  ADC12SEL = ADC345SEL = PLLP with PRESC = 0000 satisfies it for all five ADCs, with ADC1/2 in dual simultaneous mode.  VERIFIED.
   * *Remaining errata:*
     * §2.7.8 Rev Y cases 3/4 (and 1/2 at start-up): R5C-05.
     * §2.7.7: R5C-N3.
     * §2.7.6: **Rev Z only**.  Reject Rev Z (REV_ID 0x2001) parts at bring-up; §7.12 already reads REV_ID.
     * §2.7.1/2.7.2: not applicable with JQDIS = 1.
     * §2.7.3: interleaved mode only, not applicable.
     * §2.7.5: 10/8/6-bit only, not applicable.
     * §2.10.1: OPAMP PGA mode only; "not observed in … follower mode", so it does not apply.
5. **§8 items.**
   * IWDG: R5C-03.
   * Fault counters: consistent.  With AOE = 0 every DRV8323 "retry" is a firmware MOE re-enable, so counting is under firmware control.  The INA239 ALATCH holds BKIN until DIAG_ALRT is read.
   * CPU budget: the numbers are plausible, but the 32 kHz fallback is wrong (R5C-02).
   * W_ARM_S EXTI: R5C-04.
6. **Other.**  See R5C-N1 (MMS/start sequence), R5C-N2 and R5C-N3.

---

## VERIFIED OK

* TIM1 ARR 3542 / TIM8, TIM20 ARR 1771: exact 2 : 1 (7084 vs 3542 clocks); 23 997.7 Hz / 47 995.5 Hz.
* RM0440 Table 252: TIM8 and TIM20 ITR0 = tim1_trgo.
* RM0440 Table 65:
  * JEXTSEL 10 = tim8_trgo2 on ADC12 **and** ADC345;
  * EXTSEL 10 = tim1_trgo2 on ADC12.
* LL: `LL_TIM_TRGO_UPDATE` (MMS = 010), `LL_TIM_TRGO2_OC6` (MMS2 = 1001), `LL_TIM_SLAVEMODE_RESET` / `COMBINED_RESETTRIGGER`, `LL_TIM_TS_ITR0`.
* TRGO2/OC6REF are pre-output-stage.  RM0440 §28.3.34 confirms that stopping or breaking acts on the *outputs* "as if MOE was reset", so the ADC triggers keep running through a break.
* TIM8_TRGO2 with OC6 in PWM mode 2 gives one rising edge per TIM8 period at valley + CCR6.  JEXTEN = rising.
* ADC clock:
  * PLLP = 340 MHz VCO / 8 = 42.5 MHz;
  * fADC ≤ 52 MHz for all-ADC operation at VDDA ≥ 2.7 V;
  * adc_hclk (170 MHz) ≥ fADC / 4.
* ES0430 §2.7.9 workaround 2 satisfied: same source (PLLP), /1, all five ADCs.  ADC1/2 dual simultaneous is exempt in any case.
* The injected group is 75 cycles = 1.765 µs.  The 12.5-cycle rank (294 ns) is ≥ 200 ns for the OPAMP5 internal output.  OPAMP5 VINP2 = PC3 and VOUT internal = ADC5_IN3 (RM0440 OPAMP table).
* Dual-mode rules:
  * injected lengths are equal;
  * the same channel is never sampled on ADC1 and ADC2 in the same rank (PA0 is rank 1 on ADC1 and rank 2 on ADC2);
  * regular ranks 1–4 have equal sampling times on ADC1/ADC2.
* Regular group:
  * 371 cycles = 8.73 µs;
  * rank 4 at 247.5 cycles is 5.82 µs, which meets the VREFINT ≥ 4 µs requirement;
  * VREFINT is on ADC1 (RM0440: ADC1/3/4/5).
* Channels: PF0 = ADC1_IN10, PF1 = ADC2_IN10, PB11 = ADC12_IN14, PA3 = ADC1_IN4, PA4 = ADC2_IN17, PA5 = ADC2_IN13, PA6 = ADC2_IN3, PB12 = ADC4_IN3, PB13 = ADC3_IN5, PB1 = ADC3_IN1, PA8/PA9 = ADC5_IN1/IN2.
* Weapon sampling at the TIM1 peak: works at D_w = 88 % (external shunts carry the diode current too; tSET 600 ns at 20 V/V).
* Regular trigger windows [2.9, 12.9] / [23.7, 33.8] µs: inside the recomputed [2.74, 12.99] / [23.58, 33.83] for CCR6 155–162.
* Fault counters and latch-off: consistent with AOE = 0 and ALATCH = 1.
* IWDG with LSI /4 and reload ≈ 159: 18.8–21.7 ms over the LSI tolerance.
* The DBGMCU freeze note ("drives braking, weapon coasting") matches RM0440 §28.3.34 (outputs disabled as if MOE = 0, i.e. idle states).

---

**Verdict: 0 BLOCKER, 1 MAJOR (R5C-01), 4 MINOR (R5C-02…05), 3 NOTE.**  All fixes are firmware or documentation; no
hardware change is needed.

Sources:
[RM0440 Rev 7 (WeActStudio mirror)](https://github.com/WeActStudio/WeActStudio.STM32G474CoreBoard/blob/master/Doc/STM32G4_Referencemanual_RM0440.pdf),
[ES0430 Rev 8 mirror](https://www.rxelectronics.sg/datasheet/9f/stm32g474rct3.pdf),
[stm32g4xx_hal_driver](https://github.com/STMicroelectronics/stm32g4xx_hal_driver),
[ST community: G431 TIM1 ITR1](https://community.st.com/stm32-mcus-motor-control-34/where-does-g431-tim1-itr1-acturlly-from-132684).
