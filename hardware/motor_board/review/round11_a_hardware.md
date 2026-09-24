# Round 11 / A: hardware (rev K), schematic-capture readiness

Scope: rev K's hardware change (R302/R402 0.1 Ω 1 W 2512 in each DRV8316 VM feed; 4 × 10 µF + 2 × 100 nF per drive
and the CP cap on the filtered nets L_VM/R_VM), then one more independent pass over every circuit block.  No design file was
edited.

**Snapshot.**  I copied the package to `/tmp/r11a/motor_board` (rev K).  `motor_board.py` gives "236 refs (204 placed components),
160 nets, 67 BOM lines, checks: OK", and nets.md, netlist.csv, bom.csv and mcu_pinmap.md are byte-identical to the live files.
`sim_hotplug.py` and `sim_arm.py` reproduce `hotplug.out` and `arm.out` byte-identically.

Probes (in `/tmp/r11a/probe/`, hardware venv):
* `sens.py`: the worst hotplug cases re-run with the local capacitance at 16/12/10/8 µF and with the solver step capped at 0.2 µs.
* `twobranch.py`: the same worst cases with **both** drive filters modelled (the shipped sim filters one drive and lumps the other
  drive's 16 µF straight onto VBAT in `cm 28u`).
* `ripple.py`: a 48 kHz centre-aligned SVPWM inverter input current, split between R302 (+ trace L) and the local 16 µF.
* `wripple.py`: the weapon's 24 kHz inverter input current on the bus (pack 150 nH + 56 mΩ, C1 at 20/40/100 mΩ ESR, weapon MLCCs
  12 µF, two drive branches of 0.1 Ω + 16 µF).  It gives the current and power each drive's R302 takes from the weapon ripple,
  and the dV/dt at the local-cap node.
* `zout.py`: the impedance seen at the DRV8316 VM pins from 100 Hz to 100 MHz.  It is swept over lead inductance (50 nH–1 µH),
  C1 ESR (20–300 mΩ) and the C1→R302 trace inductance (5–50 nH).

References: [DRV16] DRV8316C SLVSH07 (Dec 2022; page numbers are PDF pages); [DRV23] SLVSDJ3D; [LM] LM74502 SNOSDE5A;
[INA] INA239; [TPS] TPS22945 SLVS832D; [JLC] JLCPCB part API, 2026-09-24 (C13585 = Samsung CL31A106KBHNNNE 10 µF 50 V X5R 1206,
2.68 M in stock, Basic; C25466 = UNI-ROYAL 25121WF100LT4E 100 mΩ 1 % 1 W 200 V 2512 thick film, 76 k, Extended); [D] DESIGN.md
rev K; [N] motor_board.py / nets.md; [C] calcs.md.

## Findings

| ID | Sev | Where | Finding | Evidence | Fix |
|---|---|---|---|---|---|
| R11A-01 | MINOR | [D §3.3] VM row "Cost: 0.1–0.4 W at 1–2 A of drive bus current"; [C] row "DRV8316 VM filter"; [N] R302 comment; [C §11] heat budget (no R302/R402 line) | **R302/R402 dissipation is understated by ~1.5–3× because the RC filters none of the PWM ripple.**  The filter corner is 1/(2π · 0.1 Ω · 16 µF) = **99 kHz, above the 48 kHz PWM**.  At 48 kHz the 16 µF is 0.21 Ω against R302's 0.1 Ω, so ~90 % of the fundamental ripple, and ~95 % of the inverter's total input RMS, flows through R302.  The DC bus current alone does not set the loss.  (a) **The drive's own current** through R302: 1.03 / 1.55 / 2.27 A rms at 1 / 1.5 / 2 A rms phase current and M 0.9–0.95, i.e. **0.11 / 0.24 / 0.52 W**.  At low modulation it is less (2 A at M 0.5: 0.21 W).  The local caps carry only 0.4–1.0 A rms.  (b) **The weapon's ripple.**  Behind 0.1 Ω, each drive's 16 µF is still part of the weapon's bus decoupling.  During a weapon burst (14–20 A rms phase), each R302 carries **0.65–2.4 A rms** of 24 kHz ripple, i.e. **0.04–0.11 W** with C1 at 20 mΩ, 0.09–0.25 W at 40 mΩ and **0.2–0.58 W at C1's 100 mΩ aged 0 °C bound**.  Worst coincident case: ~1.1 W for ≤ 0.5 s bursts, inside a 2512 thick film's short-time overload (typically 2.5 × P for 5 s; **UNVERIFIED** for this maker, whose datasheet is not in datasheets/).  Sustained, the loss is ≤ ~0.5 W at the 2 A drive limit.  A 1 W part derates linearly from 70 °C to 0 W at 155 °C, i.e. to ~0.65 W at a 100 °C local board, so R302 must not sit on the DRV8316's hot thermal copper (at 2 A the IC dissipates up to 2.8 W, +72 °C JEDEC).  The part choice survives.  The numbers and the heat budget do not.  At the realistic 1–1.5 A traction limit the total is ~0.15–0.35 W per resistor | `ripple.py` (48 kHz SVPWM, R302 + 11 nH vs 16 µF/3 mΩ); `wripple.py`; [DRV16] §7.3 IOUT 8 A pk; [C §10] drive loss 2.80 W worst at 2 A; UNI-ROYAL thick-film derating (general; datasheet UNVERIFIED) | Replace the cost text with: "R302 carries ~95 % of the drive's inverter input RMS (the RC corner of ~100 kHz is above the PWM) plus 0.1–0.6 W of the weapon's ripple during bursts: ~0.1–0.35 W at 1–1.5 A, ≤ ~0.5 W at 2 A continuous, ~1 W peak coincident for ≤ 0.5 s".  Add R302 + R402 (~0.3–0.6 W together) to the calcs §11 heat budget.  Add to §6.6: place R302/R402 on the VBAT pour toward C1, not on the DRV8316 thermal-pad copper (only the caps need to be within 2 mm).  Put the UNI-ROYAL datasheet in datasheets/ |

## Notes

| ID | Sev | Finding | Evidence / action |
|---|---|---|---|
| N-01 | NOTE | **OVP through R302 during regen (asked for in scope): VM can sit above VBAT, but not up to the OVP.**  In regen, L_VM = VBAT + I_R302 · 0.1 Ω.  At the ~1–1.5 A FOC regen limit that adds ≤ 0.15–0.25 V (instantaneous, including the ripple that R302 carries, R11A-01).  At an 8 A regen peak, which the FOC limit precludes, it would add 0.8 V.  Worst stack: 18.5 V firmware coast threshold + ~0.7 V weapon-ripple half-amplitude at VBAT (0.6–1.4 V pp) + 0.25 V ≈ **19.4 V against OVP (OVP_SEL = 1) rising min 20.0 V**.  The 24 kHz ripple crest lasts ~10–20 µs, longer than t_OVP 2.5 µs min, so only ~0.6 V of margin remains.  R302 uses ~0.25 V of it.  If OVP did trip, the result is benign: outputs Hi-Z, automatic recovery below V_OVP ([DRV16] Table 8-8), i.e. a brief drive coast.  The motor's stored energy then dumps into 16 µF ∥ R302: 1.5 A → ≤ 0.2 V; 8 A with a ~50 µH phase inductance (**UNVERIFIED**) → ≤ ~0.8 V at ≤ 0.5 V/µs.  The pack-disconnected case is unchanged: D1 clamps VBAT ≤ 32.4 V, + ≤ 1 V ≤ 40 V abs max, and the DRV8316 OVP Hi-Zs the drives as §8 assumes.  The CTRL3 0x0A4E decode is correct: bit 6 reserved (reset 1), OVP_SEL = 1 (22 V), OVP_EN = 1, SPI_FLT_REP = 1, OTW_REP = 0 | [DRV16] p.13 V_OVP 20/22/23 V rising, 19/21/22 V falling, t_OVP 2.5–7 µs; p.48 Table 8-8 OVP row; p.64 CTRL3 (reset 46h); `wripple.py`.  Optional: state in §8 that the 18.5 V coast leaves ~0.6 V of OVP margin at the ripple crest |
| N-02 | NOTE | **VM droop and UVLO (asked for in scope): no issue.**  8 A × 0.1 Ω = 0.8 V.  At the switch UVLO minimum (7.7 V bus), L_VM ≥ 6.9 V against the DRV8316 UVLO of 4.3–4.5 V rising / 4.1–4.3 V falling.  The drive's own current steps into the local caps at ≤ 8 A / 16 µF = 0.5 V/µs.  Its own 48 kHz ripple at L_VM is 0.14 / 0.21 / 0.25 V pp at 1 / 1.5 / 2 A rms, up to 0.8 V pp at 8 A peaks.  The only time VM gets near the UVLO is the loaded contact bounce (sim: VM 4.4–4.7 V before re-close), which is §7.2's residual.  A DRV8316 reset there is caught by the §8 NPOR check | [DRV16] p.13 V_UVLO; `ripple.py`; `hotplug.out` |
| N-03 | NOTE | **Charge-pump reference (asked for in scope): correct.**  C303/C403 1 µF 50 V go from CP to **L_VM/R_VM**, not VBAT.  [DRV16] Table 6-1 says "Connect a … 1-µF, 16-V ceramic capacitor between the CP and VM pins", and V_VCP is specified "with respect to VM" (3.6–5.25 V).  A VBAT-referenced CP cap would have lost the 0.8 V I·R drop at an 8 A peak.  C304 47 nF 50 V CPH–CPL meets TI's "≥ 2× operating voltage".  CP abs max VM + 6 V is relative to the VM pins, which are now L_VM, so it is consistent | [DRV16] p.4 Table 6-1; p.7 V_VCP; p.19 external-component table; [N] L_CP/R_CP, L_VM/R_VM |
| N-04 | NOTE | **Stability / resonance (asked for in scope): none.**  From 100 Hz to 2 MHz the impedance at the VM pins is ≤ 0.13–0.18 Ω with no peaking.  Sweep: lead 50 nH–1 µH, C1 ESR 20–300 mΩ, C1→R302 trace 5–50 nH, the other drive's branch included.  At 48 kHz it is 0.10–0.16 Ω.  The trace-L/16 µF section is overdamped: √(L/C) = 18–56 mΩ < R = 100 mΩ.  A constant-power drive (the FOC current loop) has an incremental input resistance of −V²/P ≈ −7 Ω at 40 W and 16.8 V, **> 40× the source impedance**, so there is no negative-resistance oscillation (Middlebrook).  R302 also damps the bus's own ~10 kHz lead/C1 resonance.  The only peak is the usual MLCC-bank anti-resonance near 18 MHz (~1.5 Ω, ESL-limited), which the 100 nF pin caps handle | `zout.py` |
| N-05 | NOTE | **Weapon ripple at the filtered VM.**  The weapon's 24 kHz bus ripple (0.6–1.4 V pp at VBAT) passes the RC almost unattenuated (0.4–1.1 V pp at L_VM), but its edges are slowed to **≤ 0.4 V/µs** at the local-cap node.  §6.6's worry about weapon ripple at the VM pins is therefore closed in hardware.  The §9 step 6 scope check is still worth doing.  Each 10 µF 1206 carries ≤ ~0.65 A rms (drive + weapon share), ~2 mW at ~5 mΩ ESR.  An explicit ripple rating is not published for CL31A106KBHNNNE (**UNVERIFIED**), but self-heating is negligible | `wripple.py` (cap-node voltage from I_branch · Z_C) |
| N-06 | NOTE | **Pulse rating: the text cites the wrong spec, but the stress is benign.**  §7.21 says R302 takes "~100 A for ~1 µs (~1 mJ, well inside a 2512's short-time overload)".  STOL is a 2.5 × P / 5 s rating and says nothing about a 1 kW / 1 µs pulse (10 V across the part).  The re-close and bounce events are the same scale: ≤ ½ · 16 µF · 12.3² ≈ 1.2 mJ per event, 100–120 A peak.  Adiabatic estimate: a ~10 µm film over ~4.5 × 2.5 mm has ~0.3 mJ/K, so 1 mJ gives a **~3 K** film rise (the diffusion length in 1 µs is ~1–3 µm).  That is benign, but **UNVERIFIED** without the maker's single-pulse curve.  Side effect: if a DRV8316 fails with VM shorted to GND, R302 sees ~168 A (2.8 kW) and opens within ms.  That isolates the dead drive from the bus, but may scorch the board | [JLC] C25466 1 W 200 V thick film; `when.py` (round 10) order of magnitude.  Action: reword §7.21 ("single-pulse energy ~1 mJ; check the maker's pulse curve"), add the datasheet |
| N-07 | NOTE | **Sim fidelity: the margin holds.**  `sim_hotplug.py` runs with `tmax = 20 µs` and filters only one drive.  With the step capped at 0.2 µs and **both** drive filters modelled, the worst cases are **2.25 / 2.29 / 2.71 / 2.14 V/µs** (0.3 / 0.8 ms bounce at the 0 °C bound, −40 °C limit, min-UVLO re-close 400 ms), against 2.21 / 2.25 / 2.65 / 2.06 as shipped.  So §1's "≤ 2.7 V/µs" is 2.71: say ≤ 2.75.  The margin is also robust to the effective local capacitance: at 12 / 10 / 8 µF (DC bias, tolerance, cold) the worst case is 3.02 / 3.26 / **3.47 V/µs** (−40 °C bounce).  All are under 4 V/µs | `sens.py`, `twobranch.py` |
| N-08 | NOTE | **The drive's own hard output short now droops VM faster than without R302, but stays under 4 V/µs.**  The local 16 µF supplies the short and R302 refills it (τ 1.6 µs).  OCP_DEG = 01b (CTRL4 0x10) is 0.6 µs typ / 1.2 µs max.  At an assumed 20–40 A integrated-FET saturation current (**UNVERIFIED**; the datasheet gives only I_OCP 10–22 A), the initial droop is 1.25–2.5 V/µs, falling toward the I·R asymptote, and recovery is ≤ ~1.5 V/µs.  Informational | [DRV16] p.13 I_OCP, p.14 t_OCP; §8 CTRL4 0x0D10 |

## Re-verification by block (independent pass)

* **DRV8316C (U3/U4):** all 41 pins in `drv8316()` match [DRV16] Table 6-1 for the CR variant: NC 1/24, AGND 2/26, FB_BK 3,
  GND_BK 4, SW_BK 5, CPL/CPH/CP 6/7/8, VM 9–11, PGND 12/15/18, OUT 13-14/16-17/19-20, DRVOFF 21, nFAULT 22, nSLEEP 23, AVDD 25,
  INH/INL 27–32, SDO/SDI/SCLK/nSCS 33–36, VREF/ILIM 37, SOC/SOB/SOA 38/39/40.  External parts match the p.19 table: AVDD 1 µF
  (0.7–1.3 µF effective), CP 1 µF, CPH–CPL 47 nF, CBK 22 µF ≥ 10 V, RBK 22 Ω, VREF 0.1 µF, VM ≥ 10 µF bulk + 0.1 µF.  VREF = AVDD
  is within Rec. Op. "2.8 V … AVDD".  nFAULT pulled up to AVDD (> 2.2 V at power-up) is correct.  CTRL3 0x4E and CTRL4 0x10
  decode as §8 states (N-01, N-08).
* **Rev K nets:** L_VM = R302.2, C300/C301/C302/C308/C309/C310, C303.2 (CP) and U3 pins 9/10/11; R_VM is the same with 4xx.
  VBAT carries R302.1/R402.1 and no DRV8316 pin.  L_CP/R_CP each contain only C303.1/C403.1 and U3.8/U4.8.
* **Power entry:** LM74502 DDF pinout per [LM] Table 5-1 (1 EN/UVLO, 2 GND, 3 NC, 4 VCAP, 5 VS, 6 GATE, 7 OV, 8 SRC).  C12
  VCAP–VS (datasheet VCAP–VS abs max 15 V; 25 V part).  OV to GND "when OV feature is not used".
* **INA239:** DGS pinout per [INA] Table 5-1.  MISO is tri-stated with CS high (t_CS_MISO_HIZ 25 ns, §8 "MISO output is
  tri-stated"), so there is no contention with the DRV8316 SDOs on SPI3.  ALERT open-drain onto W_nFAULT (R42 to +3V3, VIO ≤ VS + 0.3).
* **U2 DRV8323RH:** CVIN 2.2 µF inside TI's "1 to 10 µF, VM-rated" (C27 50 V).  nSHDN threshold 1.05–1.38 V with the pull-up current:
  the §3.1 9.2/10.4 V figures are consistent (unchanged since round 9).
* **Sensor supply:** TPS22945 DCK pinout (1 VOUT, 2 GND, 3 OC, 4 ON, 5 VIN) and ON **active-high** ([TPS] device table:
  "TPS22945 … Active HIGH").  ON tied to VIN is correct.
* **Logic:** SN74LVC3G17 DCU pinout (1A 1, 3Y 2, 2A 3, GND 4, 2Y 5, 3A 6, 1Y 7, VCC 8) matches U9/U10.  74LVC1G17 SOT-353 (A 2,
  GND 3, Y 4, VCC 5).  BAT54S/BAV99 SOT-23 (1 A1, 2 K2, 3 common) oriented as documented.
* **Hot-plug and ARM:** sims reproduce.  The rev K filter keeps every bus event ≤ 2.71 V/µs at the VM pins (N-07).
* Round 10's checks of the ADC/comparator plan, straps, buck, BQ76907, header and MCU support carry over: nothing changed there in rev K.

## VERIFIED OK

* R302/R402 = C25466, 0.1 Ω 1 % 1 W 200 V 2512 thick film, in stock.  C302/C308–C310 = CL31A106KBHNNNE 50 V X5R 1206, Basic.  The
  ~16 µF effective holds, and even half of it keeps every simulated event ≤ 3.5 V/µs.
* CP cap on L_VM/R_VM (datasheet: CP to VM).  VM droop 0.8 V at 8 A, far above the UVLO.  No LC/RC resonance, and > 40× margin
  against the drive's negative input resistance.
* Regen through R302 raises VM ≤ 0.25 V at the FOC limit.  The OVP (20 V min) is not reached below the 18.5 V coast threshold.  VM
  stays under 40 V with D1.
* R302 thermal: adequate (≤ ~0.5 W sustained, ~1 W burst), but the documented figures are low (R11A-01).
* Weapon ripple at the filtered VM ≤ 0.4 V/µs.  Local-cap ripple current negligible.
* Hot-plug worst cases re-simulated with both filters and a 0.2 µs step: ≤ 2.71 V/µs (limit 4).
* DRV8316C, LM74502, INA239, TPS22945, LVC3G17, LVC1G17 pinouts against their datasheets.  Netlist, BOM, pinmap, `hotplug.out`,
  `arm.out` regenerate byte-identically.

**Verdict: 0 BLOCKER, 0 MAJOR, 1 MINOR, 8 NOTE.**  The rev K hardware is right.  R11A-01 is a documentation and placement
item: R302/R402 carry the PWM and weapon ripple, not only the DC bus current, so the loss figures and heat budget need correcting
and R302 should sit off the DRV8316 thermal copper.
