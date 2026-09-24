# Round 12 / A: hardware (rev K netlist, rev L docs): circuit correctness

Scope: power entry (LM74502 + Q7/Q8, soft-start, UVLO), the weapon DRV8323RH (straps, interlock, dynamic ARM), the DRV8316CR
drives including the R302/R402 VM filter, the current-sense and fast-trip thresholds, INA239, BQ76907, the sensor interfaces,
logic levels, pin numbers against the datasheet pads, absolute maximum ratings and part ratings.  Area and fit are out of scope.
I edited no design file.

**Snapshot and reproducibility.**  I copied the package to `/tmp/r12a/motor_board`.  `python3 design/motor_board.py` prints
"237 refs (205 placed components), 160 nets, 67 BOM lines, checks: OK", and nets.md, netlist.csv, bom.csv and mcu_pinmap.md
are byte-identical to the working tree.  The working tree has since moved to rev L (documentation and value strings only).
`netlist.csv` is still identical, so every connection checked here is current.  `sim_hotplug.py` and `sim_arm.py` (hardware
venv) reproduce `hotplug.out` and `arm.out` byte-identically.

Probes (in `/tmp/r12a/probe/`):
* `r302.py`: the 48 kHz centre-aligned inverter input current (centred SVPWM and flat-bottom).  It is split between R302
  (+ 11 nH) and the local 16 µF, and gives R302's loss by harmonic.
* `wrip.py`: the weapon's 24 kHz inverter input current into the bus network, in the frequency domain.  The network is the
  pack + lead, C1 at 20/40/100 mΩ, the 12 µF bridge MLCCs and both drive branches (5 nH + 0.1 Ω + 16 µF ∥ 200 nF).  It gives
  each R302's share.
* `hiccup.py`: `sim_hotplug.netlist()` with a load step on a tired pack (12.6–14 V, 0.16–0.25 Ω).  It gives the switch UVLO
  hiccup: VM dV/dt and Q7 stress.

References (PDF page numbers): [DRV16] DRV8316C SLVSH07; [DRV23] DRV8323 SLVSDJ3D; [LM] LM74502 SNOSDE5A; [INA] INA239;
[BQ] BQ76907 SLUSE96A; [TPS] TPS22945 SLVS832D; [UR] UNI-ROYAL thick-film chip resistor datasheet (Feb 2019 V.3); [HYG]
HYG015N04LS1C2; [D] DESIGN.md (rev L); [N] motor_board.py / nets.md; [C] calcs.md.

## R302/R402 loss: verified

I computed the inverter input current from first principles (three sinusoidal phase currents, SVPWM duties and a 48 kHz
centre-aligned carrier, PF 1 and 0.87).  The DC part goes through R302.  Each AC harmonic splits by
Z_C/(R + jωL + Z_C), with 16 µF at 5 mΩ.  The dominant input-ripple component is at 2·f_PWM = 96 kHz, where the 16 µF is
0.104 Ω, the same as R302.  So R302 carries ~72 % of that component's amplitude and all of the DC.

| Phase current (rms) | R302, centred SVPWM, M 0.9–1.0, PF 1 | flat-bottom SVPWM, M 0.9 (the duty cap limits M to ~0.94) | M 0.5 | PF 0.87 (M 0.9) | [D §3.3] / [C §7] |
|---|---|---|---|---|---|
| 1.0 A | 1.02–1.10 A rms, **0.10–0.12 W** | 0.11 W | 0.05 W | 0.08 W | 0.11 W |
| 1.5 A | 1.53–1.65 A rms, **0.23–0.27 W** | 0.25 W | 0.10–0.13 W | 0.18 W | 0.24 W |
| 2.0 A | 2.04–2.20 A rms, **0.42–0.48 W** | 0.45 W | 0.19–0.23 W | 0.32 W | 0.52 W |

**Weapon ripple through each R302** (`wrip.py`, 24 kHz, M 0.5–0.9):

| C1 ESR | 14 A rms phase (the 20 A limit as a peak) | 20 A rms phase |
|---|---|---|
| 20 mΩ | 0.72–0.76 A rms, 0.05–0.06 W | 1.03–1.08 A rms, 0.11–0.12 W |
| 40 mΩ | 1.08–1.13 A rms, 0.12–0.13 W | 1.55–1.61 A rms, 0.24–0.26 W |
| 100 mΩ | 1.64–1.72 A rms, 0.27–0.29 W | 2.34–2.45 A rms, 0.55–0.60 W |

The documented 0.11 / 0.24 / 0.52 W and "up to ~0.6 W of weapon ripple" hold to within ~10 %, and the 2 A figure is on the
conservative side.  The worst coincident case (2 A drive + 20 A rms weapon + C1 at its 100 mΩ bound) is 1.0–1.1 W.  That
matches the documented "≤ ~1 W" to rounding.  At the realistic 14 A rms weapon current it is ≤ 0.8 W.  It is also far inside
the part's short-time overload: RCWV = √(1 W · 0.1 Ω) = 0.32 V, and STOL is 2.5 × RCWV for 5 s ≈ 6 W ([UR] p.5 §9 and the
test table).  The continuous current rating at 1 W is 3.2 A, against ≤ 2.45 A rms here.  The 70 °C → 155 °C linear derating
gives 0.65 W at 100 °C ([UR] p.5 Fig. 1), so the §6.6 "off the thermal copper" rule matters but is sufficient.  The rated
power (1 W at 70 °C, 2512, 0.01–10 Ω at 1 %) and the part code decode (25121WF100LT4E: 2512 / 1W / F / 100·10⁻³ Ω / T4 / E)
are correct ([UR] pp.2, 4).

## Findings

| ID | Sev | Where | Finding | Evidence | Fix |
|---|---|---|---|---|---|
| R12A-01 | MINOR | [D] l.649–650 (§9 step 4, "VM filters: at a known drive current, VBAT − L_VM ≈ 0.1 V per amp"); [D] l.547–548 (§7.16 "§9 step 4 checks the resistor") | **As worded, the bring-up check cannot find the fault it exists for.**  R302 carries the drive's **DC bus** current, not its phase current.  Step 4 is a bench test (locked or slow rotor), where the bus current is only the drive's input power over VM.  Take 1 A rms phase at standstill with the Mk4.1: copper ~0.3–0.45 W, DRV8316 conduction + switching + dead time ~0.6 W ([C §5]), plus ~0.2–0.27 W quiescent.  That is ~1.1–1.3 W, i.e. **65–80 mA, so VBAT − L_VM ≈ 7–8 mV**, not the ~0.1 V that "0.1 V per amp" invites at "1 A".  A builder then either rejects a good board or accepts a shorted one: a shorted or 0 Ω R302 reads ~0 mV against 7 mV, under a 0.14 V p-p 48 kHz ripple.  An **open** R302 needs no test: the drive does not power up.  The case the step is meant to catch (shorted or wrong value, which silently removes the VM-ramp margin: 2.26 → ~3.5 V/µs per §7.16) is exactly the one it misses.  Nothing else in §9 checks the local VM caps (§7.16's other half), apart from the scope look at VM in step 6 | [DRV16] p.7 I_VMS 4–10 mA standby, I_VM 10–16 mA operating; [C §5] drive loss at 1 A; `r302.py` (R302 ripple 0.14 V p-p at 1 A rms); [N] R302 VBAT → L_VM, no other DC path between the two nets | Replace the step with a direct measurement.  **Unpowered:** force 1.0 A from a current-limited bench supply, + on TP10 (VBAT) and − on an L_VM cap pad (C302/C308), and read 0.10 V ± 10 % across R302.  The only DC path between the nets is R302.  Repeat for R402 / R_VM.  Or use a 4-wire milliohm meter.  Optional: in step 6, scope L_VM against VBAT during a drive acceleration, where the ripple amplitude also exposes missing local caps |

## Notes

| ID | Sev | Finding | Evidence / action |
|---|---|---|---|
| N-01 | NOTE | **The DRV8316 SDO resets to push-pull, not open-drain.**  [D] l.604 says "The DRV8316 SDO is open-drain until configured: ignore reads before CTRL2 is written".  CTRL2 resets to 60h: bits 7:6 = 01b (reserved, reset 1h) and bit 5 SDO_MODE = 1 = push-pull.  SDO is Hi-Z whenever nSCS is high in either mode, so the shared MISO has no contention and nothing in the hardware changes.  Two consequences: status/NPOR reads before configuration are valid, and the PC11 pull-down only defines the idle bus.  The push-pull high level is AVDD (≤ 3.465 V).  That is inside the INA239's tri-stated MISO abs max of VS + 0.3 = 3.53–3.67 V (with +3V3 at ±2 %), and inside PC11 (FT) | [DRV16] p.63 Table 8-19 (CTRL2 reset 60h, SDO_MODE reset 1h = push-pull); p.54 §8.5 "When the nSCS pin is pulled high … the SDO pin is Hi-Z"; p.37 §8.3.10.4 Fig. 8-26 (push-pull from AVDD); [INA] VIO ≤ VS + 0.3.  Action: reword to "SDO is push-pull from reset (SDO_MODE = 1) and Hi-Z while nSCS is high; CTRL2 keeps it push-pull" |
| N-02 | NOTE | **"Use the drive's own VM" is not available.**  [D] l.600 says to feed forward "the drive's own VM (or VBAT − I·R)".  The DRV8316C has no VM measurement: no ADC or VM field in the register map, and SOx carries phase current only.  Only VBAT (VBAT_SNS / INA239 VBUS) is measured, so the feed-forward must be VBAT − I_bus·0.1 Ω, with I_bus estimated from the FOC state (Vd·Id + Vq·Iq)/VBAT.  The error without the correction is ≤ 0.1–0.25 V at the 1–2.5 A bus currents seen here (~1 %) | [DRV16] §8.6 register map (CTRL1–CTRL10, status registers: no VM); [N] no L_VM connection to the MCU.  Action: "use VBAT − I_bus·R (the DRV8316 does not report VM)" |
| N-03 | NOTE | **UVLO hiccup under a sustained load on a tired pack: re-verified; settled.**  `hiccup.py`: a tired pack (12.6–14 V, 0.16–0.25 Ω) with a 20–25 A load held above 5 V hiccups the switch at ~500 Hz (14–18 openings in 30 ms).  The re-closes are soft: ≤ 0.03 V/µs at the VM pins, because the re-close is a 60 µA gate ramp.  Q7 takes 74–77 W peak, ~9.5 mJ per event and **5.7–7.3 W average**.  That is consistent with R8A-01's 4.4–5.9 W, and the per-event pulse is inside the SOA (~170 µs at ≤ 10 V is well under the 100 µs–1 ms lines [HYG] p.4 Fig. 3).  The existing requirement (firmware fold-back at ~12 V; the DRV8323 UVLO and the logic cut-off end it in the real board) stands.  No change | `hiccup.py`; round7_a R7A-01, round8_a R8A-01 |
| N-04 | NOTE | **Minimum working voltage of R13 (0402) during the BAT_IN avalanche ring.**  When the switch opens under load, BAT_IN clamps at VBAT + V(BR)(Q7) + 0.8 V ≈ 55–61 V (R8D-02), while EN is ≤ 8 V.  So R13 (100 k 0402) sees ~50–53 V for ~0.1–0.2 µs (300 nH × 22 A / ~45 V).  That is at the 0402 maximum working voltage (50 V) and well under its 100 V overload rating.  Harmless; recorded because R13 is the only 0402 on BAT_IN | [UR] p.5 §7 (0402: 50 V working / 100 V overload); round8_d R8D-02 |

## Re-verification by block (independent pass; no finding)

* **Power entry (U13, Q7/Q8).**  DDF pinout 1 EN/UVLO, 2 GND, 3 NC, 4 VCAP, 5 VS, 6 GATE, 7 OV, 8 SRC ([LM] p.3 Table 5-1).
  The back-to-back common-source orientation (Q7 drain at the pack, Q8 drain at the board, SRC at the common source) is TI's
  Figure 9-1 ([LM] p.14).  UVLO: 1.14 V × 115/15 + 3 µA × 100 k = 9.04 V off; 1.24 × 7.67 + 0.3 = 9.8 V on ([LM] p.5).
  VS abs max ±65 V ([LM] p.4): the avalanche ring stays ≤ ~61 V (R8D-02).  VCAP: the pump turns off at 11–13.9 V and sources
  162–600 µA at 7 V ([LM] p.5), so it sustains the 60 µA gate source into D4.  GATE–SRC is clamped by D4 below the 15 V abs
  max.  C12 220 nF ≥ the 0.1 µF ROC minimum even with DC bias at 12 V.  T(DRV_EN) ≈ 75 µs + 220 nF · 6.5 V / I_CP ≈ 5–9 ms on
  the first plug-in only.
* **Soft-start SOA.**  Q7 peaks at 16–22 W and 54–57 mJ over ~8 ms (`hotplug.out`).  [HYG] p.4 Fig. 3 at Tc 25 °C gives the
  10 ms/DC line ≈ 70–75 W at 10–16 V (the thermal limit, RθJC 2 °C/W).  Derated to Tc 100 °C (×0.5) that is ~37 W, i.e.
  ≥ 1.7× at the 77 µA gate-current corner and ≥ 2.3× nominal.
* **R302/R402 filter.**  L_VM / R_VM carry R302/R402.2, the 2 × 100 nF, the 4 × 10 µF, the CP cap (C303/C403.2) and U3/U4 pins
  9–11 only [N].  CP to VM per [DRV16] Table 6-1.  CP/CPH ≤ VM + 6 V and SW_BK ≤ VM + 0.3 V are relative to the pins' own VM, so
  they are consistent.  OVP at OVP_SEL = 1 is 20/22/23 V rising, t_OVP 2.5–7 µs ([DRV16] p.13), against the 18.5 V coast +
  I·R ≤ 0.25 V (as in round 11).
* **DRV8316 SPI words.**  I re-decoded all nine frames (address, data, even parity) against the register tables
  ([DRV16] pp.62–68).  CTRL2 0x7C = SDO push-pull, 200 V/µs, 3x PWM.  CTRL3 0x4E = OVP 22 V on, SPI faults off nFAULT, OTW
  off.  CTRL4 0x10 = 0.6 µs deglitch, 16 A, latched.  CTRL5 0x00 = 0.15 V/A.  CTRL6 0x19 = BUCK_PS_DIS, BUCK_CL 150 mA,
  BUCK_DIS.  CTRL10 0x18 = DLYCMP_EN, 1.8 µs.  All as §8 states.  Power sequencing only applies at BUCK_SEL 5.0/5.7 V
  ([DRV16] §8.3.4.4), so the default 3.3 V resistor-mode buck is harmless until it is disabled.
* **DRV8323RH straps.**  The EC table and Figs. 8-23/8-24 ([DRV23] pp.14–17, p.52) give MODE 45–47 k→AGND = 3x (1.24 V node
  with the 50 k/84 k internals).  GAIN Hi-Z = 20 V/V (2.07 V).  IDRIVE 75 k→AGND = 60/120 mA (1.11 V).  VDS 18 k→AGND = 0.13 V
  (0.545 V).  VDS OCP 0.13 V / 1.4–2.1 mΩ = 62–93 A.  The charge pump needs 3 · 59 nC · 24 kHz = 4.2 mA, against 25 mA average
  per driver ([DRV23] ROC p.13).  The pinout matches Table 6-4 (p.10–11) for all 49 pads.  The nSHDN pull-up current
  (−1 µA below, −4.2 µA above threshold) and the 390 k/51 k divider give on 10.42 V / off 9.17 V ([DRV23] p.18).
* **Current sense / fast trip.**  Weapon: 2 mΩ × 20 = 40 mV/A, bias VREF/2 = 1.65 V, linear 0.25–3.05 V → ±35 A.  A 30 A trip
  is SOx < 0.45 V, 0.2 V inside the linear floor.  COMP1/COMP3 share DAC3_CH1 and COMP6 uses DAC4_CH2.  The SPx/SNx abs max is
  ±1 V continuous and ±3 V for 200 ns ([DRV23] p.12), which the comparator trip keeps shoot-through far from.  Drive:
  0.15 V/A, ±(AVDD/2 − 0.25)/0.15 = ±8.7–9.9 A; SOx ≤ AVDD − 0.25 into TT_a pins.
* **INA239.**  DGS pinout (1 CS, 2 MOSI, 3 ALERT, 4 MISO, 5 SCLK, 6 VS, 7 GND, 8 VBUS, 9 IN−, 10 IN+) ([INA] p.3).
  SHUNT_CAL = 819.2·10⁶ · 1.25 mA · 1 mΩ · 4 = 4096 = 0x1000.  SOVL 38 mV / 1.25 µV = 0x76C0.  BOVL 19 V / 3.125 mV = 0x17C0.
  The reset limits (SUVL 0x8000, BUVL 0) never trip.  VOL is 0.4 V at 1 mA, so discharging C19 stays within its 10 mA output
  rating.  VIO ≤ VS + 0.3 (see N-01).
* **BQ76907.**  Pinout 1–21 ([BQ] pp.3–4).  The 4S connection is VC7–VC6, VC5–VC4, VC3–VC2, VC1–VC0 with VC6=VC5, VC4=VC3 and
  VC2=VC1 shorted ([BQ] p.32 Table 7-1).  SRP/SRN/TS go to VSS, DSG/CHG/REGOUT float (REGOUT has C11), and REGSRC = BAT ([BQ]
  p.51 Table 8-3).  The abs max for BAT/REGSRC is VSS + 40 V ([BQ] p.5).
* **Sensor interfaces.**  TPS22945 DCK pinout 1 VOUT, 2 GND, 3 OC, 4 ON, 5 VIN, ON active-high, 100 mA minimum limit, 5–20 ms
  blanking, 80 ms restart ([TPS] pp.3, 5).  A 10 µF sensor-board cap charges in 0.33 ms at 100 mA, inside the blanking.
  The MT6701 draws 3.0–5.5 V, 14 mA max.  SN74LVC3G17 (5.5 V-tolerant inputs) and the 1 k/4.7 k/BAV99 networks are unchanged.
* **Logic levels.**  U6/U14/U9/U10 run on +3V3.  INLx VIH is 1.5 V ([DRV23]).  DRVOFF is held at 2.57–2.75 V by R50 against
  the two 100 k pull-downs.  L_nFAULT/R_nFAULT (≤ AVDD 3.465 V) go into FT pins PB7/PC15.  The 5 V sensor option only
  back-feeds +3V3 through the 4.7 k pull-ups (0.36 mA/line).
* **Ratings.**  Every capacitor's rating is ≥ 1.5× its node's worst DC level: C13 50 V against a gate ≤ 29 V; C14 100 V
  against the ≤ 61 V ring; C24–C27 and the VM caps 50 V against the 32.4 V clamp.  The resistor powers are all inside
  rating: R15 41 mW (0805), R113/R117 74 mW (0603), R302 above.  The diodes' orientation (pad 1 = K) and VRRM hold: D10 sees
  ≤ 29 V (75 V part), D2 ≤ 32.4 V (40 V), D9 ≤ 3.3 V.
* **Hot-plug / ARM sims** reproduce byte-identically.  The worst VM ramp is 2.66 V/µs (−40 °C C1) and 2.26 V/µs (0 °C bound),
  against the 4 V/µs limit ([DRV16] p.6).

**Verdict: 0 BLOCKER, 0 MAJOR, 1 MINOR, 4 NOTE.**  The circuit is correct as netlisted.  The R302/R402 loss figures
(0.11/0.24/0.52 W, ≤ ~1 W in bursts) check out to within ~10 % by an independent computation.  The one actionable item is
bring-up step 4.  As written it measures R302 at a phase current that produces almost no bus current, so a shorted or
0 Ω R302 would pass.  Replace it with a 1 A forced-current (or 4-wire) measurement on the unpowered board.
