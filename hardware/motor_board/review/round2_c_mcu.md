# Round 2 (C): STM32G474RET6 and firmware-facing review of rev B

Reviewer scope: U1 and everything the firmware must be able to do.  No design file was edited.
`python3 design/motor_board.py` was run on a temp copy: `179 refs, 141 nets, checks: OK`.  The
regenerated `mcu_pinmap.md`, `nets.md`, `netlist.csv` and `bom.csv` are byte-identical to the
committed ones.

Sources:

* **DS12288 Rev 4** (`datasheets/STM32G474RET6.pdf`, `pdftotext -layout`): Table 11 (legend), Table 12
  (pin types and notes 2–5), Table 13 (AF), Table 14/15 (abs max), Figure 16 (supply scheme), Table 43
  (HSI16), Table 66 (ADC: fADC, TTRIG), Table 67 (RAIN), Table 80 (OPAMP: TS_OPAMP_VOUT, CMIR, VOH).
* **ST open pin data**: `ref/STM32G474RxTx_pins.xml` (pin signals) and
  `mcu/IP/GPIO-STM32G47x_gpio_v1_0_Modes.xml` from github.com/STMicroelectronics/STM32_open_pin_data
  (AF numbers, cross-checked against DS Table 13).
* **stm32g4xx_hal_driver** (GitHub master): `stm32g4xx_ll_adc.h` (VOPAMPx channels, trigger sources,
  JQDIS), `stm32g4xx_ll_opamp.h` (VINP/VINM mapping, OPAMPINTEN), `stm32g4xx_ll_tim.h` (TRGO2 sources,
  BKIN), `stm32g4xx_hal.h` / `stm32g4xx_ll_system.h` (VREFBUF).
* **AN2606 Rev 61** §47, Table 101 (STM32G47x system-bootloader pin configuration).
* **ES0430**: the ST PDF would not download (timeout / blocked).  I used the stmcu.com.cn HTML mirror
  (summary page only) and the text of §2.7.9 as quoted in the mjbots/moteus commit 4db3610 and on the mjbots blog.
  Findings that depend on it are marked **partially verified**.
* TI DRV8316C SLVSH07 (DLY_TARGET Table 8-6, tSET, SDO_MODE, RPU/RPD) and DRV8323 SLVSDJ3D (tSET, RPD,
  tRST) from `datasheets/`.

---

## Findings

| ID | Sev | Where | Issue | Evidence | Fix |
|---|---|---|---|---|---|
| **C-01** | **MINOR** | OPAMP5 (PC3 → ADC5), PA8, PB14, PB15, PA3; DESIGN §8 | **"OPAMP5 as follower on PC3" leaves out three register settings.  With any of them at its default, OPAMP5 corrupts another net.** (1) **VP_SEL** resets to VINP0 = **PB14 = W_INLB_M** (the weapon INLB PWM).  PC3 is **VINP2**.  (2) **OPAMPINTEN** resets to 0, so the output goes to the VOUT pin **PA8 = L_SOA_F**.  PA8 is already in analog mode for ADC5_IN1, so OPAMP5 would fight the DRV8316 SOA output through R70 330 Ω and L_SOA would read L_SOC.  (3) **VM_SEL** must be *follower* (11b); otherwise VINM0 = PB15 (W_INLC_M) or VINM1 = PA3 (VBAT_SNS) is connected.  Also, when ADC5 converts the internal VOPAMP5 channel, the sampling time must be **≥ 200 ns** (Table 80).  At 42.5 MHz that is ≥ 8.5 cycles, so use **12.5 cycles**, not the 6.5 cycles that suits the direct pins.  Smaller points: the OPAMP offset is ±3 mV (≈ 20 mA at 0.15 V/A), so L_SOC needs its own offset calibration.  The OPAMP output saturates at VDDA − 0.1 V (and CMIR is 0…VDDA), so L_SOC clips about 0.1 V before L_SOA/L_SOB at large positive current. | `ll_opamp.h` l.181–188: "VINP0 … PB14 for OPAMP5", "VINP2 … PC3 for OPAMP5"; l.205/208: VINM0 = PB15, VINM1 = PA3 for OPAMP5; l.255 "Not connected if … FOLLOWER"; l.268–274 OPAMPINTEN "OPAMP5 internal output is connected to ADC5/Channel3".  XML: PA8 has `OPAMP5_VOUT`, PB14 has `OPAMP5_VINP`, PB15/PA3 have `OPAMP5_VINM`.  DS Table 80: TS_OPAMP_VOUT ≥ 200 ns (VDDA ≥ 2 V), VIOFFSET ±3 mV, VOHSAT VDDA − 100 mV.  Netlist: `L_SOA_F: C80, R70, U1.42(PA8)`. | Replace the §8 line with: OPAMP5 **VM_SEL = follower, VP_SEL = VINP2 (PC3), OPAMPINTEN = 1 set before OPAMPEN**, high-speed mode; ADC5 SMP ≥ 12.5 cycles on the VOPAMP5 rank (see C-02); calibrate the L_SOC offset separately. |
| **C-02** | **MINOR** (firmware plan; **partially verified**) | ADC plan, DESIGN §3.4 table and §8 | **The planned sequences do not meet the ES0430 multi-ADC condition after the first rank.**  The workaround (for a synchronous clock divided by ≥ 2) needs all concurrently converting ADCs to have the same clock configuration and to be triggered simultaneously by hardware.  The plan triggers all five from TIM1_TRGO2, but the injected lengths differ (ADC1 2 ranks, ADC2 1, ADC3 2, ADC4 1, ADC5 3).  The regular groups on ADC1/ADC2 (3 vs 4 channels at 247.5 cycles) then start at different times: ADC2 starts regular while ADC1 is still in injected rank 2, and ADC1 starts its first regular while ADC2 is mid-sample.  After rank 1, conversions keep starting while another ADC is sampling, which is the disturbance the erratum describes (moteus: periodic 8-LSB errors).  Separately, the ADC1+ADC2 weapon scheme "W_SOA as the alternate for 2-of-3" needs JSQR rewrites per sector.  That conflicts with §8 "JQDIS = 1 (fixed injected sequences)", because with the queue disabled JSQR changes need JADSTP/JADSTART each time. | moteus 4db3610 comment: "Per 'ES0430 - Rev 8, 2.7.9' the ADCs can only be used simultaneously if they are in synchronous mode with a divider no more than 1" (/1 = 170 MHz, impossible: DS Table 66 fADC ≤ 52 MHz with all ADCs running).  Round-1 r3_mcu M2 quote of the /≥2 branch: "same clock configuration … trigger them with the same timer".  `ll_adc.h` l.1660 JQDIS: "only 1 sequence can be configured and is active perpetually".  Sequence lengths from DESIGN §3.4. | **Make every rank boundary line up.** Give all five ADCs **3 injected ranks with the same SMP (12.5 cycles, set by C-01)**: 3 × 25 cycles = 1.76 µs at 42.5 MHz.  Weapon, fixed and without JSQR rewrites: **ADC1 = [A (IN1), C (IN3), C (IN3)], ADC2 = [B (IN2), A (IN1), B (IN2)]**.  Rank 1 gives A+B, rank 2 gives C+A, rank 3 gives C+B, so every pair is simultaneous and the same pin is never on both ADCs at once.  R: ADC3 = [C, B, C], ADC4 = [A, A, A], which gives A+C and A+B simultaneously; B+C are both on ADC3, so they are always one slot (0.59 µs) apart.  L: ADC5 = [A, B, VOPAMP5], all sequential.  Regular: the **same count and SMP on ADC1 and ADC2** (add VREFINT or the temperature sensor to ADC1 to make 4 + 4).  Keep CKMODE = HCLK/4 (42.5 MHz); do **not** copy moteus's HCLK/2 (85 MHz exceeds Table 66). |
| **C-03** | **MINOR** | W_VA/W_VB/W_VC (PA4, PA5, PB11), NTCs; DESIGN §8 "W_Vx and NTCs on 247.5-cycle regular conversions", §4b | **The 247.5-cycle rule came from round 1, before the 1 nF capacitors were added, and it now does harm.**  With C41–C43 = 1 nF at the pin, the sampling error is set by charge sharing (5 pF / 1 nF ≤ 0.5 % of the step ≈ ≤ 20 LSB worst case, ~4 LSB average at 24 kHz).  RC recovery (τ = 8.8 kΩ × 1 nF = 8.8 µs) does not happen within any SMP, so 247.5 cycles buys nothing.  It does cost time: each conversion is 260 cycles = 6.1 µs, and ADC2's 4-channel regular group takes 24.5 µs.  **W_VA, W_VB and W_VC are then sampled 0–18 µs apart at unrelated points of the 41.7 µs PWM period**, which is useless for six-step BEMF zero-cross or catch-spin phase detection (the floating phase must be sampled at a fixed PWM phase).  At higher PWM frequencies (≥ 38 kHz) the regular group no longer fits between injected triggers. | DS Table 66: CADC = 5 pF.  Netlist: `W_VA: C41, R22, R23, U1.18` (1 nF, 68k/10k = 8.8 kΩ).  Timing: 4 × (247.5 + 12.5) / 42.5 MHz = 24.5 µs.  Channels: PA4 = ADC2_IN17, PA5 = ADC2_IN13, PB11 = ADC1_IN14 (XML). | Sample the phase voltages **simultaneously at a fixed PWM phase**: W_VA (ADC2) and W_VC (ADC1) in the same slot, W_VB in the next, SMP 12.5–24.5 cycles.  Either give them their own injected ranks or trigger the regular group from a TIM1 channel at the wanted PWM phase (same timer, so ES0430 still holds).  The NTCs (100 nF) and VBAT_SNS (100 nF) also need no long SMP.  Update §8 and §4b accordingly. |
| **C-04** | **MINOR** | L_MTEMP / R_MTEMP (J2.6 / J3.6 → PF0 / PF1) | **The round-1 M4 fix is incomplete for the motor NTC lines.  They are the only off-board signals that reach MCU pins directly.**  S1–S3 now go through Schmitt buffers ("a cable fault kills a buffer, not the MCU").  MTEMP has only the R52/R53 10 k pull-up and C72/C73 100 nF.  The NTC sits inside the motor, beside the windings, and its wire runs in the harness beside the phase leads.  A crushed harness or a winding-to-NTC insulation failure puts a phase (up to VBAT 16.8 V) on PF0/PF1.  The limit is min(VDD, VDDA) + 4 = 7.3 V on FT pins, and positive injection is not allowed, so the MCU is lost (and with it the weapon break path and all telemetry).  There is no ESD element on the connector pin either.  (VS = 5 V on pin 1 is fine: 5 V < 7.3 V with PF0/PF1 in analog mode.) | Netlist: `L_MTEMP: C72.1, J2.6(TEMP), R52.2, U1.5(PF0)`; `R_MTEMP: C73.1, J3.6, R53.2, U1.6(PF1)`.  DS Table 12: PF0 FT_fa, PF1 FT_a; Table 14 FT max min(VDD,VDDA)+4.0, note 4; Table 15 note 3.  Round-1 r3_mcu M4 proposed a TVS array; CHANGES.md only lists "100 nF on MTEMP". | Add a series resistor between J2.6/J3.6 and the pull-up node (e.g. 1 kΩ 0603; its fixed offset calibrates out, or use 470 Ω) plus a clamp at the node: a BAT54S to +3V3/GND, or the ESD array the buffers already sit beside.  At 16.8 V through 1 kΩ that is 13.5 mA into the clamp and +3V3, which survives.  Alternatively accept the risk and write it down in DESIGN §7. |
| C-05 | NOTE | System-memory bootloader (empty flash at first power-up, or a firmware jump) | **Bootloader pin states touch the drive nets** (AN2606 Table 101, G47x).  **PB14 (SPI2_MISO) is driven to 3.3 V**, which sets W_INLB_M high.  PA10 (USART1_RX pull-up) pulls W_INHC high against the DRV8323 ~100 k pull-down.  PC8/PC7 (I2C3_SCL / I2C4_SDA open-drain pull-ups) pull R_INHC and L_INHB high.  PA9 and PA2 (USART1/USART2 TX, push-pull high) drive L_SOB_F through 330 Ω and **W_SOC directly** (DRV8323 SOC, no series R).  The USB DFU forced device mode probably enables the internal DP pull-up on **PA12 = W_EN**, so it would wake U2 (**UNVERIFIED**: AN2606 lists PA12 as "input no pull").  The outcome is still bounded: PC14 is untouched, so R50 keeps DRVOFF high and both drives are off.  Weapon: INLA/INLC_M are held low (bootloader pull-downs on PA7/PB15, R47/R49), so at most phase B's low side turns on, and only if W_ARM is high.  Also: the ROM USART bootloader is on **PA9/PA10, not the header UART (PC4/PC5)**, and the I2C2 bootloader uses PC4 + PA8 (a CSA pin).  The compute board can update firmware only over SWD (on J1) or through a custom bootloader. | AN2606 Rev 61 Table 101 and its footnote 1: "as soon as the bit DMATx enable … is set … the MISO line is set to 3.3 V".  Netlist: `W_INLB_M: R48, U1.36(PB14), U6.4`; `W_SOC: U1.14(PA2), U2.23(SOC)`; `W_EN: R40, U1.46(PA12), U2.33`. | Compute board: assert W_ARM only after a heartbeat from the motor MCU application.  Document in §8/§9 that ROM-bootloader updates are not possible over MB_TX/MB_RX. |
| C-06 | NOTE | ADC triggering, TIM1 | DS Table 66 gives **TTRIG ≤ 1 ms** (the maximum external trigger period).  Every ADC is clocked by TIM1 events, so the **TIM1 counter must never stop**: not when the weapon is disarmed and not after a break.  Break only clears MOE, which is fine.  Start TIM1 before the first ADC conversion after calibration. | DS Table 66 "External trigger period … 1 ms". | Add to §8. |
| C-07 | NOTE | PB3 (R_S2) | Round-1 M15 reasoned that PB3/JTDO is only driven with TRACESWO.  In rev B, PB3 is now driven **push-pull by U10 2Y**.  After reset, SWJ-DP starts in JTAG mode, so a debugger's JTAG-to-SWD switch sequence can briefly walk the TAP through Shift-DR/IR and drive TDO.  That is a short CMOS-vs-CMOS contention, harmless at these currents.  SWO trace is unavailable (PB3 is in use). | DS Table 12 note 4; netlist `R_S2: U1.56(PB3), U10.5(2Y)`. | None.  Use SWD only; no SWO. |
| C-08 | NOTE | VREF+ / VREFBUF | VREF+ is tied to VDDA (+3V3A).  VREFBUF must stay off with HIZ = 1.  `HAL_SYSCFG_VREFBUF_HighImpedanceConfig(…DISABLE)` connects the buffer to the externally driven pin.  The reset value of HIZ was not confirmed from RM0440 (**UNVERIFIED**). | `stm32g4xx_hal.h` l.151–152 (HIZ semantics); netlist `+3V3A: U1.28(VREF+), U1.29(VDDA)`. | §8: "never enable VREFBUF; keep HIZ = 1". |
| C-09 | NOTE | HSI16, USART1 | Round 1 used ±1 %.  Over −40…125 °C, HSI16 is −2…+1.5 % drift plus the 15.88–16.08 MHz initial spread, so worst case ≈ −2.75 %/+2 %.  USART1 at 2 Mbaud (BRR = 85, fraction ≠ 0) tolerates ~3.3 % against a crystal partner, so it still works but with little margin in the cold.  No crystal is needed (no USB/CAN/RTC), and PF0/PF1, the only HSE pins, are used for MTEMP anyway. | DS Table 43. | None; optionally trim HSI at bring-up. |
| C-10 | NOTE | DRV8316 SOx range | SOx swings up to AVDD − 0.25 V, and AVDD can reach 3.465 V, which is above VREF+ (3.25–3.35 V).  That is within the TT_a 4.0 V abs max on PB1/PB12/PB13/PC3 and FT on PA8/PA9, but the top ~0.1–0.2 V of positive current reads full-scale.  This is already reflected in the asymmetric ±8.7–9.9 A in §3.3. | DS Table 14; DRV8316 VLINEAR. | None. |

---

## VERIFIED OK

**Pins and AFs (all 52 I/O).** Each MCU_PINS name and position matches the XML (script check), and each AF
string exists on its pin.  AF numbers (ST GPIO modes XML, spot-checked against DS Table 13):
* TIM1: CH1 **PC0 AF2**, CH2 **PC1 AF2**, CH3 PA10 AF6, CH1N **PA7 AF6**, CH2N PB14 AF6, CH3N PB15 **AF4**, BKIN PC13 AF2.
* TIM8: CH1 PB6 AF5, CH2 PC7 AF4, CH3 PB9 AF10, BKIN PB7 AF5.
* TIM20: CH1 PB2 AF3, CH2 PC2 AF6, CH3 PC8 AF6.
* TIM3 (PC6/PB5/PB0) AF2; TIM2 (PA15/PB3/PB10) AF1.
* SPI3 (PC10/11/12) AF6; USART1 (PC4/PC5) AF7; SWD (PA13/PA14) AF0.
* PC2 must use AF6 (TIM20_CH2), not AF2 (TIM1_CH3).

**Rev B swaps.** Each swapped pin carries the listed function:
* PC0/PC1 = TIM1_CH1/CH2 and PA7 = TIM1_CH1N.
* PB12 = ADC4_IN3, PB13 = ADC3_IN5, PA8/PA9 = ADC5_IN1/IN2, PB1 = ADC3_IN1, PA6 = ADC2_IN3.
* PC3 = OPAMP5_VINP (VINP2).
* PD2 = FT GPIO for W_ARM.
* All eight new ADC inputs (PB12, PB13, PA8, PA9, PB1, PA0, PA1, PA2) are fast channels, IN1–IN5 (DS Table 67 note 3).

**Timers.**
* **One TIM1 can drive its channels on these mixed pins.** CHx on PC0/PC1/PA10 and CHxN on PA7/PB14/PB15 all work together, because the AF mux is per pin.
* CH4, CH5 and CH6 stay internal for TRGO2 (`LL_TIM_TRGO2_OC4…OC6`).
* **PWM and ADC triggering from the same TIM1 is consistent.** TIM1_TRGO2 is an injected and regular trigger on every ADC instance (`LL_ADC_INJ/REG_TRIG_EXT_TIM1_TRGO2`), and TRGO (MMS) remains free to sync TIM8/TIM20.  I did not confirm from RM0440 that TIM8/TIM20 take TIM1 on ITR0 (**UNVERIFIED**; it is standard ST MCSDK dual-motor practice).
* **No channel conflicts:** TIM3 and TIM2 channels 1–3 are distinct.  EXTI lines do not collide: PC13 → EXTI13, PC15 → EXTI15, PD2 → EXTI2.  PA15, PB15, PB2 and PC2 are timer, not EXTI, users.
* **Break inputs:** TIM1_BKIN on PC13 and TIM8_BKIN on PB7.  Polarity is set by BKINP/BKP, and BKINE resets to on.  **Enable the BKF filter**, because both lines are 10 k pull-ups shared with other open-drain devices.

**ADC channel map and sample timing.**
* **Channel map (DESIGN §3.4):**
  * ADC1: PA0 IN1, PA2 IN3, PA3 IN4, PB11 IN14, PF0 IN10.
  * ADC2: PA1 IN2, PA0 IN1, PA4 IN17, PA5 IN13, PA6 IN3, PF1 IN10.
  * ADC3: PB1 IN1, PB13 IN5.
  * ADC4: PB12 IN3.
  * ADC5: PA8 IN1, PA9 IN2.
  * VOPAMP5 = ADC5 channel 3 (`ll_adc.h` l.964; `ll_opamp.h` l.274).
* **ADC clock:** HCLK/4 synchronous = 42.5 MHz, which is ≤ 52 MHz (Table 66, all ADCs running, VDDA ≥ 2.7 V).
* **Drive CSA filter (330 Ω + 22 pF):** τ = 330 × 27 pF ≈ 9 ns; the kick is 5/27 of the step.  At 6.5 cycles (153 ns ≈ 17 τ) the residual is negligible, and at 12.5 cycles more so.  This is consistent with Table 67 (fast, 330 Ω at 108 ns).
* **Divider and NTC sources:** VBAT_SNS (8.8 kΩ + 100 nF) and the NTCs (5 kΩ + 100 nF) show charge-share errors ≤ 0.005 %.
* **Weapon CSA:** W_SOx goes direct to the pins from a CSA with 60 pF load capability; tSET is 600 ns at 20 V/V.
* **3-shunt sampling feasibility:**
  * **Drive (DRV8316):** with DLY_TARGET = 0x5 (1.2 µs, DRV8316C Table 8-6), 84 ns slew and 1 µs tSET, a sample at the PWM centre is valid for half-window h ≥ 2.28 µs.  That means D ≤ 89 % at 24 kHz, which matches §8's 88 % cap.  The 3rd rank (1.2–1.5 µs after the centre) ends well before the delayed trailing edge (centre + h + 1.2 µs).
  * **Weapon (DRV8323, no delay compensation):** h ≥ 0.75 µs for rank 1 and h ≥ 1.5 µs for rank 3 of the C-02 scheme, so D ≤ ~92 %.

**5 V tolerance and abs max.**
* nFAULT pull-ups to DRV8316 AVDD (≤ 3.465 V) go to PB7 (FT_f) and PC15 (FT).  The limit is min(VDD, VDDA) + 4 V.  They stay within 4.0 V even while +3V3 is still ramping, and there is no positive-injection path.
* DRV8316 SDO is push-pull by default (CTRL2 SDO_MODE reset 1h, VOH ≤ AVDD) into PC11 (FT_f).
* W_ARM → PD2 (FT) and U6 LVC08 (5.5 V tolerant, Ioff), with R41 pull-down.
* Header lines: MB_RX PC5 is TT_a (4.0 V; the compute board drives 3.3 V).  SWDIO/SWCLK are FT_f and NRST is FT.  With the MCU unpowered, TT/FT inputs up to 4.0 V are allowed.
* Phase dividers on PA4/PA5/PB11 (TT_a): 16.8 V → 2.15 V.  A TVS-clamp spike (32.4 V → 4.15 V) is filtered by the 1 nF (8.8 µs).  The −7 V undershoot gives −0.09 mA, well inside −5 mA.
* VBAT_SNS PA3 (TT_a): 25.7 V → 3.3 V.
* Sensor lines reach the MCU only through the 3.3 V buffers (except MTEMP, see C-04).

**Reset and boot states.**
* Weapon PWM outputs PC0/PC1/PA10 float in reset.  The DRV8323 INHx pull-downs (RPD ~100 k) hold them, U2 sleeps on R40, and INLx = 0 via R47–R49 and the AND with W_ARM.
* PA7/PB14/PB15 float; R47–R49 hold U6's inputs low.
* The drive INHx pins float onto the DRV8316 100 k pull-downs, and DRV_OFF (PC14, floating) is held high by R50, so both bridges are Hi-Z.
* PB6 (L_INHA) dead-battery Rd only pulls low (safe).  PB4 (R_nCS) Rd is covered by §8's UCPD disable.
* The DRV8316 nSCS has an internal pull-up (RPU 80–130 k).  The INA239 CS (PA11) floats in reset; this is harmless because the INA239 is reconfigured at init.
* PC14 only sinks 0.33 mA against R50.  Driving it high sources only ~66 µA into the two DRVOFF pull-downs, inside note 2's limits.

**Decoupling and support pins.**
* VDD: 4 × 100 nF + 4.7 µF, matching Figure 16.
* VDDA 100 nF and VREF+ 100 nF + 4.7 µF on one +3V3A net (pins 28/29 adjacent), which covers Figure 16's 10 nF + 1 µF / 100 nF + 1 µF.
* VBAT is tied to +3V3; Figure 16 shows no separate capacitor.
* NRST: 100 nF plus the internal pull-up; the compute board drives it open-drain.
* BOOT0: R61 10 k to GND.
* SWDIO/SWCLK/NRST are on J1 and on TP1–TP5.

**Clocking.** HSI16 with the PLL gives 170 MHz.  USART1 BRR = 85 is exact.  SPI3 on APB1 at /32 gives 5.3 MHz (≤ 10 MHz for DRV8316/INA239).  No crystal is needed (see C-09).

**DESIGN §8, other rows.** The rest of §8 is correct for this MCU: the UCPD dead-battery disable, the rule never to enable RTC_OUT/TAMP/LSE on PC13–15, and the CHxN static-high setup (CCxNE = 0, OSSR = 1, CCxNP = 1) with break → INL low → coast.

---

**Verdict: 0 BLOCKER, 0 MAJOR, 4 MINOR (C-01…C-04), 6 NOTE.**

Sources: [ST STM32_open_pin_data](https://github.com/STMicroelectronics/STM32_open_pin_data),
[stm32g4xx_hal_driver](https://github.com/STMicroelectronics/stm32g4xx_hal_driver),
[AN2606](https://www.st.com/resource/en/application_note/an2606-stm32-microcontroller-system-memory-boot-mode-stmicroelectronics.pdf) (Rev 61 mirror),
[ES0430](https://www.st.com/resource/en/errata_sheet/es0430-stm32g471xx473xx474xx483xx484xx-device-errata-stmicroelectronics.pdf) (not downloadable),
[moteus commit 4db3610](https://github.com/mjbots/moteus/commit/4db361035ac5adc999769b530727a5067b6d457b),
[mjbots: STM32G4 ADC performance part 2](https://blog.mjbots.com/2023/07/24/stm32g4-adc-performance-part-2/).
