# Motor board: fabrication and assembly checklist (JLCPCB)

Everything the order and the build depend on, in one place. The sources are the ones listed per line; when a
design decision changes one of these, change it here too. Tick through it on order day.

## Before ordering
- [ ] `python3 design/motor_board.py` prints `checks: OK` (BOM.md "Before ordering").
- [ ] Fab source: `kicad/motor_board/motor_board.kicad_pcb` (+ .kicad_pro / .kicad_dru), the output of the last stage
      (`kicad/gen/out/exp/hS/proj/`, chain ... hD -> hP -> hX -> hS) copied in; regenerate it if any stage changes.
- [ ] From `kicad/motor_board/`: `kicad-cli pcb drc --schematic-parity --severity-error motor_board.kicad_pcb` ->
      **0 violations, 0 unconnected items, 0 schematic parity issues** (2026-10-01: all three 0).  With
      `--severity-all` only the expected lib_footprint_mismatch warnings remain (silk moved to Fab by the silk stage).
      (`kicad/gen/layout_check.py` is the v1 6-layer checker and no longer applies.)
- [ ] Connectivity of the poured board = the DRC's **0 unconnected items** above.  (`kicad/v2/r2/pourtest.py` is a
      pre-pour design tool: it removes zones to test single-net pours and does not run on the poured board.)
- [ ] Re-check stock and part class on jlcpcb.com for every BOM line; **reserve U1, U2 and U7** (U1 122 in stock on
      2026-10-01; U7 is now INA239AQDGSRQ1 C4367136, only 7 in stock: the INA239AIDGSR / INA229AIDGSR were at 0).
- [ ] Compute board designed to match this one: J1 is on this board's bottom, origin (52.5, 30.95) rot 90, pin 1 at
      (58.215, 32.95), pin 2 at (58.215, 28.95), odd pins along y 32.95 and even pins along y 28.95, stepping −1.27 in x
      to pins 19/20 at x 46.785 (board-local mm, top view: x from the left edge, y from the front edge, as in the stage
      dumps). Mounting holes MH1-MH4 at (3, 3), (82, 3), (3, 32), (82, 32): a 79 x 29 mm rectangle. Clear zones on the
      compute board under J1, J4's five pins (x 64.7-74.7, y 31.08) and every wire-hole joint (JBAT1 (8.75, 3.25),
      JBAT2 (3.25, 8.75), JW1-3 y 2.75, JL1-3 x 2.5, JR1-3 y 31.3); the Pico W antenna and USB outside this board's
      outline; J1 mated height chosen (sets the stack gap).
- [ ] Export: `/usr/bin/python3 kicad/gen/fab.py kicad/motor_board/motor_board.kicad_pcb` -> kicad/gen/out/fab/: Gerbers (X2 + `.gbrjob`),
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
| **Via-in-pad** | **yes: epoxy-filled and capped (POFV)** (JLC's POFV minimum drill is 0.2 mm; paid on 4-layer boards).  Sizes on the board: 0.40/0.20 (83), 0.45/0.25 (69: the U2 / U3 / U4 exposed-pad thermal arrays), 0.45/0.20 (3) | **155 vias in 45 parts** on the final board (centre inside a pad, `kicad/v2/r2/fabfacts.py`): U2 33, U4 26, U3 24 (EP thermal arrays + fan-out), U6 7, J1 6, U1 5, U9 3, C1 3, C302 3, R302 3, R402 3, C301 2, C400 2, C402 2, J3 2, R63 2, and one each in C4, C18, C24 (shared with U8's exposed pad: U8.21 at (71.535, 23.315)), C60, C70, C82, C92, C111, C112, C303, C401, D8, NT1-NT3, Q7, R22, R24, R26, R45, R49, R52, R110, R113, R300, RS2, TP3, TP9, U13.  Confirm on the order form |
| Min track / space | 0.15 / 0.127 mm on logic nets (Default class; 0.10 board minimum for pad escapes); 0.15 clearance on power, drive, gate, sense, rail classes (JLC 4-layer: 0.09 / 0.09) | motor_board.kicad_pro, motor_board.kicad_dru |
| Hole to copper | via hole 0.20 mm; PTH hole 0.30 mm (JLC 4-layer: via 0.2, PTH 0.28, 0.35 recommended); pad hole-to-hole 0.45 | motor_board.kicad_dru |
| Min via | 0.4 mm pad / 0.2 mm drill (Default); 0.45 / 0.25 sense and rails; 0.5 / 0.25 gate; 0.6 / 0.3 power (JLC 4-layer min 0.25 / 0.15).  The final board has 262 vias of 0.40/0.20 (of 565: 241 at 0.45/0.25, 57 at 0.6/0.3, 5 at 0.45/0.20), in JLC's surcharged small-via class (cost only); vias outside pads may grow to 0.45/0.20 where clearance allows | motor_board.kicad_pro |
| Impedance control | no | nothing on the board needs it (layout step 0) |
| Mask / silk | any colour; silk on both sides | silk only on parts handled after assembly (connectors, wire holes, JP, TP, MH, D3, C1), 0.15 mm lines / 1.0 mm text; wire names on the bottom (WA-WC, LA-LC, RA-RC), BAT+ / BAT- both sides, J4 B- / B4+, J2 / J3 VS / T, JP1 3V3 / 5V; a pin-1 / cathode dot on every IC, diode and FET (JLC checks polarity against the silk).  Not placed (no clear spot): JP2's 3V3 / 5V labels and reference, TP7 / TP12 references (stage kicad/gen/hS.py, silk.py) |
| Order number | **remove** (no marker on the board) | cosmetic |

## Assembly options (PCBA)
| Option | Value | Why / source |
|---|---|---|
| Type | **Standard PCBA, both sides** | parts on top and bottom (PLACEMENT 5.1) |
| Panel / rails | board under 70 x 70 mm: **rails, mouse-bite tabs only, no V-cut on any edge** (V-cut needs copper >= 0.4 mm from the cut; the rear edge has tracks / pads at 0.30-0.35 mm).  After the pours (`kicad/v2/r2/fabfacts.py <board> 0.5`) the left edge (x = 0) is the only edge with no non-GND copper, pad or courtyard within 0.5 mm (JLC's mouse-bite copper guidance; GND fill allowed) along its whole length; the right edge is clear at y 29.0-35.0 only.  **Order remark: mouse-bite tabs on the left edge only (JLC's minimum tab ~5 mm wide; e.g. y 6-11 and 24-29), plus right y 29.5-34.5 if a second side is needed; no tabs on the rear or front edge** (the rear x 57-61 window is 0.9 mm from C9, a 1206 on the pack-fed BMS_BAT rail); bite holes on the rail side | kicad/v2/r2/fabfacts.py; review jlc-fab-1 / jlc-assembly-2 |
| Fiducials | added by JLC | JLC help (PLACEMENT 6) |
| Reflow order | bottom side first | nothing on the bottom is heavy |
| Through-hole | J4 (JST B5B-XH-A vertical): JLC THT assembly **or** hand-solder.  **Bottom SMD pads sit 0.25-0.3 mm from J4's pads** (U6.7/U6.8 by pin 1, D8.1 GND by pin 5 = BAL4, the pack top), inside PLACEMENT's 1.5 mm solder zone, and D5.1 / C10.2 / C4.2 at 0.90-1.07 mm from pins 2-5: ask for hand soldering with a fine tip (no wave / selective nozzle) and inspect pins 1-5 for bridges.  The same care applies when the wires are hand-soldered after assembly: **R110.1 (Hall line L_H1, bottom) is 0.48 mm and C112.2 0.77 mm from JR3's pad**.  Parts within JLC's 0.3 mm body-to-edge: R6, R113 (rear edge) and C49 (right edge) by ~0.02-0.08 mm; covered by the rails | BOM.md, review jlc-assembly-3 |
| **CPL rotation check** | **fab.py applies an explicit, reviewed correction per part** (2026-10-01 footprint triple-check against JLC's own footprints): +270 U1, U3, U4, U5, U7, U11-U14, Q1-Q8; +180 U9, U10, D7-D9, J2, J3, J4; +90 J1; 0 U2, U6, U8, C1, D1-D5, D10 and every R / C / L / shunt.  kicad-jlcpcb-tools' default table would have reversed C1 and U8 (its CP_Elec_10x10 / QFN-20 rules), left U3, U4, U7, U13, J1 and Q1-Q8 90° off, turned U11, U12, U14 wrong and D7-D9 wrong.  CPL positions are pad-centre (so J4 needs no origin offset).  **Still check pin 1 of every IC / diode / FET / connector in JLC's placement preview against the silk pin-1 dots**: a reversed J4 puts B− on pin 5, a reversed J2/J3 swaps all six signals | kicad/gen/fab.py, review/v2_parts/adversarial/jlc_footprints.md |
| Not assembled | wire holes JBAT1/2, JW1-3, JL1-3, JR1-3; test pads; net ties; solder jumpers JP1/JP2 (copper, bridged 1-2 by default); MH1-MH4 | out of the BOM by design |
| DNP | C110-C112, C114-C116 (sensor line filters, fit only for Hall sensors): marked DNP on the board; fab.py leaves them out of BOM.csv and CPL.csv (check they are absent); the DNP caps' pads carry no paste on the final board | BOM.md |
| BOM / CPL | kicad/gen/fab.py from the final board (the LCSC field is on every part; 195 placements, 99 on the bottom, as of 2026-10-01) | kicad/gen/fab.py |
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
