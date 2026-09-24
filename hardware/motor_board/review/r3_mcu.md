# R3 — STM32G474RET6 pin / ADC / interface review (adversarial)

Reviewer scope: `design/motor_board.py` `MCU_PINS` and every MCU-facing net. Nothing in the design
files was edited.

Primary sources used:

* **DS12288 Rev 4** (`datasheets/STM32G474RET6.pdf`, via `pdftotext -layout`): Table 12 (pin definition), Table 13
  (alternate functions), Table 14/15 (abs max), Figure 16 (power supply scheme), Table 43 (HSI16), Table 66/67 (ADC, RAIN),
  pin-table notes 2–5.
* **ST open pin data** `ref/STM32G474RxTx_pins.xml`, dumped per pin.
* **ST STM32CubeG4 HAL/LL drivers** (github.com/STMicroelectronics/stm32g4xx_hal_driver). These are ST's own code
  and stand in for RM0440, which st.com blocks from scripted download:
  `stm32g4xx_ll_adc.h` (injected trigger list per ADC instance, OPAMP internal channels), `stm32g4xx_ll_opamp.h`,
  `stm32g4xx_ll_tim.h` (break sources), `stm32g4xx_hal_pwr_ex.c` (UCPD dead battery).
* **ES0430** (G471/473/474/483/484 errata): the summary table from the stmcu.com.cn HTML mirror, and the multi-ADC
  workaround text as quoted in search results. The ST PDF would not download, so these items are marked partially verified.
* mjbots/moteus blog, "STM32G4 ADC performance part 2" (moteus runs on the G474).
* TI DRV8323 SLVSDJ3D, DRV8316 SLVSF16B, INA229 (in `datasheets/`).

`python3 design/motor_board.py` (run on a temp copy) reports `checks: OK`. Every pin name and AF string in
`MCU_PINS` exists in the XML. The problems below are about **whether the pins work together** (ADC topology, electrical
limits, reset states), not about AF typos.

---

## Findings

| ID | Sev | Pin / net | Issue | Evidence | Proposed fix |
|---|---|---|---|---|---|
| **M1** | **BLOCKER** | L_SOx PC0/PC1/PC3, R_SOx PA6/PA7/PB1, W_SOx PA0/PA1/PA2 | **Motors cannot each be sampled at their own PWM centre by their own timer.** 8 of the 9 phase-current pins reach **only ADC1/ADC2**: PA0/PA1/PC0/PC1/PC3 = ADC12_IN1/2/6/7/9, PA2 = ADC1_IN3, PA6/PA7 = ADC2_IN3/IN4. Only PB1 also reaches ADC3 (ADC3_IN1). Each ADC has one injected sequence (max 4 ranks) and one trigger at a time, so TIM1, TIM8 and TIM20 would all compete for ADC1/ADC2. This works only if all three PWMs are phase-locked and 4 conversions run back to back on each ADC. At 42.5 MHz ADC clock with 6.5-cycle sampling that is about 1.8 µs of skew, plus 0.6–1 µs of CSA settling. It does not fit the low-side-on window of a high-duty phase (for example 2 µs at 95 % duty at 24 kHz). The drive R set is **not** simultaneous: PA6 and PA7 are both ADC2-only (PA7 could reach ADC1 only through OPAMP1). | DS12288 Table 12 "Additional functions": PA6 `ADC2_IN3`, PA7 `ADC2_IN4`, PB1 `ADC3_IN1/ADC1_IN12`, PC0 `ADC12_IN6`, PC1 `ADC12_IN7`, PC3 `ADC12_IN9`, PA0 `ADC12_IN1`, PA1 `ADC12_IN2`, PA2 `ADC1_IN3`; XML agrees. | **Swap 8 pins (all nets already exist, no new parts):** PA7 ↔ PB13 (W_INLA → PA7 = TIM1_CH1N AF6; R_SOB → PB13 = ADC3_IN5). PA6 ↔ PB12 (W_NTC → PA6 = ADC2_IN3; R_SOA → PB12 = ADC4_IN3). PC0 ↔ PA8 (W_INHA → PC0 = TIM1_CH1 AF2; L_SOA → PA8 = ADC5_IN1). PC1 ↔ PA9 (W_INHB → PC1 = TIM1_CH2 AF2; L_SOB → PA9 = ADC5_IN2). L_SOC stays on PC3 and is read through **OPAMP5 as a follower** (VINP = PC3), internal output → ADC5 (VOPAMP5 = ADC5 ch 3). Result: weapon on ADC1+ADC2, drive L on ADC5, drive R on ADC3+ADC4. See the final table. |
| **M2** | **MAJOR** (firmware architecture) | all ADCs, TIM1/8/20 | **ES0430 multi-ADC erratum.** Concurrent conversions on several ADCs disturb each other unless the ADCs share the same synchronous clock configuration **and are triggered by the same timer**. The planned "each motor triggered by its own timer" (DESIGN.md §8) is exactly the configuration the workaround excludes. moteus (G474) measured 8-LSB noise and full-scale "2048" outliers until this was fixed, and also recommends a bigger VREF+ capacitor. | ES0430 workaround as quoted by search results: "use the same clock configuration for the concurrently converting ADC instances … trigger them with the same timer using the same clock prescaler division ratio … The timer can use different outputs (such as timN_trgo, timN_oc1) for different ADC instances". mjbots blog 2023-07-24: "Use a synchronous clock, the same clock configuration for all ADCs, and trigger them all simultaneously from a hardware timer"; "both a larger 4.7uF capacitor … along with a separate smaller, 0.1uF". **Partially verified:** the ST PDF itself would not download. | Firmware: run TIM8 and TIM20 as slaves of TIM1 (same PSC/ARR, centre-aligned, in phase). Use a synchronous ADC clock (HCLK/4 = 42.5 MHz) for all ADCs. Trigger **all five ADCs from TIM1** (TRGO2 or CC4), which the LL header lists for every instance. With M1 applied, each ADC still serves only one motor. Hardware: see M7 (VREF+ decoupling). |
| **M3** | **MAJOR** | L_S3 PB0, R_S3 PB10 (and MB_RX PC5) | **5 V sensor option vs pin tolerance.** JP1/JP2 in position 2–3 feed 5 V to the sensor. PB0 and PB10 are **TT_a** (absolute max 4.0 V, no positive injection allowed), so a push-pull 5 V Hall/MT6701 output on S3 violates abs max. On the FT pins (PC6, PB5, PA15, PB3), 5 V is allowed only with the internal pull-up/pull-down **disabled**, yet DESIGN.md §3.3 tells 5 V Hall users to "use the MCU pull-ups". Many motor Hall boards also carry their own pull-ups to VS, which makes them 5 V push-pull in effect. | DS12288 Table 12: PB0 `TT_a`, PB10 `TT_a`, PC6/PB5 `FT_f`, PA15 `FT_f`, PB3 `FT`. Table 14: "Input voltage on TT_xx pins … 4.0"; FT: "min(VDD, VDDA) + 4.0", note 4 "To sustain a voltage higher than 4 V the internal pull-up/pull-down resistors must be disabled". Table 15 note 3: "Positive injection … is not possible on these I/Os". | Pick one of these. (a) **Delete the 5 V jumper option** (tie VS to +3V3 through a 0 Ω / PTC). The MT6701 runs at 3.3 V, and most Hall ICs run from 3.0 V (check the chosen motor). (b) Keep 5 V but add external 4.7 kΩ pull-ups to **+3V3** on S1–S3, place them on board, and state "open-drain sensors only". (c) Add a series 1 kΩ plus a BAT54S clamp to 3V3 on S1–S3. Pin moves cannot fix this alone: no FT timer-CH3 pin is free for TIM3/TIM2. |
| **M4** | **MAJOR** | L_S1..3, R_S1..3, L/R_MTEMP (J2/J3) | **Off-board sensor lines have no pull-ups, no filter and no ESD protection.** They run in the motor harness next to 20 A-class phase wires. Open-drain Halls would rely on the ~40 kΩ internal pull-ups. MTEMP goes straight to ADC pins PF0/PF1. | `nets.md`: `L_S1: J2.3, U1.38` (no other part), same for all S lines. `L_MTEMP: J2.6, R52.2, U1.5`. | Per line: 4.7 kΩ to +3V3 plus 100 Ω series plus 1 nF to GND at the MCU (τ = 0.1 µs, fine for 1.4 MHz ABZ edges; use 470 pF if the encoder runs faster). Enable the timer input filter (ICxF). MTEMP: 100 nF at the pin (also fixes M9). A TVS array (for example a 6-channel ESD diode on the SH connector) is cheap insurance. |
| **M5** | **MINOR** | R_nFAULT PC15 | **No TIM20 break pin exists on LQFP-64.** TIM20_BKIN/BKIN2 appear only on PF7/PF8 (larger packages). TIM20 can take a break from COMP1–7 outputs, but R_nFAULT would then have to sit on a COMPx_INP pin, and every such pin is used for ADC/PWM. Moving it gains little anyway. (1) The DRV8316 handles OCP/OTP itself. (2) With INLx tied high (3x PWM), a timer break forces INHx to its idle level, i.e. **all low sides on = short brake, not Hi-Z**. The same is true for TIM8's break on L_nFAULT. The coast path for the drives is DRV_OFF. | DS12288 Table 12: `TIM20_BKIN` only on PF7, `TIM20_BKIN2` on PF8 (LQFP64 column "-"). `stm32g4xx_ll_tim.h`: `LL_TIM_BKIN_SOURCE_BKCOMP1..7`. DRV8316 3x PWM (INL = 1, INH = 0 → low side on). | Keep PC15 on EXTI15 at the highest NVIC priority. The ISR sets DRV_OFF high and clears TIM20 MOE. Document that L_nFAULT → TIM8 break brakes the wheel (acceptable) and that DRV_OFF is the Hi-Z path. Optional: free PB8 (see M12) — still no TIM20 break, but it gives a spare EXTI/TIM1_BKIN pin. |
| **M6** | **MINOR** | W_VA PA4, W_VB PA5, W_VC PB11 | **Weapon phase dividers:** 68 k/10 k = 8.8 kΩ source, no capacitor, on **slow** channels (ADC2_IN17, ADC2_IN13, ADC12_IN14). At 12 bits, Table 67 allows RAIN ≤ 10 kΩ only at **247.5 cycles** (4.1 µs at 60 MHz) per conversion. The phase node also rings (SPICE: VDS to 29 V at 60 mA IDRIVE, 36–44 V at 400 mA). 29 V → 3.72 V and the TVS clamp of 32 V → 4.1 V, both above VDDA, and **4.1 V exceeds the 4.0 V TT abs max** of PA4/PA5/PB11. Negative SHx (−7 V → −0.9 V, ≈ 0.1 mA through 68 k) is within the 5 mA injection limit. | DS12288 Table 67 (12-bit: 247.5 cycles → 10 kΩ slow). Table 12: PA4/PA5/PB11 `TT_a`. Table 14 TT max 4.0 V. DESIGN.md §5 SPICE figures. | Add **1 nF** from each W_Vx to GND at the MCU (τ = 8.8 µs, kickback 5 pF/1 nF ≈ 0.5 %; filters the ns ringing; ≈ 10° lag at the 3 kHz max electrical frequency, which firmware compensates). Optionally 68 k/8.2 k to gain headroom. Put these on the ADC2 **regular** group (TIM1-triggered) with long sampling, not in the injected group. |
| **M7** | **MINOR** | VDDA pin 29, VREF+ pin 28 | Decoupling below the datasheet scheme. Figure 16 shows **VDDA: 10 nF + 1 µF** and **VREF+: 100 nF + 1 µF** as separate pairs. The design has one 100 nF + one 1 µF shared by both pins through R60. moteus found concurrent-ADC artefacts improved with 4.7 µF + 100 nF on VREF+ (see M2). | DS12288 Figure 16 and Caution "Each power supply pair (VDD/VSS, VDDA/VSSA etc.) must be decoupled … as close as possible". mjbots blog (M2). | Add C at pin 29 (10 nF or 100 nF) and at pin 28 (100 nF). Make the VREF+ bulk 4.7 µF (0402/0603 X5R 10 V, the same part as C64). Keep R60 (ferrite option). VDD×4 (4×100 nF + 4.7 µF) matches Figure 16. |
| **M8** | **MINOR** | SPI_MISO (R51 10 k), SPI3 clock | **DRV8323 SDO is open drain** on a shared MISO with a 10 kΩ pull-up. With ~30–40 pF of bus (4 devices + trace), τ ≈ 0.3–0.4 µs, so reliable reads only up to about 1 MHz. Separately, SPI3 on APB1 at 170 MHz gives /16 = 10.6 MHz, **above** the 10 MHz limit (100 ns tSCLK min) of both DRV parts. The DRV8316 SDO is push-pull by default (SDO_MODE = 1h) and Hi-Z when nSCS is high, so sharing is fine. | DRV8323 pin table: "SDO … This open drain pin requires an external pullup". DRV8316 §8 "SDO_MODE … 1h = Push Pull"; tSCLK min 100 ns (both). INA229: tSCLK_H/L ≥ 40 ns. | Use SPI prescaler /32 (5.3 MHz) for DRV8316/INA229 and drop to ≤1 MHz (/256 = 0.66 MHz) for DRV8323 transactions, **or** change R51 to 2.2 kΩ (1.5 mA sink, within the DRV8323 SDO rating) to run ~5 MHz. All four parts use SPI mode 1 (CPOL 0, CPHA 1). |
| **M9** | **MINOR** | W_NTC, L/R_MTEMP (10 k pull-up + 10 k NTC) | Source ≈ 5 kΩ at 25 °C, no capacitor, slow channels. This needs 247.5-cycle sampling. It is harmless in the regular group, but the nodes are unfiltered and the motor ones are off-board. | DS12288 Table 67 (slow, 12-bit, 92.5 cycles → 3.9 kΩ max). | 100 nF on each NTC node at the MCU (τ = 0.5 ms, irrelevant for thermal). |
| **M10** | **MINOR** (firmware) | PB4 (R_nCS), PB6 (L_INHA); PA9/PA10 = UCPD1_DBCC1/2 | **UCPD dead-battery Rd.** After reset, the dead-battery pull-downs on UCPD1_CC1 = PB6 and CC2 = PB4 are enabled, gated by DBCC1/DBCC2 = PA9/PA10. PA10 is a weapon PWM output (and PA9 becomes an analog input after M1). If firmware does not disable it, PB4 = R_nCS can be pulled low by ~5 kΩ whenever PA10 is high, selecting U4 during other SPI transfers and contending MISO. | DS12288 Table 12: PB4 `FT_c UCPD1_CC2`, PB6 `FT_c UCPD1_CC1`, PA9 `UCPD1_DBCC1`, PA10 `UCPD1_DBCC2`. `stm32g4xx_hal_pwr_ex.c`: "After exiting reset, the USB Type-C dead battery behavior will be enabled, which may have a pull-down effect on CC1 and CC2 pins. It is recommended to disable it in all cases". | Call `HAL_PWREx_DisableUCPDDeadBattery()` (PWR_CR3.UCPD_DBDIS = 1) first thing in `main()`, before GPIO init. Optional hardware: 10 kΩ pull-ups on all four chip selects (W/L/R/INA) so they are defined during reset. |
| **M11** | **NOTE** | W_INLA/B/C on TIM1_CHxN (DRV8323 3x PWM) | In DRV8323 3x mode, INLx is a **per-phase enable** (INL = 0 → Hi-Z). A complementary CHxN output would put the phase in Hi-Z every time INH goes low. For FOC, firmware must hold CHxN **statically high**: CCxNE = 0, OSSR = 1, CCxNP = 1 ("off-state, output enabled with inactive level"). For six-step, per-phase Hi-Z comes from switching CCxNP / CCxNE at commutation. A good property of this wiring: on break (MOE = 0) with OISxN = 0, INL goes low, so the weapon **coasts** instead of short-braking a 64 J drum. Keep INL on the timer (M1 preserves this: PA7/PB14/PB15). | DRV8323 Table 8-3 (3x PWM truth table: INLx 0 → Hi-Z; 1/0 → GL on). RM0440 output-control table for complementary channels (from memory; **UNVERIFIED** against the PDF). | Firmware only. |
| **M12** | **NOTE** | PB8-BOOT0 | A fresh part samples the pin: the factory option word 0xFFEFF8AA has nSWBOOT0 = 1 (BOOT0 from pin) and nBOOT0 = 1. R61 10 k to GND boots from flash. **Option:** after first flash, program nSWBOOT0 = 0 and nBOOT0 = 1 to free PB8 (TIM1_BKIN AF12, TIM8_CH2, EXTI8) as a spare I/O. SWD programming does not depend on BOOT0. | DS12288 §3.7 "The BOOT0 value may come from the PB8-BOOT0 pin or from an nBOOT0 option bit depending on the value of a user nBOOT_SEL option bit". Note 5 on PB8. Default word 0xFFEFF8AA (ST community / tk233 notes; **RM0440 table not read directly**). | None required. Keep R61. |
| **M13** | **NOTE** | PC13 TIM1_BKIN, PC14 DRV_OFF, PC15 R_nFAULT | Backup-domain pins. PC13–15 outputs are limited to ≤2 MHz / 30 pF, a 3 mA total sink, and **no current sourcing**. PC14 drives DRV_OFF **low** against the 10 k pull-up R50 (0.33 mA sink) and never needs to source. PC13 and PC15 are inputs. All OK. PC13 as TIM1_BKIN is AF2. Because VBAT is tied to VDD, the backup domain powers up with VDD and the pins start as GPIO. Firmware must never enable RTC_OUT/TAMP1 (PC13) or LSE (PC14/15). | DS12288 Table 12 notes 2 and 3; Table 13 PC13 AF2 = TIM1_BKIN. | None. |
| **M14** | **NOTE** | USART1 PC4 (FT_fa) / PC5 (**TT_a**) | PC5 = MB_RX is 3.6 V tolerant only, so the compute board must drive 3.3 V (an RP2040 is fine). There is no pull-up, so RX floats when the compute board is absent; enable the internal pull-up. HSI16: 15.88–16.08 MHz at 30 °C, ±1 % over 0–85 °C, so worst case ≈ −1.75 %/+1.5 %. 2 Mbaud from 170 MHz: BRR = 85, exact. The USART's ~3.4 % tolerance (OVER16, BRR[3:0] ≠ 0) covers this with a crystal-clocked partner. | DS12288 Table 12 (PC5 `TT_a`), Table 43 (HSI16). | Internal pull-up on PC5. No crystal needed. |
| **M15** | **NOTE** | SWD PA13/PA14, JTAG pins PA15/PB3/PB4 | After reset PA13 (pull-up), PA14 (pull-down), PA15 (pull-up) and PB4 (pull-up) are debug AF. PB4 = R_nCS pulled up = deselected (good). PA15 = R_S1 pull-up is harmless. PB3 = JTDO has no pull, and in SWD it is only driven when TRACESWO is enabled, so it does not fight R_S2. Firmware reclaims these by writing MODER/AFR (G4 has no remap lock). ES0430 2.2.1 (full JTAG without NJTRST) is irrelevant with SWD. The compute board must keep SWDIO/SWCLK/NRST Hi-Z (NRST open-drain) when not debugging. | DS12288 Table 12 note 4 "the internal pull-up on PA15, PA13, PB4 pins and the internal pull-down on PA14 pin are activated". ES0430 summary 2.2.1. | None. |
| **M16** | **NOTE** | Drive sensors TIM3 (PC6/PB5/PB0 = CH1/2/3, AF2) and TIM2 (PA15/PB3/PB10 = CH1/2/3, AF1) | Hall interface: TI1S = 1 XORs CH1/CH2/CH3 into TI1. Both timers have the three halls on CH1–3, so this is correct. Encoder mode uses TI1/TI2 = S1/S2 (A/B), also correct. **Z/index:** the G4 hardware index (TIMx_ECR) needs **ETR**, and Z on CH3 is not ETR. Use a CH3 input-capture interrupt to latch or zero in software, which is enough for wheel odometry. MT6701 ABZ has no absolute angle at power-up, so FOC needs an alignment step (or use UVW mode on the same pins). TIM3 is 16-bit: at 116 k counts per wheel revolution it wraps within one wheel turn, so extend it in software. TIM2 is 32-bit. | DS12288 Table 13 (AFs). TIM3_ETR only on PB3/PD2 and TIM2_ETR on PA0/PA5/PA15, all already used. | None (firmware). |
| **M17** | **NOTE** | DRV8316 SOx (VREF = own AVDD) vs ADC VREF+ = +3V3 (AP2112) | The DRV8316 CSA gain is absolute (0.15 V/A) and its offset is AVDD/2. It is not ratiometric to the ADC reference, so the LDO's accuracy (±~1.5–2 %) becomes current-gain error. VREFBUF cannot be used because VREF+ is tied to VDDA. Also, the CSA is specified to settle to 1 % in 1 µs with 30 pF, so do not add more than ~30 pF directly on SOx. | DRV8316 EC table: "tSET Settling time to ±1%, 30 pF … 1 µs". | Calibrate offset at start-up (already planned) and gain once on the bench. Any SOx RC filter must include a series R. |
| **M18** | **NOTE** | ADC silicon revision | ES0430 lists injected-queue erratum 2.7.1 ("New context conversion initiated without waiting for trigger when writing new context in ADC_JSQR with JQDIS = 0 and JQM = 0"). ST community threads also report an "ADC input channel switch" disturbance on rev X, fixed on rev Y. The M1 plan avoids JSQR rewrites (a fixed injected sequence per ADC). | ES0430 summary (stmcu.com.cn mirror). ST community thread "STM32G4 ADC Input channel switch errata…". Details **UNVERIFIED**. | Set JQDIS = 1 (no queue) and write JSQR once. Check the date/rev code of the JLC stock. |

---

## VERIFIED (no action)

* **All 52 MCU_PINS entries** match the XML pin names/positions and the DS12288 Table 12 LQFP64 column. `motor_board.py` check is OK.
* **AF numbers** (DS12288 Table 13): TIM1_CH1/2/3 PA8/PA9/PA10 AF6. TIM1_CH1N PB13 AF6, TIM1_CH2N PB14 AF6, TIM1_CH3N PB15 **AF4**.
  TIM8_CH1 PB6 AF5, TIM8_CH2 PC7 AF4, TIM8_CH3 PB9 AF10. **TIM20_CH1 PB2 AF3, TIM20_CH2 PC2 AF6, TIM20_CH3 PC8 AF6**: TIM20 CH1–3
  really are available on LQFP-64. TIM3_CH1/2/3 PC6/PB5/PB0 AF2. TIM2_CH1/2/3 PA15/PB3/PB10 AF1. SPI3 SCK/MISO/MOSI
  PC10/PC11/PC12 AF6. USART1 TX/RX PC4/PC5 AF7. **TIM1_BKIN PC13 AF2**, **TIM8_BKIN PB7 AF5**. SWD PA13/PA14 AF0.
  For the M1 swaps: TIM1_CH1 PC0 AF2, TIM1_CH2 PC1 AF2, TIM1_CH1N PA7 AF6.
* **Injected triggers:** TIM1_TRGO/TRGO2/CC4, TIM8_TRGO/TRGO2/CC4 and TIM20_TRGO/TRGO2 are available on **every** ADC instance
  (`stm32g4xx_ll_adc.h` `LL_ADC_INJ_SetTriggerSource`; only TIMx_CH2/CH3, TIM2/3/16 channels and EXTI lines are instance-restricted).
  So separate per-motor triggers are *possible*, but see M2.
* **OPAMP internal channels** (`stm32g4xx_ll_adc.h`): VOPAMP1 → ADC1 ch13, VOPAMP2 → ADC2 ch16, VOPAMP3 → ADC2 ch18 / ADC3 ch13,
  VOPAMP4 → ADC5 ch5, VOPAMP5 → ADC5 ch3, VOPAMP6 → ADC4 ch17. OPAMP5_VINP is available on PC3 (XML, DS12288).
  HAL: "When this output is enabled, regular output to I/O is disabled".
* **Fast channels** = ADCx_IN1..IN5 (DS12288 Table 67 note 3).
* Break sources: TIMx_BKIN pin plus COMP1..7 (`LL_TIM_BKIN_SOURCE_BKCOMPx`). BKINP polarity is programmable (nFAULT = active low).
* VDD decoupling 4×100 nF + 4.7 µF matches Figure 16. The VBAT pin tied to +3V3 is allowed (1.55–3.6 V). NRST 100 nF matches Figure 27.
  PG10-NRST keeps its reset function by default.
* PC14 DRV_OFF at reset: floating, so R50 holds DRV_OFF high (drives off). PB13–15/PA8–10 floating at reset: the DRV8323 input pulldowns
  keep the weapon off, and U6 ENABLE is low anyway.
* VBAT_SNS 68 k/10 k + 100 nF: 5 pF/100 nF kickback is negligible, so any sampling time works. PA3 is ADC1_IN4 (fast).
* 5 V tolerance of the remaining off-board digital lines: SWDIO/SWCLK FT_f, NRST, PC4 FT_fa. W_ARM goes to U6, not the MCU.

---

## Proposed final ADC assignment (after the M1 swaps)

Pin changes relative to the current `MCU_PINS` (8 pins, swaps only; every AF/channel is in the XML):

| Pin | Now | Proposed | Function after the change |
|---|---|---|---|
| 8 PC0 | L_SOA | **W_INHA** | TIM1_CH1 (AF2) |
| 9 PC1 | L_SOB | **W_INHB** | TIM1_CH2 (AF2) |
| 20 PA6 | R_SOA | **W_NTC** | ADC2_IN3 |
| 21 PA7 | R_SOB | **W_INLA** | TIM1_CH1N (AF6) |
| 34 PB12 | W_NTC | **R_SOA** | ADC4_IN3 (fast) |
| 35 PB13 | W_INLA | **R_SOB** | ADC3_IN5 (fast) |
| 42 PA8 | W_INHA | **L_SOA** | ADC5_IN1 (fast) |
| 43 PA9 | W_INHB | **L_SOB** | ADC5_IN2 (fast) |

The weapon's INHA/INHB/INLA leave the right-hand pins 35/42/43 for pins 8/9/21. U2 wiring gets longer, so place U2
toward the MCU's left/bottom edge. These pins are digital outputs sitting beside analog inputs (PC2, a digital pin, already
sat between PC1 and PC3 in the current plan): keep the INH traces away from PA0–PA2/PC3.

| ADC | Trigger (per ES0430: all from TIM1; TIM8/TIM20 slaved and in phase) | Injected (currents, at PWM centre) | Regular (TIM1-triggered, DMA) |
|---|---|---|---|
| ADC1 | TIM1_TRGO2 | W_SOA PA0 (IN1, fast), W_SOC PA2 (IN3, fast) | VBAT_SNS PA3 (IN4), W_VC PB11 (IN14, 247.5 cyc), L_MTEMP PF0 (IN10) |
| ADC2 | TIM1_TRGO2 | W_SOB PA1 (IN2, fast) (+ W_SOA IN1 as the alternate for 2-of-3 sector selection) | W_VA PA4 (IN17), W_VB PA5 (IN13), W_NTC PA6 (IN3), R_MTEMP PF1 (IN10) |
| ADC3 | TIM1_TRGO2 (TIM20 in phase) | R_SOC PB1 (IN1, fast), R_SOB PB13 (IN5, fast) | — |
| ADC4 | TIM1_TRGO2 (TIM20 in phase) | R_SOA PB12 (IN3, fast) | — |
| ADC5 | TIM1_TRGO2 (TIM8 in phase) | L_SOA PA8 (IN1, fast), L_SOB PA9 (IN2, fast), L_SOC PC3 via OPAMP5 follower → VOPAMP5 (ch3) | — |

* Weapon: any 2 of the 3 phases can be converted simultaneously on ADC1 + ADC2 (A is on both; B only on ADC2, C only on ADC1),
  as ST MCSDK 3-shunt sector selection requires.
* Drive R: A (ADC4) is simultaneous with B or C (ADC3). B and C are 1 conversion apart (~0.45 µs).
* Drive L: 3 sequential conversions on ADC5 (~1.35 µs, or read 2 of 3 per sector). This is acceptable for the 1–4 A drive motors. If it
  is not, a later revision can move one L phase to ADC4 through OPAMP6 (VINP on PB12/PB13) at the cost of an R channel.
* Not reachable from ADC3/4/5 after the change: nothing that needs to be. PB0 (ADC3_IN12/ADC1_IN15), PB2 (ADC2_IN12), PC2
  (ADC12_IN8), PC4/PC5 (ADC2_IN5/IN11), PB14/PB15 (ADC4_IN4/IN5, ADC1_IN5/ADC2_IN15) stay on their digital functions.
  Those are the analog channels given up to other needed functions.

---

## Sources

* [DS12288 — STM32G474 datasheet](https://www.st.com/resource/en/datasheet/stm32g474cb.pdf) (local copy `datasheets/STM32G474RET6.pdf`)
* [ST stm32g4xx_hal_driver (LL ADC / OPAMP / TIM, HAL PWREx)](https://github.com/STMicroelectronics/stm32g4xx_hal_driver)
* [ES0430 errata](https://www.st.com/resource/en/errata_sheet/es0430-stm32g471xx473xx474xx483xx484xx-device-errata-stmicroelectronics.pdf) and [HTML mirror](https://www.stmcu.com.cn/upload/pdf_html/a1c72b8f1ba37808f5b980c0c2bea42a.html)
* [mjbots: STM32G4 ADC performance part 2](https://blog.mjbots.com/2023/07/24/stm32g4-adc-performance-part-2/)
* [ST community: STM32G4 ADC input channel switch errata](https://community.st.com/t5/stm32-mcus-products/stm32g4-adc-input-channel-switch-errata-for-intermixed-regular/td-p/298217)
* [tk233 notes: changing STM32 default boot option](https://tk233.gitbook.io/notes/stm32/misc/changing-stm32-default-boot-option)
* TI DRV8323 SLVSDJ3D, DRV8316 SLVSF16B, INA229 (local `datasheets/`)
