# Motor board v2 layout: design lessons from attempt 1

Attempt 1 went from 4 to 6 layers (8e562e3) and grew the board from 75 to 85 x 35 mm (0d00345). It stopped at
**13 unconnected, 0 DRC errors** (3d6b776; `kicad-cli` agrees and reports warnings only):

- left sensor front end: L_VS x2, L_S3, L_MTEMP;
- right sensors: R_H2, R_H3, R_H3B;
- +5V at JP2 and at R20;
- SPI_MOSI at U7, SWDIO at TP2, R_SOC at R82;
- one F GND island.

Coordinates are the current board: origin at the front-left, y toward the rear. "North" in the logs means toward
the front.

## A. Root cause

### 1. The limit was via room on the inner layers around U1, not area
**Evidence.** Adding area barely helped:

| Change | Open connections |
|---|---|
| Board grown 75 to 85 mm | 60 → 59 |
| U1 block moved 5 mm into the free band (353675b) | 13 → 26 |
| Left front end moved into the band (04462b6) | 48 |

The density map (cb9e115) explains why. Copper occupancy on F / L3 / L4 / L5 / B:
- the core: 42 / 49 / 46 / 38 / 52 %;
- the band: 43 / 38 / 27 / 7 / 24 %.

The band only looked empty. It was a corridor on the inner layers: the east bus on L3 and the W_* bundle on L4 left
no via spot there. On 4 layers the diagnosis was the same (2026-09-25): "U1's field is sealed on L3", and U2's region
was enclosed with no path for its rear group, R_S1/R_S2, L_S3 or W_INLx_M.

**Rule.** Every via field is a wall on all layers:
- U1's fan-out under its body;
- the U2/U3/U4 thermal arrays;
- the bridge VBAT/GND fields;
- bus via columns.

No net may need to cross U1's footprint, or another IC's via field, to reach its partner. Check ratsnest crossings
at placement.

## B. Clusters that caused trouble

### 2. The left sensor front end sat on top of U1
**Evidence.**
- U1 is on the bottom at (35.55, 26.05), with pins at x 29.9-41.2 and y 20.4-31.7.
- J2 is on the top at the rear edge (x 30.9-35.9). U9 at (31.6, 27.45) sits over U1's west half.
- U11, JP1, R54-R56, R110-R112 and C110-C112 all lie inside U1's outline.
- J2 went on top only because the bottom there held U3's thermal field and J1 (PLACEMENT 5.1).

What it cost:
- L_H1 needed pad-edge vias in J2.3 and R54.1, two lifted runs and an L5 jumper (2f5c431).
- L_VSRC needed a via in U11.5's pad and an L5 jumper.
- The GND pads of C111 and C45 were stranded on fenced islands.
- Four nets were still open at the end.
- A region rip-up with 12 random routing orders ended at 24-27 open.

**Rule.** Build each sensor channel as one block beside its connector, about 12 x 14 mm. The block holds:
- the pull-ups, 1 k series resistors and DNP caps;
- the LVC3G17 buffer;
- the TPS22945 supply switch and its decoupling;
- the jumper;
- the NTC R, C and clamp.

It never sits over another IC. Its outputs leave from the side facing the U1 pins that receive them.

### 3. The right sensors: pin order reverses along the chain
**Evidence.**
- J3 is on the bottom, rotated 180°. From west to east its pins read TEMP, H3, H2, H1, GND, VS.
- U10 sits east of J3.
- The SN74LVC3G17 has **inputs on pins 1/3/6 and outputs on 7/5/2**, so channel 3 crosses the package.
- The filter row R114-R116 sat in a one-part band under the L3 bus.
- The pull-ups R58/R59 were 7-9 mm from J3.
- U10 sat on the bus's turn: U10.6 (H3B) and U10.7 (R_S1) shared one escape gap.

Every trial traded one net for another: R_H2 against R_H1, R_H3B against R_S1. Moving R117 beside J3 fixed R_TEMPJ
but cost R_H3B.

The pull-ups cannot move to the buffer side of the 1 k. The buffer's VT- is 0.84 V, and the divider plus the Hall VOL
lands at 0.74-0.91 V (decision 2026-09-27).

**Rule.** Make each channel a monotonic chain: connector pin → pull-up → 1 k → buffer input → buffer output → MCU pin.
- Derive the order after mirroring for the connector's side.
- Use the free choices. Which channel goes to which buffer gate is a schematic choice. Encoder A and B can take TIMx
  CH1 and CH2 in either order (a sign constant, as in rev L1).
- Put the pull-ups in a row at the connector pads, with a +3V3 bar behind them.
- If channels still cross, use single-gate or flow-through buffers.
- No bus under a connector pin row.

### 4. The JP1/JP2 supply jumpers need two rails
**Evidence.** Each jumper ties together +3V3, +5V and L_VSRC.
- JP2 (bottom, at (47.2, 23.4)) sat in the W_* bundle, with the L3 bus to its south. Its +5V is still open.
- Moving JP2 to the top closed +5V but stranded its other two pads.
- JP1's +5V connection forced the W_VA hop onto L5 (0d0b06b).

**Rule.** Put the jumper where both rails already run, at the block's supply corner. The alternative is to remove the
5 V option: DESIGN says the MT6701 runs from +3V3, and 5 V exists only for Hall ICs. That is the user's decision.

### 5. U2's logic side was enclosed; the W_INL nets looped through the north-west
**Evidence.**
- The interlock U6 is on the bottom at (30.55, 8.55), under RS4's VBAT pad and its stitching vias. Its escapes had to
  go between its own pin rows (route_blocks 12a2).
- It sits in series between U1's W_INLx_M pins and U2's rear pins, so every INL net loops U1 → north-west → U2,
  27-45 mm each.
- L4 alone carries W_INLB 61 mm, W_INLC 51, W_INLA 36, W_INLB_M 39, W_INLC_M 23 and W_INHA/B/C ~30 each.
- On 4 layers U2's rear was enclosed: the bus to the south, the bus's north group to the west, U4's via columns to
  the east, the VBAT feed to the north.
- U2's west pins 28/33 had no fan-out spot.
- R_SOC "crosses the INL lanes whatever it does" (route_blocks 12d).

**Rule.**
- Put U6 and U14 on the line between U1's TIM1 pins and U2's INL/INH pins, near U2.
- No logic IC goes under a power pad or a via field.
- Keep a corridor open from U2's logic edge to U1, and let no other bus cross it.
- Run the six W_INH/INL lines as one ordered bundle on one layer.

### 6. The east bus walled off the rear half
**Evidence.**
- The bus is twelve 0.15 mm L3 lanes at 0.3 mm pitch behind U2 (y 27.8-31.1).
- Its north group climbs U1's east side (x 42.1-43.4), which sealed U1's east pins. Its south group wraps round U1's
  rear.
- Everything placed later under it lost its via spots: U10, U12, R20, JP2, J3's filters and every part tried in the
  band. U12 had to move 1.6 mm to get one GND via (fb389ec).
- On L3: SPI_SCK 74 mm, DRV_OFF 70, MISO 67, R_nFAULT 65, MOSI 62, R_INHx 49-56, R_nCS 47.

**Rule.**
- U4's lines land on the U1 side that faces U4, without wrapping round U1 or crossing the U1-U2 corridor.
- Reserve the bus strips on the floorplan after placement.
- Never place a part that needs a via inside a bus strip.

### 7. +5V has one source, at U2, and loads everywhere
**Evidence.** The buck is inside the DRV8323RH, with L1/C29/C30 beside U2. The loads are spread out:

| Load | What happened |
|---|---|
| J1 +5V pins 1/2/13 (≤ 0.45 A) | only reachable by a 36 mm L5 trunk |
| R20 (FB top) | +5V end sits over the bus, 12 mm from any +5V copper; still open |
| R62 | was 35 mm from D3 |
| U5, JP1, JP2 | further branches |

**Rule.** Draw +5V as a named trunk on the floorplan: C29 → J1, with branches to U5 and the jumpers. Close R20 to C29
as part of the buck block, before any bus goes in.

### 8. Test pads over U1's fan-out field
**Evidence.**
- TP2-TP6 and TP12 were placed "above the MCU" on the top.
- SWDIO to TP2 is still open.
- TP12's GND needed a lifted run (4db1bf7). TP8 and TP12 were moved twice.

**Rule.** Put each test pad on or beside a via its net already has, at the rim of the logic block. Put GND pads on
stitching vias. Test pads stay on the top and reachable with the compute board mounted (DESIGN 6.9).

### 9. Two-pin parts anchored to one end
**Evidence.** `place_v2.py` scored each passive by its distance to one pad only. The results:

| Part | Far end |
|---|---|
| C410 | 20 mm from U4 |
| C409 | 12.8 mm from U4 |
| R23/R25 | about 15 mm from their nets |
| R40, R43, C68, R50 | 9.6-12 mm |
| D8 | in the far north-west |
| R62 | 22 mm from D3 at 75 mm |

Tail rounds 08, 23, 36, 37, 40 and 43 only moved such parts back. C410 ended up on a 0.15 mm L3/L5 link (17e916e).

**Rule.** Place every 2-pin part against both ends; series parts go on the line between them. Flag anything more than
5 mm from either partner. Reserve room for the drive VM bulk caps (4 x 10 µF each) first.

### 10. GND pads that depended on the outer fills
**Evidence.**
- About 63 GND pads reached a plane only through the F/B fill; round 05 gave each its own via.
- Eight had no legal via spot within 1.5 mm.
- Rounds 34, 35, 41, 42 and 47 only turned or flipped a cap to free a GND pad.

**Rule.** Every GND pad gets a reserved via at placement. Point GND pads at open space, away from lanes.

## C. MCU pin assignment

### 11. U1's pin sides did not face their loads
**Evidence.** U1 is on the bottom, rotated -90°. Pins 1-16 face the front (bridge, U6, U7), 17-32 face east (U2, U4),
33-48 face the rear edge, 49-64 face west (U3, J1). Mismatches in the rev L1 map:

| Nets | U1 side | Load |
|---|---|---|
| MB_TX/RX (22/23) | east | J1, west |
| R_S1/R_S2 (51/56) | west | U10, east |
| L_S3 (24) | east | U9, west |
| R_INHB/A/C (10/26/40) | three sides | U4 |
| W_INHA/B (8/9), W_INLA_M (21), W_INLB/C_M (36/37), W_INHC (44), W_EN (46) | front, east, rear | U2 / U6 |
| W_SOA/B (12/13) vs W_SOC (33); L_SOC_F (11) vs L_SOA/B_F (42/43) | split across sides | U2; U3 |

MB_TX/RX, L_S3 and R_S1/R_S2 were exactly the nets that had to cross U1's field on 4 layers.

What was tried:
- **Rev L1** (68f28dd): L_S1/L_S2 → PB5/PB4, R_nCS → PA11, INA_nCS → PB8-BOOT0 (R61 removed, set by option bytes).
  **PC6 was left unused**: it had no reachable via.
- **W-group rotation**: no net gain.
- **Rev L2**: AF-checked but never applied (L_S1 → PC7, L_S2 → PC6, L_MTEMP → PB15, W_INLC_M → PF0, L_INHB → PB8,
  INA_nCS → PB5).

The fixed pins are:
- TIM1 CH1-3/CH1N-3N and BKIN = PC13;
- TIM8 CH1-3 and BKIN = PB7;
- TIM20 CH1-3;
- weapon CSA on PA0/PA1/PB11 (COMP3/1/6, with the ADC1/2 pairing);
- ADC5 PA8/PA9 and PC3 → OPAMP5; ADC3/4 on PB1/PB12/PB13;
- TIM2/TIM3 CH1-3 for the encoders;
- SPI3 on PC10-12, USART1, SWD on PA13/14.

**Rule.**
1. Fix U1's position, side and rotation first.
2. Assign each peripheral to the side that faces its partner:
   - TIM1 and the weapon CSA toward U2/U6;
   - TIM8 and ADC5 toward U3;
   - TIM20, ADC3/4 and SPI3 toward U4;
   - USART1, SWD, NRST and W_ARM_S toward J1.
3. Check the choices with motor_board.py against the ST pin database before freezing the netlist.

### 12. U1 on the bottom mirrors pin order against the top-side ICs
**Evidence.**
- The U3 → U1 trio (L_INHA, L_nFAULT, L_SOC) has "source and pin order reversed, needs a layer hop".
- U1's west pins run opposite to the bus's south group, which cost nCS a hop under J2 (route_blocks 8b).
- U2's front row runs opposite to the cells' gate vias.

**Rule.** Check that every IC-to-IC bus is monotonic as seen from one side of the board. Put U1 on the same side as
U2/U3/U4, or assign its pins with the mirror applied.

## D. What worked and must be kept

### 13. The weapon bridge macro
Three identical U-cells, C, B, A from left to right:
- The low side and high side sit side by side, the phase strip runs along their front edges, and the JW hole is in
  front of the strip.
- The shunt sits right behind the low-side source. The 10 µF stands behind the high-side drain, with its GND pad
  0.75 mm from the shunt's. The loop is about 4 nH, under the 6 nH limit.
- The Kelvin net ties NT1-NT3 sit at the shunt's inner edge.
- Each gate via sits at its gate pin, and the gates run in the bottom gate corridor. The SH vias sit at the quiet end
  of the source row.
- The divider top resistors sit beside the JW holes.
- U2 is rotated 180°, with the B/C pins facing the bridge.

Block 1 routed all 15 gate and Kelvin nets with DRC 0 (ecebe1d). The board growth split cell C off by 10 mm, and it
had to be restored from its pre-grow copper (0fc8429).

**Rule.** The bridge, U2 with its straps, the buck loop and the gate corridor form one rigid macro. Reuse its geometry
(route_blocks blocks 1-2, `frozen/pregrow_cellc.json`) and never cut through it.

### 14. The pack path and the VBAT feed
What worked:
- The pack path runs JBAT1 → Q7 → Q8 → RS4 → C1 on L1 pours. The return offset at the MCU was 1-4 mV (review).
- U7 sits under RS4 for Kelvin taps from the pad edges.
- R302 and R402 have their own branches from C1.

What didn't:
- The L3 VBAT feed and the top VBAT pours blocked every north-west via (4da3bcd). The feed was trimmed where no pack
  current flows (d384ad4).
- R402's feed (~36 mm) wraps U1: it now runs 25.8 mm on B, 12.5 mm on L5 and 7 mm on L3.

**Rule.** The inner VBAT pour covers the pack path only. No logic goes under VBAT via fields. R402's feed gets a
planned lane.

### 15. Keep-outs and corridors that paid off
- **The bottom gate and sense corridor** behind the bridge (PLACEMENT 4).
- **The thermal fields** of U2/U3/U4 plus 1 mm. L3 lanes are allowed only in the gaps of the U3/U4 arrays.
- **Solder zones and washer zones.**
- **The L3 front strip** (y 4.9-5.8) for W_VA/W_VB/W_NTC across the gate bundles. Even so, they later needed
  19-38 mm of L5 each to reach U1 pins 18-20. Their filter caps sat 3.8-6.6 mm from the pins, and R23/R25 were far to
  the west.
- **The motor outputs:** 0.8 mm top lanes, with pin order matching the connector order (block 6b).

## E. Going from 6 to 4 layers

### 16. What lives on the inner layers now

| Layer | Track | What it carries |
|---|---|---|
| L3 | 953 mm, 41 nets | the east bus, plus W_SOC 41, W_EN 32, L_INHC 26, and the VBAT feed pour |
| L4 | 809 mm, 41 nets | the U2 rear bus (W_INLx 36-61 mm, W_INHx ~30); the hub nets R_S1-3, MB_TX/RX, VBAT_SNS, SWCLK, W_INLB/C_M, R_MTEMP, W_EN, INA_nCS, W_NTC; the +3V3 fill |
| L5 (GND plane) | 300 mm of jumpers, 21 nets | W_VA 38, +5V 36, +3V3 34, W_INLA_M 29, W_NTC 29, W_VB 19, SWDIO 18, SPI_SCK 14, R_VM 12.5, NRST 12, MB_TX 11, R_TEMPJ 10, and others |

With a single inner signal layer, about 1100 mm of L4 + L5 routing has to disappear, not move. What removes it:
- U6/U14 beside U2 (item 5): about 250 mm;
- pin sides (item 11): MB, R_S, L_S3 and the W_INH wraps;
- the +5V trunk (item 7) on L3 or as a top pour.

Other consequences:
- **+3V3 has no fill layer.** Route it as a planned tree from U5. The L4 fill fragmented with every run (e124e8a).
- **Analog references.** On 4 layers, B references L3. Keep the CSA, divider and NTC lines on F over L2, and short.
- **Via-in-pad.** It was used for the thermal vias, RS2 and 7 signal pads, and FAB.md records it as free only on
  6-layer boards. Check the 4-layer price, and plan so no signal pad needs it.
- **Stack-up.** On the old 4-layer stack (JLC04161H-7628, L1-L2 0.21 mm) the loop was about 4 nH. Pick a thin L1-L2
  prepreg with 1 oz inner copper, and redo the clearance and via rules for JLC's 4-layer limits.

## F. Placement checklist for v2

1. Place in this order: the power macro, then U1 with its pin sides decided, then everything else. Co-design the pin
   plan with the placement.
2. No net crosses U1 or any via field. Count ratsnest crossings.
3. Each sensor block sits beside its connector, off every IC. Its chain is monotonic after mirroring, the pull-ups sit
   at the connector, and the outputs face U1.
4. U6/U14 go between U1 and U2, and U2's logic edge stays open.
5. U4's bus lands on U1's U4 side. Bus strips hold no parts that need vias.
6. +5V and +3V3 are planned trunks. R20 closes at C29.
7. Put the J1 functions (SWD, NRST, USART, W_ARM_S) on U1's J1 side. U14/C15/D9 go at pin 19, U8 at pins 15-17.
8. Place 2-pin parts by both ends. Reserve the bulk caps first.
9. Every GND pad has a reserved via. Test pads go on existing vias at block rims.
10. The inner VBAT pour covers the pack path only.
