# Motor board: fabrication and assembly checklist (JLCPCB)

Everything the order and the build depend on, in one place. The sources are the ones listed per line; when a
design decision changes one of these, change it here too. Tick through it on order day.

## Before ordering
- [ ] `python3 design/motor_board.py` prints `checks: OK` (BOM.md "Before ordering").
- [ ] Fab source: the final stage board `kicad/gen/out/exp/<last stage>/proj/` (.kicad_pcb/.kicad_pro/.kicad_dru; today
      `hS`, gitignored) copied into `kicad/motor_board/`, which today holds a board with no copper.
- [ ] `/usr/bin/python3 kicad/gen/layout_check.py`: DRC 0 errors, schematic parity 0, **0 unconnected items**,
      every via field OK, no pour with extra islands, section 5 (GND pads) empty.  **The script still targets the v1
      6-layer board (gate vias on all FETs, v1 pour names, 6-layer renders): update it for v2 before it can gate an order.**
- [ ] Re-check stock and part class on jlcpcb.com for every BOM line; **reserve U1, U2 and U7** (U1 122 in stock on
      2026-10-01; U7 is now INA239AQDGSRQ1 C4367136, only 7 in stock: the INA239AIDGSR / INA229AIDGSR were at 0).
- [ ] Compute board designed to match this one: J1 is on this board's bottom, origin (52.5, 30.95) rot 90, pin 1 at
      (58.215, 32.95), pin 2 at (58.215, 28.95), odd pins along y 32.95 and even pins along y 28.95, stepping −1.27 in x
      to pins 19/20 at x 46.785 (board-local mm, top view: x from the left edge, y from the front edge, as in the stage
      dumps). Mounting holes MH1-MH4 at (3, 3), (82, 3), (3, 32), (82, 32): a 79 x 29 mm rectangle. Clear zones on the
      compute board under J1, J4's five pins (x 64.7-74.7, y 31.08) and every wire-hole joint (JBAT1 (8.75, 3.25),
      JBAT2 (3.25, 8.75), JW1-3 y 2.75, JL1-3 x 2.5, JR1-3 y 31.3); the Pico W antenna and USB outside this board's
      outline; J1 mated height chosen (sets the stack gap).
- [ ] Export: `/usr/bin/python3 kicad/gen/fab.py <final stage>` -> kicad/gen/out/fab/: Gerbers (X2 + `.gbrjob`),
      Excellon drill (PTH / NPTH), BOM.csv and CPL.csv (DNP parts left out, JLC rotations from the reviewed per-part
      table in fab.py).  Do **not** use plain `kicad-cli pcb export pos` or kicad-jlcpcb-tools' default corrections for
      the CPL (see the CPL rotation row).  Open the Gerbers in JLC's viewer and check the layer order (L1 F.Cu, L2 In1
      GND, L3 In2, L4 B.Cu) before paying.

## PCB options (order form)
| Option | Value | Why / source |
|---|---|---|
| Layers | **4** | layout v2 (2026-09-29, branch layout-v2) restarts on 4 layers; the 6-layer v1 is kept on branch worktree-routing. Layer jobs as built: L1 parts + power, L2 solid GND (no traces), L3 VBAT band under the bridges (y < 16) plus the main signal lanes behind it (~1050 mm of tracks on 47 nets), GND fill in every free L3 area stitched to L2, L4 parts + signals + GND fill.  Accepted by the owner 2026-10-01 in place of the earlier contract (review/v2_lessons/README.md 3.1: L3 'GND elsewhere'); DESIGN 6.2 |
| Stack-up | **JLC041611-1080** (1.6 mm): L1-L2 1080 prepreg 0.069 mm, L2-L3 core 1.23 mm, L3-L4 1080 prepreg 0.069 mm | thin L1-L2 keeps the weapon commutation loop at the ~4 nH estimate (PLACEMENT 3); L3 couples to L4, not L2, so L4 traces never cross a VBAT/GND boundary on L3 (solid GND under the VBAT band).  In KiCad (kicad/v2/build_board.py STACKUP4).  Confirm the name on the order form: JLC renames stack-ups |
| Outer copper | 1 oz | 0.5 mm-pitch QFNs; the pack current rides the L1 pours + the L3 band |
| **Inner copper** | **1 oz** (select it explicitly; JLC's 4-layer default is 0.5 oz) | the pack current rides the L3 VBAT band (DESIGN 6.2); the extra copper is two inner layers of 85 x 35 mm, ~3 g |
| Board size | **85 x 35 mm**, 1 design (fixed for v2) | PLACEMENT 1 |
| Surface finish | ENIG | flat pads for the QFN / LQFP / PDFN parts |
| **Via-in-pad** | **yes: epoxy-filled and capped (POFV), 0.40 mm pad / 0.20 mm drill** (JLC's POFV minimum drill is 0.2 mm; paid on 4-layer boards) | 44 vias on the hS board (centre inside a pad; all 0.40/0.20 except NT1-NT3 0.45/0.20): U2 pins 1, 13, 14, 18, 19, 21, 22, 23, 24, 37, 39, 41, 48; U6 pins 3, 4, 5, 6, 8, 10; U1 pins 5, 42, 45, 49, 50; U4 pins 5, 37; U9 pins 1, 4, 8 (pin 8's via is shared with C47.1); J1 pins 3, 5, 6, 17; NT1/NT2/NT3 pad 1; RS2 pad 1; C111.1, C112.1, D8.2, R52.2, R110.1, R113.2, TP3.1.  The weapon gate/Kelvin and U2/U6 fan-outs have no room otherwise (DESIGN 6.2, review/v2_layout/gate_corridor.md, stage files kicad/gen/h*.py).  Re-list after every layout change; add U2/U3/U4 exposed-pad thermal vias if they are filled.  Confirm on the order form |
| Min track / space | 0.15 / 0.127 mm on logic nets (Default class; 0.10 board minimum for pad escapes); 0.15 clearance on power, drive, gate, sense, rail classes (JLC 4-layer: 0.09 / 0.09) | motor_board.kicad_pro, motor_board.kicad_dru |
| Hole to copper | via hole 0.20 mm; PTH hole 0.30 mm (JLC 4-layer: via 0.2, PTH 0.28, 0.35 recommended); pad hole-to-hole 0.45 | motor_board.kicad_dru |
| Min via | 0.4 mm pad / 0.2 mm drill (Default); 0.45 / 0.25 sense and rails; 0.5 / 0.25 gate; 0.6 / 0.3 power (JLC 4-layer min 0.25 / 0.15).  The board has 201 vias of 0.40/0.20, in JLC's surcharged small-via class (cost only); vias outside pads may grow to 0.45/0.20 where clearance allows | motor_board.kicad_pro |
| Impedance control | no | nothing on the board needs it (layout step 0) |
| Mask / silk | any colour; silk on both sides | silk only on parts handled after assembly (connectors, wire holes, JP, TP, MH, D3, C1), 0.15 mm lines / 1.0 mm text; wire names on the bottom (WA-WC, LA-LC, RA-RC), BAT+ / BAT- both sides, J4 B- / B4+, J2 / J3 VS / T, JP1 3V3 / 5V; a pin-1 / cathode dot on every IC, diode and FET (JLC checks polarity against the silk).  Not placed (no clear spot): JP2's 3V3 / 5V labels and reference, TP7 / TP12 references (stage kicad/gen/hS.py, silk.py) |
| Order number | **remove** (no marker on the board) | cosmetic |

## Assembly options (PCBA)
| Option | Value | Why / source |
|---|---|---|
| Type | **Standard PCBA, both sides** | parts on top and bottom (PLACEMENT 5.1) |
| Panel / rails | board under 70 x 70 mm: **rails, mouse-bite tabs only, no V-cut on any edge**.  Tabs only where nothing lies within 1.5 mm of the edge: front (y = 0) x 44.7-48.9, 54.3-62.0, 67.4-73.9; left (x = 0) y 11.2-18.8; right (x = 85) y 5.5-13.7.  **No tabs on the rear edge.**  Re-check the spans after the power pours and state them in the order remark | rear-edge copper and pads sit 0.30-0.38 mm from the outline (SPI_MOSI, R_S1, SWDIO, +3V3 tracks; C9, D8, C30, R6, R113 pads); the right edge has copper at 0.33-0.35 mm (review 2026-10-01, jlc-fab-2 / jlc-assembly-4) |
| Fiducials | added by JLC | JLC help (PLACEMENT 6) |
| Reflow order | bottom side first | nothing on the bottom is heavy |
| Through-hole | J4 (JST B5B-XH-A vertical): JLC THT assembly **or** hand-solder | BOM.md |
| **CPL rotation check** | **fab.py applies an explicit, reviewed correction per part** (2026-10-01 footprint triple-check against JLC's own footprints): +270 U1, U3, U4, U5, U7, U11-U14, Q1-Q8; +180 U9, U10, D7-D9, J2, J3, J4; +90 J1; 0 U2, U6, U8, C1, D1-D5, D10 and every R / C / L / shunt.  kicad-jlcpcb-tools' default table would have reversed C1 and U8 (its CP_Elec_10x10 / QFN-20 rules), left U3, U4, U7, U13, J1 and Q1-Q8 90° off, turned U11, U12, U14 wrong and D7-D9 wrong.  CPL positions are pad-centre (so J4 needs no origin offset).  **Still check pin 1 of every IC / diode / FET / connector in JLC's placement preview against the silk pin-1 dots**: a reversed J4 puts B− on pin 5, a reversed J2/J3 swaps all six signals | kicad/gen/fab.py, review/v2_parts/adversarial/jlc_footprints.md |
| Not assembled | wire holes JBAT1/2, JW1-3, JL1-3, JR1-3; test pads; net ties; solder jumpers JP1/JP2 (copper, bridged 1-2 by default); MH1-MH4 | out of the BOM by design |
| DNP | C110-C112, C114-C116 (sensor line filters, fit only for Hall sensors): marked DNP on the board; fab.py leaves them out of BOM.csv and CPL.csv (check they are absent) | BOM.md |
| BOM / CPL | kicad/gen/fab.py from the final board (the LCSC field is on every part; 195 placements, 101 on the bottom, as of 2026-10-01) | kicad/gen/fab.py |
| **Check in JLC's 3D/placement preview** | D3 (vendor pin numbering is reversed: check the cathode mark), every diode and polarized cap (D1, D2, D4, D5, D7-D10, C1), the PQFN FETs' pin 1, U1-U14 pin 1, J1 pin 1 (58.215, 32.95, bottom), and the vertical connectors (mating faces up): J2 pin 1 at (8.0, 33.62) by the rear edge, J3 pin 1 at (83.57, 26.0) by the right edge, J4 pin 1 at (64.7, 31.08) (B−) | BOM.md, DESIGN 3.1 |

## After assembly (by hand)
- [ ] Stake C1 with adhesive (hot glue / silicone / epoxy), ~2 mm clear above it (DESIGN 6.10).
- [ ] Solder the wires (they enter from the top, soldered on the bottom, before stacking): battery pigtail 16-18 AWG to
      JBAT1 (BAT+) and JBAT2 (BAT-), twisted; weapon leads to JW1-3 (WA/WB/WC on the bottom silk); drive leads to
      JL1-3 / JR1-3 (LA-LC / RA-RC). Strain-relieve the leads on the chassis within ~20 mm (DESIGN 6.9).
- [ ] Cover the wire joints on the bottom (Kapton or conformal coat) so they cannot touch the compute board (DESIGN 6.9).
- [ ] Glue the SH plugs into J2/J3 once fitted (no latch) (PLACEMENT 2).
- [ ] Stack: chassis boss -> soft washer/grommet -> compute board -> nylon standoff (= J1 mated height) -> motor board ->
      nylon washer -> M2 screw (PLACEMENT 2).
- [ ] Bring-up per DESIGN 9.
