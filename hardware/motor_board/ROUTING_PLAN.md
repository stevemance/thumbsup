# Motor board routing plan

How the rest of the board gets routed, written before routing it (layout-pro order: plan the layers and
channels, power before signals, local hookups before long runs, review after every block).  Built by
`kicad/gen/route_all.py` from `route_blocks.py` (hand-planned geometry; the grid router only for short,
uncontested links), checked after each block with DRC, `layout_check.py` and crop renders.

## Layer jobs

| Layer | Front half (bridge, y < 19) | Rear half (logic + drives, y > 19) |
|---|---|---|
| L1 F.Cu | bridge power pours, gate stubs | parts; local hookups (decoupling, straps, filters); drive-IC outputs to JL/JR; VM pours at U3/U4 |
| L2 In1.Cu | solid GND (unbroken) | solid GND (unbroken) |
| L3 In2.Cu | VBAT feed pour; front lane strip y 4.9-5.8 for W_VA/W_VB/W_NTC | **long signal runs** in planned channels, +3V3 trunk |
| L4 B.Cu | gate/Kelvin bundles in the corridor | U1 and its ring of passives; U1 fan-out; local hookups |

L2 is never cut.  Everything on L1/L4 references it; L3 signals reference it too (L3 sits right under it).

## Order

1. **done** Weapon gate drive + Kelvin (block 1), U2 local (block 2), power-switch corner mostly (block 3).
2. **U1 fan-out** (block 5): every U1 pin gets a short stub inward to a via under U1's own body (the LQFP
   has no exposed pad, so the 9 x 9 mm under it is a free via field): signals to 0.4/0.2 vias in staggered
   rows, GND pins to vias to L2, VDD pins to their decaps on the bottom.  Outer ring of filters/decaps untouched.
3. **GND hookups** (block 4, after the fan-out): a via to L2 at every GND pad still off the plane;
   the dense ones by hand.
4. **U3 / U4 local** (blocks 6, 7): like U2: charge pump, AVDD, VM decoupling, buck feedback, outputs to JL/JR.
5. **Rails** (block 8): VM to each drive as top-layer pours/wide traces from R302 / R402; +5V from L1/C29
   to U5, J1, the sensor-supply jumpers; +3V3 from U5 as an L3 trunk with vias down at each load cluster.
6. **East bus** (block 9, L3): U1 to U2 (W_INH/INL/SO/EN/nFAULT), U4 (R_INH/nCS/nFAULT/SPI), U10 (R_S):
   lanes along y 27-33, south of U2's thermal field, up into U4 from below.
7. **West bus** (block 10, L3): U1 to U3 (L_INH/nCS/nFAULT/SO/SPI), U9 (L_S).
8. **Front-left logic** (block 11, F/B: L3 is the VBAT pour there): U6 interlock, U7 INA239, ARM, divided
   phase/NTC lanes (L3 front strip) up to U1, BMS/J1 lines.
9. **Sensors** (block 12): J2/J3 halls through U9/U10 and their RC filters.
10. **Close-out**: GND pours on F/B in the open rear areas, stitched to L2; 0 unconnected; DRC and
    `layout_check.py` green; JLC checks (FAB.md).

## Status (2026-09-25)

Done, DRC 0: items 1-4 above; the **east bus** (route_blocks 8a/8b: twelve L3 lanes behind U2, U4 front group
round U1's NE corner, south group round U1's rear, CSA filters R80/R81 moved to U4's corner, R82 beside U1.25,
C90/C91 swapped); **BMS corner** (9a); **NW bottom-side logic, local pairs** (11a).

What the remaining nets run into (found by a trial pass of the router over everything left: 66 of 134 pairs
routed, every long U1-hub net failed):

- **U1's field is sealed on L3** except U1's west strip and a gap on the east side at y 26.9-29.05 (once the
  two +3V3A vias go: +3V3A is bottom-local).  Nets that must cross it: MB_TX/MB_RX (east pins -> J1 west),
  L_S3 (U9 west -> U1.24 east), R_S1/R_S2 (U10 east -> U1.51/.56 west).  A pin swap would remove these
  crossings, but the pins are tied to peripherals (TIM2 hall inputs, USART1), so it is a firmware decision.
- **Everything east of the bus's north group** (x 42.1-42.7, y 20.5-28.4 on L3) reaches U1 only on F/B:
  the U2 rear group (W_INHA/B/C, W_INLA/B/C), W_EN, W_nFAULT.
- **U6 (INL gates) in the far NW** makes W_INLx a loop U1 -> NW -> U2's rear (27-45 mm); **U10 sits under the
  bus's east-end columns** (no via reachable near it); the **sensor clusters** are boxed in (J2's pins face
  U1's fan-out via row with U9 right behind it; J3's filters R114-R116 sit in a one-part band under the bus).
  None of these can simply move: a free-spot search finds no room near any of them on either side.

Feasibility check (TRIAL=hard in route_blocks.py: the hub crossers alone, routed first, any layer, cheap vias):
MB_TX/MB_RX, R_S3, INA_nCS and W_EN's U1 leg route (long, 1-4 vias); **no path exists** for the whole U2 rear
group (W_INHA/B/C, W_INLA/B/C), U2's own W_EN / W_nFAULT pins (U2's west side is sealed on F and has no via
spot), R_S1/R_S2, L_S3, W_INLA/B/C_M.  U2's region is enclosed: the bus south, its north group west, U4's
columns east, the VBAT feed north.  So the board does not complete on 4 layers with this placement and pinout;
it needs one of: two more layers, a re-placement of U6/U10 and the sensor clusters (needs board area), or
MCU pin swaps (firmware).  Trials kept behind `TRIAL=` in route_blocks.py (west, nw, hard) for re-measuring.

Tools added: `spot.py` (free spots for re-placing a part, on the routed board), router `avoid` boxes
(reserve planned corridors in a router request).

## Status (2026-09-26): 6 layers, 496 of 585 connections, DRC 0

Stack-up now F / L2 GND / L3 (VBAT feed + lanes) / L4 signals / L5 GND / B (base_edits.py).  Since then: U2 rear
bus on L4, all hub nets (W_INH/INL/EN/nFAULT, R_S1-3, L_S3, MB_TX/RX, INA_nCS), NW logic, rails, GND pad vias,
F/B GND fills, and a rip-up-and-reroute post-pass in router.py (only `soft` = router-made local routes).
Hand-placed escapes are reservations applied right after block 7d (route_blocks.py, `_reserve`).

89 left (about 38 rail/GND, 51 signal), all blocked by placement or hand geometry, not by router order:
- U1 west pins 59/60 (L_INHA / L_nFAULT to U3): C112 (left-sensor cap, top) sits over their only outward via
  spots; U3's right-column SOA/SOB/SOC face C306 (its AVDD cap).  -> re-place the left-sensor island (U9,
  C110-C112, R110-R112) and C306's neighbourhood.
- Right sensors: R114-R116 in a one-part band under the east bus; U10's inputs.  -> re-place.
- Phase-sense caps C42/C44 (W_VB/W_NTC) east of U1 behind C92 / R117.
- A few +3V3/+5V islands and GND pads in dense spots.

## Status (2026-09-27): freeze-and-edit tail, 65 open, DRC 0

The board is no longer rebuilt from route_all.py: `kicad/gen/frozen/board.kicad_pcb` is the accepted board and
`tail_edits.py` lists edits on top of it (`tail.py` applies them + DRC in ~30 s, `tail.py freeze` accepts).  Every
accepted round is in `kicad/gen/tail_log/NN_*.py`, in order.  Deviations made in the tail (for review):
- **L3 VBAT feed trimmed** in its south-west corner (x 21-34.6 / y 16.5-20.8 and x 21-26 / y 10.2-16.5): no pack
  current there (C1 sits on the L1 pack pour; the feed's stitching vias are all at y <= 15.8); frees L3 for the
  U7 / J1 / U1-north signals.
- **+3V3 pour on L4** ("L4 3V3 fill", lowest priority, around every L4 signal) with pad drops; the U7-area +3V3
  wiring on B was lifted onto it.
- **Via-in-pad** (filled + capped, already in FAB.md for the thermal vias) on three boxed-in passive pads
  (C112.2, C74.1, C62.1).  Own GND drop vias added for ~63 GND pads that relied on the outer fills only.
- **Moved parts:** C92 (R_SOC_F filter cap) to the top under R82; R23 / R25 (W_VA / W_VB divider bottoms) beside
  R22 / R24 (they were 15 mm west of the rest of their nets); INH pair hand-laid with a jog on L4.
- Stack-up chosen and set in the boards: JLC061611-1080B (FAB.md).

Decisions (researched 2026-09-27):
- **Hall pull-ups stay at the connector** (no move to the U10 side of the 1 k filters): the SN74LVC3G17's VT- is
  0.84 V min at VCC 3 V; a 1 k / 4.7 k divider plus an open-drain Hall's VOL (0.2-0.4 V) gives 0.74-0.91 V at the
  input, no margin.  J3's filters / pull-ups get re-placed instead.
- **Logic lanes on L3 between U3 / U4's thermal vias: allowed**, only in the gaps of the via array (no vias added
  there).  TI asks for as much thermal-pad GND copper as possible on every layer; here the array reaches the two
  full GND planes (L2, L5), L3 under the pad has no copper to lose, and the drive dissipates ~1 W at the ~1 A
  traction limit (design/calcs.md 5), so an L3 GND island would add little.
- **L3 VBAT feed trim: kept**: no VBAT via or pad lies in the removed area and the feed width on the pack path is
  unchanged.

Open clusters (need re-placement or a decision): right-sensor J3 fan-out (H2/H3 filters and pull-ups: re-place), U1 east W_NTC / W_INLA_M, the U3 -> U1 trio
(L_INHA / L_nFAULT: source and pin order reversed, needs a layer hop), SPI to U7 and U3, SWDIO / NRST to J1,
left-sensor island (L_VS, L_H1/H2, L_S1/S2), +5V to JP1 / JP2 / J1 / R20, LED R62.

## Status (2026-09-27, later): 60 open, DRC 0 - placement-bound

Since the decisions above: J3's H2B / H3B filter outputs routed (under the connector body, L3 south strip to
C115 / C116); Default (logic) netclass clearance 0.127 and hole-to-copper 0.2 (JLC 6-layer: 0.09 / 0.2; FAB.md);
the router refuses wandering routes (`max_ratio`).  Every remaining item was tried with rip-up / re-lay and fails
on placement, not routing order:
- **U10 sits on the L3 east bus's northward turn**: no via can reach its pins, so U10.6 (H3B) and U10.7 (R_S1)
  share one bottom-side gap and cannot both escape.  The H2 / H3 pull-ups (R58 / R59) can't reach J3's pins:
  J3's body (courtyard y 28.8-35) takes the space south, the bus the vias north.  Needs U10 (+ C50, C114-C116) moved
  off the bus, or J3 moved.
- **Left-sensor front end (U9, R110-R112, C110-C112, R54-R56, U11) sits on top of U1** (bottom side): every link
  to U1's pins needs a via through U1's escape field.  Needs the group moved off U1.
- **U3 -> U1 (L_INHA, L_nFAULT, L_SOC, SPI to U7, SWDIO / NRST to J1)**: pin orders reversed and one L3 corridor.
- The free board area left is on the bottom only: the left edge (x 5-13) and the top strip (x 35-70, y 0-8.5).
A placement revision of the U1 / U3 / J2 / J3 / U10 region is the next real step.

## Board growth 75 -> 85 mm (2026-09-28): 59 open, DRC 0

`kicad/gen/grow.py` cut the board along a stepped line and moved the east part +10 mm: between weapon cells C and B
(each cell's commutation loop untouched; the VBAT / GND pours between them stretch), then between U2 and its small
parts, then west of the buck (L1, C28-C30, D2 move with U2) and east of U1's cluster.  46 crossing tracks were
bridged, 8 re-routed.  Moved with the east part: MH2 / MH4, J3, U2, U4, U10, U12, JW1 / JW2, JR1-3 (compute board and
chassis must follow).  The new band (x ~45-59, y 17-35) is free of parts; crossing it: the L3 bus (y 27.8-31.3), L4
lanes (y 33.2-34.4, 23.6-25.9), and bridged B / F tracks (B y 21.0, 25.95, 28.07, 33.7).  Vias in the lower band only
at y 31.55-33.0.

Right-sensor block tried in the band (U10, filters, pull-ups): H2 / H3 pull-ups and H3B connected, but J3's pin
order is the reverse of U10's input order and the block's power pins sit over the bus: net zero, reverted.  A clean
version needs the block drawn by hand around the via strip.

## Status (2026-09-28, later): 43 open, DRC 0 - L5 takes jumpers

Rounds 17-21 (tail_log): U12 1.6 mm north with C49 beside its R_VS pin (R_VS / R_VSRC done); a `reroute` option on
rips (lift a blocking run, route the open, re-join the run's cut ends); L4 3V3 fill islands stitched with short hops;
a batch of per-open experiments (`TAIL_EXP`: one edits module per trial, own work dir, run in parallel).

**Decision: L5 (In4, the second GND plane) takes short signal jumpers** where U1's field is full on all four signal
layers (a via-spot search finds no legal 0.3 mm via within 1.5 mm of eight boxed-in GND pads there).  The router
uses L5 only when a request lists it, at layer cost 4, so it goes there just to get past a fence; the plane refills
around the jumpers.  Why this is acceptable: L2 stays unbroken and is the reference for F and L3; the jumpers carry
slow logic (NRST, W_NTC, L_SOC, +3V3 ties), none of the gate / Kelvin / SPI-clock / shunt nets; motor supplies
(R_VM) never go there.  Cost: small slots in L5 under the U1 area, where the L4 signals above it then reference L3 /
L2 over the slot length.  First pass: +3V3 x2, NRST, W_NTC, L_SOC (L5 lengths 4.6-9 mm).

`netcc.py` lists a net's disconnected pieces the way DRC counts them (zone islands, tracks, vias, pads); DRC's
zone-to-zone items carry no position.  GND: 8 padded pieces left (C64 / C90 / C73, TP12, C111, C45, C61, R61, C50,
U7.7), all fenced by signal tracks with no legal via spot.

## Status (2026-09-28, end): 38 open, DRC 0 - needs decisions

Rounds 22-24: L_INHC (L3 + L5); **power LED D3 and R62 moved** into the band beside the +5V bridge (R62 had been
35 mm from D3, at U4; D3 is still on the rear edge, top side); +5V to JP1; **+5V trunk to J1** (compute-board feed,
<= 0.45 A) as a 0.35 mm L5 run ~2.5 mm inside the rear edge (y ~32.5, x 18-51): no other path exists, and a strip
right at the edge is blocked by the GND via rows at y 33.2 / 34.1.  L2 is untouched; the L5 strip south of the trunk
is stitched by those rows.  W_VA's hop over U1's east pins is now on L5 (analog sense between planes).

Left (38): 8 GND pads (C64 / C90 / C73, TP12, C111, C45, C61, R61, C50, U7.7: no legal via within 1.5 mm even at
0.3 / 0.15, `viaspot.py`), and 30 signal / rail connections in three knots:
1. **Left Hall front end on top of U1** (U9, R110-R112, C110-C112, R54-R56, U11, C46 / C47): L_S1-3, L_VS x2, L_VSRC,
   L_H1, L_MTEMP, +3V3 at C47 / U9.  U9 sits on U1's escape via field (the vias under it are U1's fan-out); a via
   search finds no legal spot for any of its outputs.
2. **Right sensors** (U10 on the L3 bus turn, J3 filters): R_H2 / R_H3 / R_H3B / R_TEMPJ / R_SOC / W_NTC: every
   trial trades one for another (R_H2 vs R_H1, R_H3B vs R_S1).  C410 (U4's third VM bulk cap, 20 mm from U4 since
   placement) has no free spot within 7 mm of U4.
3. **U1 west / south-west** (SWDIO x2, SPI_SCK / SPI_MOSI to U7, L_nCS, INA_nCS, R_MTEMP x2, W_INLA_M, VBAT_SW, +5V
   at JP2 / R20).  Re-laying U1's west fan-out automatically makes it worse (38 -> 45): the hand-planned escapes
   are denser than the grid router reproduces.

Options, cheapest first: (a) **MCU pin swaps** for the hall inputs (L_S1-3, R_S1-3: TIM2 / TIM3 channels have
alternate pins) and SWD-adjacent signals, putting each on the U1 side facing its source: schematic + firmware
change; (b) **8 layers** (JLC 8-layer): two more signal layers under the same placement; (c) a hand re-placement of
the U1 surround (left front end off U1, U10 off the bus), which means re-drawing U1's fan-out by hand.

## MCU pin swaps (2026-09-28, rev L1): 35 open, DRC 0, parity 0

User chose pin swaps (option a above).  Done in `design/motor_board.py` (ST pin-database check passes),
netlist / pin map regenerated, `mcu.kicad_sch` edited in place (the sheet generator re-rolls every symbol uuid, which
would break the footprint links), board pads re-netted with the tail op `swap_pin` (review/CHANGES.md "Rev L1"):
L_S2 -> PB4 (takes R_nCS's pin-57 via beside U9.5), L_S1 -> PB5, R_nCS -> PA11 (takes INA_nCS's pin-45 stub beside
its own L3 lane via), INA_nCS -> PB8-BOOT0 (R61 removed; nSWBOOT0 / nBOOT0 option bytes), PC6 unused.
Why PC6 is left empty: it has no via reach at all (pins 37 / 39's vias, C91 under it, J2's mounting pad above), so
whatever sits there cannot route; the only way to free it was to give BOOT0's pin a second job.

Tried and not taken: a W-group rotation (W_INLA_M -> PC13, W_nFAULT -> PA6 / PB8, W_NTC / R_MTEMP -> PA7 / PF1):
W_INLA_M and R_MTEMP connect, but pin 6 (PF1) and pin 61 (PB8) have no escape for the net pushed onto them (PF1 is
boxed by L_MTEMP's and NRST's fan-out vias, PB8 by an L4 lane under its only westward exit) and W_INLA_M's L4 path
splits an L4 3V3 island: net zero.  Tail gotcha found: `SaveBoard` re-nets an unconnected new via to the plane net
(GND); hand vias for signal nets must get their track in the same step, or be left to the router.

## Conventions

- Signals 0.2 mm (Default 0.15 allowed in fan-out), gates 0.25, rails 0.3-0.4 in trunks, VM/SW per class.
- Vias 0.4/0.2 for signals, 0.45/0.25 for GND/rails, 0.6/0.3 in power.  Via-in-pad only where FAB.md says.
- Every block leaves DRC at 0 errors; its geometry is documented at the top of its section in route_blocks.py.
