# Review → design changes

## Round 1 (r1–r6) → rev B

| Finding | Change |
|---|---|
| W-01/R4-02 blocker: ENABLE-as-interlock resets an SPI DRV8323; B1 DRV8323RS out of stock | U2 → **DRV8323RHRGZR** (C543035), pin-strapped: MODE R44 47k→GND (3x), IDRIVE R45 75k→GND (60/120 mA), VDS R46 18k→GND (0.13 V), GAIN open (20 V/V), CAL GND.  Removed from SPI; W_nCS deleted |
| W-01 interlock | U6 74LVC1G08 → **74LVC08 quad AND**: INLx = TIM1_CHxN AND W_ARM (3x mode: INL 0 = Hi-Z).  ENABLE = W_EN directly.  R47–R49 100k pull-downs on the MCU-side INL nets.  W_ARM also to PD2 (FT) |
| M1 (r3): ADC instance conflicts | Pin swaps: PC0/PC1 = W_INHA/B, PA6 = W_NTC, PA7 = W_INLA_M, PB12/PB13 = R_SOA/R_SOB (ADC4/ADC3), PA8/PA9 = L_SOA/L_SOB (ADC5), PC3 = L_SOC via OPAMP5, PB1 = R_SOC (ADC3_IN1) |
| M2 (r3) ES0430 | Firmware: all ADCs from TIM1 TRGO2, TIM8/TIM20 slaved (DESIGN §3.4, §8) |
| B2 DRV8316R stock | U3/U4 → **DRV8316CRRGFR** (C5447274); firmware section rewritten (CTRL6 = 0x19, 200 V/µs, DLY_TARGET) |
| D-06 | R301/R401 nFAULT pull-ups → own AVDD |
| D-09 | C305/C405 AVDD → 1 µF 50 V 0603 |
| D-13 | Added C308/C408 second 10 µF VM bulk |
| M2 (r5) | R300/R400 → 22 Ω 1206 (C17958) |
| D-12/R4-03 | DRV8316 footprint → custom `thumbsup:TI_RGF0040E…`; U7 → `Package_SO:MSOP-10_3x3mm_P0.5mm`; U8 → `QFN-20-1EP_3.5x3.5mm_P0.5mm_EP2x2mm`; U2 → `Texas_RGZ0048A…` |
| B3 INA229 stock | U7 → **INA239AIDGSR** (C2876522); INA229 documented as drop-in |
| D-01/M3/D-02/M4/D-05 sensor lines | Per connector: TPS22945 current-limited VS switch, SN74LVC3G17 Schmitt buffer from +3V3, 4.7k pull-ups; 100 nF on MTEMP |
| D-10 | 330 Ω + 22 pF C0G on each DRV8316 SOx at the MCU |
| M6/M9 | 1 nF on W_VA/B/C; 100 nF on W_NTC |
| M7 | VREF+ gets its own 100 nF + 4.7 µF; VDDA 100 nF |
| W-02/M3 (r5) L1 Isat | L1 → FNR5040S220MT (C167971) 1.8 A |
| W-03 D2 rating | D2 → SS34 SMA (C8678) |
| W-05/m4 C21 | → 1 µF 50 V 0603 |
| W-06/M1 (r5) C1 25 V | C1 → EEHZK1V331P 330 µF 35 V (C278516); hot-plug sim rerun: 1.6 V/µs |
| B5 C27 Y5V | → C377773 X5R |
| m1 R4 stock | → C137735 |
| m7 C64 | → 4.7 µF 16 V 0603 (C19666) |
| W-09 | C10 100 nF on BUCK_EN |
| R4-01 VC0 | D5 Schottky GND→CELL0 |
| R4-04 | R11 → 100 Ω, C9 → 2.2 µF 50 V 0805 |
| R4-05 | C11 1 µF on REGOUT |
| R4-06 | C4–C8 → 220 nF |
| R4-07 | "SHUTDOWN when stored" dropped; storage = unplug the balance lead |
| B4 SM06B stock | J2/J3 → SH1.0 6P clone C3029345 |
| W-08/D-07/M8 | R51 deleted (no open-drain SDO left on the bus) |
| R4-10 | J1 → custom vendor-land footprint |
| m8 | RS1–RS3 → custom HoLR 1–4 mΩ land |
| W-04, W-07, W-11–W-19, D-03/04/14–23, M5, M10–M18, R4-09/11–17 | Documentation / firmware notes in DESIGN.md §3, §7, §8 and compute-board requirements in §3.5 |

## Round 2 (round2_a–e) → rev C

| Finding | Change |
|---|---|
| R2A-02 hot-plug margin (stiff pack / short lead / aged or cold C1 → 4–6.7 V/µs) | **Q8 inrush limiter** back-to-back with Q7 (common source RPP_S), C12 220 nF G–S, C13 10 nF G–GND (Miller), D6 B5819W gate discharge to VBAT, D4 now G–S.  `spice/sim_hotplug.py` rewritten: 0.06–0.08 V/µs, 5 A in every case; bounce cases documented (DESIGN §7.2) |
| R2A-01 regen OV too slow | INA239 BOVL ≈ 19 V on ALERT → TIM1 break (hardware coast); C68 comment corrected (0.87 ms) |
| D2-01 (MAJOR) INA239 has no per-limit mask | §8: only SOVL + BOVL written, all others at reset; ALATCH = 1, CNVR = 0, APOL = 0 (also R4-13 / D2-05) |
| R2A-03 L1 Isat claim | Docs/calcs corrected: 1.6 A guaranteed, TI's recommendation |
| R2A-04 strap noise margin | Layout rule §6.3 |
| R2A-05…R2A-10 | §8: W_ARM EXTI handling, INA229 register differences + DEVICE_ID, CSA offset after wake, H-variant fault behaviour + AOE = 0, drum/power-switch note (§7.5), DBGMCU freeze + BOR |
| B-01 / m1 CBK 6.3 V | C307/C407 → 22 µF 25 V 0805 (C45783) |
| B-02 drive thermal | calcs §5 adds quiescent 0.27 W, dead-time loss, full edge = VM/(0.6·SR), worst-case RDS/SR; guidance ≤ 2 A rms continuous; OTW reporting on |
| B-03 / N2 / D2-13 TPS22945 CIN | C45/C48 → 4.7 µF 16 V 0603 |
| B-04 S-line glitches | R110–R112 / R114–R116 1 k series + C110–C112 / C114–C116 100 pF DNP |
| B-05 / C-04 NTC line unprotected | R113/R117 2.2 k series + D7/D8 BAT54S clamps; VS-to-phase short documented as residual (§7.6) |
| B-06 SH clone tabs / pin 1 | J2/J3 → custom `thumbsup:SH1.0-6P_RA_XUNPU_WAFER-SH1.0-6PWB`; silkscreen + pin-1 check (§6.8) |
| N-01…N-11 | Full DRV8316C register sequence with frames in §8; ILIM unusable noted; sequential CTRL writes; MT6701 programmed off-board; stale SLVSF16B refs fixed; TPS blanking 5–20 ms; REG_LOCK |
| D2-02 D5 margin | D5 → B5819W (lower VF at mA); plug-order rule (§3.1) |
| D2-03 C11 derating | C11 → 4.7 µF 16 V 0603 |
| D2-04 INA CS floats in reset | R12 100 k pull-up on INA_nCS |
| D2-06 / m4 BOM.md 68k list | fixed |
| D2-10/11/12/14/15/16/17 | §7.1 wording, LED meaning, BMS I²C floats without compute board, VM pin 10 note, C74 on U1 VBAT, main-negative-open residual (§7.7), stale refs |
| m2 C9 derating | C9 → 4.7 µF 50 V X7R 1206 (C29823) |
| N4 R11 pulse | R11 → 100 Ω 0603 (C22775) |
| m3 C4–C8 extended | → 220 nF 25 V 0603 Basic (C21120) |
| C-01 OPAMP5 config, C-02 ES0430 sequences, C-03 phase-voltage sampling | §3.4 ADC plan rewritten (3 equal injected ranks per ADC, fixed weapon pairing, equal regular groups, W_Vx at a fixed PWM phase); §8 OPAMP5 bits |
| C-05…C-10 | §3.5 compute-board heartbeat before ARM, SWD-only updates; §8 TIM1 never stopped, VREFBUF off, HSI margin |
| User question (braking/reversal) | §8 row: regen path, weapon reversal with ~10 A regen limit, no short-braking the drum |

## Round 3 (round3_a–e) → rev D

| Finding | Change |
|---|---|
| R3A-01 (BLOCKER) low-side inrush FET floats GND at power-on → BQ76907 cell inputs −12 V below VSS | Power switch moved to the **high side**: U13 LM74502 + back-to-back Q7/Q8 (common source), Cdvdt C13 22 nF + RG R1 4.7 k (2.7 V/ms, ~1 A), VCAP C12, VS C14, EN/UVLO R13/R14 (off < ~6.5 V).  BAT− = GND.  D4, D6 and the old R1/C12/C13 gate network removed.  RS4/INA239 moved after the switch (INA inputs ≥ −0.3 V).  Also removes R3A-06 (USB ground bypassing the switch) |
| R3A-02 (MAJOR) quick re-close with the real (not 30 Ω) load | R15 6.8 k bleeder: bus below the switch UVLO ~1 s after opening; re-close within that second 1.3–3.3 V/µs (< 4); DESIGN §3.1, §7.2 |
| R3A-03 / R3B-02 D6 leakage | D6 removed with the old topology |
| R3A-04 sim fidelity | `sim_hotplug.py` rewritten: LM74502 behavioural model, realistic load (buck constant power + UVLO, dividers, bleeder), true ramp rate, Q7 power/energy, re-close sweep to 3 s |
| R3A-05/07 notes | cell-1 error under load documented; stale U7 text fixed |
| R3B-01 BAT54S leakage on NTC clamps | D7/D8 → BAV99 (C2500, Basic) |
| R3B-03 OTW on nFAULT | CTRL3 = 0x0A4E (OTW polled over SPI) |
| R3B-04 / R3C-03 REG_LOCK blocks CLR_FLT | §8 fault recovery: unlock → CLR_FLT → relock |
| R3B-05/06, R3D M1–M8 doc mismatches | BOM.md, README, datasheets README rewritten; C25/C26/**C31** one 10 µF per half-bridge; U7 text; counts |
| N3-1 / N3-4 pulse dissipation | R113/R117 → 2.2 k 0603, R6 → 100 Ω 0603 |
| N3-2 DNP filter value | C110–C116 → 1 nF DNP |
| R3C-01 CC4 not a regular trigger | injected on TIM1_CC4 (both edges, 48 kHz), regular on TIM1_TRGO2 (OC6REF) |
| R3C-02 VREFINT sampling | regular rank 4 at 247.5 cycles on both ADC1 (VREFINT) and ADC2 (R_MTEMP) |
| R3C-04…10 | BOR as an option byte; ITR0; dual simultaneous ADC1/ADC2; bootloader pins; HSI figure; "centre of the low-side-on interval"; revision-ID check |
| E3-01 (MAJOR) no command-loss failsafe, hung Pico keeps ARM | **Dynamic ARM**: W_ARM_CLK (J1 pin 19) → C15 → D9 BAT54S → W_ARM (C16, R41 1 M, R18 pull-down); must be toggled by compute-board software; firmware command timeout + CRC (§8) |
| E3-02 (MAJOR) header is the only mechanical joint | MH1–MH4 M2 NPTH for nylon standoffs (§6.10) |
| E3-03 (MAJOR) single-sided vs J1 facing down | J1 alone on the bottom side (§3.5, §6.10) |
| E3-04 return current path | §6.2 layout rule, 1 oz inner copper |
| E3-05 NRST / MB_RX mid-level | R16, R17 10 k pull-ups |
| E3-06 brownout re-arm | fresh ARM edge required after any reset (§8) |
| E3-07 power budget | SOVL raised to 38 A; shared budget + sag foldback in §8 |
| E3-08 stop time / switch-open detection | §7.6 measure coast-down; firmware detects the switch open by ≈ 0 A (§7.5) |
| E3-09 heat budget | calcs §11 (~3.8 W average) |
| E3-10 vibration | C1 adhesive; 1206/2512 orientation rule |
| E3-11 testability | TP6–TP12 (W_ARM, W_EN, DRV_OFF, W_nFAULT, VBAT, 5V, GND); §9 step 3 safety-path tests |
| E3-12, E3-16–18 | antenna keep-out, balance-tap routing, W_ARM moved next to GND (pin 19), LED visible |
| User: drive motor = Repeat Mini Mk4.1 + magnet on the motor end + MT6701 | calcs §10 (speed, traction-limited current, stall, FOC rate); drives at 48 kHz; DESIGN §3.3 |

## Round 4 (round4_a–d) → rev E

| Finding | Change |
|---|---|
| R4A-01 / R4B-01 / D4-01 (MAJOR) ARM hold time: 1.3 s with the clock stuck high, 4–45 ms false disarm when hot (BAT54S leakage), one edge arms | C15 470 nF, C16 2.2 µF, R41 47 k: simulated 100–160 ms disarm stuck high or low at 25–85 °C (incl. 25 µA diode leakage), ~10 ms / ~8 edges to arm at 500 Hz, 2.74–2.83 V armed.  Compute board toggles at ≥ 500 Hz with gaps < 20 ms |
| R4A-02/03, D4-02, R4C-06 slow ARM edge into non-Schmitt LVC08, leakage vs 1 MΩ | U14 74LVC1G17 Schmitt buffer (C212314): W_ARM → W_ARM_S → U6 and PD2; R41 47 k swamps input leakage |
| R4A-04, D4-06 silent ARM-path faults | boot self-test (compute board holds the clock high, then low; the heartbeat reports W_ARM_S) in §3.5/§8 |
| R4A-05 gate-source overvoltage during a sag | D4 MMSZ5242B 12 V zener PSW_G → PSW_S |
| R4A-06 EN sink current shifts the UVLO | R13/R14 → 100 k / 22 k (off ~6.6 V, worst 7.35 V) |
| R4C-01/02 (MAJOR) CC4 both-edges trigger impossible / dies with MOE | injected trigger = TIM8_TRGO2 (OC6REF) at 48 kHz, drives in PWM mode 2, TIM1/TIM8 ARR 3542/1771, URS = 1 (§3.4) |
| R4C-03 ES0430 prescaler | asynchronous ADC clock from PLLP 42.5 MHz, /1, all ADCs |
| R4C-04 regular/injected collision | TIM1 OC6 regular trigger inside the documented windows |
| R4C-05 CPU budget | §8: bare-metal ISRs in CCM SRAM, measure at bring-up, fallback rates |
| R4C-07, D4-07 re-arm handshake | heartbeat "ARM edge required" flag; compute board holds the clock low ≥ 250 ms |
| R4C-08/09/10 | slaving details, 8.2–9.8 updates per electrical cycle, VREFEN, PWM_100_DUTY_SEL note |
| D4-03 no MCU watchdog | IWDG in §8; compute board pulses NRST if the heartbeat stops |
| D4-04 duty at 48 kHz | fixed by the TIM8_TRGO2 scheme (≤ 88 %) |
| D4-05 bus short not disconnected | §7: documented; optional inline fuse in the pack lead |
| D4-08 stack mechanics | §3.5/§6: standoff height = mated header height, max part height under the board, no bare power copper on the bottom facing the compute board, soft-mount the stack |
| D4-09 two-sided cost | §3.5 option: through-hole 1.27 mm header hand-soldered instead of JLC second side |
| D4-10 builder view | §7 note: the cell monitor block can be DNP for a fight build |
| D4-11 retry storms | §8: fault counter + latch-off for DRV8323 OCP retries and DRV8316 recoveries |
| R4B-02…07, notes | docs/calcs numbers re-synced to the new simulation; R13 class; reversed pack + balance lead (R6/U8 damage) moved to §7 residuals; D1 text |

## Round 5 (round5_a–d) → rev F

| Finding | Change |
|---|---|
| R5D-01 (MAJOR) board does not fit the chassis bay single-sided | two-sided placement plan + area/mass budget (DESIGN §1, §4, §6.13): power/tall parts top, low-profile passives/logic bottom; outline to be drawn from the chassis before layout |
| R5A-01 (MAJOR) boot self-test cannot catch R41 open | timed self-test (toggle → hold high → toggle → hold low; MCU times the PD2 falling edge, pass 25–250 ms); failure action = refuse to arm (§3.5) |
| R5C-01 (MAJOR) drive duty cap ignores DRV8316 dead time | drive duty ≤ ~81 % (L) / ~84 % (R), flat-bottom SVPWM; DLY_TARGET 1.8 µs option (§3.4, §8) |
| R5A-02, R5B-01, R5D-06 ARM timing figures / reproducibility | `spice/sim_arm.py` + `arm.out` (U14 thresholds, 25/85 °C, 250 Hz–10 kHz): 52–164 ms nominal, ~30–200 ms with tolerances; docs and §9 windows updated |
| R5A-03 W_ARM_S floats if U14 opens | R19 100 k pull-down |
| R5A-06, R5B-02 re-close margin (3.98 V/µs worst corner) | UVLO R14 22 k → 18 k (off ~7.8 V): worst corner now 3.4 V/µs; bus below UVLO in ~0.3–0.4 s; sim adds min-UVLO / cold-C1 cases; "wait ≥ 2 s" |
| R5B-03 bus load 35 k vs 18.7 k | sim and calcs use 18.7 kΩ; drain figures corrected |
| R5B-04 docs said U6/PD2 take W_ARM | §2, §3.2 now W_ARM_S |
| R5B-05 C25792 on two lines | R41 value text unified (62 BOM lines) |
| R5B-06, R5D-08, N-notes | §4a 0603, 8–10 updates per electrical cycle, stale labels, C17/U14 in docs and calcs |
| R5C-02 CPU fallback broke the 2:1 lock | fallback keeps 48 kHz PWM, loops at 24 kHz |
| R5C-03 IWDG only from the control loop | task-flag watchdog, HardFault safe state, debug freeze |
| R5C-04 ARM edge filter contradiction | falling edge acts at once, only the rising edge is qualified |
| R5C-05, N1, N3 | regular windows relative to CCR6; ADC errata handling (circular DMA, JQDIS before JSQR, discard first samples, reject rev Z); TIM1 MMS/start sequence |
| R5D-02 mass budget | §4 estimate; weigh at bring-up |
| R5D-03 stack-up contradiction | §6.2 explicit stack-up (no pack current on the bottom) |
| R5D-04 SMD wire pads peel | J_BAT±, J_WA–WC, J_LA–RC → KiCad `Connector_Wire:SolderWire-…` plated through-holes (3 custom footprints removed) |
| R5D-05 Pico VSYS diode misstated | §3.5 item 2: Schottky from +5V into VSYS |
| R5D-07 "deep-discharge cutoff" | renamed logic cutoff; §7.17 not pack protection, idle drain, low-cell alarm |
| R5D-09…15 | IWDG debug freeze + NRST rule suspended during SWD; CTRL4/CTRL5 written and read back; §9 step 0 post-assembly; single-fault list incl. U6/U14; bring-up 1.5 A first closure; LiPo 4.20 V/cell only; ARM toggle from a RAM timer ISR, no flash erase while armed, link timeout vs controller report behaviour |

## Round 6 (round6_a–d) → rev G

| Finding | Change |
|---|---|
| R6D-01 (MAJOR) area budget / chassis fit | user decision: area is settled at layout.  §4/§6.13 now an informational estimate (~3600–4400 mm² vs ~3100 mm² bay) with the levers; "fits the chassis" no longer claimed |
| R6B-01 (MAJOR) / R6A-01 hot-plug model gate-sink leak hid the worst re-close | sink now acts only below the falling threshold; "min UVLO" cases at the true worst bus level (7.7 V: minimum threshold, 1 % resistors, no sink); UVLO R14 18 k → **15 k** (off ~9.0 V typ, 7.7–10.0 V) to cut the worst re-close step |
| R6B-02 bus DC load 18.7 k vs ~66 k | sim and calcs use 66 kΩ (the weapon phase dividers have no DC path while Hi-Z); drain and decay figures corrected |
| R6A-02 reversed pack: C13 to GND can turn Q7/Q8 on | **D10 1N4148W** steering diode in series with C13 + **R32 1 M** reset; sim: 100–145 A without D10 (weak U13 hold) → only the C14 spike with it; §9 reverse test as a step |
| R6A-03 R19 100 k vs input leakage | R19 → 10 k |
| R6A-04 / R6C-03 self-test timing reference | compute board times the test; heartbeat fields defined (§8, ≤ 10 ms); single-edge step added (N-02) |
| R6A-05 hole sizes | docs give the real drills (2.15 / 1.15 mm) and thermal-spoke rule |
| R6A-06 / R6D-04 bottom-side exposure, heights | wire joints outside the compute-board outline or insulated; U13/BAT_IN, TPs and parts > ~1.1 mm (U5, C9, SOD-123) on top (§6.9, §6.13) |
| R6D-02 mass | ~4 g per 1000 mm² → 18–23 g board, 32–42 g stack |
| R6D-03 / R6B-03 "J1 only bottom part" | §3.5 rewritten (two-sided assembly required) |
| R6D-05 test pads unreachable | TP1–TP12 on the top side |
| R6D-06 compute-board ISR keeps ARM on a hung main loop; stale frames | permission refreshed every ≤ 50 ms; sequence number must advance |
| R6D-07 radio-loss time unbounded | ≤ 0.5 s requirement, tested |
| R6D-08…11 | pause-tolerance wording; §9 MT6701 programming + weapon supply; §7.20 U2 buck single point; Pico USB cut-out |
| R6C-01 drive R duty cap | rank-2 pair, C = −(A+B): ~86 % |
| R6C-02 DLY_TARGET | 1.8 µs default (CTRL10 0x1818), CCR6 ≈ 257–264, regular windows [3.34, 13.59] / [24.18, 34.43] µs, weapon ranks 1–2 |
| R6C-04 top speed | ~3.7 m/s at 16.8 V (duty-capped); motor ≤ ~47 k rpm, inside the MT6701 rating |
| R6C-05 OPAMP self-calibration | forbidden (factory trim) |
| R6C notes | CLL lockup → break, no flash erase while running, CTRL3 read-back + mismatch action, break flags cleared at boot, USART1 clock text, CCR6 trim in §9 |
| R6B-04/05, notes | stale netlist comments, spice README (arm.out), stock figures |

## Round 7 (round7_a–d) → rev H

| Finding | Change |
|---|---|
| R7B-01 (MAJOR) / R7A-02 sim comparator not hysteretic, worst re-close under-reported | `sim_hotplug.py`: hysteretic EN/UVLO comparator (sw with vt/vh) gating source and sink; finer re-close sweep (350/400/450 ms) and a 40 µA min gate-current case: worst re-close **3.44 V/µs** (min UVLO, C1 300 mΩ, re-closed just before the FETs open), 14 % under 4 V/µs |
| R7A-01 switch UVLO sees the weapon ripple unfiltered | **C18 100 nF** on PSW_EN (1.3 ms); firmware current fold-back at ~12 V made an explicit requirement |
| R7A-03, R7B-02…05, R7D-01 stale thresholds/figures | §4 switch UVLO 9.0 V (7.7–10.1 incl. 1 % resistors), on ≤ 10.8 V; netlist R13/R15/R32/C13/D4 text; ramp 2.2 V/ms (1.3–3.0); inrush ~0.8 A; 0.1–0.4 s to UVLO |
| R7B-06, R7D-05 gap wording | §3.5: gaps beyond ~30 ms may disarm (~50 ms nominal) |
| R7B-07 spice README / docstring | updated (D10/R32, reversed pack, sweep range, rev) |
| R7B-08 / N-06 D10 datasheet | datasheets/1N4148W.pdf |
| R7C-01 read-back expected values | §8: CTRL2 reads 0x7C, NPOR = 1 good; full expected set |
| R7C-02 CLL on TIM20 | BKE = 1, BKINE = 0 on TIM20 |
| R7C-03 break-flag ordering | cleared after U2 wake fault, DRV8316 clear, INA alert read |
| R7C-04 W_ARM_S row | heartbeat reports the edge; compute board times it; field widths/ack |
| R7C-05 sequence wrap / reboot | session ID + 16-bit modulo sequence |
| R7C-06 trigger setup | TIM8 OC6 PWM mode 2, TIM1 OC6 CCR ranges, DUAL = 00001, weapon sample by DIR |
| R7C notes | heartbeat CRC/counter; CCR6 sweep method; short-pulse delay-comp check; single SPI3 owner; SDO open-drain before config |
| R7D-02 radio loss must stop drives; tests | §3.5 requirement; §9 transmitter-off / hung main loop / switch-open-with-drum tests |
| R7D-03 weapon control rate | §8: 7 pole pairs (confirm), observer with angle prediction at speed |
| R7D-04 jammed drum | §8 stall cut-out (current limit, no speed rise > 0.5 s, TH1 > 100 °C) |
| R7D-06 open MODE/GAIN straps | §7.16 + boot 1x/3x discrimination and offset check |
| R7D-07/08/10/11 | §7.5 coast weapon too + re-close with drum spinning; compute-board 470 µF hold-up; no MB_RX drive while unpowered; §7.21 phase short vs FET rating, comparator fast trip note |
| R7D-09 encoder plausibility | §8 timer-inputs row |

## Round 8 (round8_a, b, d) → rev I

| Finding | Change |
|---|---|
| R8D-02 BAT_IN rings to 40–60 V on a loaded switch opening; C14 50 V | C14 → 100 nF 100 V X7R 0805 (C28233); Q7 avalanches by design |
| R8D-04 compute-board reset pull-down loads VBAT_SNS | R33 100 k series on the header branch (J1.11 = VBAT_SNS_H); 18.5 V coast from the INA239 VBUS |
| R8D-01 weapon ripple at the DRV8316 VM pins | layout rule §6.6 (VM from C1 on its own branch) + §9 step 6 scope check |
| R8D-03 R45/R46 open straps | §7.16 + §9 step 2 strap-pin voltage check |
| R8D-05 hard bus short | §7.14: UVLO retry into the short will likely kill Q7: inline fuse recommended |
| R8D-06/07, R8B-01…03, audit notes | §7.2 3.44 V/µs; inrush 0.8 A; sim docstring; grounding plan (one solid L2 plane); §6.6 placement incl. C18/D10/R32; §7 item order; C110–C112/C114–C116; PA2 COMP2_INM; reserve U1 too; calcs Isat 1.6 A; U14 VT− at 3.3 V; FET comment 1.4 mΩ; bench ≥ 1.5 A with the compute board attached |
| R8A-01 C18 delays the UVLO: loaded contact bounce re-closes hard (up to 4.3 V/µs at C1's −40 °C ESR) | sweep in review/round8_c18_sweep.md: no C18 value avoids it without the ripple trip.  C18 kept; operating envelope ambient ≥ 0 °C (DESIGN §1): worst 3.37 V/µs; loaded-bounce cases added to `sim_hotplug.py`; §7.2 residual; "~9 V step" wording qualified as unloaded |

## Round 9 (round9_a, b, d) → rev J

| Finding | Change |
|---|---|
| R9D-02 only firmware limits weapon phase current between 20 A and the 62–93 A VDS trip (INA239 sees pack current) | **PA2 ↔ PB11 swap**: W_SOC → PB11 (ADC1_IN14 + COMP6_INP), W_VC → PA2 (ADC1_IN3); all three weapon CSAs reach a comparator (COMP3/COMP1/COMP6) → TIM1 break; §3.2/§6/calcs text corrected |
| R9D-01 weapon fault-clear kick (6–36 V/µs at the DRV8316 VM pins) | §7.21 + §8: required comparator fast trip, latch off on the first large trip (the ~0.5 µs / ≤ 3.8 V/µs figures were optimistic: corrected in rev K, see round 10) |
| R9D-03 regen with the pack disconnected: D1 is the real clamp | INA239 conversions ≤ 150 µs; D1's role and open-D1 single fault in §7.21 |
| R9D-04/05 | self-test window rationale; U6 stuck-high = partial brake on a coasting drum |
| R9A-01 60 mΩ "aged 0 °C" C1 ESR not supported by the ZK datasheet | bound 100 mΩ (interpolated); sim bounce cases at 100 mΩ: worst **3.76 V/µs** (~6 % margin); §1, §5, §7.2, round8_c18_sweep.md updated |
| R9A N-01/N-03 | §3.5: compute board reads VBAT_SNS_H through ~109 kΩ (pulls off, 10 nF); keep BQ76907 TS protections off |
| R9A N-02 C13 DC-bias derating | C13 → 22 nF 50 V 0603 (C21122) |
| R9B-01/02 R33 could be bypassed when drawing | §2/§3.4 text; J1 pin 11 named VBAT_SNS_H |
| R9B notes | C14 100 V in §3.1 and the flex rule; bounce range 0.1–1.2 ms; 54 mJ everywhere; pause ~45–50 ms; spice README/docstring bounce cases |

## Round 10 (round10_a, b, d) → rev K

| Finding | Change |
|---|---|
| R10D-01 realistic weapon trip (~0.8–0.9 µs) still kicks the DRV8316 VM at 9–11 V/µs | **R302/R402 0.1 Ω 1 W 2512 (C25466)** in each DRV8316 VM feed + **C309/C310, C409/C410** (4 × 10 µF per drive, ~16 µF): new nets L_VM/R_VM (VM pins, VM caps, CP cap).  Sim: loaded bounce 3.75 → 2.25 V/µs, worst re-close 3.44 → 2.06 V/µs, C1 at its −40 °C ESR 4.3 → 2.65 V/µs, weapon fault-clear kick ~1 V/µs.  The ≥ 0 °C envelope is no longer a margin condition.  Cost 0.1–0.4 W per drive |
| R10D-02…05 | §8 weapon fast-trip settings (OSSI = 1, BKF = 0, blanking, comparators only while U2 is awake, interrupts, internal DAC only); coverage 30–60 A by angle → ~25 A threshold; §9 step 4 trip test; PA2 is FT |
| R10B-01/02 | README/BOM.md revision labels |
| R10B notes | PC3 wording, bounce cases 0.1/0.3/0.8 ms, sim docstring, reviewer-sim provenance, U1 stock, 44 µs cell-to-cell filter |
| R10A-01 fast-trip timing claim | §7.21 rewritten: realistic chain 0.7–1.0 µs; with R302/R402 ~1–2 V/µs; phase-to-ground short (VDS trip only) ~7–8 V/µs residual |
| R10A notes | §8 fast-trip row: CSA inverts (trip below ~0.45–0.65 V), DAC3_CH1/DAC4_CH2, BRK not BRK2, dead time 0, blanking off, POL = 0 |

## Round 11 (round11_a, b, d) → rev L

| Finding | Change |
|---|---|
| R11B-01 passives per drive channel | ~20 |
| R11B notes | sim now models the real cap placement (3 bridge MLCCs on VBAT, both DRV8316 VM filter branches): results move ≤ 2 %; Q7 22.0 W, 54–57 mJ, VM 0.002–0.005 V/µs, reversed pack 102–147 A; "≤ 2.7 V/µs" scoped to switch/bounce events; fault-clear kick ~1–2 V/µs; R302 datasheet added (pulse curve absent: stated); heat budget incl. R302/R402; §8 drive VM feed-forward; mcu_pinmap NRST/BOOT0 labels |
| R11D (system: ROUND CLEAN, notes) | comparator default 30 A; weapon latches off on its first VDS OCP / comparator trip; **C19 1 nF** on W_nFAULT at PC13 (BKF = 0); §9 step 4: trip test on a pack + VBAT − L_VM ≈ 0.1 V/A check; §7.16 R302/R402 short / missing VM caps; blanking wording; §3.2 coverage text |
| R11A-01 R302/R402 loss understated | 0.11/0.24/0.52 W at 1/1.5/2 A rms (PWM ripple through the filter), ≤ ~1 W in weapon bursts; heat budget row; layout rule (off the DRV8316 thermal copper) |
| R11A notes | "≤ 2.75 V/µs"; §7.21 pulse wording (~3 K rise, fuse role) |

## Round 12 (round12_a, b, d) → rev L

| Finding | Fix |
|---|---|
| R12B-01 stale sim numbers | DESIGN §3.1/§5/§7.2 now quote hotplug.out: 2.09, 0.8–2.26, 2.66 V/µs |
| R12B-02 Q7 / τ half-applied | calcs 22.0 W, 54–57 mJ; DESIGN τ ≈ 2.3 s (~374 µF) |
| R12B-03 no rev bump for C19 | Package is rev L (rounds 11–12); DESIGN rev history, BOM.md, README, CHANGES heading |
| R12B-N01..N04 | L1 maker Changjiang; DNP 1 nF labelled "1nF 50V"; 2.26 V/µs in R302 description; OPAINTOEN |
| R12D-01 fault latch policy | §8 fault classes: short class latches (VDS OCP or 2nd comparator trip in ~1 s); supply class (VBAT dip, U2 UVLO, recharge SOVL, CP-UV/NPOR) auto-restarts, not counted; single comparator trip → catch-spin restart; latch cleared only by an explicit compute-board command (+ disarm/new ARM edge for the weapon) |
| R12D-02 drive start angle | §8 Timer inputs: d-axis alignment at enable after reset / sensor re-power / invalid angle; Z as reference; §9 step 6 checks |
| R12D-03 R44 shorted → 6x | §7.16 + boot test reads W_Vx during the INH pulse |
| R12D-04 encoder over-speed | §8 speed cap ≤ ~50 k rpm on the encoder; field weakening only sensorless (§3.3) |
| R12D-05 bring-up | §9 step 3 armed soak (zero disarms); step 6 full-pack regen VBUS < 18.3 V |
| R12D heat budget | calcs §11 adds DRV8323 quiescent + gate drive (0.3 W): ~4.4 W average |
| R12A-01 R302/R402 check could not detect a short | §9 step 0: unpowered 1 A force between TP10 and an L_VM/R_VM pad → 0.10 V (in-operation check removed: bus current is only mA) |
| R12A-N01/N02 | §8: DRV8316 SDO Hi-Z with CS high (CTRL2 reset 0x60 push-pull); VM feed-forward from VBAT − I_bus × 0.1 Ω |

## Round 13 (round13_a, b, d) → rev L (text only)

| Finding | Fix |
|---|---|
| R13B-01 weapon latch stated two ways | §7.21 and §8 fast-trip row now defer to the §8 fault classes |
| R13B-N01..N04 | §3.3/§7.16 2.26/2.09 V/µs from hotplug.out; OPAEN; calcs §10 field-weakening wording; Q7 54–57 mJ everywhere |
| R13A-01 supply class undetectable for short bounces | §8: classify by W_nFAULT low time (< ~3 ms UVLO/wake vs ~4 ms VDS OCP), SOVL without a comparator flag, a VBAT dip (> ~2 V below the running mean of the 24 kHz VBAT_SNS samples); DRV8316 CP-UV/NPOR only for long dips; > ~5 restarts/s → 1 s hold-off; unmatched break = short class |
| R13A-02 start angle can be 180° off | §8: two-step alignment with an encoder-motion check; MT6701 power-up ABZ train off; Z offset measured and stored at bring-up (§9 step 5), checked at the first Z |
| R13A-N01..N03 | §9 step 0 measure on R302's own pads; §7.16 6x boot test only when W_Vx ≈ 0; §6 keep DRV_OFF (PC14) short |
| R13D-01 single-chip DRV8316 event → endless restart | §8: CP-UV/NPOR are supply class only with a bus dip or both chips; single-chip events count toward that drive's latch; per-drive hold-off via TIM8/TIM20 MOE (DRV_OFF only for both); §9 R_nCS-held-high test |
| R13D-02 start angle | (with R13A-02) no alignment while moving (sensorless until stopped); offset instead of zeroing the count; stored Z offset checked at first Z; 180° start test |
| R13D-03 lost encoder at standstill | §8: no edges for ~150–200 ms with torque → angle step probe → sensorless + report; §9 unplug test |
| R13D-N1..N3 | §8 short-class precedence; classes for GDF, OTSD/OTW, BOVL, overload SOVL, stall; latches in TAMP backup registers, no auto-re-arm; §7.16 boot test ≥ 30 µs one-shot with in-pulse sample, fail → latched |

## Round 14 (round14_a, b, d) → rev L (text only)

| Finding | Fix |
|---|---|
| B14-01 per-drive "coast" does not exist | §8: DRV_OFF high for the check; a latched drive is held at 0 % duty (low sides on) once slow, then DRV_OFF released for the healthy drive; self-Hi-Z faults need no hold-off |
| B14-02 lost-encoder probe false-trips on a pushing stall | §8: no standstill detector (ABZ has no status); heartbeat "no edges, torque commanded" flag; observer catches it when moving; return to encoder on edges + matching Z; §9 stall-against-wall test |
| B14-03 rows still using DRV_OFF for single-chip events | §8 DRV8316 and timers rows defer to the fault classes / per-drive hold-off |
| B14-04 SOVL classified twice | supply class needs a VBAT dip within ~1 ms; without a dip it is overload |
| B14-05 §3.5 auto re-arm vs latch | §3.5 re-arm only with no weapon latch reported |
| B14-06 rev labels | rev L rounds 11–14; README fourteen |
| B14 notes | t_RETRY measured at bring-up; boot test placed in the boot order; latches lost at BOR; §9 unplug/stall tests |
| R14A-01 per-drive coast | (with B14-01) |
| R14A-02 VBAT-dip rule | §8 bus event = VBAT_SNS falling slope > ~5 V/ms (bounce ≥ ~10, load step ≤ ~2.5 V/ms); SOVL is supply class only after a bus event or U2 UVLO |
| R14A-03 W_nFAULT timing | §8 re-read/clear DIAG_ALRT every ≤ 0.5 ms while low; §9 step 4 measures OCP and UVLO release times |
| R14A-04 lost-encoder probe | (with B14-02: probe removed) |
| R14A-N01/N02 | first-Z threshold 30°; backup-domain access notes (RTCAPBEN, DBP, never RTCSEL) |
| R14D-01..08 + notes | The §8 fault prose is replaced by **§8.1 Fault policy**: an ordered weapon-break classification table (short = comparator re-trip ≤ ~200 µs after re-enable or measured VDS-OCP retry; isolated trips restart with cool-down, never latch; bus event from INA239 VBUS or VBAT_SNS slope; W_nFAULT timing with DIAG_ALRT re-reads; SOVL-only = overload fold-back; unknown = short), a drive-event table, per-drive coast via 6x mode + INH high (reviewer-confirmed Hi-Z), SPI health check (INA239 ID), stall cut-out as cool-down, MCU-reset counting, CRC'd latch word in backup registers, operator-only clearing and a throttle-zero interlock (§3.5 updated).  §8 timer inputs: alignment sign check (wiring fault latches, no sensorless fallback), stale Z offset reported not applied, optional torque-relax probe.  §9 step 6: classifier, phase-swap and 6x-coast tests |

## Round 15 (round15_a, b, d) → rev L (text only)

| Finding | Fix |
|---|---|
| R15A-01 6x-mode coast unsafe; CTRL4 DRV_OFF bit exists | §8.1 per-drive coast = CTRL4 0x0C90 (bit 7 "Hi-Z FETs", Table 8-21; verified parity), register check expects 0x90 while coasted; bench-verify |
| B15-01 / R15D-02 SOVL/BOVL swallowed by the timing row | §8.1 reorders: DIAG_ALRT (BOVL, SOVL) before the W_nFAULT timing rows; U2-only wake/UVLO acts on the weapon only, counted, latches after ~5 in 10 s |
| R15A-03 / R15D-01 bus evidence not there at the break | ISRs only record; the SPI owner task classifies after the first INA239 conversion started after the event, VBAT_SNS window −1…+0.5 ms |
| R15D-03 / R15A-04 200 µs window | window from the first applied vector, two consecutive fast re-trips; ~3 restarts ending in trips before speed → latch (standstill phase short); restarts always three-phase FOC |
| R15A-02 / R15D-04 / B15-02 deaf chip | §8.1 drive rows 3/4 split unpowered (nFAULT low, CSA ~0 V) vs powered-but-deaf (DRV_OFF high, both drives latched); §9 tests updated |
| B15-03 register check vs coast | CTRL4 expected 0x90 while coasted |
| B15-04 TH1 latch vs cool-down | over-temperature never latches (row 9, §8 weapon-safety row) |
| R15D-05 switch open | §8.1 row 0 hold until operator clear |
| R15D-06 NRST reset loop | §3.5: ≤ 2 resets per 10 s, heartbeat within ~50 ms, then stop |
| Notes | BORRSTF/PINRSTF, cumulative uptime timebase in backup regs, compute board mirrors the weapon latch across power cycles, self-test with weapon command at zero, supply-restart budget, INA239-only failure, latched comparator flags, strap boot-test row, W_EN pulse on GDF clear, §3.3/§8 cross-refs, ≤ 34 A explained, §9 classifier expectations |

## Round 16 (round16_a, b, d) → rev L (text only)

| Finding | Fix |
|---|---|
| B16-01 CTRL4 0x0C10 odd parity | leave coast with 0x0D10 |
| B16-02/03 rewrite and boot un-coast a chip | §8 DRV8316 sequence writes CTRL4 0x0C90 (coasted); "release" 0x0D10 is a separate last step for unlatched drives only; the rewrite is the same sequence |
| B16-04 row 5 latches a jammed drum | row 5 is now a restart DC resistance check (V/I per phase pair vs the bring-up value); jams go to row 10 (retry, never latch) |
| B16-05/06 stale row refs | §8 fast-trip → row 6; §7.21 matches rows 4/5 |
| B16-07 polled TH1 had no row | row 10 covers polled TH1 > ~100 °C; row 9 uses TH1 > ~90 °C for U2 OTSD |
| B16-08 rev labels | rounds 11–16, sixteen |
| Notes | CTRL1 in the read-back list; row 0 needs ≥ ~5 A commanded for ≥ ~50 ms; nFAULT from a commanded coast is not an event |
| R16A-01 CTRL4 exit parity | (same as B16-01) 0x0D10 |
| R16A notes | drive rows 3/4 criteria (CTRL2 0x00 = not answering; row 3 needs nFAULT low and all CSAs < 0.3 V, else row 4); INA239 config read-back each poll; firmware computes DRV8316 parity; light-load bounce may be row 7; first heartbeat early in boot; INA239 latency |
| R16D-01 row 0 switch-open | continuous monitor (\|I\| < ~30 mA, VBUS > 8 V, ≥ ~100 ms, any drum state, suspended in regen), hold stored in the latch word; bounces never reach it |
| R16D-02 row 5 | (with B16-04) restart DC resistance check |
| R16D-03 single bad read → both drives latched | row 4 confirmed by ≥ 3 reads with the other devices answering |
| R16D-04 swapped sensor cables | align one drive at a time, other encoder still; §9 swap test |
| R16D notes | overload budget ramp-back; U13 restarts in the supply budget; latched drive INH high; BOR resets → supply budget; compute-board latch copy program-only flash write; weapon direction check after rewiring |

## Round 17 (round17_a, b, d) → rev L (text only)

| Finding | Fix |
|---|---|
| B17-01 resistance check vs a slow drum's BEMF | row 5 runs only with the drum stopped (< ~50 rpm) |
| B17-02/03/04 stale refs | TH1 → row 10; INA239 row → continuous monitor; 0x0D10 = Release word |
| B17-05 rewrite vs DRV_OFF pin | boot with the pin high; single-chip rewrite leaves the pin as is |
| B17-06 flash write while armed | compute board disarms on a weapon latch, then persists its copy |
| B17-07 first heartbeat | in the §8 boot order after clocks |
| B17-08 nFAULT at bring-up | §9 step 2 checks nFAULT high after Release with DRV_OFF low |
| B17-09 TIM8 break idles INH low | TIM8/TIM20 OISx = 1 |
| Notes | DIAG_ALRT poll flags use the classifier |
| R17A-01 resistance check | drum stopped by W_Vx < ~25 mV; R = ΔV/ΔI from two same-polarity steps; reference stored with the drum fitted |
| R17A-02 row 0 vs back-driven regen | averaged ≥ 100 ms mean; suspended while any motor's electrical power is negative or the firmware pack-current estimate is near 0; idle current measured at bring-up |
| R17A-03 DIAG_ALRT read clears evidence | every read feeds the classifier; health poll compares config bits only |
| R17A notes | alignment still-encoder tolerance; CTRL4 exit bench check; CTRL2 bit 6 never written 0 |
| R17D-01 unbounded BOVL restarts | row 1: pack current ≥ 0 at the trip → row 0 hold; else restart with halved regen limit, > ~3 in 10 s → held until operator clear |
| R17D-02 coasting drum suspends row 0 | only actively driven motors suspend it |
| R17D-03 switch-open hold persisted as a latch | own flag, not persisted, cleared by a fresh power-up |
| R17D-04 swapped sensor cables | drive row 7: both drives sensorless until re-alignment after operator clear |
| R17D notes | stopped-drum test calibration/averaging/2 s timeout; check on first start after arming; re-measure reference after motor/lead change |

## Round 18 (round18_a, b, d) → rev L (text only)

| Finding | Fix |
|---|---|
| B18-01 DRV_OFF pin nFAULT → false supply events | §8.1 drive table first-match; nFAULT while/after DRV_OFF pin high or a commanded coast is not an event; re-arm TIM8/TIM20 MOE after Release |
| B18-02 BOVL sign after the coast | uses the last INA239 reading before the event |
| B18-03 undefined persistence of holds | row 1 cap → weapon latch; "supply unstable" and drive row 7 stored in the latch word |
| B18-04 break idle level | §3.3 updated; OSSI = 1 on TIM8/TIM20 |
| B18-05 boot never releases the chips | boot order: DRV_OFF pin low + per-chip Release, then MOE |
| B18-06 labels | rounds 11–18 |
| Notes | NPOR = 1 wording; two-device SPI failure = SPI3 fault; idle current measured in step 4 |
| R18A-01 BOVL switch-open test | first two post-alert conversions: \|I\| < ~50 mA and VBUS stays > ~18 V (closed switch: bus back near the pack in ~0.15 ms); §9 tests both cases |
| R18A-02 OSSI | (with B18-04) |
| R18A-03 stopped-drum test | max \|W_Vx\| over ≥ 200 ms + catch-spin no rotation; ΔV from differential duty × VBUS |
| R18D-01 bounce during regen → hold | row 1 "looks open" → weapon coast, drives zero torque, row 0 (100 ms) decides; a returning current restarts as supply |
| R18D-02 estimate includes coasting drum | estimate from actively driven channels only; suspension drops samples and restarts the mean |
| R18D-03 shorted C2 → permanent hold | plausibility: ≈ 0 A with a steady bus and a stopped drum → INA239-failure path |
| R18D notes | drive row 7 only when the aligning drive's own encoder stayed still; drive row 1 includes DRV8316 OVP with an INA239 BOVL |

## Round 19 (round19_a, b, d) → rev L (text only)

| Finding | Fix |
|---|---|
| B19-01 left drive left braking after DRV_OFF-pin restarts | §8.1 "drives resume" procedure for every DRV_OFF-pin low and Release (fault recovery if nFAULT still low, wait high, clear break, MOE); exemption covers it |
| B19-02 watchdog row break clear | TIM1 at boot; TIM8/TIM20 only via drives resume |
| B19-03 latch word contents | lists supply-unstable, row 7, row 1 count, supply-budget history |
| B19-04 double count / table precedence | one event one count; weapon row 1 deferral governs drives |
| B19-05/06 §9 ordering | idle current in step 4; drum fitted before the reference |
| Notes | "commanded" wording; latched drives excluded from resume; C1 ~30 V (CHANGES B18-02 row superseded by R18A-01) |
| R19A-01 TIM8 re-enable | (with B19-01 drives resume) + §9 link timeout/recover test |
| R19A-02 stopped-drum test at the noise floor | ~1 ms average before the max; threshold from a stopped-drum reading in §9 step 6, hand-turn check |
| R19A notes | plausibility also under ≥ ~1 A estimated load; OSSI in the timers row; INA239 AVG = 1, CNVRF |
| R19D-01 crossed motor bundles look like crossed sensor cables | row 7 report "left/right crossed: sensor cables or motor bundles"; §9 forward-move check after any drive rewiring |
| R19D-02 INA239 failure modes | cross-check vs the firmware estimate (~200 ms) → INA239-failure path; plausibility gate widened; overload fold-back floor at the drives' traction limit |
| R19D notes | estimate = idle + actively driven channels; row 1 open-bus-under-load note; IC_STAT FAULT in the 100 Hz poll |

## Round 20 (round20_a, b, d) → rev L (text only)

| Finding | Fix |
|---|---|
| B20-01 / R20A-02 plausibility & cross-check vs a coasting drum | the ≥ 1 A clause counts only a motoring weapon; cross-check only with the drum stopped or motoring; §9 step 3 switch-open-while-driving test |
| R20A-01 silently reset DRV8316s re-enabled | drives resume reads IC_STAT/NPOR/registers first; reset chips get rewrite + Release, counted once with the supply event |
| B20-02 resume timeout | classify through the drive table (first match) |
| B20-03 boot order | Release then drives resume (pin low, nFAULT wait, break clear, MOE) |
| B20-04 labels | rounds 11–20, twenty |
| B20-05 INA239-failure exit | held until operator clear (latch word), re-enters while still failing |
| Notes | INA239 ADC_CONFIG 0xB480 (verified); IC_STAT FAULT expected 0; left/right-crossed wording; watchdog row; step 4 idle-draw wording; §9 drive-after-Release check |
| R20D-01 silent DRV8316 reset loop | (with R20A-01) |
| R20D-02 switch-open while driving | (with B20-01 / R20A-02) |
| R20D-03 shove during alignment latches a drive | drive row 6 disturbance → repeat (movement 0.5–2× expected, encoders still); row 6a wiring fault only after two clean wrong-sign alignments; §9 shove test |
| R20D notes | row 9 reason "INA239" when failed; resume brake window bench check at top speed |

## Round 21 (round21_a, b, d) → rev L (text only)

| Finding | Fix |
|---|---|
| R21A-01 resume brake trips OCP at speed | "drives resume" rewritten: chips stay coasted while the pin goes low; BKE off, MOE with FOC at zero current on a valid angle (or wait until slow); then Release; OCP in a resume window counted separately; §9 top-speed resume test and no-angle speed limit |
| B21-01 drive row 6 swallows row 7 / low-motion path | row 6 ordered (a) crossed → row 7, (b) too little motion → timer-row path, (c) disturbance → repeat ≤ ~5 then sensorless |
| B21-02 switch open under throttle | weapon with positive torque but negative power is coasted at once (coasting-drum rules then apply) |
| B21-03 latch word | INA239-failure hold listed |
| B21-04 IC_STAT FAULT expectation | only with the pin low and outside a resume |
| B21-05 §9 ordering | switch-open tests moved to the end of step 6 (incl. drum under throttle) |
| Notes | silent reset without supply event → drive row 2; row 1 waits for its second conversion; Release only via drives resume (§8 row, boot order, per-drive coast) |
| R21D-01 row 6 blocks rows 7 / low-motion | (with B21-01) |
| R21D-02 switch open under throttle | (with B21-02) |
| R21D-03 one bad INA239 read | ≥ 3 consecutive bad polls; a mismatch fixed by one rewrite is reported only |
| R21D-04 single-chip reset during a pending supply restart | drive row 2 defers to "drives resume" while a supply restart is pending; latched drive: rewrite only |
| §9 | switch-open tests at the end of step 6, incl. weapon throttle held |

## Round 22 (round22_a, b, d) → rev L (text only)

| Finding | Fix |
|---|---|
| B22-01 zero-current FOC on a coasted chip ≠ back-EMF | resume presets V_q = ω·λ (λ measured in §9 step 5) before the Release |
| B22-02 no speed without an encoder | zero-vector catch-spin probes on the CSAs; wait ≤ ~2 s, else stay coasted and report |
| B22-03 step 1 coasted the healthy drive | only chips being resumed |
| B22-04 negative-power coast too broad | motoring command, < ~−20 W for ≥ ~1 ms; restart via catch-spin if row 0 does not hold |
| B22-05/06/07 stale text | timer row matches row 6(c); "rewrite" = configuration sequence; §9 step 2 via drives resume |
| B22-08 labels | rounds 11–22 |
| Notes | BKE off only for steps 2–4 (wait happens before); "> 3/s → latch that drive"; §9 step 3 punctuation |
| R22D-01 instant weapon coast on a closed switch | needs INA239 ≈ 0 A while the estimate is not; else no coast |
| R22D-02 resume feed-forward / step-4 contradiction | (with B22-01) back-EMF preset required; resume OCPs never go to row 1 |
| R22D-03 no drive voltage sense | (with B22-02) zero-vector probes |
| R22D-04 row 7 on a dead encoder + shove | row 7 needs the other encoder to follow both alignment steps (~171 counts, sign) on two consecutive alignments |
| R22A-01 no catch without an encoder | encoder counting: wait for Z (stored offset); no encoder: fixed coast time then resume, OCP retried every ~0.5 s, never latches; zero-vector probe claim removed; start-angle rule uses Z |
| R22A-02 back-EMF preset accuracy | latency/MT6701 compensation required; fallback resume speed cap or OCP_LVL 24 A in the resume window (0x0D94 / 0x0C14, parity checked) |
| R22A-03 BKE = 0 disables the CLL break | use TIM8_AF1 BKINE = 0 |
| R22A-04 bounce under throttle | (covered: INA239 ≈ 0 condition + restart if row 0 does not hold) |
| R22A notes | safe-resume ~0.5 m/s expectation + coast-down time; re-coast before fault recovery in resume |

## Round 23 (round23_a, b, d) → rev L (text only)

| Finding | Fix |
|---|---|
| B23-01 align before Release | still rotor: preset 0, Release, then align (step 3); only a turning rotor needs the Z angle first |
| B23-02 stale "zero current" summaries | boot order, §8 Release, per-drive coast say back-EMF preset (0 at standstill); BKINE |
| B23-03 24 A window vs register check | window ≤ ~50 ms, check expects 0x94/0x14 during it |
| Notes | no-encoder preset 0; §9 step 2 no wait; BKINE window ≤ ~10 ms; step-4 repeat once per resume; paren |
| R23A-01 switch-open-under-throttle check could never fire | weapon under FOC with power ≤ 0 and INA239 \|I\| < 50 mA on 3 conversions → coast; pack current returning → immediate catch-spin restart; the estimate then lets row 0 confirm |
| R23A-02 24 A window vs register check | (with B23-03) |
| R23A notes | TIM8 BDTR LOCK = 0; restore BKINE/MOE between no-encoder retries; MT6701 wording (latency compensated, angle error calibrated) |
| R23D-01 switch open under throttle | (with R23A-01) + the weapon never suspends row 0 and is left out of the estimate test; weapon restarts only when pack current returns |
| R23D-02 dead encoder looks like a still rotor | OCP at a zero preset marks the encoder suspect → no-encoder branch, not counted |
| R23D notes | no Z-offset path while "Z offset stale"; drive row 7 now latches both drives (crossed bundles would drive backwards); §9 expectation updated |

## Round 24 (round24_a, b, d) → rev L (text only)

| Finding | Fix |
|---|---|
| B24-01 alignment inside the BKINE window | still-rotor alignment runs after step 4 |
| B24-02 re-coast while locked | one unlocked sequence 0x0603 → 0x0C90 → 0x097D → 0x0606 |
| B24-03/04 stale text | timer row after-clear wording; "per unit" calibration reference removed |
| B24-05 labels | rounds 11–24 |
| Notes | TIM8 BKINE named; standstill short noted in the encoder-suspect branch; row 0 regen wording; §9 step 2 "no motion" expected |
| R24A (0 MINOR+) notes | 0x0D10 return bracketed by unlock/lock; persistent OCP after coast-down reported as a suspected phase short; optional CLR_FLT after lowering the pin |
| R24D-01 signed mean crosses zero after a weapon brake | row 0 needs \|I\| < 30 mA on every reading for ≥ 100 ms; paused while the weapon has a braking command; §9 brake/reverse test |
| R24D-02 instant coast at the end of every brake | only with a zero or positive (motoring) torque command |
| R24D notes | OCP-at-standstill report "encoder suspect or drive phase short"; (N2: §9 switch-open-while-braking may show the 18.5 V coast first — end result unchanged) |

## Round 25 (round25_a, b, d) → rev L (text only)

| Finding | Fix |
|---|---|
| R25A-01 bare CLR_FLT on a locked chip | folded into the Release: 0x0603 → 0x097D → 0x0D10 → 0x0606 |
| R25A notes | BKINE window up to ~12 ms (no hard 10 ms timeout); §9 logs max \|I\| with the switch open |
| B25-01 row 0 "mean" leftover / weapon pause wording | every-reading run restarted by a suspension or the braking pause; regenerating weapon vs explicit braking command |
| B25-02 bare CLR_FLT | (with R25A-01); §9 step 2 records whether nFAULT stays low after lowering the pin |
| B25 notes | restore BKINE/MOE before a waiting repeat; no Z path before a Z offset is stored; duplicate Round 24 heading removed |
| R25D-01 braking pause hides an open switch | pause keyed on a regenerating FOC torque command (brake or speed-loop decel), ended by any protective coast; no brake resume after a coast with \|I\| < 50 mA until pack current returns; regen limit is a current limit; row 1 sentence and §9 expectation corrected |
| R25D notes | instant coast only with a positive (motoring) command; 18.5 V coast classified/restarted as row 1 |

## Round 26 (round26_a, b, d) → rev L (text only)

| Finding | Fix |
|---|---|
| R26A-01 CLR_FLT before the Release word | order 0x0603 → 0x0D10 → 0x097D → 0x0606 |
| R26A notes | open-bus decay ~0.27 V/ms |
| B26-01 row 0 leftover "explicit braking" | "regenerating torque command" |
| B26-02 labels | rounds 11–26 |
| B26 note | step 3 Release shows the optional CLR_FLT and the 24 A variant |
| R26D (0 MINOR+) notes | §9 step 4 idle-current pass ≥ ~100 mA; regen current limit ≤ ~10 A (TVS clamp vs sense-pin rating) |

## Round 27 (round27_a, b, d) → rev L (text only)

| Finding | Fix |
|---|---|
| R27A-01 regen current not measured | §9 step 6 brake test logs INA239 current: ≥ ~−10 A combined |
| R27A notes | §3.2 1 nF protects only short spikes, sustained clamp relies on the regen limit; idle-current pass replaced by "band ≤ half the measured idle"; (N1 bridge ring at 28.7 V: avalanche-rated, harmless) |
| B27-01 unescaped pipes break rendered tables | \|I\| / \|W_Vx\| escaped in DESIGN.md and CHANGES.md; calcs uses ∥; all tables column-checked |
| B27-02 idle pass mark | (with R27A N2) band ≤ half the measured idle |
| B27 note | Braking row points to the combined ~10 A regen limit |
| R27D (0 MINOR+) notes | Z-count mismatch beyond drift → encoder suspect (slipped magnet); §7.2 bounce window to ~1.3 ms with the extra sim figures |

## Round 28 (round28_a, b, d) → rev L (text only)

| Finding | Fix |
|---|---|
| R28D-01 / R28A-01 Z-count check | cause stated as missed/extra A/B edges (a slipped magnet keeps Z consistent); Z edge with the direction bit / Z pulse width 1 LSB (§9 step 5); first mismatch re-references, second → encoder suspect; slipped magnet caught by a torque-sign check below observer speed — corrects the round-27 claim |
| R28A-02 / R28D-N1 bounce figures | §1, §7.2 and calcs: ≤ 2.75 V/µs in the environment, 2.82 only at C1's −40 °C limit; re-close from ~3.8–10 V |
| Notes | armed brake ≈ 0.5 s; D1 "at most" this current |
| B28-01 labels | rounds 11–28 |
| B28-02 bounce figures | §3.3/§5/§7.2 add the ~1.3 ms figures; load wording corrected |
| B28 notes | sense-pin nominal/worst labelled; LiHV at the 10 A limit; §9 step 6 wording; idle ~95–113 mA in §7.17 and calcs |

## Round 29 (round29_a, b, d) → rev L (text only)

| Finding | Fix |
|---|---|
| R29D-01 torque-sign slip check trips in every push | removed; slip stays the accepted bounded residual caught by the observer check |
| R29D notes | Z mismatch held as a candidate until the next Z confirms; "since reset"; second mismatch also re-references |
| R29A-01 slip check trips on braking/pushing | (with R29D-01: removed) |
| R29A notes | Z noise handled by the candidate reference; §7.18 LiHV wording (upper end trips) |
| B29-01 brake time | §7.6 ~0.5 s |
| B29 notes | BOVL delay ~0.3–0.45 ms everywhere; pre-filter bounce ~3.75 V/µs; EN sink 0–5 µA in calcs and the R13 description; nets.md lists the DNP parts (generator) |

## Round 30 (round30_a, b, d) → rev L (text only)

| Finding | Fix |
|---|---|
| R30D-01 intermittent A/B line never flagged | a Z matching neither reference nor candidate counts as the second mismatch |
| R30D-02 resume trusts Z on an encoder-suspect drive | encoder-suspect drives use the no-encoder resume branch |
| B30-01/02 | labels superseded by the trim below; §4b INA239 rate now 150 + 150 µs ≈ 3.3 kHz |

## Trim (after round 30): firmware-contract audit

Rounds 12–30 changed no hardware; almost every finding was a hole in firmware-policy text written the
round before. Four audits (review/trim_a–d) sorted every §7–§9 rule into keep / simplify / cut. Their
datasheet claims and SPI words were re-checked independently before merging (DRV8316C, DRV8323, INA239,
MT6701, SMBJ20A, STM32G474 DS). §8.1 went from ~4 000 to ~2 200 words; DESIGN.md from ~19 400 to ~17 300.

| Area | Result |
|---|---|
| §8.1 weapon | rows 0–12 kept by number; cut: pack-current estimate suspension, INA239 cross-check/plausibility, instant-coast patches, persisted "supply unstable" hold; row 7 no longer latches (bounces never latch); row 12 latches on a second unknown in ~10 s; row 0 pause limited to drive-motor regen or a commanded weapon brake |
| §8.1 drives | coast a chip over SPI before handling its fault; Release always ends with CLR_FLT; one "failed resume" rule (encoder suspect → no-encoder retries, never latched) |
| §8 / §3.5 | Timer-inputs row trimmed (torque-relax probe and Z candidate rules cut); DRV8316 row regrouped (all words unchanged); INA239 ID checks DIEID 239h only; DRV8323 t_RST 8–40 µs; compute-board latch persistence across power cycles made optional; link session ID cut |
| §7 / §9 | §7.4 states the PA3–PA5 TT_a limits honestly (inside 4.0 V abs max, briefly above VDD + 0.3 V); §7.21 states the phase-to-ground residual exceeds the DRV8316 4 V/µs abs max; §9 impossible "dip below 5 V" UVLO test removed; speculative firmware tests moved to trim_d §3 for a future firmware test plan |
