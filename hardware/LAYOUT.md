# ThumbsUp v1 — layout brief

Everything the PCB layout needs that the schematic cannot say. Numbers come from the
datasheets in `datasheets/pdf/`, the SPICE checks in `tools/spice/`, and the 2026-09-03
review (`REVIEW.md` §6). Reference designators are those in `kicad/`.

## 1. Board, stackup, fab

| Item | Decision |
|---|---|
| Outline | ≤ 90 × 60 mm (C-4); final outline from the chassis floor (`models/Chassis - Main Chassis.3mf`, 121 × 98.8 × 33.6 mm envelope). Export the floor and drum-mount positions to DXF on User.Drawings before placing. |
| Stackup | JLC 4-layer 1.6 mm FR-4, **2 oz outer**, 1 oz inner (2 oz inner only if orderable with Standard PCBA in the same order — confirm before placement). L1 power stages + phase copper + VBAT pours; L2 solid GND; L3 signals + +VDRV/+5V/3V3 distribution; L4 VBAT/phase mirror pours + thermal copper under FET tabs. |
| Rules | Signals 0.2 / 0.2 mm; 2 oz absolute minimum 0.16 / 0.16 mm; vias 0.3 mm drill / 0.6 mm pad; ≥ 0.25 mm clearance around power pours; no tracks between 0.5 mm-pitch QFN pads (fan out outward). |
| Mounting | H1–H4 M3 (3.2 mm) on the pack sheet — move them to the chassis hole positions. FID1–FID3 1 mm fiducials, 3 per side that carries SMT. Leave 5 mm rail space for the JLC panel. |
| Assembly | JLC Standard PCBA, top side only. Hand-soldered after SMT: Pico W (castellations; keep the module outline and the 4 USB-shell pads clear), J1/J4 XT30, J2/J3 headers, J20/J30/J40 SWD headers, motor pads. Everything else SMT including the 470 µF hybrid cans. |
| Silk | "+" next to J1 pad 2 and J4 pad 2, "3S ONLY" next to J1, "ARM" at J2, phase letters at the motor pads, TP names. |

## 2. Net classes and currents

Design point: pack trunk **20 A continuous / 30 A for ≤ 2 s** (the XT30 is rated 15 A
continuous / 30 A instantaneous and is the limiting element; realistic draw is 14 A).

| Class | Nets | Current | Copper |
|---|---|---|---|
| POWER_30A | VBAT_PACK, VBAT_LINK, VBAT, MOTOR_W_A/B/C, I_W+ | 15 A cont / 30 A pk | pours only, ≥ 8 mm at 2 oz, L1 + L4 mirror stitched with ≥ 16 vias |
| POWER_20A | MOTOR_L/R_A/B/C, I_L+, I_R+ | 10 A cont / 20 A pk | pours, ≥ 6 mm at 2 oz |
| GATE | x_HO1-3, x_LO1-3, x_GxH, x_GxL, x_VB1-3, x_BT1-3 | 2 A pulses | 0.4 mm, < 20 mm, no vias if possible, return (VS / COM) on the adjacent layer |
| VDRV | +VDRV, W_VCC, U1_SW, +5V, +5V_PICO | ≤ 2 A | 0.8 mm |
| 3V3 | +3V3_A, +3V3_MCU, +3V3_PICO | ≤ 0.3 A | 0.4 mm |
| SENSE | x_ISENSE, x_CSA_OUT, I_x_S+/-, PACK_S+/-, U4–U7_IN+/-, x_VSENSE, x_BEMF_A/B/C, x_VN, PACK_V_ADC, 3V3_MON, NTC_ADC | signal | 0.2 mm, guarded, never over a plane split |
| default | everything else | signal | 0.2 mm |

## 3. Ground and current sensing (the part that decides whether the numbers are true)

Every current measurement on this board is 1 mΩ × I: 10 mV at 10 A. One square of 1 oz
copper is 0.5 mΩ, so the sense path must be **4-wire**.

1. Each shunt (R2, R235, R335, R435, footprint `thumbsup:R_2512_Shunt_Kelvin`) has two
   net-ties (`NT*`, 0.5 mm pads). **Place each NT pad on the inner edge of the shunt pad**
   so the sense net starts at the pad, not in the pour. DRC then keeps `I_x_S+/-` and
   `PACK_S+/-` off the current copper.
2. Sense pairs run as short, matched 0.2 mm traces to the INA180 (U22/U32/U42, within 5 mm
   of its shunt) and to the INA226 filter resistors (R30–R61, within a few mm of pins 9/10).
   The INA226 100 nF bypass sits at pins 6/7.
3. Per cell, a local **PGND island** on L1: low-side FET sources → shunt hot pad (I_x+);
   shunt cold pad → C?23/C?24 MLCC negatives and the hybrid can(s) → main GND plane through
   ≥ 8 stitching vias at the shunt cold pad. This is the only place the cell touches L2.
4. FD6288 COM, its 10 µF + 100 nF (C?09/C?10), the AT32 EP and its decoupling, and the
   INA180 GND all return to that cold-pad star, not to the FET pour.
5. Pack entry: TVS D1 and C1–C4 between J1 and J4, nothing else on VBAT_PACK. R2 in series
   after J4 with its full 3.1 × 4 mm pads and ≥ 150 mm² of 2 oz copper each side.
6. Logic (Pico, INA226 ×4, IMUs, LDOs) sits away from the three cell star points; no slots in
   L2 under DShot / I2C / SPI.
7. Plan a per-board current calibration against the INA226 pack channel (0.1 % gain) — the
   shunt tolerance plus copper TCR (3900 ppm/°C) will not give 1 % on its own.

## 4. Power stage placement (per cell, lay out once and copy)

* Switching loop MLCC (C?23/C?24) → high FET drain → phase → low FET → shunt → GND → MLCC
  ≤ 10 nH: MLCCs within 3–5 mm of the half-bridges with the return on L2. 30 A / 50 ns adds
  ≤ 6 V; Vds peak ≈ 19 V against 40 V BVDSS.
* FET tabs (`PQFN-8-EP` pad 5 = **drain**; leads 1–3 source, 4 gate): ≥ 150 mm² of 2 oz
  copper per tab, ≥ 12 × 0.3 mm vias to the L4 mirror pour; via-in-tab is fine, tent the
  bottom. Weapon FETs: 0.59 W each at 15 A → ~27 °C rise; 30 A pulses ≤ 2 s.
* Gate loops HO/LO → 10 Ω → gate < 20 mm with VS / COM return underneath; the 10 k gate-source
  resistors at the FET; C?20–22 (100 nF) directly across VB/VS; D?0–2 + R?32–34 (2.2 Ω)
  within 5 mm of the driver's VCC cap.
* VS traces from the phase copper at the FET, not from the motor pad; low-side source → shunt
  path with no vias (VS negative transient 2.4–4.2 V at 30 A vs the FD6288 −4 V limit).
* BEMF dividers (R?05–R?13) and the 3 × 10 k neutral star at the AT32, taps routed away from
  gate loops. INA180 + R?04/C?07 near PA3.
* FD6288 pad 25 (EP) = COM: solid pad, 4–9 vias. AT32 EP is its **only** ground: solid pad,
  4–9 vias, paste 60–70 % in windows.
* 10 µF 50 V MLCCs are X5R 85 °C — keep them off the FET thermal copper. Hybrid cans ≥ 5 mm
  from FET copper; glue fillet (C-5).
* TH1 (NTC) within 3 mm of Q40–Q45.

## 5. Everything else

* **Pico W**: antenna end flush with a board edge (≤ 1.2 mm past the module), the 42 × 10 mm
  RF keep-out off-board or copper-free on all layers, chassis wall there plastic; USB and
  BOOTSEL facing an access cut (MCU-2). Nothing under the module except tented vias; module
  ground castellations stitched to L2; D3 next to the VSYS castellation.
* **AP63205** per DS Fig. 25: C10–C12 within 2 mm of VIN/GND, GND pad with ≥ 6 vias, L1 and
  C14/C15 within 3 mm, FB (on +5V) as a sense trace from the C14/C15 pads, C13 across BST/SW.
  0.6 W at 0.9 A / 9 V needs the copper the DS assumes.
* **LDOs** U2/U3 184 °C/W — small GND pour at pin 2; +3V3_A on J3 is limited to ~100 mA.
* **I2C** daisy-chain U4 → U5 → U6 → U7 → U8/U9 → J3 with adjacent ground; away from phase
  nodes; ADC RC caps (C20/C21/C24) at the Pico ADC pins with AGND (pin 33).
* **DShot** (R24–R26 at the Pico) over solid L2, ≥ 2 mm from 20–30 A copper.
* **IMUs** U8/U9 near the mechanical centre, away from L1 (inductor); C72 at U9 pin 6, C73 at
  pin 1; C70 at U8 pin 8, C71 at pin 5.
* **Access with armour off**: SW1, J2, J3, J20/J30/J40, TP40 (WEAPON_EN bench enable), the
  Pico BOOTSEL; D4/D5/D6 visible through a window.
* **Bench notes** carried into the bring-up plan: USB alone powers only the Pico (all other
  rails are behind D3) — first-article rail tests use a bench supply on J1; the weapon cell is
  in reset unless ARM link in **and** WEAPON_EN high (3.3 V on TP40); the L/R cells enter
  the AM32 bootloader when the DShot line is held high ≥ 2 s (for am32.ca passthrough).
