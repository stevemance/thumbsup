# Weapon bridge gate/Kelvin routing (v2): rule areas and exceptions

Decision: option 3 of review/v2_layout/gate_corridor.md (adopted 2026-09-30).  Copper:
kicad/gen/v2_bridge.py, applied with tail.py (experiment v2_bridge) to the board placed by place.py.
Coordinates are board-local mm, top view, y toward the rear.

The pour/DRC step must reproduce the rule areas below.

## 1. L3 VBAT / GND boundary

- **Rule area "L3 VBAT band (cells)":** the L3 (In2.Cu) VBAT pour ends at **y = 16.0 for x ≥ 44.5**.
  - This clears the cap VBAT vias (pads end at y 14.6).
  - Behind y 16.0 the L3 pour is GND. This puts the shunt and cap GND pads over L3 GND.
- **Rule area "L3 VBAT band (drives)"** (added for the drive-IC fan-out, kicad/gen/v2_drive.py; decided
  2026-09-30): the L3 VBAT pour also ends at **y = 16.0 for x 14-27**, in front of U4.
  - The band there only has to feed R302.1 / R402.1 (VBAT pads end at y 15.6).
  - Behind y 16.0 the L3 pour is GND, and L3/L4 tracks and vias may use y ≥ 16.3.
  - This carries U4's SPI/CSA/VREF/buck fan-out (L4: R_SOA along y 16.75 and U3's L_SWBK hop; L3: the SPI link to
    U3 at y 17.35 / 17.85 / 18.35 and R_FBBK at y 16.45).
- **Elsewhere** the band stays at y < 18.5, as in memo 3.1.
- **L4 (B.Cu) under the L3 VBAT band is solid GND**, with no tracks (margin 0.3 mm, so y < 16.3 in the cells).
  - This does not apply to the two lane exceptions (§2).
  - Everything else on L4 from this work (Kelvin C/B, the SN_A hop, the C pair's run to U2) is at y ≥ 16.75, over
    L3 GND.

## 2. Exceptions: L4 gate-pair lanes under the L3 VBAT band

Only these areas may carry tracks on L4 under L3 VBAT. Each is the lane's two 0.25 mm tracks plus the pour clearance,
so about 1.2 mm of L4 GND is cut.

| Rule area | L4 extent (x; y) | Contents |
|---|---|---|
| **lane C (y-lane)** | x 50.6-51.9, y 6.0-12.9, then the 45-degree jog to x 52.1-53.1, y 13.0-16.3 | W_GHC + W_C from the mouth vias (51.6, 7.55/6.45), under the RS3 \| C31 gap |
| **lane B (x-lane)** | x 57.7-65.1, y 6.1-7.9 | W_GHB + W_B from the mouth vias (64.7, 7.55/6.45) to the C\|B channel vias (58.05, 7.55/6.45). Parallel to the feed current |
| **lane A (y-lane)** | x 76.2-77.5, y 6.0-12.9, jog to x 77.7-78.7, y 13.0-16.3 | W_GHA + W_A from (77.2, 7.55/6.45), under the RS1 \| C25 gap |

**Boundary crossing.** Lanes C and A cross the y = 16.0 VBAT/GND boundary on L4 as a balanced pair.
- Lane C crosses at x 52.35/52.8. C31's pads start 0.25 mm to the right.
- Lane A crosses at x 77.95/78.4. C25's pads start 0.25 mm to the right.
- The cell's 10 µF VBAT-GND cap, 0.25-0.7 mm away, is the stitching capacitor for this crossing.
- DRC should waive "L4 track crosses an L3 net boundary" for exactly these two crossings.

## 3. Keep-outs for the via fields and pours (P3/P6)

The stitching and pour steps must leave these clear.

**L4 must stay clear of the lanes and the Kelvin runs:**
- RS3 GND-pad vias at x ≤ 51.85.
- C31 GND/VBAT-pad vias at x ≥ 53.4.
- RS1 GND-pad vias at x ≤ 77.45.
- C25 vias at x ≥ 78.9.
- RS2 GND-pad vias at y ≤ 16.3. SN_B runs at y 16.85 and SL_B at 17.55 under its rear edge.
- C26 GND-pad vias at x ≥ 66.7. SN_B descends at x 66.25.
- No GND stitching on L4 inside x 45.8-67.0, y 16.75-20.0, except where it clears the Kelvin/pair tracks by 0.2 mm.

**HS drain-tab VBAT vias:** stay on the tab (Q5 x ≥ 52.7, Q3 x ≥ 65.8, Q1 x ≥ 78.3). They are clear of the mouth
vias.

**L1 pours:**
- The phase pours W_A/W_B/W_C and the source pours W_SLx fill around the gate stubs, the GL strip (y 12.9) and the
  mouth vias at the zone clearance.
- The SLx pour joins Q-pins 1-3 to the SL pad directly.
- **Pin 3 connects along the pin row. No SLx copper in the strip x > 48.3 (C) / 61.4 (B) / 73.8 (A) at y 12.45-13.35.**

**L2:** the gate via pairs are 1.1 mm apart. With 0.7 mm antipads, the web is 0.4 mm. Do not add vias between them.

**Anchored parts:** kicad/v2/spec.py KEEPOUT "bridge: …" entries (top: the L1 gate paths; bottom: the L4 Kelvin/pair
run to U2).

## 4. Via-in-pad (POFV, filled and capped) for FAB.md

JLC's POFV needs a 0.2-0.5 mm drill. All vias below are 0.2 mm drill.

| Where | Net | Via (pad / drill) | Position |
|---|---|---|---|
| U2 pin 13 | W_SNB | 0.40 / 0.20 | (66.25, 20.30), outer end of the pad |
| U2 pin 14 | W_SLB | 0.40 / 0.20 | (65.75, 20.80), inner |
| U2 pin 18 | W_GHC | 0.40 / 0.20 | (63.75, 20.80), inner (not in the original list: phase C's gate pair ends on L4) |
| U2 pin 19 | W_C (SHC) | 0.40 / 0.20 | (63.25, 20.30), outer (not in the original list) |
| U2 pin 21 | W_SLC | 0.40 / 0.20 | (62.25, 20.80), inner |
| U2 pin 22 | W_SNC | 0.40 / 0.20 | (61.75, 20.30), outer |
| U2 pin 23 | W_SOC | 0.40 / 0.20 | (61.25, 20.80), inner (via only; its L4 exit is not routed) |
| U2 pin 24 | W_SOB | 0.40 / 0.20 | (60.75, 20.30), outer (via only) |
| RS2 pad 1 | W_SLB | 0.40 / 0.20 | (60.85, 16.95), SL pad inner-rear corner |
| NT1 pad 1 | W_SNA | 0.45 / 0.20 | (74.50, 16.85) |
| NT2 pad 1 | W_SNB | 0.45 / 0.20 | (62.00, 16.85) |
| NT3 pad 1 | W_SNC | 0.45 / 0.20 | (48.90, 16.85) |

**Clearances at U2** (pads 0.25 × 0.875 mm, pitch 0.5 mm):
- The vias are staggered 0.5 mm along the pad (outer y 20.30, inner y 20.80).
- Copper to the neighbouring pad: 0.175 mm.
- Copper to the neighbouring in-pad via: 0.307 mm.
- Copper to the thermal pad: 0.425 mm.
- Mask web between pad openings is unchanged: 0.25 mm in KiCad, ~0.15 mm after JLC's 0.05 mm expansion.
- On L4 the tracks pass the neighbouring via at 0.2 mm.

## 5. Via list (all through L1-L4)

Gate-pair vias are 0.6 / 0.3 mm:

| Via | Net |
|---|---|
| (51.60, 7.55) | W_GHC |
| (51.60, 6.45) | W_C |
| (64.70, 7.55) | W_GHB |
| (64.70, 6.45) | W_B |
| (58.05, 7.55) | W_GHB |
| (58.05, 6.45) | W_B |
| (77.20, 7.55) | W_GHA |
| (77.20, 6.45) | W_A |
| (78.85, 18.55) | W_GHA |
| (77.65, 17.95) | W_A |

Kelvin vias are 0.45 / 0.2 mm:

| Via | Net |
|---|---|
| (47.50, 18.30) | W_SLC |
| (72.40, 18.00) | W_SNA |

Plus the 12 POFV vias in §4. That is **24 vias** in total.

## 6. Net summary

| Net | Route | Vias |
|---|---|---|
| W_GLC, W_GLB, W_GLA | L1 only | 0 |
| W_GHA / W_A (SH) | L1 → lane A (L4) → L1 → U2 pins 8/9 | 2 each |
| W_GHB / W_B (SH) | L1 → lane B (L4) → L1 through the C\|B channel → U2 pins 17/16 | 2 each |
| W_GHC / W_C (SH) | L1 → lane C (L4) → L4 → U2 pins 18/19 | 1 + POFV each |
| W_SLC, W_SNC | L1 tap → L4 → U2 pins 21/22 | via + POFV |
| W_SLB, W_SNB | POFV at the tap → L4 → U2 pins 14/13 | 2 POFV each |
| W_SLA | L1 only → U2 pin 11 | 0 |
| W_SNA | NT1 POFV → L4 hop → via → L1 → U2 pin 12 | 2 |

The SH taps are a 0.25 mm L1 stub from each mouth via, in front of the HS gate pin, to HS source pin 3. This is the
HS-source / LS-drain junction (SLVA951 §6.3).
