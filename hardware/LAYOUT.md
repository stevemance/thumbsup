# ThumbsUp v1 — layout (rev v1.2, 2026-09-04)

The board is **generated**: `tools/pcb/build_pcb.py` builds `kicad/thumbsup.kicad_pcb`
from the schematic netlist, the chassis-derived outline (`mech/board_outline.json`), the
placement in `tools/pcb/placement.py`, the hand copper in `tools/pcb/copper.py`, and then
Freerouting for the logic nets (`tools/pcb/route.py`).  Never hand-edit the `.kicad_pcb`;
change the scripts and rebuild:

```
hardware/tools/.venv/bin/python hardware/tools/sch/build.py          # schematic + netlist
/usr/bin/python3 hardware/tools/pcb/build_pcb.py --render            # place, copper, route, DRC, previews
/usr/bin/python3 hardware/tools/pcb/fab.py                           # Gerbers / BOM / CPL for JLC
```

`build_pcb.py --no-route` skips Freerouting (fast, for placement work).  Previews land in
`kicad/preview/pcb_*.png`; the DRC report in `kicad/drc.json`.

## 1. Mechanical (from the chassis 3MF, `tools/mech/chassis.py`)

Board frame: origin = chassis (76.0, 174.5), x to the right, y toward the drum.  The
outline is the PCB bay of `models/Chassis - Main Chassis.3mf` with 1 mm wall clearance:
a 104.5 × 37.5 bay with 16.5 mm chamfers at the back corners and 9.5 mm notches at the
front corners, plus a 46.5 × 13.5 neck (x 33..79.5, y 37.5..51) under the drum.  `chassis.py
outline` re-runs the fit check (walls, bosses, floor height) — 0 offending cells.

| Item | Decision |
|---|---|
| Mounting | 3 × M2.5 on **bosses to add to the print** at board (3.7, 18.8), (101.5, 20.5), (52.8, 47.3) = chassis (79.7, 155.7), (177.5, 154.0), (128.8, 127.2); 3 mm standoffs. Bottom-side parts ≤ 2.5 mm tall (tallest is the 2 mm inductor). |
| Wall slots | J1 (XT30, x 16.6..31) and the Pico's micro-USB (x 61.7..74.1) mate through slots in the back wall at y = 0. |
| Under the drum | Neck parts ≤ 8 mm: J3 needs a ≤ 8 mm header (5 mm-pin low-profile) or soldered leads; no cans / XT30 / switch there. |
| Lid bosses | Ø7 lid-screw bosses at chassis (79,171) and (176,171) are cleared by the corner chamfers. |
| Fiducials | FID1 (11, 36), FID2 (47.3, 49), FID3 (99.7, 25.7), top side. |

## 2. Stackup, rules, fab

| Item | Decision |
|---|---|
| Stackup | JLC 4-layer 1.6 mm, **2 oz outer / 1 oz inner**. F.Cu: power stages, phase copper, VBAT and I_x+ pours. In1 (`GND`): ground plane with an 8 mm VBAT corridor (cans → left edge of the L block → along the front → R can; 1 oz ≈ 7 A continuous, enough for the geared drive motors — the weapon is fed on F.Cu). In2 (`SIG`): signals only. B.Cu: VBAT_PACK/VBAT under J1 and under the W high row, solid GND pour everywhere else (thermal spokes starve in the packed bottom). Freerouting also routes signals on In1 where it needs to, so the plane is a fill around those tracks, not a solid sheet; the B.Cu pour is the solid ground. |
| Rules | Board minimum 0.15 / 0.15 mm (JLC 2 oz); Default class 0.15 clearance, 0.15 tracks; vias 0.25 drill / 0.45 pad (hand vias 0.3 / 0.6); hole-to-copper 0.2. Power copper: `kicad/thumbsup.kicad_dru` applies **0.35 mm** wherever a zone meets a POWER_20A/30A item, so the 0.5 mm-pitch driver / INA226 pins that carry VBAT or a phase are not flagged pad-to-pad. |
| Net classes | POWER_30A (VBAT_PACK, VBAT, MOTOR_W_*, I_W+), POWER_20A (MOTOR_L/R_*, I_L+, I_R+): pours only. GATE 0.3 mm, VDRV 0.8 mm, 3V3 0.3 mm, SENSE 0.15 mm (patterns in `build_pcb.py`, written into `thumbsup.kicad_pro`). |
| Assembly | JLC Standard PCBA, **both sides**: top = FETs, shunts, cans, TPs, LEDs, SWD pads; bottom = everything else (AT32 / HX6288 / INA180 under their FET block, INA226 at their shunts, buck, LDOs, flash, IMUs, level shifter, passives). Hand-soldered after SMT: Pico W (castellations), J1 XT30, J2/J3 headers, the nine motor leads. |
| Mask | JLC needs 0.20 mm between pads for a mask dam at 2 oz; the VSSOP-10 (0.15) and LGA-14 (0.175) simply get no dam between those pads. |

## 3. Floorplan (top side; all coordinates in mm, board frame)

```
 y=0 wall:  [chamfer/TPs][ J1 XT30 16.6..31 ][ L can 31..45 ][ W can 45..56 ][ Pico USB ]
            SW1 (12.6,13)                       L block 35.8..53.5 x 13.6..30.6
 W block 12.6..30.3 x 17.5..34.5  R435 rot90    R235 (39.8,33.5)  TP200-203    Pico 56.1..79.3 x 0..51
 LEDs D5/D6/D4 at x 9.6..10.6      (32.9,31.5)                                   R block 79.6..97.3 x 9.3..26.3
 J2 ARM (4.9,24.8) H1 (3.7,18.8)                                                  R335 (84.5,4.4)  R can (86.3,31.9)
 neck: J3 (33.4..49.7 x 37.6..43.8), J20/J30/J40 SWD pads, TP4/5/6/40, FID2, H3 (52.8,47.3)
```

**FET blocks** (`placement.fet_block`): three half-bridge columns on 5.9 mm pitch, FETs
rotated so the drain tab faces one edge and the leads the other, rows 9.6 mm apart, and the
**motor holes between the rows** (`thumbsup:MotorHoles_1x03_P5.90mm`, 2.0 mm holes / 3.0 mm
pads, 0.3 mm from both FET bodies, all three the phase net).  This is the only way three phase
nodes get out of a 2 × 3 FET block without inner-layer phase copper.

* L: rot 90, VBAT tabs at the top (y 13.6) against the cans, I_L+ leads at the bottom → R235.
* W: rot 90, VBAT tabs at the top fed from under J1 (bottom pour + 11 vias + the top-layer
  bridge x 30.3..35.8), I_W+ leads at the bottom → R435 (rot 90 beside the block).
* R: rot 270 (mirrored): I_R+ leads at the top → R335 in the strip above the block, VBAT tabs
  at the bottom against the R can; the block's top-right corner sits exactly on the chamfer.

**Shunts**: `thumbsup:R_2512_Shunt_Kelvin` with the two Kelvin net-ties
(`thumbsup:NetTie-2_Kelvin_0.4mm`, copper-only 0.4 mm pads, no mask opening) **in the 1.3 mm
gap between the shunt pads under the body**; `copper.kelvin_stubs` joins tie pad 1 into the
shunt pad, the sense trace leaves tie pad 2 sideways.  The pack shunt R2 is on the bottom
under J1 between its pegs and pins.

**Bottom side** is packed by `placement.Packer` into named regions; through-hole pads, the
motor holes, the fixed ICs, and every via field / GND patch / gate via from `copper.py`
(`reserved_rects`) are obstacles it steps around.  The build prints the fill of every region
and `placement check: 0 problems` (outline, courtyards, holes, Pico keep-outs, tall parts
under the drum) — keep it at 0.

## 4. Copper (`tools/pcb/copper.py`)

* **Phase pours** (priority 3): one per column, from the high FET's lead row to the low FET's
  tab end, containing the motor hole.  Each high-side **gate** gets a via 1.045 mm outboard of
  pad 4 and 1.0 mm into the pour, with the pour (and the neighbouring column's pour) notched
  around it; a 0.25 mm stub joins pad 4 to the via and Freerouting takes it from there on
  B.Cu to the driver.  Low-side gates do the same in the I_x+ pour.
* **I_x+ pours** (priority 2): block-wide under the low-FET leads, extended over the shunt's
  hot pad.  The R band above the notches is ≥ 1.6 mm; the shunt is at the left so only the
  third column's current crosses a notch.
* **VBAT**: top pour W block + bridge + both cans + L block top row; top pour R block bottom
  row + R can; the In1 corridor between them with 24 vias at the left field (x 31.9..34.9,
  under the L can) and 21 at the R can; bottom pour under J1 → R2 → W high row.  Bottom drain
  MLCCs (C?23/C?24) get a B.Cu patch + via into the top pour above them.
* **GND**: In1 plane + solid B.Cu pour (0.35 mm clearance); F.Cu GND patches with 4–8 vias at
  every shunt / can GND pad; FET-adjacent sides of the R235 patch have no vias.
* **Pack entry**: VBAT_PACK pour top + bottom between J1 pad 2 and R2 pad 1 (J1 is THT, no vias
  needed); TVS D1 and C1/C2 sit in that pour on the bottom.

## 5. Routing (`tools/pcb/route.py`)

Freerouting 2.4.1 (bundled JRE, `tools/freerouting/`, git-ignored — download the linux-x64
bundle from github.com/freerouting/freerouting/releases into that folder) runs headless on the
Specctra export with fanout disabled (`--router.fanout.enabled=false`; its escape-via stage
burns 20 passes on this board for nothing).  Zones are exported as planes; Freerouting routes
other nets through them and KiCad refills around the tracks.  Freerouting declares an inner
layer a power plane when it has no track and a conduction area ≥ 50 % of its (badly computed)
board area — In1 is meant to be that; In2 carries no copper of ours so it stays a signal
layer.  `route.py import <pcb> <ses>` / `route.py stats <pcb>` import a session and list the
unrouted nets.  The bottom GND pour is left out of the export (`route.py export`) so the router
joins every GND pad to a nearby GND via instead of assuming the pour connects it; every SMD GND
pad also gets its own via before routing (`copper.gnd_pad_vias`), and every F.Cu pour gets
pickup vias (`copper.pickup_via_spots`) because Freerouting never connects to a pour.

**Status (2026-09-17, run L, 16 passes, 1 oz rules):** the committed `kicad/thumbsup.kicad_pcb`
is that run imported: 49 connections unrouted by Freerouting, **102 unconnected in KiCad**
(54 GND pads / pour islands, 48 signal ends across ~30 nets), 11 DRC errors.  The board is
over-dense for a fully automatic finish: the three AM32 cells plus the Pico put ~310 parts on
4 400 mm² with the bottom side packed at 100 %.  Convergence history: 2 oz rules plateaued at
~100 Freerouting-unrouted; 1 oz rules and the pour fixes brought it to ~50.  Finishing this
board needs either hand-routing of the last ~50 ends or fewer parts; the drive-architecture
decision (AM32 sensorless vs brushed + encoders vs FOC) changes the part count by ±100, so
that decision comes first.

## 6. Checks still on a human

* Confirm XT30 polarity on a physical connector before soldering J1 ("+" = pad 2, at x 21.3).
* The chassis print must gain the three M2.5 bosses and the two wall slots (§1).
* Motor leads: 16–18 AWG into 2.0 mm holes on 5.9 mm pitch; pre-heat, the pads are solid 2 oz.
* JLC's CPL rotation preview for the QFN / SOT parts (`fab/thumbsup_cpl.csv`).
* Bench: USB alone powers only the Pico; the weapon cell stays in reset until ARM link **and**
  WEAPON_EN; the L/R cells enter the AM32 bootloader if DShot idles high ≥ 2 s.
