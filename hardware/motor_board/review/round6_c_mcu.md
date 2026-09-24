# Round 6 (C): MCU timer/ADC plan and firmware contract, rev F

Scope: DESIGN.md rev F §3.4 (timers/ADC), §3.5 (compute-board requirements, self-test), §8 (firmware contract), §9
(bring-up), checked against `round5_c_mcu.md` and `CHANGES.md` (round 5 → rev F).  No design file was edited.

Sources used this round:

* **SLVSH07** (`datasheets/DRV8316C.pdf`):
  * §8.5.1.1 SPI format (B15 W0, B14–B9 address, B8 even parity);
  * Tables 8-18…8-24 (CTRL1–CTRL6, CTRL10 fields and resets);
  * Table 8-3 (6x truth table), Table 8-6 (DLY_TARGET per slew rate);
  * §7.5 tPD 650/1050 ns and tDEAD 500/750 ns at 200 V/µs, tREADY 1 ms, tSCLK ≥ 100 ns;
  * §8.3.14.1 (VM UVLO → NPOR), l.3591 (SDO Hi-Z with nSCS high).
* **SLYS027A** (`datasheets/INA239.pdf`): SOVL/BOVL scaling, SHUNT_CAL eq. 1, DIAG_ALRT bits, SPI edges.
* **DS12288** (`datasheets/STM32G474RET6.pdf`): flash tERASE 22.02 / 24.47 ms.
* **RM0440 Rev 7** (the WeActStudio mirror, the copy fetched in round 5):
  * SYSCFG_CFGR2 bit 0 CLL (Cortex-M4 LOCKUP → TIM1/8/15/16/17/20 break);
  * §25.3.1 and §25.3.7 (OPAINTOEN and calibration; the OPAMP6 pin table).
* **ES0430 Rev 8**: §2.7.1–2.7.9, §2.10.1, §2.12.1–2.12.4, and the summary table (Rev Z / Y / X columns).
* **stm32g4xx_hal_driver master** `Src/stm32g4xx_hal_opamp.c`: l.666 and l.698–699 (`HAL_OPAMP_SelfCalibrate` refuses to run with OPAMPINTEN set).
* Design files:
  * `design/nets.md` l.125–126 (W_ARM_CLK reaches only C15/R18/J1.19; W_ARM_S goes to PD2);
  * `design/mcu_pinmap.md` (all 64 pins used);
  * `design/calcs.md` §10.

---

## 1. Re-check of the rev F fixes

### 1a. Drive duty caps 81 % (L) / 84 % (R) with flat-bottom SVPWM

This uses round 5's model:

* timings: 170 MHz timers, 42.5 MHz ADC, tLATR 1.5–2.5 cycles, 12.5 + 12.5 cycles per rank;
* DLY_TARGET T = 1.2 µs and CSA tSET 1 µs;
* the valid window for both current directions is [−h + T + tDEAD + tSET, h + T − tDEAD], with h = (1 − D) × 10.4175 µs.

The injected rank sampling intervals are:

| CCR6 | rank 1 | rank 2 | rank 3 |
|---|---|---|---|
| 155 | 0.947–1.265 µs | 1.535–1.853 µs | 2.124–2.441 µs |
| 156 (the centre) | 0.953–1.271 µs | 1.541–1.859 µs | 2.129–2.447 µs |
| 162 | 0.988–1.306 µs | 1.576–1.894 µs | 2.165–2.482 µs |

The resulting caps at CCR6 = 156:

| Samples used | tDEAD 500 ns (typ) | tDEAD 750 ns (max) |
|---|---|---|
| Drive L, ranks 1–3 (ADC5 A/B/C) | 83.2 % | **80.8 %** |
| Drive R, C at rank 1 (or rank 3) | 83.2 % | **80.8 %** |
| Drive R, **rank 2 only** (A on ADC4 + B on ADC3, C = −A − B) | 88.9 % | **86.5 %** |

* **L at ~81 %: VERIFIED.**  The exact worst case is 80.5–80.8 % over CCR6 = 155–162.
* **R at 84 % is not supported by the stated derivation**; see R6C-01.

### 1b. DLY_TARGET 1.8 µs option, frame 0x1818

* 0x1818 decodes as W0 = 0, address 0x0C (CTRL10), P = 0, data 0x18: DLYCMP_EN = 1 and DLY_TARGET = 8h = 1.8 µs (Table 8-24).
* The whole word has four 1-bits, so it has **even parity: correct**.
* 1.8 µs equals the worst-case tPD + tDEAD at 200 V/µs (1.05 + 0.75 µs).
* The option's side effects on CCR6, the weapon samples and the regular windows are not written down: see R6C-02.

### 1c. CTRL4 0x0D10 and CTRL5 0x0F00

Every frame in the §8 sequence was decoded and its parity recomputed:

| Frame | Register | Data | Meaning | Parity |
|---|---|---|---|---|
| 0x0603 | CTRL1 | 03 | unlock | even ✓ |
| 0x1019 | CTRL6 | 19 | BUCK_PS_DIS, BUCK_CL 150 mA, BUCK_SEL 3.3 V, BUCK_DIS | even ✓ |
| 0x0A4E | CTRL3 | 4E | reserved bit 6 = 1 (its reset value), PWM_100 = 0, OVP_SEL 22 V, OVP_EN, SPI_FLT_REP = 1 (off nFAULT), OTW_REP = 0 | even ✓ |
| **0x0D10** | CTRL4 | 10 | DRV_OFF bit 0, OCP_CBC 0, OCP_DEG 0.6 µs, retry 5 ms (unused), OCP_LVL 16 A, OCP_MODE latched | even ✓ |
| **0x0F00** | CTRL5 | 00 | CSA 0.15 V/A, ASR/AAR off | even ✓ |
| 0x1915 | CTRL10 | 15 | DLYCMP_EN, 1.2 µs | even ✓ |
| 0x1818 | CTRL10 | 18 | DLYCMP_EN, 1.8 µs | even ✓ |
| 0x087C | CTRL2 | 7C | reserved bits 7–6 = 01 (their reset value), SDO push-pull, SLEW 200 V/µs, 3x mode | even ✓ |
| 0x097D | CTRL2 | 7D | the same + CLR_FLT | even ✓ |
| 0x0606 | CTRL1 | 06 | REG_LOCK | even ✓ |

All **VERIFIED**.  The recovery sequence 0603 → 097D → 0606 is correct: while locked, the device ignores writes to anything except CTRL1 bits 2–0 (Table 8-18).

### 1d. IWDG task-flag scheme and HardFault safe state

**The rule is correct.**
* The main loop refreshes the IWDG only when every task has checked in, including the ISRs and the command-timeout handler.
* A hung main loop, a stalled ISR or a dead timeout handler therefore each lead to a reset.
* Boot refreshes the IWDG explicitly, and debug builds freeze it.

**The HardFault state is correct in intent.**
* DRV_OFF high puts both drives in coast.
* TIM1 MOE = 0 with OISxN = 0 drives INL low, so the weapon coasts.

**Gaps:**
* The handler can itself fault (stack overflow → lockup), and nothing forces the outputs off in hardware.  See R6C-N1.
* Flash erase is longer than the IWDG period.  See R6C-N2.

### 1e. W_ARM_S falling-edge handling

**VERIFIED.**
* A falling edge acts at once and latches.
* Only the rising edge is qualified (≥ 5 ms), and a new edge is needed since the latch.
* The PD2 EXTI (line 2) is alone on its line.
* R_nFAULT is on EXTI15, a different line.

### 1f. Timed self-test

**Not implementable as written; see R6C-03.**
* The MCU never sees W_ARM_CLK: `nets.md` l.125 has W_ARM_CLK only on C15, R18 and J1.19.
* So the MCU cannot know when the toggling stopped, and cannot "time the falling edge after the toggling stops".
* It can only time-stamp, or age, the PD2 edge.  The interval has to be formed on the compute board.

### 1g. CPU fallback

**VERIFIED.**
* The fallback keeps 48 kHz PWM, the 2 : 1 lock and the sampling.
* Only the loop rates change.
* The consequence for the update rate is in R6C-N5.

### 1h. ADC errata handling

**VERIFIED** against ES0430:
* **Circular DMA and ADDIS/ADEN** instead of a bare ADSTP cover §2.7.8 cases 3 and 4 (Rev Y).
* **Non-overlapping triggers** cover cases 1 and 2.
* **JQDIS before JSQR** covers §2.7.1 and §2.7.2.
* **Discarding the first sample after a start or halt** covers §2.7.7.
* **Rejecting Rev Z** covers §2.7.5 and §2.7.6 (Rev Z only).
* **§2.10.1** is PGA-only.  OPAMP5's VINM0 is PB15 = W_INLC_M, a toggling pin, but the follower mode is exempt.

There is a new trap in OPAMP calibration; see R6C-05.

### 1i. TIM1 MMS and slave start

**VERIFIED.**
* The settings are TIM1 MMS = update and TIM8/TIM20 SMS = 1000, TS = ITR0.
* Either start order locks at the first TIM1 update: the first TIM1 update is the TIM1 peak, which is a TIM8 valley.
* The wording "slaves enabled first" is ambiguous (arm SMS with CEN = 0, or set CEN).  Both work.  The samples taken before lock are covered by the discard rule.  Clarify in passing (R6C-N6).

---

## 2. Findings

| ID | Sev | Where | Issue | Evidence | Fix |
|---|---|---|---|---|---|
| **R6C-01** | **MINOR** | §3.4 l.280–282 "drives ~81 % (L…) / ~84 % (R)"; l.295 "Drive R: A is simultaneous with C and B"; §8 DRV8316C row | **The 84 % cap for drive R does not follow from the ranks as written.**<br><br>**Where 84 % came from.** It is round 5's figure for a centred rank 1–2 span: 0.88 µs + jitter.<br><br>**Why it does not hold.**<br>• CCR6 is one value, shared by all ADCs, and it is centred on **L's** 3-rank group at valley + T + tSET/2 = 1.7 µs.<br>• R's rank 1–2 span (0.95–1.89 µs) is therefore 0.28 µs early.<br>• R_SOC is only on ADC3 ranks 1 and 3, and both are 0.59 µs off-centre.<br>• A measured C is valid only up to **80.8 %** (max tDEAD) or 83.2 % (typ), the same as L.<br>• At 84 %, the valid window for i > 0 at max tDEAD is [1.28, 2.12] µs.  Rank 1 ([0.95, 1.29]) and rank 3 ([2.13, 2.48]) both fall outside it.<br><br>**A firmware author who reads l.295 literally** takes A and C from rank 1, and at 81–84 % gets corrupted currents at top speed.<br><br>**What does work.** Rank 2 alone (ADC4 R_SOA + ADC3 R_SOB, centred at 1.70 µs) with C = −(A + B), which is valid for a 3-wire motor.  The R cap is then **86.5 % (max tDEAD) / 88.9 % (typ)**, so 84 % is safe **only** with that reconstruction. | Table in §1a (computed from CCR6 = 155–162, tLATR 1.5–2.5 cycles, 25 cycles per rank); SLVSH07 §7.5 tDEAD 500/750 ns; §3.4 ADC table (ADC3: C/B/C, ADC4: A/A/A) | In §3.4 and §8, say that drive R uses the **rank-2 pair (A, B) and reconstructs C**, with cap ~86 %.  Use rank 1/3 C only as a plausibility check below ~80 %.<br><br>Also say "L ≤ ~80.5 % worst case" (or keep "~81 %" with CCR6 trimmed to the centre). |
| **R6C-02** | **MINOR** | §8 DRV8316C row, l.549: "0x1818 = 1.8 µs covers the worst-case delay if bench scope shows the 1.2 µs target is not held"; §3.4 l.279 regular windows | **The 1.8 µs option moves every sampling instant, and the text does not say what else must change.**<br><br>**CCR6 and the regular windows.** The drive centre moves to 1.8 + 0.5 = 2.3 µs, so CCR6 ≈ 258–264 (+102 counts).  Then:<br>• the injected busy interval becomes [1.55, 3.38] µs;<br>• the regular windows become **[3.34, 13.59] / [24.18, 34.43] µs**;<br>• a regular trigger left in the documented [2.9, 12.9] window starts **while the injected group is still converting**.  On Rev Y silicon that is ES0430 §2.7.8 case 1, which returns zero samples.  §3.4's "recompute if CCR6 moves" covers this in principle, but the §8 option sentence does not point to it.<br><br>**Weapon cap.** The weapon uses the same trigger at the TIM1 peak.  Rank 3 would end at peak + 3.08 µs, beyond the valid peak + h_w + 0.15 µs at 88 % (peak + 2.65).  The weapon cap drops to **85.9 %**, unless the weapon uses ranks 1–2 only: A+B and C+A give all three phases, and the limit stays at 88.7 %.<br><br>**The decision criterion.** "Bench scope shows 1.2 µs not held" cannot find the worst case, because tPD + tDEAD reaches 1.8 µs only at process and temperature corners (1.05 + 0.75 max).  One board at room temperature will usually hold 1.2 µs. | SLVSH07 §7.5, Table 8-6, Table 8-24; round 5 weapon window (valid ≈ [peak − 1.1, peak + 2.65] at 88 %); ES0430 §2.7.8 case 1 (Rev Y "A"); computed windows above | Either:<br>• make 1.8 µs (0x1818) the default: it holds by specification and costs 0.6 µs of latency;<br>• or keep 1.2 µs and accept that the caps are typical-part figures.<br><br>If 1.8 µs is used, list the knock-on changes in one place:<br>• CCR6 ≈ 258–264;<br>• regular windows [3.4, 13.5] / [24.2, 34.4] µs, or the relative formula (R6C-N4);<br>• the weapon uses injected ranks 1–2 only. |
| **R6C-03** | **MINOR** | §3.5 item 4 "Boot self-test (timed)… The motor MCU times the PD2 falling edge and reports it"; §8 W_ARM_S row "Time the falling edge after the toggling stops and report it" | **The MCU cannot measure the interval the self-test needs, and the report it should send is not defined.**<br><br>**Why the MCU cannot do it.** The 25–250 ms pass window is measured from "toggling stops".  Only the compute board knows that instant: W_ARM_CLK does not reach any MCU pin.<br><br>**What is undefined.**<br>• §8 does not define what "report it" means (a level, a time stamp in MCU time, or an age).<br>• §8 does not define the heartbeat rate.  Only §4b *proposes* a 1 kHz fast frame, and §3.5 implies ≤ 100 ms.<br>• With a level-only report at 10–100 ms granularity, the 25 ms lower bound (the C16-open detection) cannot be resolved. | `nets.md` l.125 (W_ARM_CLK: C15, J1.19, R18 only), l.126 (W_ARM_S → PD2); §3.5 l.342–346; §4b | Define the heartbeat fields and rate in §8:<br>• W_ARM_S raw level;<br>• latched "fell" flag;<br>• **age of the last PD2 falling edge in ms** (a saturating u16);<br>• "ARM edge required";<br>• heartbeat period ≤ 10 ms (1 kHz fast frame is fine).<br><br>The compute board computes t_fall = t_rx − age − frame latency and compares it with its own t_stop.  A 1 kHz heartbeat carrying the level alone also works (±1–2 ms).  Either way, word it as "the compute board times it; the MCU reports the edge age". |
| **R6C-04** | **MINOR** | §3.3 l.197 "No-load 4.7 m/s at 16.8 V"; §4 l.365; calcs §10 l.126–127, l.137 | **The drive top speed was not re-derived at the new cap**, although R5C-01's fix asked for it.<br>• Flat-bottom SVPWM between D_min ≈ 2.9 % (tMIN_PULSE 600 ns) and D_max 81 % gives a line-to-line peak of ≈ 0.78 × V_bus, against ≈ 1.0 for the calcs' KV × V.<br>• No-load top speed is therefore about **3.7 m/s at 16.8 V (≈ 46 k rpm) and ≈ 3.0 m/s at 14 V**, not 4.7 / 3.9 m/s.<br>• As side effects, the MT6701's 55 k rpm limit is never reached with FOC current sampling, and at top speed it gives ~10.4 updates per electrical cycle instead of 8.2. | calcs.md l.126–137; SLVSH07 tMIN_PULSE 600 ns; §3.4 caps | Update calcs §10, §3.3 and §4 with the capped figure (or state the six-step/over-modulation plan above the cap, which has no current sampling).  If speed matters, clamp the bottom phase at 0 % (INH held low = LS on, allowed in 3x mode) instead of 2.9 %: that gives +3 %. |
| **R6C-05** | **MINOR** | §8 STM32 row: "OPAMPINTEN = 1 **before** OPAMPEN (otherwise it drives PA8) … calibrate the L_SOC offset separately" | **The standard OPAMP calibration path contradicts the rule.**<br>• `HAL_OPAMP_SelfCalibrate` only runs with OPAMPINTEN = 0 (HAL l.666, l.698–699).<br>• During its ~25 ms calibration, OPAMP5's output drives **PA8**, swinging between the 10 %/90 % VDDA levels.  RM0440 §25.3.7 confirms that the output GPIO toggles when you calibrate with OPAINTOEN = 0.<br>• PA8 is L_SOA_F.  It is driven by U3's SOA through R70 = 330 Ω, so the contention is ≈ 10 mA, and the result is a bad L_SOA offset and possibly a bad trim.<br><br>A CubeMX-generated init calls the self-calibration by default. | HAL `stm32g4xx_hal_opamp.c` l.666 ("If OPAINTOEN is enabled, disable it before calling this function"), l.698–699; RM0440 §25.3.7 ("the OPAMP output GPIO toggles during the calibration and care must be taken that there is no conflict"); nets.md L_SOA_F = PA8 | Add to §8:<br>• **do not run the OPAMP self-calibration**; use the factory trim (USERTRIM = 0).  The follower's offset is absorbed by the L_SOC system offset measurement that §8 already requires;<br>• if a trim is wanted, use RM0440's ADC-based procedure with OPAINTOEN = 1. |
| R6C-N1 | NOTE | §8 Watchdog row "HardFault handler: DRV_OFF high, TIM1 MOE = 0, then wait for the IWDG" | **A HardFault inside the handler, or a stack overflow, locks up the core.**<br>• TIM1, TIM8 and TIM20 keep PWM-ing the last duty for up to 21.7 ms until the IWDG fires.  DBGMCU freeze only acts on a debug halt, not on lockup.<br>• The G4 can route the core LOCKUP signal to the timer breaks in hardware. | RM0440 SYSCFG_CFGR2 bit 0 CLL ("Cortex-M4 LOCKUP output connected to TIM1/8/15/16/17/20 break input") | At boot, set **SYSCFG_CFGR2.CLL = 1** (it is write-once and locks).  A lockup then clears MOE on TIM1 (weapon coasts) and on TIM8/TIM20 (drive INH idle low = brake; the DRV8316 OCP bounds it).<br><br>Write the handlers (HardFault and **NMI**, e.g. a flash ECC double error) as naked register writes that use no stack. |
| R6C-N2 | NOTE | §8 Watchdog row (IWDG ~20 ms = 18.8–21.7 ms) | **A flash page erase outlasts the IWDG.**<br>• One page erase takes 22.02 ms typ / 24.47 ms max.<br>• It stalls every flash fetch in that bank, so the main loop cannot refresh the IWDG in time.<br><br>Any firmware that stores calibration (encoder offsets, motor parameters) resets mid-erase. | DS12288 flash table: tERASE 22.02 / 24.47 ms | State: no flash erase or program while running.  Store to flash only when disarmed: refresh the IWDG, erase the other bank (DBANK, read-while-write) with the vector table and ISRs in RAM, or do it before starting the IWDG. |
| R6C-N3 | NOTE | §8 DRV8316C row "Read back CTRL2/CTRL4/CTRL5/CTRL6/CTRL10 … (registers reset on any sleep/UVLO)" | **The read-back list and the mismatch action are incomplete.**<br>• CTRL3 (OVP 22 V, the drive's regen protection) is not read back.<br>• The contract does not say what to do on a mismatch.<br>• A DRV8316 that has reset comes up in **6x mode** (CTRL2 reset 60h).  With INL tied high, INH = 1 gives Hi-Z and INH = 0 turns the LS on (Table 8-3), so the drive pulses in brake until it is re-initialised.<br>• Every SPI response already starts with an 8-bit status byte (FAULT, NPOR), which is a free check on every transfer. | SLVSH07 Table 8-3, §8.3.14.1 (NPOR, no nFAULT on VM UVLO), §8.5.1.1 (status byte), Table 8-19 reset 60h | Add CTRL3 (and CTRL1 lock state) to the read-back.  On a mismatch or NPOR = 0: set DRV_OFF high, then run the full init sequence, then CLR_FLT.  Check the status byte on every frame. |
| R6C-N4 | NOTE | §3.4 l.278–279 absolute windows "valid for CCR6 = 155–162; recompute if CCR6 moves"; §8 "(relative to CCR6)" | CHANGES lists R5C-05 as "regular windows relative to CCR6", but the document still gives absolute windows with a caveat and no formula. | round5_c R5C-05 fix text | Add the formula: t_reg_trigger ∈ [CCR6/170 MHz + 1.85 µs, CCR6/170 MHz + 20.835 µs − t_reg − 0.06 µs] (and the same + 20.835 µs), where t_reg = 8.73 µs. |
| R6C-N5 | NOTE | §8 CPU budget fallback | If the drive current loops fall back to 24 kHz, the drive gets ~4.1 updates per electrical cycle at 16.8 V no-load (~5.2 at the capped top speed of R6C-04).  calcs §10 calls ~4 inadequate.  The weapon observer at 12 kHz gives ~4 per cycle at 25.6 k rpm (7 pole pairs, 3 kHz electrical). | calcs.md l.137 | Name the consequence and the preferred order: first move non-control work out of the ISR, then run the weapon observer at 12 kHz, then the drive loops at 24 kHz. |
| R6C-N6 | NOTE | §8 USART1 row; §3.4/§8 start sequence; bring-up | Small wording and bring-up gaps:<br><br>**(a) USART1 clock.** "2 Mbaud from HSI16 (BRR exact at 170 MHz)" mixes two options that are both exact:<br>• HSI16 kernel clock needs **OVER8 = 1**, BRR = 0x0010 (USARTDIV = 16);<br>• PCLK2 at 170 MHz uses OVER16 with BRR = 85.<br>Pick one.<br><br>**(b) Slave start.** "Slaves enabled first" should read: SMS = 1000, TS = ITR0, CEN = 0, then start TIM1.<br><br>**(c) Break flags.** The DRV8316 at power-up (before CTRL6/CLR_FLT) and the DRV8323 wake pulse (~1 ms) both set TIM8/TIM1 BIF.  Clear SR.BIF only after the source is released, then set MOE.<br><br>**(d) No debug pin.** There is no free GPIO or SWO: all 64 pins are used, PB3 = TIM2_CH2, and J1 pins 7 and 18 are NC.  Consequences:<br>• measure ISR cycles with DWT CYCCNT and report them over the UART;<br>• trim CCR6 from the scoped INHx→OUTx delay (TP or motor wire), not from a sampling marker.<br><br>**(e) §9 steps missing.** §9 has no step for the OUT-edge delay (the DLY_TARGET decision), the CCR6 trim, the cycle measurement, or a check at high modulation.  R5C-01 noted that the high-modulation corner is invisible at low-speed bring-up. | mcu_pinmap.md; nets.md NC list; RM0440 USART BRR rules | Word it in §8 and add a §9 step 5a: scope INH/OUT, trim CCR6, log cycles, run one drive with the wheel loaded at maximum modulation and check the current waveform. |

---

## 3. Consistency sweep (§3.4 / §8 against the rest of the document and the datasheets)

**Pins:**
* PD2 = W_ARM_S (EXTI), PC13 = TIM1_BKIN (W_nFAULT + INA ALERT), PB7 = TIM8_BKIN, PC15 = R_nFAULT (EXTI), PC14 = DRV_OFF.
* PA12 = W_EN; SPI3 on PC10/11/12, CS on PC9/PB4/PA11; USART1 on PC4/PC5.
* Encoders: TIM3 on PC6/PB5/PB0, TIM2 on PA15/PB3/PB10.
* PWM: TIM20 on PB2/PC2/PC8, TIM8 on PB6/PC7/PB9, TIM1 on PC0/PC1/PA10 and PA7/PB14/PB15.
* §3.3, §3.4, §8, `nets.md` and `mcu_pinmap.md` all agree.

**INA239:**
* SOVL 0x76C0 = 30400 × 1.25 µV = 38.0 mV, i.e. 38 A at 1 mΩ (ADCRANGE = 1).
* BOVL 0x17C0 = 6080 × 3.125 mV = 19.0 V.
* SHUNT_CAL = 819.2e6 × 1.25 mA × 1 mΩ × 4 = 4096 = 0x1000 (1.25 mA/LSB, matching §4).
* DIAG_ALRT: ALATCH is bit 15, CNVR bit 14, APOL bit 12 (0 = active-low open drain).
* DEVICE_ID reset value is 2391h.
* SPI: MOSI is sampled on the falling edge and MISO shifted on the rising edge, i.e. mode 1.
* All consistent.

**DRV8316:**
* The SPI mode-1 edges and a 10 MHz maximum (tSCLK ≥ 100 ns) are compatible with /32 = 5.31 MHz.
* SDO goes Hi-Z with nSCS high (l.3591), so push-pull SDO on the shared MISO is fine.
* tREADY is 1 ms.

**Thresholds:**

| Item | Value |
|---|---|
| Firmware weapon coast | 18.5 V |
| INA239 BOVL | 19.0 V |
| DRV8316 OVP | 22 V, trips at ≥ 20 V |
| Shared current budget | ≤ 32 A |
| SOVL | 38 A |
| Weapon limit | 20 A |

The ordering is consistent across §1, §7.4, §7.18 and §8.

**Timers:** TIM1 ARR 3542 / TIM8 and TIM20 ARR 1771, PWM mode 1/2, URS = 1, TRGO/TRGO2 and ITR0 are the same everywhere in §3.4 and §8.

**Stale item:** only the drive top speed (R6C-04).

---

## VERIFIED OK

* **All ten DRV8316C SPI frames:**
  * address, field decode and even parity (§1c);
  * the recovery sequence and REG_LOCK semantics;
  * CTRL4 0x0D10 = 16 A latched OCP with 0.6 µs deglitch;
  * CTRL5 0x0F00 = 0.15 V/A;
  * 0x1818 = DLYCMP_EN + 1.8 µs with correct parity.
* **Drive L duty cap ~81 %** (80.5–80.8 % worst case over the CCR6 trim range, 83.2 % typ).  CCR6 ≈ 156 centres L's group at 1.70 µs.
* **Flat-bottom SVPWM** with PWM_100_DUTY_SEL = 0 is fine at the cap.
* **IWDG task-flag rule:**
  * boot refresh;
  * DBG_IWDG_STOP only in debug builds;
  * 18.8–21.7 ms over the LSI tolerance.
* **HardFault outputs:**
  * DRV_OFF high → drives coast;
  * MOE = 0 with OISxN = 0 → INL low → weapon coast.
* **W_ARM_S handling:**
  * the falling edge acts at once and latches;
  * the rising edge is qualified at ≥ 5 ms plus a fresh edge;
  * the "ARM edge required" handshake agrees with §3.5.
* **CPU fallback** keeps 48 kHz PWM and the 2 : 1 lock.
* **ES0430 handling** covers §2.7.1/2.7.2 (JQDIS), §2.7.5/2.7.6 (reject Rev Z), §2.7.7 (discard) and §2.7.8 cases 1–4 (windows, circular DMA, ADDIS/ADEN).  §2.10.1 does not apply (follower).  §2.12.1 does not apply (MSM = 0).  §2.12.4 does not apply (no OCREF_CLR).
* **TIM1 MMS = update + SMS = 1000/ITR0:** locks from either start order, with no steady-state disturbance.
* **INA239 register values and scaling.**
* **Pin, threshold and timer-value consistency** across §3.3, §3.4, §3.5 and §8 and the generated pin map.

---

**Verdict: 0 BLOCKER, 0 MAJOR, 5 MINOR (R6C-01…05), 6 NOTE.**  All of them are firmware or documentation fixes; no
hardware change is needed.
