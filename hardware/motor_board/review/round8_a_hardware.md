# Round 8 / A: hardware (rev H), schematic-capture readiness

Scope: rev H's only hardware change (C18 100 nF on U13 EN/UVLO: soft-start delay, UVLO response to real sags, ripple
rejection), then an end-to-end re-check of every circuit block against the datasheets.  No design file was edited.

**Snapshot.**  I copied the package to `/tmp/r8a/motor_board` at the start of the review (rev H, 23:58).  While I worked, the live
package moved to rev I (files rewritten 00:08–00:09: C14 → 100 V, R33, §7.14 hard-short text, doc fixes from R8B/R8D).  All
evidence here is against the rev H snapshot.  R8A-01 still applies to rev I: C18 and the texts it cites are unchanged there.

Tools and probes (all in `/tmp/r8a/probe/`, run with `hardware/tools/.venv/bin/python`):

* `bounce.py`, `bounce2.py`, `bounce3.py`, `bounce4.py`: `sim_hotplug.py`'s circuit (imported unchanged) plus a 20 A
  (or 10 A) load that runs while VBAT > 6 V, standing in for the DRV8323 VM UVLO of 5.4–5.8 V.  The switch is closed at 1 ms and
  the load is applied at 40 ms.  The pack contact opens at 60 ms for 20 µs–2.5 ms and then re-closes.  C18 is set to 0 (rev G),
  4.7 n, 10 n, 22 n or 100 n.  The probes report the bus and Vgs at the re-close, the peak VM dV/dt, and the peak Q7 current.
* `ripple.py`: a 0/30 A, 24 kHz square load (weapon PWM input current) on a 16.8 V / 56 mΩ pack and a 13.6 V / 120 mΩ pack,
  with C1 at 20 and 40 mΩ.  It reports the EN dip below its mean, referred to the bus.
* `sag.py`: a tired pack with a held 20–25 A load, max UVLO thresholds (1.235/1.32 V, 5 µA sink).  It reports Q7's peak and
  average power while the switch hiccups.
* `short.py`, `short_dbg.py`: a 1 mΩ short across VBAT with C18 = 0 and 100 nF.

References: [LM] TI SNOSDE5A (LM74502), [DRV23] SLVSDJ3D, [DRV16] SLVSH07 (DRV8316C), [INA] SLYS027A (INA239), [BQ] SLUSE96A,
[TPS] SLVS832D, [HYG] HYG015N04LS1C2 V1.0, [D] DESIGN.md rev H, [N] design/motor_board.py rev H, [C] design/calcs.md rev H.

## Findings

| ID | Sev | Where | Finding | Evidence | Fix |
|---|---|---|---|---|---|
| R8A-01 | MINOR | C18 (PSW_EN); [D §3.1] R13/R14/C18 row "limits a quick re-close step to ~9 V"; [N] R13 desc (same words); [C] §9 Switch UVLO row; [D §7.2] "steps the bus from 8–16 V" | **C18 widens and deepens the hard re-close after a contact bounce under load.**  §3.5 item 4 expects ms contact bounce at the switch or XT30 under load (it is why the compute board gets 470 µF).  During a bounce the pack is disconnected and a 20 A load drains C1 (330 µF plus the MLCCs) at ~55 V/ms, so the bus collapses in ~0.1 ms.  **Rev G:** EN followed the bus within 2 µs.  The FETs opened as the bus crossed ~9 V, and a re-close after that was a soft Cdvdt ramp; the hard (FETs-on) window lasted ≤ ~45 µs.  **Rev H:** C18 (τ 1.3 ms) holds EN up for ~1.3–1.9 ms after the bus has collapsed.  A re-close in that window finds the FETs fully on (Vgs 11.9 V) and the bus at ~5.5 V, the level where the load's DRV8323 stops.  The result is an ~11 V step and ~200 A peak.  At the design's own worst corner (stiff pack, C1 at its −40 °C ESR), the peak VM dV/dt reaches the DRV8316's **4 V/µs absolute maximum** ([DRV16] 7.1).  At 25 °C with a stiff pack it is 2.8 V/µs, and with the nominal pack and lead 1.1–2.0 V/µs.  So the "~9 V step" in the R13/C18 texts holds only for an unloaded bus, and §7.2 covers only the unloaded, open-switch decay case. | `bounce.py`/`bounce3.py` (stiff pack 20 mΩ / 50 nH, 20 A load). C18 100 n, C1 40 mΩ: off 200–1500 µs → bus 5.35–5.87 V, Vgs 11.92, **2.76–2.81 V/µs**, 195–204 A; 2.5 ms → FETs off, 0.07 V/µs.  C1 60 mΩ: 3.08–3.12; 100 mΩ: 3.45–3.48; **300 mΩ: 3.92–4.05 V/µs** (100–1000 µs; 100 µs = 4.045 "EXCEEDS").  10 A load, 40 mΩ: 500–1000 µs → 2.97 V/µs.  `bounce4.py` nominal pack 48 mΩ / 150 nH, 0.5 ms: 1.09 (40 mΩ) / 1.98 (300 mΩ) V/µs; no bus overshoot (VM ≤ 16.9 V).  Rev G (C18 = 0): 40 mΩ ≤ 1.72 V/µs at 90 µs; 300 mΩ ≤ **2.92 V/µs** at 40 µs, FETs off from 45 µs (0.076 V/µs).  `bounce2.py`: 10 n → hard window ≤ 200 µs (40 mΩ) / ≤ 150 µs (300 mΩ, still 4.0 V/µs at 100–150 µs); 4.7 n → ≤ 150 / ≤ 100 µs; 22 n → ≤ 300 µs.  τ = (100k ∥ 15k) × 100 nF = 1.30 ms. | No EN capacitor value removes this: any τ ≳ 20 µs lets the bus fall to ~6 V with the FETs on at the 300 mΩ corner.  And C18 = 100 nF earns its keep elsewhere: in the tired-pack hiccup (R7A-01), `sag.py` gives Q7 an average of **4.4–5.9 W** with 100 nF, 14–17 W with 10 nF and 47–68 W with none.  So: **keep C18 = 100 nF** (or accept 10 nF if the bounce window matters more) and correct the documentation.  In the R13/C18 row, the R13 netlist description and calcs §9, change "limits a quick re-close step to ~9 V" to "…~9 V with the bus unloaded".  Add to §7.2: "a contact bounce of ~0.1–1.5 ms under load re-closes with the FETs on from ~5.5 V: 1–2 V/µs with the nominal pack and lead, 2.8 V/µs with a stiff pack, ~4 V/µs with C1 at its −40 °C ESR; secure the XT30 and switch leads".  Optionally add a loaded-bounce case to `sim_hotplug.py`. |

## Notes

| ID | Sev | Finding | Evidence / action |
|---|---|---|---|
| N-01 | NOTE | **C18's intended effects check out.**  (a) Ripple: the EN dip below its mean, bus-referred, is 0.47–0.64 V without C18 and 0.002–0.004 V with 100 nF (10 nF would give 0.02–0.03 V).  (b) Soft-start delay added by C18: EN reaches V(EN_UVLOR) 1.1 ms after closure at 16.8 V (typ), 2.2 ms at 12 V, and 2.8 ms worst (12 V, 1.32 V threshold, 5 µA sink).  The charge pump's T_DRV_EN (4.8 ms typ, ~10 ms at 162 µA / 7.5 V) dominates.  The closure cases in `hotplug.out` are unchanged in substance.  (c) Slow sags: the trip now acts on the mean bus voltage.  After the switch opens the bus decays with τ ≈ 2.4 s, so C18's 1.3 ms lag moves the opening point by ~5 mV, and the re-close figures (≤ 3.44 V/µs) stand.  (d) EN stays inside its abs max in every case, including a reversed pack (EN ≥ V(VS)) and the 40–60 V BAT_IN ring on a switch-off under load (EN ≤ 7.8 V before the filter; [LM] 6.1: 65 V). | `ripple.py`; [LM] 6.5 V(EN_UVLOR) 1.16/1.24/1.32 V, I(EN) 3/5 µA, Eq. 1; `hotplug.out` re-run byte-identical |
| N-02 | NOTE | **Hard bus short (independent confirmation of R8D-05, now in rev I §7.14).**  Without C18 the switch opens within ~1 µs of the short.  With C18 it stays fully on for **0.9–1.0 ms** (~270 A, VDS ~0.4 V: within the FETs' ratings).  Then it trips and retries into the short with Q7 in its linear region: 80–230 A at VDS 2–11 V, i.e. ~0.5–1 kW pulses.  Rev I's fuse recommendation is the right action. | `short.py`/`short_dbg.py`: C18 100 n, 48 mΩ / 150 nH: EN falls below 1.14 V at 40.9 ms, the gate drops at 41.0 ms, and at 42.0 ms I = 232 A, BAT_IN 3.6 V, Vgs 3.6 V |
| N-03 | NOTE (UNVERIFIED) | **SPx during a weapon phase short (§7.21).**  At the ~500 A reached by the end of the 4 µs VDS deglitch, the 2 mΩ shunt puts ~1.0 V (plus ESL) on SPx.  That is the edge of the ±1 V continuous rating; the ±3 V rating covers only 200 ns.  The current ramps up over the deglitch, so it spends only a short time near 1 V.  No change: this is inside the documented residual. | [DRV23] 6.1 "SLx, SPx, SNx −1 / 1 V; transient 200 ns −3 / 3 V"; 500 A × 2 mΩ |
| N-04 | NOTE | **MODE strap value.**  The EC table specifies the four-level mode-2 input as "45 kΩ ± 5 % tied to AGND", while §8.3.1.1.2 says 47 kΩ.  R44 = 47 k 1 % gives 3.3 × (47∥84)/(50 + 47∥84) = 1.24 V, against 1.22 V at 45 k.  The decision points are ~0.6 V and ~1.6 V, so it is fine. | [DRV23] 7.5 four-level inputs: RPU 50 k, RPD 84 k, VI2 1.2 V, VI3 2.0 V |

## Re-verification by block

* **C18 (rev H change):** see R8A-01 and N-01.  100 nF 16 V 0402 X7R (C1525): EN ≤ 2.2 V in normal operation, −2.2 V with a
  reversed pack.  Placement at U13 pin 1: rev I §6.6 now says so.
* **Power entry:** the U13 DDF pinout, OV to GND, C12 ≥ 0.1 µF (220 nF 25 V vs VCAP–VS ≤ 13.9 V), C14 ≥ 22 nF, D4 cathode on the gate
  (GATE–SRC 0–15 V), D10 polarity (A = PSW_RG, K = PSW_DV) and the Q7/Q8 orientation (Q7 D = BAT_IN, Q8 D = VBAT_SW, common S/G)
  all match nets.md.  The back-to-back common-source arrangement is TI's own; the SRC ≤ V(VS) + diode during reverse or off states
  is intrinsic to it.  UVLO: off 9.04 V typ (7.7–10.14), on 9.81 V (≤ 10.80): recomputed.  R15 0805 at 41 mW.  RS4/U7: INA239
  pinout (CS 1, MOSI 2, ALERT 3, MISO 4, SCLK 5, VS 6, GND 7, VBUS 8, IN− 9, IN+ 10); CM −0.3…85 V; IB ≤ 2.5 nA into 10 Ω;
  ALERT/MISO ≤ VS + 0.3 V; MATHOF/MEMSTAT do not drive ALERT.  D1 SMBJ20A (K = VBAT); C1 35 V > 32.4 V clamp.  Soft-start sim:
  2.19 V/ms, ≤ 0.009 V/µs, Q7 16.2 W / 53.5 mJ (21.5 W at 77 µA); [HYG] Rjc 2 °C/W, EAS 370 mJ, IDM 600 A.
* **Weapon driver U2:** the RGZ pin table matches [N] pin for pin (FB 1 … nSHDN 48, GAIN 32 NC, CAL 34 GND).  Straps: MODE
  47 k → 1.24 V (3x); IDRIVE 75 k → 1.11 V = 60/120 mA; VDS 18 k → 0.545 V = 0.13 V; GAIN Hi-Z 2.07 V = 20 V/V ([DRV23] 7.5 tables).
  VREF 3.3 V within 3–5.5 V, 2–3 mA from +3V3.  VCP 1 µF (TI 1 µF 25 V), CPH–CPL 47 nF VM-rated, DVDD 1 µF, VM 100 nF + bulk.
  The charge pump supplies 4.2 mA of 25 mA.  tDRIVE 4 µs × 60 mA ≫ Qg 59 nC.  Dead time is by VGS handshake, not only the 100 ns
  digital dead time ([DRV23] 8.3.x TDRIVE).  Logic inputs have 100 k internal pull-downs; ENABLE also has R40.  Buck: nSHDN
  thresholds 1.05/1.25/1.38 V with −1/−4.2 µA give on 10.4 / off 9.2 V typ; FB 5.05 V; L1, D2, C27–C30 as TI's; current limit, no
  hiccup.
* **Interlock U6/U14/ARM:** SN74LVC08A TSSOP pinout, fourth gate grounded, R47–R49 and R19 pull-downs; U6 IOFF plus the
  DRV8323 INLx internal pull-downs keep the phases Hi-Z unpowered.  74LVC1G17 SOT-353 pinout (NC, A, GND, Y, VCC).  `arm.out`
  re-runs byte-identical.
* **Bridge:** HYG015N04LS1C2 pads (S 1–3, G 4, D tab); VGS ±20 V vs VGSH ≤ 12.5 V; high sides on VBAT, VDRAIN Kelvin; SPx on the
  FET-source side, SNx through NT1–NT3 to the shunt pads; shunts 0.8 W peak on a 3 W part.
* **U3/U4:** VM 4.5–35 V operating / 40 V abs; CVM1 0.1 µF ×2 and CVM2 ≥ 10 µF (2 × 10 µF 50 V); CP 1 µF; CFLY 47 nF 50 V;
  CAVDD 1 µF 50 V; CBK 22 µF 25 V with RBK 22 Ω; VREF/ILIM = AVDD (2.8 V…AVDD); nFAULT pulled up to AVDD (> 2.2 V at power-up);
  INLx/nSLEEP on +3V3 ≤ 5.5 V; SDO Hi-Z while nSCS is high, so it can share MISO with U7 (push-pull high = AVDD ≤ 3.465 V < U7's
  VS + 0.3); SPI tSCLK ≥ 100 ns vs 5.3 MHz.  In sleep AVDD is off, so neither SOx nor nFAULT back-powers the MCU.
* **Sensors:** TPS22945 is active-high ON (so ON = VIN is correct); SC-70 pinout VOUT 1, GND 2, OC 3, ON 4, VIN 5; VIN
  1.62–5.5 V.  SN74LVC3G17 DCU pinout (1A 1, 3Y 2, 2A 3, GND 4, 2Y 5, 3A 6, 1Y 7, VCC 8).  BAV99 and 2.2 k NTC clamp.
* **BQ76907:** RGR pinout and 4S wiring per Table 7-1; unused pins per Table 8-3 (SRP/SRN/TS to VSS, CHG/DSG open, REGSRC = BAT;
  VC0 through R + C to VSS); SCL/SDA/ALERT ≤ VSS + 6 V.  With TS and VC0 at VSS it cannot wake from SHUTDOWN (R4-07; §8 uses SLEEP
  only).
* **U5 AP2112K:** pinout VIN 1, GND 2, EN 3, NC 4, VOUT 5; EN = VIN; ~0.2 W; the +3V3 net carries well over 1 µF.
* **MCU support:** VDD 4 × 100 nF + 4.7 µF; VDDA/VREF+ 100 nF + 100 nF + 4.7 µF on +3V3A; VBAT pin to +3V3; NRST 100 nF + 10 k;
  BOOT0 10 k; the G4 has no VCAP pin; PC14 (backup domain) only sinks R50's 0.33 mA; `motor_board.py` AF checks pass.
* **Header J1:** 3 × +5 V / 5 × GND pins at ≤ 150 mA per pin (3 A rating); I²C and ALERT ≤ BQ VSS + 6 V; W_ARM_CLK with R18.
* **Netlist regeneration** (rev H snapshot): "229 refs (197 placed components), 157 nets, 65 BOM lines, checks: OK"; nets.md,
  netlist.csv, bom.csv and mcu_pinmap.md are byte-identical to the committed rev H outputs; `hotplug.out` and `arm.out` re-run
  byte-identical.

## VERIFIED OK

* C18 value/rating/function: ripple rejection (0.47–0.64 V → ≤ 0.004 V), soft-start delay (+1.1–2.8 ms, dominated by T_DRV_EN), trip on the mean in slow sags, EN abs max in every case.
* Power entry pinouts, polarities, UVLO arithmetic, soft-start and reversed-pack results, INA239 limits and pins.
* U2 pin map, all four straps (voltages computed from the internal 50k/84k and 73k/73k networks), charge pump, VREF, buck.
* U6/U14/ARM network; bridge pinout and gate-drive margins; shunt Kelvin arrangement.
* U3/U4 external components vs [DRV16] Table 8-1, VREF/AVDD, SPI sharing and timing, sleep behaviour.
* Sensor supply switch polarity and pinout, Schmitt buffer pinout, NTC clamp.
* BQ76907 pinout, 4S wiring, unused-pin terminations, I/O limits.
* AP2112K, MCU supply/reset/boot, header currents and pin functions.
* Netlist, BOM and both SPICE outputs regenerate byte-identically from the rev H snapshot.

**Verdict: 0 BLOCKER, 0 MAJOR, 1 MINOR, 4 NOTE.  Not clean (R8A-01: C18 loaded-bounce re-close; documentation fix, C18 value is a trade-off).**
