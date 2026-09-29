# Adversarial review: the v2 floorplan (critique §4) at 85 x 35 mm, 4 layers

Inputs:
- Courtyards, pads and nets of every footprint in `kicad/motor_board/motor_board.kicad_pcb`, queried with pcbnew
  (236 footprints; top 1733 mm², bottom 806 mm²).
- `design/netlist.csv`.
- `ref/STM32G474RxTx_pins.xml`.
- DESIGN.md §3.4 (ADC plan) and §6.13 (side rules).

Method:
- Every part was assigned to a block of the critique §4 table. Parts the table leaves out went to their obvious
  owner: the MTEMP R/C/clamp to the sensor block, the MCU pull-ups and filters to the MCU bottom, and so on.
- Crossings were counted on the MST of each net's pins, with the blocks at the §4 coordinates. U1 sits at
  (43.5, 24), rotation 0, with pins 33-48 facing east.
- Capacity is counted in raw lanes at 0.3 mm pitch on L1 + L4. L3 adds nothing where L4 is used (memo rule), and
  L2 carries nothing.

**Verdict: the floorplan is not feasible as drawn.**
- Five blocks hold more courtyard than their box.
- The top side of the rear band is 76 % courtyard, and 85 % once DESIGN §6.13 is obeyed.
- The U1→U4 bus has no corridor past the U2/buck column on 4 layers. This is v1's east-bus wall again.
- The single-edge pin plan conflicts with the documented ADC plan.

All of it can be fixed. The fixes are in §5.

## 1. Area per block (courtyard sum / box area)

| Block | Box (x / y) | Side | Box mm² | Courtyard mm² | Fill |
|---|---|---|---|---|---|
| Pack entry | 0-22 / 0-14 | T | 308 | 183 | 59 % |
| Current sense (U7 on top) | 22-31 / 0-10 | T | 90 | 69 | 76 % |
| Bus bulk C1 + D1 | 31-44 / 0-13 | T | 169 | 159 | **94 %** |
| Weapon bridge | 44-85 / 0-18 | T | 738 | 497 | 67 % (v1 geometry, proven) |
| U2 + straps | 55-67 / 18-28 | T | 120 | 87 | 72 % |
| Interlock + ARM (TSSOP U6) | 50-56 / 18-30 | B | 72 | 77 | **107 %** |
| U2 buck | 67-74 / 18-28 | T | 70 | 90 | **129 %** |
| MCU | 37-50 / 17.5-30.5 | T | 169 | 158 | 94 % (box < the 13.5 mm courtyard) |
| MCU passives | same | B | 169 | 71 | 42 % |
| J1 | 28-35 / 15-29 | B | 98 | 93 | 95 % (one part, fine) |
| Left drive | 12-28 / 18-35 | T / B | 272 | 101 / 59 | 37 / 22 % |
| BMS (J4 as is) | 0-12 / 15-30 | T | 180 | 199 | **110 %** |
| Left sensors | 26-37 / 29-35 | T | 66 | 122 | **185 %** |
| Right sensors | 52-64 / 29-35 | T | 72 | 122 | **169 %** |
| LDO + test strip | 38-51 / 31-35 | T | 52 | 59 | **113 %** |
| Right drive | 74-85 / 18-35 | T / B | 187 | 147 / 65 | 79 / 35 % |

By side:
- **Top:** 2045 mm² (68 % of the board).
- **Bottom:** 495 mm² (17 %).
- **Rear band (y ≥ 18):** top 1091 of 1445 mm² (76 %). v1 had 773 here, with U1 on the bottom.
- **Front band:** top 954 of 1530 mm² (62 %). The slack is in the front band and on the bottom, and the plan uses
  neither.

## 2. Findings

### Critical

**C1. The sensor blocks are 2-3x too small.**
- The 20 parts per channel (J2/J3, LVC3G17, TPS22945, JP, 3 pull-ups, 3 x 1 k, 3 DNP caps, 3 supply caps, NTC
  R/C, BAV99) total 122 mm².
- The boxes are 66 and 72 mm².
- design.md B2 itself sizes the block at ~12 x 14 mm (168 mm²). critique §4 gives it 11 x 6. The memo contradicts
  itself.

**C2. The buck does not fit its box.**
- L1 (5.7 x 5.6), D2 (3.6 x 7.1), C27-C30, R4/R5/R20/R21 and C10 total 90 mm² in 70 mm².
- v1's buck used ~136 mm² (x 55-72, y 25-35).
- The box also makes the buck, U2 and U4 one solid top-side wall from y 18 to y 28.

**C3. U1 and its fan-out ring overrun the test strip.**
- The box is 13.0 mm and the courtyard is 13.5 mm.
- critique §8 puts the fan-out via rows 1.5-2 mm outside the pads, so the real envelope is ~16.5 mm (y ≈ 15.9-32.1).
- That leaves the strip 2.9 mm of height. U5 alone needs 3.5-4.2 mm.
- Strip demand is 59 mm² against ~32 mm² left (184 %).
- Twelve TPs at ≥ 2.54 mm pitch need ~31 mm of length. The strip is 13 mm long.

**C4. The U1→U4 bus cannot pass the U2/buck column.**
- The bus is 12 nets plus +3V3, not the "7 nets" in §4: R_INHA/B/C, R_SOA/B/C, R_nCS, R_nFAULT, SPI x3 and DRV_OFF.
  It crosses x = 67 and x = 74 with 13 nets.
- At x ≈ 63 the only route south of U2 is:
  - **L1:** blocked. The right-sensor block covers y 29-35, and U2's buck pins 44-48 (CB/SW/VIN/nSHDN, U2's
    south-east corner when rotated 180°) cut the 1.85 mm gap at y 27.2-29.
  - **L4:** the keep-out under SW (electrical C10) blocks y ≈ 26-28. The rest, y 28.5-35 under the sensor block,
    carries its ~20 pad vias, which leaves ≈ 11 lanes.
- **Demand 13 against ~11 raw lanes (118 %), against a 70 % gate.**
- This is v1's "east bus" failure, and the §8 channel plan (the U1-U2 channel only) does not address it.

### Major

**M1. The plan ignores the side rules in DESIGN §6.13.**
- §6.13 says loop-critical parts stay on their IC's side: DRV decoupling, CSA filters and the gate network. Parts
  taller than 1.1 mm go on top: C9, the SOD-123 diodes, and the 10 µF 1206 50 V caps (C13585 ≈ 1.6 mm).
- The plan puts 15 of these on the bottom anyway: C302/C308-C310, C402/C408-C410, C307/C407, C9, D4/D5/D10, and U6
  (TSSOP, 1.2 mm). The gate network and the ADC filters also go on the bottom.
- Obeying §6.13 adds 170 mm² to the top, which takes the rear-band top to **85 %**.
- One of the two has to give. Either §6.13 is relaxed explicitly (which needs the user's stack-height decision), or
  the top budget has to shrink.

**M2. TIM1 on pins 35-44 breaks the ADC plan in DESIGN §3.4.**
- TIM1 on those pins takes PA8/PA9 (35-37 = PB13-15, 42-44 = PA8-10):
  - PA8/PA9 are the only external ADC5 inputs, used by the left drive.
  - PB13-PB15 are three of the six ADC3/4 inputs, and COMP5/COMP7.
- The right drive survives on PB12 (ADC4) plus PB0/PB1 (ADC3, rear edge).
- The left drive keeps only OPAMP5←PC3 on ADC5, so it has to move to injected ranks 3-4 on ADC1/ADC2. ES0430 then
  forces 4 ranks on every ADC, and the §3.4 drive-duty limits (81/86 %) have to be re-derived.
- This is feasible, but it changes the firmware contract. The memo presents it as a free win.

**M3. The edge budget cannot be met (XML).**
- On the east side:
  - The east-bound demand is 28 nets: weapon 12, U4 8, right sensors 4, W_VA/VB/VC/NTC 4.
  - The E edge has 14 signal pins. With the adjacent half-edges it has 23.
- On the N edge, which faces the bridge, pins 49-64 have **no ADC and no COMP input at all**. The bridge sense nets
  and every CSA must enter on the E, S or W edges.
- Timer and SWD pins are fixed:
  - **TIM20** exists only on PB2 (S), PC2 (W) and PC8 (E). Whichever drive uses it leaves from three edges.
  - TIM8 CH3 is on PC8 or PB9 only.
  - SWD is fixed on PA13/PA14 (pins 49/50, the NE end of the N edge), so "SWD facing J1 at the west" is impossible
    at this rotation.
- **Count on 4-6 unavoidable wrap-arounds**, not zero. Plan their channels.

**M4. The plan assumes two open user decisions.**
- The BMS box fits only a "smaller/vertical J4" (J4 now: 12.6 x 16.0 = 199 mm²).
- The interlock box fits only a "shrunk U6".
- README §5 lists both as undecided.

**M5. The ARM pump's placement is contradictory.**
- design.md F7 puts U14/C15/D9 at J1 pin 19. The critique table puts them at U2.
- As drawn, W_ARM_CLK (a clock) crosses the MCU's bottom field from J1 to x 53.

**M6. The right corner cannot hold R402 at the required distance.**
- Electrical C15 requires R402 ≥ 5 mm from U4's thermal copper.
- The 11 x 17 corner already holds U4 (8 x 6), JR1-3 and MH4 (79.5-84.5 / 29.5-34.5). R402 (7.8 x 4) has no legal
  spot there.

### Minor

- **m1.** C1 (13.4 x 11.1) is wider than its 13 mm box. D1 does not fit beside it.
- **m2.** U1's north via ring (y ≈ 16-17.5) and J1's y 15-18 end sit over the L3 VBAT pour, so the L4 escapes there
  reference VBAT. Either end the pour at y ≈ 14 for x < 52, or accept it.
- **m3.** "ADC filters on the bottom under the pins" and "via rows outside the body" can both hold only if the
  passives stay inside the body shadow. Say so.
- **m4.** A VBAT test pad in the rear strip drags pack copper into the logic band.
- **m5.** The boxes overlap: left sensors with the left drive (x 26-28), and right sensors with the interlock (x 52-56,
  y 29-30).

## 3. Cut-line demand against capacity (proposal)

| Cut | Nets | Raw lanes (L1 + L4) | Load |
|---|---|---|---|
| x = 36.5, y 18-35 (west of U1) | 24 | ~90 | 27 % OK |
| x = 50.5, y 18-35 (east of U1) | 36 | ~59 (L4 blocked by the 107 % interlock block) | 61 % tight |
| x ≈ 63, south of U2 (U4 bus, C4) | 13 | ~11 | **118 % fails** |
| x = 74, y 18-35 | 13 | ~45 (y 28-35 is free) | 29 % OK |
| y = 18, x 44-85 | 22 (15 gate/Kelvin) | v1 block 1 routed them | OK |
| y = 30.5 behind U1 | 9 (SWD/NRST/TPs, into the strip that doesn't fit) | — | moot |

## 4. Conflicts between the memo and the user's rules

1. critique §11 says: "If it will not close, add ~5 mm of length or move the BMS off the board."
   - The outline is fixed.
   - Moving the BMS off the board is a removal, which needs the user's approval.
   - Delete this fallback, or turn it into a question.
2. §5's part shrinks are called "the user's call", yet §4 depends on them (M4). They are prerequisites, so present
   them that way.
3. The memo leaves the bottom at 17 % while the top rear sits at 76-85 %.
   - The user's only side rule is "hot parts on top", and the hot set (Q1-Q8, RS1-RS4, U2-U4, R302/R402, L1/D2, C1,
     U13, U5) is ~940 mm², only 32 % of the board.
   - The overflow comes from the memo's own stacking rule plus DESIGN §6.13, not from the user.
4. Cable exits (JL rear-left, JR right edge, JW front) are respected. The sensor connectors are not user-constrained.
   Moving J3 (below) should still be put to the user, because the right motor's sensor cable would cross the robot.

## 5. Fixes: an alternative floorplan

The alternative moves work into the front-band slack and onto the empty bottom, and clears the U4 corridor.

1. **Front logic strip, x 22-36 / y 10-18** (between the pack blocks and the rear band; 112 mm² per side):
   - **Top:** TP1-TP12 and D1, 70 mm² (63 %).
   - **Bottom:** J1, with its long axis along x and pins 5-10 at the east end. Put L3 GND under it; no pack current
     flows there.
   - SWD (U1 pins 49/50, north edge) then reaches the TPs and J1 directly, without wrapping.
   - Put the ARM pump (C15/D9/R18/C16/R41) at J1 pin 19. Only the DC W_ARM travels east.
2. **Rear strip:** U5, C69/C70, D3 and R62 only (22 mm² in 45 mm², 48 %). Move U1 to y ≈ 23 so the ring ends at
   y ≈ 31.2.
3. **Sensor front ends on the bottom**, beside their connectors. They are self-contained blocks, so the memo's
   stacking rule allows it. The connectors stay on top at the rear edge.
4. **Move J3 to the rear-left beside J2** (x 17-35 on the rear edge, 18 mm for two 9 mm connectors).
   - U3 moves to y ≈ 21-27.
   - Both front ends go on the bottom at x 24-37 / y 18-35. That area is empty once J1 has left, which gives 136 in
     221 mm² (62 %).
   - Encoders: TIM3 on PA4/PA6 (S-west) for L_S, and TIM2 on PA5/PA1 (the SW corner) for R_S.
5. **Buck south of U2**, as in v1, limited to y 27-33.
   - Take critique §6's D2/L1 shrink (~15 mm²), which gives ~72 % fill.
   - The rear-edge L1 strip (y 33-35) and L4 under the buck's quiet half (GND pads toward the north) become the U4
     corridor: ~22 raw lanes for 13-14 nets (≈ 64 %). No part or via goes in it.
6. **Interlock:** U6 + R47-R49 on the bottom under the U1-U2 gap. Take the WQFN option (40→12 mm²) to get it under
   ~70 %. U14 goes next to U6.
7. **R402** goes in the corner at y ≈ 18-20 behind cell A's rear edge, or under a user-approved rotation of U4.
   Check the 5 mm rule at placement.
8. **Pins** at rotation 0:
   - TIM1 CH1N-3N on PB13-15 and CH1-3 on PA8-10 (E).
   - W_nFAULT on TIM1_BKIN PB10.
   - Weapon CSAs on PB11 (COMP6, ADC1/2), PA3 (COMP2) and PB0 (COMP4), all ADC1. This keeps rank pairs A+B and C+A
     with A on ADC2.
   - R_SO on PB12 (ADC4) and PB1 (ADC3), with C = −(A+B) as §3.4 already does.
   - Right drive on TIM20 (PB2 / PC2 / PC8), accepting the one wrap for R_INHB.
   - Left drive on TIM8 PB6/PB8/PB9 (NW corner). Left CSAs per M2.
   - Expect ≈ 5 wraps. Budget them as named channels before placement.

Re-counted with the same MST method:

| Cut | Proposal | Alternative |
|---|---|---|
| x = 50.5 | 36 | 31 |
| Behind U1 | 9 | 2 |
| y = 18, x 0-44 | 6 | 18 (the J1 nets; the front strip has ~70 free lanes, so this is fine) |
| U4 pass | fails | ≈ 64 % |

Rear-band top fill drops from 76 % to ≈ 63 % (≈ 70 % with the §6.13 drive bulks on top). The bottom rises to ≈ 34 %.

**What must be true for 85 x 35 x 4L to close:**
- D2/L1 smaller.
- U6 in WQFN.
- J4 at its current size fits only in an exact 12.6 x 16 slot at x 0-12.6 / y 13.5-29.5. That is legal, but with no
  margin.
- The ADC re-plan accepted.

Put all four to the user **before** placement, then run the memo's routability gate on this alternative. It is a
block-level argument, not a placement.
