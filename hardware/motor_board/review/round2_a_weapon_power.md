# Review round 2-A: weapon channel (U2 DRV8323RH, U6 interlock, integrated buck) and power entry

**Scope:** U2 DRV8323RHRGZR pins, straps and H-variant behaviour; the U6 SN74LVC08A INLx interlock; the LMR16006
buck inside U2 (L1, D2, C27, R4/R5/C10, R20/R21); power entry (Q7, R1/D4, RS4, D1, C1, U7 INA239); `spice/sim_hotplug.py`.

**Source of truth:** `design/motor_board.py` (rev B working tree). I regenerated it in a scratch copy
(`/tmp/mbcopy`): "checks: OK", and nets.md, netlist.csv, bom.csv and mcu_pinmap.md are byte-identical to the
committed outputs. I edited no design files.

**Datasheets** (text via `pdftotext -layout`; page numbers are the printed ones):
- DRV8323: SLVSDJ3D
- LMR16006: SNVSA24
- INA239: SLYS027A
- INA229: SLYS023A
- SN74LVC08A: SCAS283
- FNR5040S: CJiang catalogue, rendered p.12–14 and p.19
- EEHZK: Panasonic ZK (31-May-19)
- SMBJ20A: BORN
- SS34: MDD
- HYG015N04LS1C2: HUAYI
- DRV8316C: SLVSH07

## Findings

| ID | Sev | Ref / net | What is wrong | Evidence | Proposed fix |
|---|---|---|---|---|---|
| R2A-01 | **MINOR** | VBAT_SNS (R63/R64/C68), firmware "coast above 18.5 V" (DESIGN §7.3, §8), U7 ALERT | **The regen over-voltage guard is too slow to protect anything.** W-07's fix depends on firmware reading VBAT_SNS. That node's filter is 68k‖10k × 100 nF = **0.87 ms** (the netlist comment "7 ms" is also wrong; 68k × 100 nF would be 6.8 ms). If the pack is disconnected (main switch opened, XT30 bounce) while firmware is braking or its FOC loop commands negative torque, 20 A × ~15 V ≈ 300 W goes into ~0.38 mF (C1 + 6 × ~4 µF MLCC). That is dV/dt ≈ P/(C·V) ≈ 45 V/ms, so VBAT goes from 16.8 V to the 32 V TVS knee in **~0.35 ms**, before the filtered ADC reading has moved even halfway. D1 then clamps at 32–33 V, which with the ~12 V switching overshoot (DESIGN §5) exceeds the 40 V FETs. Coasting itself is the correct action. With INLx = 0 the bridge is a passive 6-diode rectifier and VBAT cannot rise above the BEMF peak (≤ KV × 16.8 V line-line, i.e. ≤ ~15.4 V after two diode drops), so the only problem is detection speed. | netlist: R63 68k, R64 10k, C68 100 nF ("pack divider filter (7 ms)"). calcs §7 / DESIGN §3.1: C1 330 µF. SMBJ20A: VC 32.4 V @ 18.6 A, PPPM 600 W (10/1000 µs). INA239 Table 7-13: BUSOL can drive ALERT. U7.3 ALERT is already on W_nFAULT → TIM1_BKIN. | Firmware (no hardware change): also enable **BOVL ≈ 19 V on the INA239 ALERT** (VBUSCT 50–150 µs), so a bus over-voltage trips the TIM1 break in hardware. Break → OISxN = 0 → INL = 0 → coast. Optionally drop C68 to 10 nF (τ 87 µs) and add an ADC analog watchdog on PA3. Fix the "7 ms" comment and update DESIGN §8 ("only SOVL" → SOVL + BOVL). |
| R2A-02 | **MINOR** | C1, `spice/sim_hotplug.py`, DRV8316 VM | **The hot-plug margin to the DRV8316's 4 V/µs absolute maximum is thinner than DESIGN claims ("≤ 1.7 V/µs").** The simulation's nominal case (150 nH lead, 4 × 12 mΩ pack) is not the worst case. Early dV/dt is set mostly by ESR × dI/dt, so it grows with a stiffer pack, a shorter lead, and higher C1 ESR (from aging or cold). I re-ran the sim unchanged (output identical to `hotplug.out`), then ran a sensitivity copy (`/tmp/hp/hp2.py`), shown in the table below this one. **Two 330 µF in parallel only reach 2.5–3.3 V/µs**, so a second capacitor is not a full fix. | DRV8316C SLVSH07 §7.1: "Power supply voltage ramp (VM) 4 V/µs" is an **absolute maximum**. EEHZK list: 1V331P ESR 20 mΩ at 100 kHz/20 °C; "ESR after endurance (−40 °C) ≤ 0.3 Ω" for case G; endurance ESR ≤ 200 % of the initial limit. | (1) Add the stiff/short/aged cases to `sim_hotplug.py`, and change DESIGN §5/§1 to "1.6 V/µs nominal, up to ~4 V/µs with a stiff pack, short leads and an aged C1". (2) Bring-up: scope DRV8316 VM at switch closure with the real pack, switch and leads. (3) Cheapest real margin: put a DNP footprint for a second EEHZK1V331P and ~3 × 10 µF 1206 MLCC right at C1, or make the lead loop ≥ 150 nH on purpose. The only complete fix is an inrush limiter, which Q7 cannot provide because its body diode conducts at plug-in. |
| R2A-03 | **MINOR** | L1 FNR5040S220MT; DESIGN §3.2, calcs §3, CHANGES W-02 | **The round-1 fix (W-02) does not meet its own target.** W-02 asked for Isat ≥ 1.8 A, above the 1.7 A maximum current limit. The guaranteed Isat of FNR5040S220MT is **1.60 A**; 1.80 A is typical. Isat here means the current at which L has dropped ~30 %. DESIGN §3.2 ("Isat 1.8 A (above the 1.7 A max current limit)") and calcs §3 ("a shorted +5V cannot saturate it") are therefore wrong. Only the netlist comment is correct. Into a hard +5V short (J1 pins 1/2 are next to GND pins 3/4), with L ≈ 15 µH, one 80 ns minimum on-time at 16.8 V adds ~0.09 A. The ~1.35 µs off-time with ~0.45 V diode drop + I × DCR removes only ~0.06–0.08 A, so the current can ratchet above ILIMIT until the part reaches thermal shutdown. This is soft ferrite roll-off, not a cliff, and 1.6 A is exactly TI's own recommendation, so the part is acceptable. The claims are what is wrong. | CJiang p.13 FNR5040S220MT row: 22 µH ±20 %, DCR 0.168 max, Isat 1.60 / 1.80 (typ), Irms 1.50 / 1.60. p.19 note *3: "Isat: DC current at which the inductance drops approximate 30%". SLVSDJ3D §7.5: ILIMIT 1200 typ / 1700 max mA. SNVSA24 §9.2.2.2: "22 µH with a 1.6 A current rating"; SNVSA24 §7.5: TON_MIN 80 ns. | Correct DESIGN §3.2, calcs.py §3 and CHANGES ("1.8 A") to "Isat 1.6 A guaranteed (−30 % L), 1.8 A typ; TI recommends 1.6 A". For real margin, **FNR5045S220MT** (same catalogue p.14: 22 µH, DCR 0.163 max, **Isat 2.00 / 2.35 A**, 5 × 5 × 4.5 mm, KiCad `L_Changjiang_FNR5045S`, same land dimensions per p.2). LCSC number and stock are UNVERIFIED. |
| R2A-04 | **MINOR** | R44/R45/R46 (MODE/IDRIVE/VDS), U2.32 GAIN open; DESIGN §6 | **The layout rules say nothing about the strap resistors, and their noise margins are small.** Seven-level pins (internal 73k/73k divider from DVDD): the 18k strap gives 0.55 V and the 75k strap gives 1.11 V. The neighbouring levels are 0 / 0.5 / 1.1 / 1.65 V, so the comparator margin is only **~±0.27 V**. Four-level MODE with 47k gives ~1.24 V against levels 1.2 / 2.0, margin ~±0.4 V. The netlist returns R44–R46 to the single "GND" net. If the strap ground is taken from the power ground under the bridge, a few hundred mV of ground bounce during a weapon edge moves the pin across a threshold. The result would be VDS OCP at 0.06 or 0.26 V, IDRIVE at 30 or 120 mA (120/240 overshoots per §5), or a different PWM mode. Whether the straps are latched at wake or sampled continuously is **UNVERIFIED**. The datasheet's "set all INHx and INLx pins low before changing the MODE pin" (§8.3.1.1) suggests they are live. GAIN is left floating (Hi-Z needs > 500 kΩ to AGND), which makes it a similar ~31 kΩ-Thevenin node. | SLVSDJ3D §7.5 "FOUR-LEVEL H/W INPUTS" (VI2 1.2 V, VI3 2 V, RPU 50k, RPD 84k) and "SEVEN-LEVEL H/W INPUTS" (VI2 0.5, VI3 1.1, VI4 1.65 V, RPU/RPD 73k). Fig. 8-23 / 8-24: straps "to AGND". Table 6-4: DVDD capacitor "to AGND … minimize the path". | Add to DESIGN §6: R44–R46 within ~2 mm of pins 29–31, grounded to the AGND pin 35 / DVDD-capacitor return (the quiet AGND island at the thermal pad), not to the bridge power ground. No trace on the GAIN pad, or a DNP 0402 footprint from pin 32 to AGND for a later gain change. Keep the area flux-clean (500 kΩ criterion). |
| R2A-05 | NOTE | W_ARM → PD2, TIM1 control loop | ARM can drop (compute-board disarm, glitch, connector chatter) while FOC is running. The phases then float in hardware, but the MCU only learns of it by polling PD2. The current PI integrators wind up while no current flows. When ARM returns, INL = 1 re-applies the wound-up voltage vector, and the result is a current spike limited only by firmware or by VDS OCP at 62–93 A. | nets.md: W_ARM → U6.2/5/10, U1.55 (PD2), J1.7, R41. SLVSDJ3D Table 8-3 (INLx = 0 → Hi-Z). | Firmware: EXTI2 on PD2, both edges, at high priority. On ARM low, reset the controllers and force CHxN low (so re-arm needs an explicit restart). Treat any ARM low as a full weapon stop. |
| R2A-06 | NOTE | INA229 "pin- and register-compatible" (DESIGN §1, §3.1; netlist comment; BOM.md) | **Pin and footprint compatible: yes.** Both are VSSOP-10 (DGS) with an identical Table 5-1 (1 CS, 2 MOSI, 3 ALERT, 4 MISO, 5 SCLK, 6 VS, 7 GND, 8 VBUS, 9 IN−, 10 IN+). **Register compatible: no.** On the INA229, VSHUNT, VBUS and CURRENT are 24-bit (16-bit on the INA239), it adds 3h SHUNT_TEMPCO and the 40-bit 9h ENERGY and Ah CHARGE, the SHUNT_CAL constant is 13107.2 × 10⁶ (INA239: 819.2 × 10⁶, with CURRENT_LSB = max/2¹⁹ instead of /2¹⁵), and DEVICE_ID differs (2291h vs 2391h). SPI frame lengths therefore differ by register. | INA239 SLYS027A Table 7-3, eq. 1, §7.6.1.17. INA229 SLYS023A Table 7-3, eq. 2, §7.6.1.20. | Change the wording to "pin/footprint-compatible; firmware must read DEVICE_ID and use the matching register widths and SHUNT_CAL". |
| R2A-07 | NOTE | U2 CAL tied low | With CAL permanently low the CSA auto-trim never runs, so the offset is untrimmed. SLVSDJ3D specifies VOFF ±4 mV only for "CAL = 3.3", so the untrimmed offset is **UNVERIFIED**, possibly larger. Firmware measuring SOx with the bridge idle (INLx = 0) covers it; re-measure after each wake, because the CSA is powered down in sleep. The 100 µs calibration also switches the gain to 40 V/V, so nothing is lost by not using it. | SLVSDJ3D §8.3.4.3; §7.5 VOFF test condition. | Firmware: capture the offset after every U2 wake, with ≥ 1 ms tWAKE plus settling. |
| R2A-08 | NOTE | U2 fault handling, H variant | Fixed behaviour: VDS OCP has a 4 µs deglitch and **4 ms auto-retry**; SEN_OCP is fixed at **1 V = 500 A** on 2 mΩ, which is the SPx ±1 V continuous absolute maximum, so it is effectively absent; TDRIVE is 4 µs; dead time is 100 ns; CPUV is always on. **GDF is the only latched fault**, and the 8–40 µs ENABLE pulse is what clears it. nFAULT is one bit, shared with U7 ALERT, so firmware cannot tell OCP, GDF, UVLO, CPUV, OTSD and the INA alert apart except by reading INA239 DIAG_ALRT and by timing (OCP releases after ~4 ms, GDF never does). TIM1 AOE must stay 0, or the 4 ms retry turns a hard short into repeated shots. | SLVSDJ3D §8.3.6.3 ("On hardware interface devices … 4 ms automatic retry"), §8.3.6.4 ("fixed at 1 V … 4 ms automatic retry"), §7.5 tDRIVE H/W 4000 ns, tDEAD H/W 100 ns, §8.4.1.3. | Firmware / DESIGN §8: add the fault-discrimination logic and AOE = 0. |
| R2A-09 | NOTE | Main switch vs spinning drum | With the switch open and the drum spinning, the bridge body diodes rectify BEMF into VBAT, so the buck, MCU and compute board stay powered until the BEMF falls to ~10.6 V (UVLO 9.2 V + 2 diode drops, i.e. ~19 k rpm on the 1800 KV motor). The drum cannot be accelerated (there is no source), but the robot is not "off" until the drum slows. | 6-diode rectifier: VBAT ≈ V_LL,pk − 2 V_F. calcs §9 UVLO. | Document for the pit crew/SPARC inspection: "power LED stays lit while the drum coasts". |
| R2A-10 | NOTE | TIM1 in debug; MCU BOR | A debugger halt with DBG_TIM1_STOP = 0 leaves the weapon PWM running with the core stopped. Separately, the G4's default BOR (~2.0 V) is fine for the interlock: below it the MCU is reset and all INH/INL are pulled low, and above it U6 still outputs ≥ VIH 1.5 V. | RM0440 DBGMCU_APB2FZR (UNVERIFIED bit name). SLVSDJ3D §7.5 VIH 1.5 V. SN74LVC08A 1.65–3.6 V operation. | Firmware: set DBGMCU TIM1 stop, which disables the outputs on halt, and consider BOR level 2.8 V. |
| R2A-11 | NOTE | `spice/sim_hotplug.py` model | The model roughly matches the rev B parts (330 µF / 20 mΩ matches the ZK list; RS4, Q7 body diode, TVS). Small inaccuracies: one DRV8316's 10 µF is counted twice and un-derated (24 µF lumped + 10 µF at vm2); C24/C27/C21 and U2's buck load are omitted; there is no load resistor, so "final" = peak. None of these changes the conclusion. Peak surge through Q7's body diode and RS4 is **183 A nominal, up to ~460 A** with a stiff pack. That is below IDM 600 A, and RS4's I²t is ~1.4 mJ. | Sim rerun (output identical to `hotplug.out`); `/tmp/hp/hp2.py`. HYG015N04LS1C2: IS 150 A, IDM 600 A. | Fold into R2A-02's sim update. |
| R2A-12 | NOTE | U6 SN74LVC08A (TI) | TI's SCAS283 revision history says "Deleted Ioff throughout data sheet". The TI part is therefore not specified for partial power-down. This is harmless here: U6's outputs only drive U2 INLx (100 kΩ internal pull-down), and its 5.5 V-tolerant inputs have no clamp to VCC, so a USB-powered compute board driving W_ARM with the motor board off cannot back-power it. The Nexperia alternative (C6053) does specify Ioff. | SCAS283 p.1 revision history ("Deleted Ioff …"), "Inputs Accept Voltages to 5.5 V". | None. For information only. |

**R2A-02 sensitivity results** (sim copy `/tmp/hp/hp2.py`):

| Case | VM dV/dt |
|---|---|
| Nominal (as `hotplug.out`) | 1.57 V/µs |
| ESR 40 mΩ (end of life) | 1.95 V/µs |
| ESR 100 mΩ (cold) | 2.81 V/µs |
| Stiff 4 × 3 mΩ pack, 16 AWG 80 nH / 3 mΩ lead | **3.11 V/µs** (Ipk 364 A) |
| Same, ESR 40 mΩ | **3.87 V/µs** |
| Same, ESR 100 mΩ | **5.43 V/µs** |

## Interlock analysis (U6, INLx = TIM1_CHxN AND W_ARM, 3x PWM)

The DRV8323 3x PWM truth table (SLVSDJ3D Table 8-3) is: INL = 0 → GL = GH = L → Hi-Z; INL = 1, INH = 0 → low side on; INL = 1, INH = 1 → high side on. The U6 pinout matches SCAS283 (1A1 1B2 1Y3 2A4 2B5 2Y6 GND7 3Y8 3A9 3B10 4Y11 4A12 4B13 VCC14), and the 4th gate's inputs are grounded.

| State | INHx | CHxN (MCU side) | W_ARM | INLx | Bridge |
|---|---|---|---|---|---|
| Power-up / MCU in reset (pins analog/Hi-Z) | U2 100 k RPD → 0 | R47–R49 → 0 | R41 → 0 or compute | 0 | Hi-Z, and U2 asleep (R40) |
| Running, ARM low | PWM | any | 0 | 0 | Hi-Z (coast) ✔ |
| Running, ARM high, FOC | PWM | 1 (static) | 1 | 1 | normal |
| ARM glitch low | PWM | 1 | 0 for t | 0 for t | Hi-Z for t; winding current freewheels into C1 (½LI² ≈ mJ); see R2A-05 |
| INL low while INH high | 1 | 0 | x | 0 | Hi-Z (INL overrides) ✔ |
| TIM1 break (U2 nFAULT or U7 ALERT), OSSI = 0 | pins Hi-Z → U2 RPD → 0 | Hi-Z → R47–R49 → 0 | x | 0 | Hi-Z ✔ |
| MCU brownout/reset during PWM | → 0 (100 k, ~µs) | → 0 | x | 0 | inputs low before W_EN falls, i.e. inside the tRST window of §8.4.1.1 (Fig. 8-34 case) ✔ |
| +3V3 lost (LDO fault or +5V short) with VM present | 0 | 0 | x | U6 unpowered → 0 (U2 RPD) | Hi-Z; U2 asleep (W_EN = 0) ✔ |
| ARM removed at 25 k rpm, pack connected | x | x | 0 | 0 | 6-diode rectifier; conducts only if V_LL,pk > VBAT + 2 V_F (sagging pack), and then charges the pack. No OV possible |
| ARM removed, pack disconnected | x | x | 0 | 0 | VBAT settles at ≈ V_LL,pk − 1.4 V ≤ ~15.4 V; board keeps running (R2A-09). No pumping in coast. Pumping only happens with active switching (R2A-01) |

The DRV8323's own 100 kΩ pull-downs (SLVSDJ3D §7.5 RPD) are on INHx/INLx/ENABLE. U6 drives INLx push-pull at VOH ≈ 3.3 V against VIH 1.5 V, so the pull-downs do not load it meaningfully (IIH ≤ 70 µA at 5 V).

## VERIFIED OK

- **U2 48-pin R pin map, all 49 connections,** against SLVSDJ3D Table 6-4 **DRV8323RH column**: 1 FB, 2 PGND, 3 CPL, 4 CPH, 5 VCP, 6 VM, 7 VDRAIN, 8 GHA, 9 SHA, 10 GLA, 11 SPA, 12 SNA, 13 SNB, 14 SPB, 15 GLB, 16 SHB, 17 GHB, 18 GHC, 19 SHC, 20 GLC, 21 SPC, 22 SNC, 23 SOC, 24 SOB, 25 SOA, 26 VREF, 27 DGND, 28 nFAULT, **29 MODE, 30 IDRIVE, 31 VDS, 32 GAIN**, 33 ENABLE, 34 CAL, 35 AGND, 36 DVDD, 37–42 INHA/INLA/INHB/INLB/INHC/INLC, 43 BGND, 44 CB, 45 SW, 46 NC (float allowed), 47 VIN, 48 nSHDN, pad GND. Also Fig. 6-7.
- **Straps.**
  - MODE 47k → AGND = 3x PWM (§8.3.1.1.2, Fig. 8-23; the EC table's "45 kΩ ±5 %" row also accepts 47k 1 %).
  - IDRIVE 75k → AGND = 60 mA source / 120 mA sink (§7.5 H/W rows, Fig. 8-24).
  - VDS 18k → AGND = 0.13 V (§7.5).
  - GAIN Hi-Z = 20 V/V, 19.4–20.6 (§7.5).
  - CAL = GND: no calibration (see R2A-07).
  - Computed pin voltages: MODE 1.24 V, IDRIVE 1.11 V, VDS 0.55 V, GAIN 2.07 V.
- **H-variant timings.** TDRIVE fixed at 4 µs, well above the ~1.1 µs needed for Qg ≈ 65 nC at 60 mA, so no false GDF. Dead time 100 ns with VGS handshake. VDS trip 62–93 A (calcs §6).
- **ENABLE.** tRST 8–40 µs; tWAKE / tSLEEP ≤ 1 ms. The buck is independent of ENABLE (§8.4.1.1). In the H variant no configuration is lost in sleep, which resolves W-01(a).
- **CSA.**
  - VBIAS = VREF/2 on the H device (no VREF_DIV).
  - VREF = +3V3 is the CSA supply and reference (Table 6-4), drawing IVREF 2–3 mA.
  - Linear range ±35 A at 40 mV/A. SPx to the FET source side and SNx through a net-tie match Table 6-4.
- **Charge pump and decoupling.** C20 47 nF 50 V, C21 1 µF 50 V 0603, C22 DVDD 1 µF, C23 VREF 100 nF, C24 plus C25/C26 on VM, C28 CB–SW 100 nF 50 V. All per Table 6-4 and §11.1.
- **Buck.**
  - FB: 0.765 × (1 + 56k/10k) = 5.05 V (VFB 0.747–0.782 V, §7.5).
  - fSW 595–805 kHz; L min 20.9 µH at 16.8 V; ripple 0.23 A p-p. The inductor land pattern (KiCad `L_Changjiang_FNR5040S` pads ±1.85 mm, 1.4 × 4.2 mm) matches the catalogue p.2 (a 2.3, b 1.4, c 4.2 mm).
  - L1 heat rating 1.5 A exceeds the 0.7 A peak.
  - D2 SS34: 40 V ≥ 1.25 × 16.8 V; 3 A; IFSM 80 A; CJ ~250 pF (~30 mW switching loss). C27 2.2 µF 50 V X5R matches TI's design, with ~0.15 V input ripple even at 50 % DC-bias derating.
- **UVLO R4/R5/C10.**
  - Thresholds: on 10.4 / off 9.2 V typ, and 8.7/7.4 V to 11.5/10.3 V across the 1.05–1.38 V threshold spread (node equation with −1 / −4.2 µA, §7.5).
  - C10 dynamics: τ = 45.1 kΩ × 100 nF = 4.5 ms. At plug-in the pin reaches 1.25 V after ~4.5 ms, by which time Q7 is fully enhanced (τ_gate ≈ 0.4 ms), so the buck start current never flows through the body diode.
  - Turn-off stays monotonic because the hysteresis current source keeps pushing once the threshold is crossed. There is no chatter: the buck's 0.18 A input step × 70 mΩ is far below the 1.17 V hysteresis.
  - Pin voltage is 3.9 V at the 32 V clamp, far below the 60 V limit. R4 390k satisfies the "≥ 100 kΩ" advice (§8.3.5.4).
- **Power entry.**
  - Q7 orientation (S = GND, D = BAT−; body-diode anode on GND). R1/D4 gate bias (48 µA; Vgs ≤ ~12 V < 20 V).
  - Reversed pack: Q7 off and the board floats.
  - Plug-in surge 183–460 A through the body diode, below IDM 600 A.
  - D1 SMBJ20A: VRWM 20 V, VBR 22.2–24.5 V, VC 32.4 V @ 18.6 A; after Q7; below the 35 V rating of C1 and the 40 V of the DRV8316.
  - C1 EEHZK1V331P: 330 µF / 35 V / 20 mΩ / 2.8 A (100 kHz, 125 °C) = 2.4 A at 24 kHz with the 0.85 factor, adequate for 0.5 s bursts.
  - RS4 1 mΩ: 0.48 W at 22 A.
- **U7 INA239.**
  - Pinout matches Table 5-1 exactly. IN+ on VBAT_PACK (supply side) and IN− on VBAT is correct for high-side sensing.
  - VBUS = VBAT, below the 85 V absolute maximum.
  - VS 3.3 V; the MISO push-pull is tri-stated when CS is high (§7.5.1).
  - **SPI mode 1**: MOSI sampled on the falling SCLK edge, MISO shifted on the rising edge (§7.5.1), so CPOL 0 / CPHA 1, matching the DRV8316; 10 MHz max.
  - **ALERT is open drain and active-low by default** (APOL = 0h, Table 5-1 / Table 7-13). Resets: DIAG_ALRT 0001h (CNVR = 0); SOVL / BOVL / TEMP / PWR limits at the never-trip extremes. It therefore cannot hold W_nFAULT low at boot, and the wire-OR with U2 nFAULT is valid.
  - ADCRANGE = 1 gives ±40.96 mV = ±41 A at 1.25 mA/LSB. R2/R3 10 Ω with C2 100 nF follows §8.1.4.
- **INA229 footprint compatibility** (DGS VSSOP-10, same pin table). Registers are not compatible (R2A-06).
- **U6 SN74LVC08A.** Pinout (SCAS283 Pin Functions, TSSOP); 5.5 V-tolerant inputs; VCC +3V3 with C40; 4th gate inputs grounded; R47–R49 keep the MCU-side inputs defined in reset. W_ARM to PD2 is present in nets.md (U1.55).
- **`sim_hotplug.py` rerun.** Output identical to the committed `hotplug.out`, and the parameters match the rev B parts (margin caveat in R2A-02).
- **netlist regeneration.** `motor_board.py` checks pass, and all four generated files are identical to the committed ones.

**Verdict:** 0 BLOCKER, 0 MAJOR, 4 MINOR, 8 NOTE.
