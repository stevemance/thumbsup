# Motor board v1 layout: post-mortem and v2 (4-layer) restart guide

Independent review of the routed board `worktree-routing` @ 79dc2e9
(`hardware/motor_board/kicad/motor_board/motor_board.kicad_pcb`), with the numbers queried from the board using
pcbnew. Coordinates follow PLACEMENT.md: origin at the front-left corner, x toward the right (battery end at
x = 0), y toward the rear (drum/front edge at y = 0, drive-motor/rear edge at y = 35).

## 1. What is on the board (measured)

| Item | Value |
|---|---|
| Board | 85.1 x 35.1 mm = 2987 mm2, 6 Cu |
| Courtyards | top 1731 mm2, bottom 806 mm2, total **2537 mm2 = 85 % of the board outline** |
| DESIGN.md 6.13's own area estimate | **3600-4400 mm2** (the board started at 75 x 35 = 2625, then was grown) |
| Vias | 688: GND 269, VBAT 58, +3V3 46, **signals 304 over 105 nets** (0.6/0.3 x193, 0.45/0.25 x254, 0.4/0.2 x241) |
| Track length | B 1283 mm, F 989, L3 953, L4 809, **L5 (the "GND plane") 300 mm** |
| Longest signal nets | DRV_OFF 130 mm (5 vias), SPI_SCK 102, W_EN 92, SPI_MISO 85, W_VA 74, W_NTC 73, W_INLB_M 70, R_nFAULT 68, W_SOC 67 (10 vias) |
| Largest footprints | J4 199 mm2, U1 158, C1 126, J1 93, U2 66, J2/J3 54 each, U6 (TSSOP-14) 40 |

The weapon bridge is the best part of the board: the three U-cells (Q1-Q6 at y 9, shunts at y 15, a 10 uF per
cell, wire holes in front) are a textbook commutation loop (~4 nH estimated). Keep that cell geometry. Almost
everything else follows from a floorplan that was never checked for routability.

## 2. Floorplan: where the blocks ended up

- **Pack path** (front-left, top): JBAT1 (3, 9) / JBAT2 (9, 3), Q7/Q8 at y 9 x 10-18, RS4 (26, 9), then **C1 at
  (24, 18)**, 20-30 mm from the bridge cells it serves. The pack current runs forward, turns back and crosses to
  x 44 on an L3 VBAT pour that takes the whole inner layer over x 21-85, y 4-20.
- **MCU U1 on the bottom at (35.5, 26)**, west of the board centre. Its loads: U3 10-16 mm west, **U2 25-27 mm
  east, U4 38-43 mm east, U10 34-35 mm east**. About 22 MCU nets cross the x 42-57 band eastward and about 12 go
  west. The east nets formed the 11-lane L3 "east bus" (y 27.8-30.8), which then boxed in U2, J3 and U10.
- **U6** (the INL AND-gate interlock between the MCU and U2) sits at (30, 9), front-left. U1 -> U6 -> U2 makes a
  W_INLx loop of 58-70 mm routed, where the direct path is ~25 mm. One badly placed 14-pin part cost six long nets.
- **The left sensor front end** (J2 (33, 32), U9, U11, JP1 and the filters) is on **top, directly over U1's
  fan-out** on the bottom. Two independent blocks stacked on one footprint compete for the same via sites. The
  density map shows 45-65 % occupancy there against 18-39 % in the band beside it. ROUTING_PLAN's own conclusion
  ("the limit is inner-layer via capacity through the core") is right. Its cause is this stacking.
- **J1** (B2B, bottom) at (16.6, 19): 18-22 mm west of the MCU, so SWD/UART/NRST have to cross U3's region.
- **Test pads**: 8 of the 12 (TP2, TP4, TP5, TP7, TP9, TP10, TP11, TP12) are 2 mm top pads inside x 26-46, the
  logic core. Their nets live on the bottom, so each one costs a via plus a stub in the densest area of the board.
- **The bottom under the bridge** (x 45-85, y 0-20) was reserved as a "gate corridor" plus thermal fields. The
  bottom courtyard map shows it is mostly empty, while the core next to it is saturated.

## 3. MCU orientation and pin-to-block facing

Pad positions against destination direction, U1 as placed:

| U1 edge (pins) | Faces | Where its nets actually go |
|---|---|---|
| 1-16 | front | 7 east (W_INHA/B, W_SOA/B, W_nFAULT, R_INHB, R_nFAULT), 2 west, 2 front |
| 17-32 | east | **MB_TX/MB_RX west (to J1), L_S3 west**, W_INLA_M front, R_S3 east |
| 33-48 | rear | 8 east (W_SOC, R_SOA/B, R_INHC, W_INHC, R_nCS, W_EN), **W_INLB/C_M front (opposite)**, 2 west |
| 49-64 | west | **R_S1/R_S2 east, 35 mm (opposite)**, SPI/L_INH/L_nFAULT west (correct) |

Seven nets leave the side opposite their destination. The 11 weapon-control nets leave from **three** sides. The
TIM1 outputs are scattered over PC0/PC1/PA10 (pins 8, 9, 44) and PA7/PB14/PB15 (21, 36, 37), even though the ST
pin database in `ref/` has the whole set on one edge: **TIM1_CH1-3 = PA8/PA9/PA10 (pins 42-44), TIM1_CH1N-3N =
PB13/PB14/PB15 (pins 35-37)**, and TIM8_CH1-3 on PC6/PC7/PC8 (38-40) on the same edge. The pin map was built
from peripherals alone, then frozen, and the placement had to live with it. That is the order backwards.

For v2: place the blocks first, then assign pins with a scoring pass (sum of pin-edge to destination-bearing
mismatch, AF-checked against the XML), then re-place the passives. Constraints that limit swaps: encoder inputs
must be CH1/CH2 of one timer (DESIGN 8, TIM2/TIM3 encoder mode). The CSA inputs need their specific ADCs/COMP.
PA8/PA9 currently carry L_SOA_F/L_SOB_F (ADC5), which would have to move. Every swap goes into DESIGN.md's
firmware contract and CHANGES.md.

## 4. Proposed v2 floorplan (85 x 35, 4 layers)

Principles: the MCU goes **on top**, in the middle of its loads. Every IC and its peers share a side. The bottom
holds only (a) the passives of the IC directly above them and (b) self-contained blocks whose nets do not need
vias through the area above. Power lives in the front 18 mm, logic in the rear 17 mm, and the two meet only at U2
and the drive VM feeds.

```
 y=0  front (drum)
 +--------------------------------------------------------------------------------------+
 |JBAT2  Q7  Q8   RS4    C1 bulk  | JW3 cellC    JW2 cellB    JW1 cellA                  |
 |JBAT1  U13 net  U7(INA) D1      |  Q6 Q5 RS3 C31 Q4 Q3 RS2 C26 Q2 Q1 RS1 C25          |
 |--------------------------------+------------------------------------------ y~18 ------|
 |J4  U8  | R302  U3 caps |  J1(bot) | U1 MCU (top)   | U6 | U2 DRV8323 | buck | U4  JR1|
 |bal BMS |      U3       |          |                |    |            | L1   |     JR2|
 |JL1 JL2 JL3   (rear)    | J2 U9 U11| TP strip  U5   | J3 U10 U12      | R402 |     JR3|
 +--------------------------------------------------------------------------------------+
 y=35 rear (drives)
```

| Block | Parts | Side | Box x / y (mm) | Notes |
|---|---|---|---|---|
| Pack entry | JBAT1 (3, 9), JBAT2 (9, 3), Q7/Q8, U13, C12/C14/C18 | top | 0-22 / 0-14 | v1 geometry is fine. The gate network (R1, D10, C13, R32, D4, R14) goes on the bottom directly under Q7/Q8 |
| Current sense | RS4, **U7 INA239 moved to the top** 2-3 mm behind RS4, R2/R3/C2 | top | 22-31 / 0-10 | IN+/IN- Kelvin <= 3 mm on L1 with no vias. Only SPI/nCS leave |
| Bus bulk | C1 (or its smaller replacement, section 6), D1 | top | 31-44 / 0-13 | Between RS4 and cell C's drain: the pack path becomes one straight L1 pour, and C1 finally sits at the bridge |
| Weapon bridge | Q1-Q6, RS1-RS3, C25/C26/C31, NT1-3, TH1, JW1-3 | top | 44-85 / 0-18 | Keep v1's U-cells unchanged |
| Under the bridge | VBAT/GND via fields, phase dividers R22-R27 beside each JW | bottom | 44-85 / 0-18 | No reserved "gate corridor": gates route on L1 |
| Weapon driver | U2 centred about (61, 23), straps R44-R46, C20-C23 | top | 55-67 / 18-28 | Gate/sense pins face the bridge (front), logic pins face the MCU (west) |
| Interlock + ARM | U6 (shrunk), U14, D9, C15/C16, R18/R19/R41/R47-R49 | bottom under U2's west edge, or top | 50-56 / 18-30 | INL_M in, INL out: both hops <= 8 mm |
| U2 buck | L1, D2, C27-C30, R4/R5/R20/R21, C10 | top | 67-74 / 18-28 | Tight SW loop, output toward U5 along the rear edge |
| **MCU** | U1 **top**, centre about (43.5, 24), pins 33-48 facing east (U2/U4) | top; decaps and ADC RC filters on the bottom directly under their pins | 37-50 / 17.5-30.5 | Every U1 net to U2/U3/U4/U9/U10 needs zero or one via |
| J1 (B2B) | 2x10 1.27 | bottom | 28-35 / 15-29, long axis along y | West of the MCU, pins 5-10 (UART/SWD/NRST) facing it, pins 15-17 (BMS) toward U8. This is an interface change: agree it with the compute board and the Pico W antenna keep-out |
| Left drive | U3 about (20, 28), 100 nF/CP/AVDD on top, 4 x 10 uF + R300/C307 on the bottom under it, R302 | top | 12-28 / 18-35 | JL1-3 on the rear edge at x 4-14 as in v1 |
| BMS | J4 (smaller/vertical) on the left edge, U8 + R6-R11/C4-C9/D5 | J4 top, U8 network bottom | 0-12 / 15-30 | A self-contained block. Its nets go only to J4, J1 (I2C) and BAT |
| Left sensors | J2 on the rear edge, U9, U11, JP1, R54-R56, R110-R113, C110-C112 | top | 26-37 / 29-35 | **Beside** the MCU's rear-west corner, not on top of it |
| Right sensors | J3 on the rear edge, U10, U12, JP2, R57-R59, R114-R117 | top (same side as J2) | 52-64 / 29-35 | Faces the MCU's rear-east corner: R_S1-3 ~10 mm |
| LDO + test strip | U5, C69/C70, D3/R62, rail and signal pads | top | 38-51 / 31-35 | One reachable strip |
| Right drive | U4 about (79, 25), JR1-3 on the right edge (83, 20-30), R402 + bulk under/behind it | top (bulk bottom) | 74-85 / 18-35 | As in v1 |
| Mounting | MH1-4 at the corners (3, 3), (82, 3), (3, 32), (82, 32) | - | 5 mm circles | Unchanged |

Expected lengths with this plan: U1 to U2 logic 12-18 mm, U1 to U3 10-15, U1 to U4 30-35 (unavoidable, 7 nets),
halls 8-12, W_INLx 15-20 in total. DRV_OFF and SPI keep a ~60 mm span, which is inherent (U3 and U4 sit at
opposite ends) and harmless.

## 5. Connector pin orders

- **J1**: 5 GNDs and 3 +5V pins are fine. The problem is the placement, not the order. If the compute board is
  re-spun anyway, group MB_TX/MB_RX/NRST/SWDIO/SWCLK in the rows nearest the MCU and I2C/ALERT/VBAT_SNS_H at the
  end nearest U8. Keep a GND pin between W_ARM_CLK (19) and the UART pins. It is already 7 rows away: fine.
- **J2/J3** (VS, GND, S1, S2, S3, TEMP): the order is sensible. v1 put J2 on top and J3 on the bottom (mirrored),
  so the two front ends are laid out differently and J3's filters landed in a one-part band under the bus. Put
  both on the same side, in the same orientation. Assign LVC3G17 channels by physical order (U9's inputs are on
  pins 1, 3 and 6: pick the channel mapping so S1-S3 do not cross). Channel swaps inside the buffer are free. MCU
  swaps are limited by the encoder CH1/CH2 rule.
- **Wire holes**: phase order JW (C, B, A left to right) and JR are consistent with their drivers. Keep them.

## 6. Parts that are larger than they need to be (flag only, the circuit is unchanged)

| Part | Now | Candidate | Saves |
|---|---|---|---|
| J4 balance | JST-XH 5P side-entry THT, **199 mm2**, 6.1 mm tall | JST-PH 2.0 mm or GH 1.25 mm (pigtail adapter to the pack's XH), or vertical | 100-150 mm2 |
| C1 | 330 uF 35 V hybrid 10 x 10.5, 126 mm2 | 8 x 10 hybrid, or 2 x 6.3 x 7.7 hybrid (check the 2.8 A rms ripple rating: calcs 85) | 30-60 mm2 |
| U6 | SN74LVC08 TSSOP-14, 40 mm2, uses 3 gates | same function in WQFN-14 (2.5 x 3 mm) | ~28 mm2 |
| J2/J3 | SH 6P right-angle, 54 mm2 each | SH vertical (~25 mm2) if the cable exits upward | ~55 mm2 |
| R300/R400 | 22 ohm 1206 on an unused buck | 0603 (no dissipation) | ~15 mm2 |
| 8 x 10 uF 50 V 1206 (C302, C308-10, C402, C408-10) | 1206 | 10 uF 35 V 0805 (4S max 16.8 V; check effective C) | ~40 mm2 |
| C9 1206, R15 0805, R6/R11 0603 | | 0805/0603/0402 where voltage and power allow | small |
| D2 SS34 SMA, L1 5040 | | SOD-123F Schottky, 4030 inductor (check the current) | ~15 mm2 |

These add up to **~300 mm2, or 10 % of the board**. That is the difference between 85 % and ~75 % courtyard fill.
Keep U1 in LQFP-64: the G474 has no 64-pin QFN, and the design uses about 57 pins. R302/R402 stay 2512 (0.1 ohm,
up to ~1 W in bursts), and RS1-RS4 are sized correctly. The bigger lever that already exists (DESIGN 6.13) is
moving U8/J4/the cell network to the compute board, which frees ~250 mm2.

## 7. Two-sided placement here

Two sides are unavoidable (2537 mm2 of courtyard on 2987 mm2, and J1 must be on the bottom). The pros: decaps
and filters directly under their IC, and J1 mates downward. The cons as they played out: a bottom MCU with top
peers made every MCU net pay one or two vias. Stacking unrelated blocks (J2 front end over U1, TPs over U1)
doubled via demand in the same 13 x 13 mm. The bottom faces the compute board, so no test access there, and a
second stencil. The v2 rule: **stack only an IC with its own passives, or a block that is self-contained.** Never
put an IC's fan-out under another block's fan-out.

## 8. Stack-up and via strategy (4 layers)

- L1: parts, power pours (pack path, bridge, VM), gate pairs, short hookups. **L2: solid GND, no traces, ever.**
  L3: VBAT pour **only** over the front power region (y < 18); in the rear it holds signal channels plus +3V3/+5V
  as wide traces or small pours. L4: bottom parts, north-south signals, GND fill stitched to L2.
- Use JLC's thin-prepreg 4-layer stack (about 0.1 mm L1-L2) for the commutation loop. v1's own estimate was
  ~4 nH even on 7628 (0.21 mm), inside the 6 nH limit.
- Signal budget: **no more than 1 via per connection end, ~1.1 per connection overall** (v1: 2.2). With the MCU on
  top that means roughly 120-150 signal vias against 304.
- Every GND pad gets its own via within 0.5 mm. VBAT/GND via fields go at the drain tabs and shunt pads
  (0.3 mm drill, 1 mm pitch). Thermal arrays under U2/U3/U4 are placed at placement time and counted in the
  channel plan.
- **Plan the fan-out grid before routing**: U1 escapes outward to a via row 1.5-2 mm outside the pads on the
  sides that need a layer change, not inside the body. Inside-body fan-out sealed U1's footprint on L3 in v1.
- Pre-draw the channels (MCU-U2 east channel x 50-55, ~20 nets, fits on L1 + L4 at 0.35 mm pitch; MCU-U3/J1
  west channel ~15 nets) and keep via fields out of them.

## 9. Which nets must be short, which can be long

**Short (mm, not negotiable):** commutation loops. Gate/return pairs GHx/SHx and GLx/SPx, as pairs, target
<= 20 mm (v1: 10-28). Kelvin SNx/SPx from the shunt pad edges. U7 IN+/IN- (<= 3 mm). Buck SW (C27-VIN-SW-D2).
U2/U3/U4 charge-pump and CP caps, DVDD/AVDD, VREF+, VDD decaps. NRST cap. The 330 ohm/22 pF CSA filters at the
MCU pin. BMS cell filters at U8. U2 straps and the GAIN pad.

**Moderate (<= 30-40 mm, over solid L2, away from analog):** PWM (INH/INL), W_SOx/L_SOx/R_SOx before their
filters, W_ARM_CLK away from MB_TX.

**Can be long (slow, filtered or open-drain):** DRV_OFF, nFAULTs, W_EN, SPI (~1-5 MHz) and the nCS lines,
UART, BMS I2C/ALERT, VBAT_SNS/VBAT_SNS_H (DC), NTC/MTEMP (filtered), halls after the Schmitt buffers, the LED,
the sensor-supply enables. Route these last, in the channels left over.

## 10. Test points

Put SWD/NRST/UART on J1 (already there) plus one Tag-Connect TC2030-NL (or a 1.27 mm 5-pad row) at the MCU's
edge for bring-up without the compute board. Rails (VBAT, 5V, 3V3, 2 x GND) and debug signals (DRV_OFF, W_EN,
W_nFAULT, W_ARM) go in **one top strip at the rear edge, x 38-51, y 31-35**, placed inline on each net's
existing route (no stubs, no extra vias). Nothing in the MCU core. 1.0 mm pads are enough for probes.

## 11. Root causes, ranked

1. **The board was ~20-30 % smaller than its own design estimate.** DESIGN 6.13 said 3600-4400 mm2; placement
   started at 2625 and ended at 2987 with 85 % courtyard fill. PLACEMENT 5.3 then accepted relaxations (bulk caps
   up to 19 mm from their pins, sensor front ends 8-12 mm) that pushed the problem into routing. Area is yours to
   set, but a 4-layer v2 at 85 x 35 needs the section 6 shrinks and section 7's stacking rule to reach ~75 % fill.
   If it will not close, add ~5 mm of length or move the BMS off the board. Decide that before placement, not
   after routing.
2. **The MCU pin map was fixed before placement and never revisited.** Seven nets exit the wrong side, the weapon
   group leaves from three sides, and TIM1 is split, although one edge (pins 35-44) carries all six TIM1 outputs.
3. **MCU on the bottom, with an unrelated block stacked on top of it.** Every MCU net paid vias, and the J2/U9/U11
   front end fought U1's fan-out for the same sites. This was the stuck cluster through 47 rounds.
4. **MCU off-centre relative to its loads, and U6 on the wrong side.** 22 east-bound nets formed a bus wall that
   enclosed U2. U6 at (30, 9) turned 3 short links into six 58-70 mm nets.
5. **Inner layers given to power by region-wide reservation.** L3 was a VBAT pour over the whole front half, and
   the bottom under the bridge was a keep-out. The logic got the rear 15 mm on 2-3 usable layers. Going to 6
   layers added capacity but put 300 mm of signal on L5 "GND", which is worse for the loops than 4 good layers.
6. **Process: no routability gate between placement and routing.** Placement was scored per part (pin distances,
   loop area) with two review rounds, but never with a ratsnest crossing and channel-capacity check. Routing was
   power-first hand reservations plus a greedy router, then a 47-round freeze-and-edit tail. A straight-cut board
   grow split the bridge, and block moves were tried after the fact. When a trial route finds "no path exists" for
   a whole group, go back to the floorplan. Do not add layers.
7. **Test pads and oversized parts in the scarce area**: 8 TPs in the core, J4/C1/U6/J2/J3 taking ~470 mm2 of
   which ~300 are recoverable.

### Restart order for v2
1. Freeze board size and part shrinks. 2. Block floorplan (section 4) with a ratsnest check: crossings, and nets
per channel against channel capacity. 3. MCU pin assignment against that floorplan (score, AF-check, firmware
contract). 4. Place the power cells and the IC fan-out/via grids, and reserve the channels. 5. Route the critical
short nets, then the channels, then the long slow nets. 6. Stop and re-floorplan if any block cannot reach its
neighbours with at most 1 via per end.
