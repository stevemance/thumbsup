# Round 3 (C): MCU plan and firmware contract, rev C

Scope: DESIGN.md rev C §3.4 (ADC plan), §3.5 (compute-board requirements) and §8 (firmware contract), checked
against U1 STM32G474RET6 and the SPI devices U3/U4 (DRV8316C) and U7 (INA239).  No design file was edited.

`python3 design/motor_board.py` was run on a temp copy: `201 refs (180 placed components), 150 nets, 56 BOM lines, checks: OK`.
The regenerated `mcu_pinmap.md`, `nets.md`, `netlist.csv`, `bom.csv` and `calcs.md` are byte-identical to the committed ones.

Sources:

* **DS12288 Rev 4** (`datasheets/STM32G474RET6.pdf`, `pdftotext -layout`): Table 19 (BOR levels), §3.11.2 (BOR is set
  through option bytes), Table 43 (HSI16), the VREFINT table (tS_vrefint, tstart_vrefint), the temperature sensor table (tS_temp),
  and the pin table (PA9/PA10 `_d` = UCPD1_DBCC1/2, PB4/PB6 = UCPD1_CC2/CC1).
* **ST pin database** `ref/STM32G474RxTx_pins.xml`: the analog signals were dumped for every ADC pin in §3.4.
* **stm32g4xx_hal_driver** (GitHub master): `stm32g4xx_ll_adc.h` (regular/injected trigger lists, internal channels),
  `stm32g4xx_ll_tim.h` (TRGO2 sources, TS_ITRx), `stm32g4xx_ll_opamp.h`, `stm32g4xx_ll_system.h` (DBGMCU),
  `stm32g4xx_hal_pwr_ex.c` (UCPD dead battery).
* **AN2606 Rev 61**, §47 Table 101 (G47x bootloader pins), from the kolegite.com mirror.
* **ES0430**: st.com timed out again, both via curl and WebFetch.  I have §2.7.9's title, its Description and its Note from the
  errata screenshot on the mjbots blog (2023-07-24).  The dual-mode exception comes from a search-engine extract of the same
  erratum.  Anything that depends on the workaround wording is marked **partially verified**.
* **RM0440**: could not be downloaded (st.com timeout; mirrors are blocked).  Claims that need it are marked **UNVERIFIED**.
* TI **SLVSH07** (DRV8316C: §8.5 SPI, Tables 8-18 to 8-24, VOVP/tREADY), **SLYS027A** (INA239), and the INA229 datasheet in `datasheets/`.

---

## Findings

| ID | Sev | Where | Issue | Evidence | Fix |
|---|---|---|---|---|---|
| **R3C-01** | **MINOR** | §3.4 table header "Regular (TIM1 CC4 …)", §8 "regular groups ADC1/ADC2 4 + 4 on TIM1 CC4" | **TIM1 CC4 is not a regular-group trigger on any ADC of this part.**  The regular EXTSEL list has only three TIM1 sources: TIM1_TRGO, TIM1_TRGO2 and TIM1_CH1/CH2/CH3.  CH1/CH2 are on ADC1/2 only, and all three are the weapon PWM compares, so they move with duty.  TIM1_CH4 exists only as an **injected** trigger (JEXTSEL).  Of TIM1's two outputs, TRGO carries the TIM8/TIM20 sync and TRGO2 carries the injected trigger.  So the regular group has no TIM1 source at a free, fixed phase.  The plan cannot be built as written.  CC4 itself is free: CH4 has no pin in use, and CC4E = 0 still lets the compare generate events. | `ll_adc.h` `ADC_LL_EC_REG_TRIGGER_SOURCE` (l.976 ff.): TIM1_TRGO, TIM1_TRGO2, TIM1_CH1 ("only on ADC1/2"), TIM1_CH2 ("only on ADC1/2"), TIM1_CH3; **no `LL_ADC_REG_TRIG_EXT_TIM1_CH4`**.  `LL_ADC_INJ_TRIG_EXT_TIM1_CH4` (l.1422) has no instance restriction.  `ll_tim.h` l.919–934: TRGO2 = OC4REF/OC5REF/OC6REF and their combinations. | **Swap the two triggers:** injected ← **TIM1_CH4** (JEXTSEL, available on all five ADCs; CCR4 at the centre of the low-side window) and regular ← **TIM1_TRGO2** with MMS2 = OC6REF (or OC5REF), CCR6 at the phase you want for W_Vx.  Either way, set CMS / OCxM so that only one edge per PWM period triggers, and scope it at bring-up.  The mapping of the CC4 event to an ADC trigger in centre-aligned mode is **UNVERIFIED** (RM0440).  Alternative: keep injected on TIM1_TRGO2 and trigger the regular group from **TIM8_TRGO2** (MMS2 = OC4REF/OC6REF of the in-phase slave), which is available on ADC1/2.  In both cases ADC1 and ADC2 share one trigger and ADC3–5 are idle during the regular groups, so the ES0430 condition holds.  Update §3.4 and §8. |
| **R3C-02** | **MINOR** | §3.4 "12.5-cycle sampling everywhere", "ADC1/ADC2 get equal-length regular groups"; ADC1 regular rank 4 = VREFINT | **VREFINT needs ≥ 4 µs of sampling, which is 170 cycles at 42.5 MHz, so it must use 247.5 cycles and not 12.5.**  The temperature-sensor alternative needs ≥ 5 µs, which is also 247.5 cycles.  "4 + 4" regular groups then go out of step unless the ADC2 rank at the same position uses the same SMP: equal *count* is not enough.  ADC1 would still be sampling VREFINT while ADC2 starts its next conversion, which is the concurrency ES0430 §2.7.9 describes.  VREFINT is on ADC1 (channel 18; not on ADC2), and the temperature sensor is on ADC1 channel 16 / ADC5 channel 4, so the channel choice is valid.  VREFINT also needs VREFEN in ADC12_CCR and up to 12 µs of buffer start-up. | DS12288 VREFINT table: `tS_vrefint` min **4 µs**, `tstart_vrefint` max 12 µs; temperature-sensor table: `tS_temp` min **5 µs**.  SMP options: 2.5/6.5/12.5/24.5/47.5/92.5/247.5/640.5 cycles.  `ll_adc.h` l.933–942: VREFINT = channel 18, "all instances but ADC2"; TEMPSENSOR_ADC1 = channel 16, TEMPSENSOR_ADC5 = channel 4. | Make the SMP pattern match **rank by rank** on ADC1/ADC2: ADC1 [W_VC, VBAT_SNS, L_MTEMP, **VREFINT @ 247.5**] and ADC2 [W_VA, W_VB, W_NTC, **R_MTEMP @ 247.5**] (a 100 nF node, so the long SMP does no harm).  Each group then takes 3 × 25 + 260 = 335 cycles = **7.9 µs**, which still fits in the 41.7 µs period with ≥ 2 µs clearance from the injected trigger.  Alternatively drop VREFINT and repeat VBAT_SNS in rank 4.  Change "12.5-cycle sampling everywhere" to "12.5 cycles except VREFINT and its ADC2 partner (247.5)". |
| **R3C-03** | **MINOR** | §8 DRV8316C sequence "… CTRL2 0x097D (CLR_FLT) → CTRL1 0x0606 (REG_LOCK)"; §3.3 "nSLEEP +3V3 (fault clear via SPI CLR_FLT)" | **After REG_LOCK the DRV8316C ignores every register write except REG_LOCK itself.  CLR_FLT is a CTRL2 bit, so a runtime fault clear written while locked is silently dropped.**  nSLEEP is tied to +3V3, so SPI is the only fault-clear path.  The latched faults on this board include CTRL4 OCP (latched mode, kept at reset), OVP and the SPI/BUCK flags.  Also, OVP at the 22 V setting trips at **20 V min** (rising).  That is the only margin above the 18.2–18.8 V worst-case regen bus.  On any nFAULT the MCU drops that drive (TIM8 break / EXTI → DRV_OFF).  If the recovery routine only writes CLR_FLT, the drive stays dead for the rest of the match.  The frames themselves are correct (see VERIFIED OK). | SLVSH07 Table 8-18: REG_LOCK "6h = Write 110b to lock the settings by ignoring further register writes except to these bits and address 0x03h bits 2-0".  §8.5.1.1: B8 even parity.  VOVP (OVP_SEL = 1) rising 20/22/23 V, falling 19/21/22 V, tOVP 2.5–7 µs.  Netlist `+3V3 → U3/U4 nSLEEP` (§3.3). | §8: "Runtime fault clear = **CTRL1 0x0603 (unlock) → CTRL2 0x097D → CTRL1 0x0606**; read STAT back.  Then re-arm the timer (TIM8 MOE / R_nFAULT path) only after nFAULT is high."  Also add the 20 V minimum OVP threshold to the braking row, so nobody raises the regen limit on the assumption of a 22 V margin. |
| R3C-04 | NOTE | §8 boot order "BOR level raised" | **The BOR level is an option byte (FLASH_OPTR BOR_LEV), not a runtime register.**  Changing it needs a flash option-byte program and OBL_LAUNCH, which resets the part, so as a step in the boot sequence it becomes a flash-wear or reset-loop hazard.  No level is given. | DS12288 §3.11.2: "other higher thresholds can be selected through option bytes"; Table 19: BOR4 = 2.76–2.86 V falling / 2.85–2.95 V rising; BOR3 = 2.47–2.57 V falling. | "Option bytes, programmed once over SWD at bring-up (§9 step 2): **BOR_LEV = 4** (≈ 2.8 V; the AP2112K rail is 3.25 V min).  Firmware only checks OPTR at boot and reports a mismatch." |
| R3C-05 | NOTE | §3.4 "TIM8 and TIM20 are slaved to TIM1"; §8 DBGMCU freeze | (a) **The ITR is not named.**  TIM8's ITR0 = tim1_trgo is confirmed only by secondary sources (RM0440 Table 250 as quoted in search results).  TIM20's ITR0 = tim1_trgo is **UNVERIFIED** (RM0440 not retrievable), though it is the usual MCSDK dual-motor setup.  (b) With DBG_TIMx_STOP set, RM0440 disables the timer outputs as if MOE = 0 (from memory, **UNVERIFIED**).  The weapon then goes to OISxN = 0 → INL low → coast (correct).  On TIM8/TIM20, INH goes to idle-low, which with INL = +3V3 in 3x mode means **low sides on = brake** while DRV_OFF (a GPIO) stays low.  At a breakpoint the drive wheels brake hard; this is safe but should be known. | `ll_tim.h` l.965 (TS_ITR0…11, no per-instance map); `ll_system.h` l.287–297 (`DBG_TIM1/8/20_STOP` in APB2FZ exist); DESIGN §3.3 "a timer break forces the low sides on = brake". | §8: "TIM8/TIM20: SMS = trigger (or reset) mode, **TS = ITR0 (tim1_trgo)**, TIM1 MMS = enable/update; confirm in RM0440 'TIMx internal trigger connection'."  Add one line: debug halt = weapon coast, drives brake. |
| R3C-06 | NOTE | §3.4 ADC plan; question "same pin on two ADCs" | **Same pin in different ranks: fine.  The same pin on ADC1 and ADC2 at the same time: not allowed.**  RM0440's dual-mode rule says the same channel must not be sampled by both ADCs with overlapping sampling times (**UNVERIFIED** wording; RM0440 not retrieved).  The fixed weapon sequence never does that: PA0 is on ADC1 in rank 1 and on ADC2 in rank 2.  But in independent mode, lockstep only holds if both ADCs always start together.  One software-started conversion (for example an "on-demand VREFINT") or an injected pre-emption of a regular conversion that differs between ADC1 and ADC2 would break it.  ES0430 §2.7.9 (search extract, **partially verified**): "ADC1 and ADC2 operating in a dual mode other than *alternate trigger mode only* do not impact one another regardless of clock source." | XML: PA0 = ADC1_IN1 + ADC2_IN1; PA1 = ADC1_IN2 + ADC2_IN2; PA2 = ADC1_IN3 only.  mjbots screenshot of ES0430 §2.7.9 (Description + Note: "ADC conversion comprises the sampling phase and the successive approximation phase"). | Recommend **ADC1/ADC2 in dual mode** (combined regular simultaneous + injected simultaneous; ADC1 master), which gives hardware lockstep and uses ES0430's own exception for the pair.  ADC3/4/5 keep the synchronous-clock, same-trigger scheme.  Never software-start a single ADC while the others run. |
| R3C-07 | NOTE | §3.5 item 4/5, AN2606 bootloader pins | Round 2 C-05 missed some pins.  The G47x ROM bootloader also enables **USART3 on PC10 (TX, push-pull high) = SPI_SCK and PC11 (RX pull-up) = SPI_MISO**, and SPI1 with **PA6 MISO driven to 3.3 V = W_NTC** (into the 10 k / NTC node: harmless).  USART2 RX on PA3 adds a pull-up to VBAT_SNS (the header reading shifts while in the bootloader).  With PB4's dead-battery Rd still active (U4 nSCS low) and SCK held high, U4 at most logs an SPI frame error, which the §8 sequence clears.  In DFU mode, AN2606's note "No external pull-up resistor is required" means the internal DP pull-up on **PA12 = W_EN** comes on, which wakes U2.  That resolves round 2's UNVERIFIED point toward "yes".  It stays bounded by W_ARM low (the §3.5 heartbeat rule). | AN2606 Rev 61 Table 101: USART3 PC11/PC10 "alternate push-pull, pull-up"; SPI1 PA6 MISO footnote 1 ("MISO line is set to 3.3 V"); USB DP PA12 "No external pull-up resistor is required". | None beyond §3.5 item 4; optionally list these pins in §8. |
| R3C-08 | NOTE | §3.4 "HSI16 is ±1 % at 0–85 °C" | The ±1 % is **temperature drift only**.  Adding the 15.88–16.08 MHz initial spread gives −1.85/+1.55 % at 0–85 °C (−2.85/+2.05 % at −40…125 °C, as round 2 said).  USART1 BRR = 85 (DIV_Fraction 5 ≠ 0) tolerates ~3.3 %, so the link still works.  The sentence understates the error. | DS12288 Table 43. | Reword: "±1 % drift + −0.75/+0.5 % initial". |
| R3C-09 | NOTE | §3.4 "at the PWM valley" / §4b | With centre-aligned PWM mode 1, the counter valley is the **high-side** centre.  Low-shunt sampling needs the low-side centre, which is the counter **peak** (CNT = ARR), unless PWM mode 2 or inverted polarity is used.  Since TRGO2/CC4 can be placed anywhere, this is wording only.  A firmware writer who takes "valley" literally would sample with the high sides on. | DRV8316/DRV8323 3x mode: INH high = high-side on; DESIGN §8 "Sample the CSAs ≥ 1 µs after the low-side window opens". | Say "at the centre of the low-side-on interval". |
| R3C-10 | NOTE | §7.11 LCSC STM32 sourcing | ES0430 has fixed ADC errata that depend on silicon revision (e.g. the intermixed regular/injected channel-switch disturbance fixed on later revisions, per the ST community thread).  Parts from a non-authorised distributor may be old stock. | ST community "STM32G4 ADC input channel switch errata…" (ES0430 Rev 1 text; later revisions fixed). | §9 step 2: log DBGMCU_IDCODE REV_ID and check it against ES0430's applicability table. |

---

## VERIFIED OK

**Injected sequences: every channel exists on its instance.**  The XML was dumped per pin.
* ADC1 [PA0 **IN1**, PA2 **IN3**, PA2 IN3] and ADC2 [PA1 **IN2**, PA0 **IN1** (ADC12 shared pad), PA1 IN2].
  * Rank pairs: A+B, C+A, C+B.
  * Every pair is simultaneous, and no pin is ever on both ADCs in the same rank.
  * All three pins are fast channels (IN1–IN5).
* ADC3 [PB1 **IN1**, PB13 **IN5**, PB1] and ADC4 [PB12 **IN3** ×3]: R gives A+C, A+B, A+C.
* ADC5 [PA8 **IN1**, PA9 **IN2**, **VOPAMP5 = channel 3**] (`ll_adc.h` l.964, `ll_opamp.h` OPAMPINTEN note "OPAMP5 … ADC5/Channel3").
* Regular channels:
  * ADC1: PB11 IN14, PA3 IN4, PF0 IN10, VREFINT channel 18.
  * ADC2: PA4 IN17, PA5 IN13, PA6 IN3, PF1 IN10.

**OPAMP5 settings.**
* VP_SEL = 10b (VINP2) = PC3.  VINP0 = PB14 = W_INLB_M and VINP1 = PD12, so VINP2 is the only correct choice.
* VM_SEL = 11b is follower.  In follower mode VINM0 = PB15 and VINM1 = PA3 are not connected.
* OPAMPINTEN = 1 routes the output to ADC5 channel 3.
* The 12.5-cycle SMP gives 294 ns, which meets ≥ 200 ns.

**TIM1 resources.**
* CH1–3 and CH1N–3N are the weapon; CH4/CH5/CH6 are internal and free.
* TRGO2 can be OC4REF, OC5REF, OC6REF or their edge combinations (`ll_tim.h` l.926–934).
* TIM1_TRGO2 is both an injected and a regular trigger on all ADCs.
* **Timing:**
  * 3 injected ranks × (12.5 + 12.5) = 75 cycles = 1.76 µs.
  * Regular 4 × 25 = 2.35 µs at 12.5 cycles, or 7.9 µs with the R3C-02 fix.
  * Both fit in the 41.7 µs period at 24 kHz, and still fit at 48 kHz.

**DBGMCU and UCPD.**
* `DBG_TIM1_STOP`, `DBG_TIM8_STOP` and `DBG_TIM20_STOP` exist in DBGMCU_APB2FZ.
* `HAL_PWREx_DisableUCPDDeadBattery()` sets PWR_CR3.UCPD_DBDIS (`hal_pwr_ex.c` l.1157).  It needs the PWR clock enabled first.
* PB4 = UCPD1_CC2 and PB6 = UCPD1_CC1 (DS pin table).  The Rd pull-downs matter only until this call, as in §8.

**DRV8316C frames (SLVSH07 §8.5.1.1: B15 W0 = 0 write, B14–9 address, B8 = even parity over the word, B7–0 data; mode 1 = capture on falling edge, SCLK idle low).**  Each frame was recomputed:

| Frame | Addr | Data | Ones (addr + data + P) | Meaning (tables 8-18…8-24) |
|---|---|---|---|---|
| 0x0603 | 0x03 CTRL1 | 0x03 | 2+2+0 = 4 | REG_LOCK unlock (011b) |
| 0x1019 | 0x08 CTRL6 | 0x19 | 1+3+0 = 4 | BUCK_PS_DIS=1, BUCK_CL=1 (150 mA), BUCK_SEL=00, BUCK_DIS=1 |
| 0x0B4F | 0x05 CTRL3 | 0x4F | 2+5+1 = 8 | reserved b6=1 (reset value kept), OVP_SEL=1 (22 V), OVP_EN=1, SPI_FLT_REP=1 (off nFAULT), OTW_REP=1 |
| 0x1915 | 0x0C CTRL10 | 0x15 | 2+3+1 = 6 | DLYCMP_EN=1, DLY_TARGET=5 (1.2 µs) |
| 0x087C | 0x04 CTRL2 | 0x7C | 1+5+0 = 6 | b7–6=01 (reset), SDO_MODE=1 push-pull, SLEW=11 (200 V/µs), PWM_MODE=10 (3x) |
| 0x097D | 0x04 CTRL2 | 0x7D | 1+6+1 = 8 | same + CLR_FLT |
| 0x0606 | 0x03 CTRL1 | 0x06 | 2+2+0 = 4 | REG_LOCK lock (110b) |

* The kept reset values are as stated: CTRL4 0x10 (OCP_DEG 0.6 µs, 16 A, latched) and CTRL5 0x00 (0.15 V/A).
* SPI timing: tREADY is 1 ms, and tSCLK min 100 ns permits the planned 5.3 MHz.

**INA239 settings (SLYS027A).**
* **Configuration registers:**
  * CONFIG ADCRANGE is bit 4: ±40.96 mV, 1.25 µV/LSB.
  * **SHUNT_CAL** = 819.2e6 × (40.96 A / 2^15 = 1.25 mA) × 1 mΩ × 4 = **4096 (0x1000)**.
  * The same register value serves the INA229: 13107.2e6 × 78.125 µA × 1 mΩ × 4 = 4096, with its 20-bit CURRENT_LSB.
* **Limits:**
  * **SOVL**: 35 mV / 1.25 µV = **28000 = 0x6D60**.  It stays below 32767, so it is inside the ±40.96 mV range.
  * **BOVL**: 19 V / 3.125 mV = **6080 = 0x17C0**.
  * SOVL and BOVL have the same LSBs on the INA229, so the same values work on both parts.
  * The reset values never trip:
    * SUVL 0x8000 and BUVL 0x0000.
    * TEMP_LIMIT 0x7FF0 (+4095 °C).
    * PWR_LIMIT 0xFFFF × 256 LSB, which is above the ~0x320000 POWER count at 820 W.
* **DIAG_ALRT** = 0x8000: ALATCH at b15, CNVR = 0 at b14, APOL = 0 at b12, SLOWALERT = 0.  MATHOF and MEMSTAT do not assert ALERT.
* **IDs:** DEVICE_ID 0x2391 (INA229: 0x2291); MANUFACTURER_ID 0x5449.
* **SPI:** INA239 is mode 1 (MOSI sampled on the falling edge), at ≤ 10 MHz.

**Netlist consistency (§3.3/§3.4/§8 against `netlist.csv`).**
* Power and support parts:
  * C60–C64 on +3V3.
  * R60 +3V3 → +3V3A, with C65/C66/C71 on it; U1.28 VREF+ and U1.29 VDDA are on +3V3A.
  * C74 on VBAT/+3V3; C67 on NRST; R61 BOOT0 → GND.
  * R63/R64/C68 on VBAT_SNS → U1.17 PA3 and J1.11.
  * U5 AP2112K goes from +5V to +3V3.
* Weapon control nets:
  * R12 is the INA_nCS pull-up (U1.45 PA11 and U7.1 CS).
  * **W_nFAULT** = R42, U1.2 PC13, U2.28 and U7.3 ALERT.
  * R40 is on W_EN (PA12, U2.33 ENABLE).
  * R41 is on W_ARM (J1.7, PD2).
  * R47–R49 are on W_INLx_M.
* Drive nets:
  * R50 is on DRV_OFF (PC14, U3/U4.21).
  * R301/R401 pull L_/R_nFAULT (PB7 / PC15) up to L_/R_AVDD.
* SPI3: PC10/11/12 go to U3, U4 and U7; the chip selects are PC9, PB4 and PA11.
* SO filters:
  * R70–R72 / C80–C82 → PA8, PA9, PC3.
  * R80–R82 / C90–C92 → PB12, PB13, PB1.
* Motor NTCs: R113/R117 with D7/D8 on L_/R_MTEMP → PF0/PF1.
* All ADC-pin nets match the §3.4 table.

**Other §8 items.**
* JQDIS = 1 with fixed JSQR is consistent: there are no per-sector rewrites any more.
* CKMODE = HCLK/4 = 42.5 MHz is within the Table 66 limit.
* TTRIG ≤ 1 ms is met by "TIM1 never stopped".
* VREFBUF stays off.
* The compute-board heartbeat gate on W_ARM covers the bootloader pin states, including R3C-07.

---

**Verdict: 0 BLOCKER, 0 MAJOR, 3 MINOR (R3C-01…03), 7 NOTE.**

Sources: [stm32g4xx_hal_driver](https://github.com/STMicroelectronics/stm32g4xx_hal_driver),
[STM32_open_pin_data](https://github.com/STMicroelectronics/STM32_open_pin_data),
[AN2606 Rev 61 mirror](https://kolegite.com/EE_library/application_notes/MCU/STM32/STM32%20microcontroller%20system%20memory%20boot%20mode.pdf),
[mjbots: STM32G4 ADC performance part 2](https://blog.mjbots.com/2023/07/24/stm32g4-adc-performance-part-2/) (ES0430 §2.7.9 screenshot),
[ES0430](https://www.st.com/resource/en/errata_sheet/es0430-stm32g471xx473xx474xx483xx484xx-device-errata-stmicroelectronics.pdf) (not downloadable),
[RM0440](https://www.st.com/resource/en/reference_manual/rm0440-stm32g4-series-advanced-armbased-32bit-mcus-stmicroelectronics.pdf) (not downloadable),
[ST community: G4 ADC channel-switch errata](https://community.st.com/t5/stm32-mcus-products/stm32g4-adc-input-channel-switch-errata-for-intermixed-regular/td-p/298217),
[ST community: G431 TIM1 ITR1](https://community.st.com/stm32-mcus-motor-control-34/where-does-g431-tim1-itr1-acturlly-from-132684).
