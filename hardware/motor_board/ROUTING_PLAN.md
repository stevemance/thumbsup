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

## Conventions

- Signals 0.2 mm (Default 0.15 allowed in fan-out), gates 0.25, rails 0.3-0.4 in trunks, VM/SW per class.
- Vias 0.4/0.2 for signals, 0.45/0.25 for GND/rails, 0.6/0.3 in power.  Via-in-pad only where FAB.md says.
- Every block leaves DRC at 0 errors; its geometry is documented at the top of its section in route_blocks.py.
