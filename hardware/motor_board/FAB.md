# Motor board: fabrication and assembly checklist (JLCPCB)

Everything the order and the build depend on, in one place. The sources are the ones listed per line; when a
design decision changes one of these, change it here too. Tick through it on order day.

## Before ordering
- [ ] `python3 design/motor_board.py` prints `checks: OK` (BOM.md "Before ordering").
- [ ] `/usr/bin/python3 kicad/gen/layout_check.py`: DRC 0 errors, schematic parity 0, **0 unconnected items**,
      every via field OK, no pour with extra islands, section 5 (GND pads) empty.
- [ ] Re-check stock and part class on jlcpcb.com for every BOM line; **reserve U1, U2 and U7** (each under ~210 in
      stock). Stock notes and alternates: BOM.md.
- [ ] Compute board designed to match this one (PLACEMENT.md 5.2): J1 mirrored (pin 1 at (14.6, 24.92) in this
      board's top-view coordinates, rows toward the front), clear zones under J3 and every wire-hole joint and J4's
      pins, the Pico W antenna and USB outside this board's outline, J1 mated height chosen (sets the stack gap).

## PCB options (order form)
| Option | Value | Why / source |
|---|---|---|
| Layers | **4** | layout v2 (2026-09-29, branch layout-v2) restarts on 4 layers; the 6-layer v1 is kept on branch worktree-routing. Layer jobs: L1 parts + power, L2 solid GND (no traces), L3 VBAT band under the bridges + GND elsewhere, L4 parts + signals + GND fill (review/v2_lessons/README.md 3.1) |
| Stack-up | **JLC041611-1080** (1.6 mm): L1-L2 1080 prepreg 0.069 mm, L2-L3 core 1.23 mm, L3-L4 1080 prepreg 0.069 mm | thin L1-L2 keeps the weapon commutation loop at the ~4 nH estimate (PLACEMENT 3); L3 couples to L4, not L2, so L4 traces never cross a VBAT/GND boundary on L3 (solid GND under the VBAT band).  In KiCad (kicad/v2/build_board.py STACKUP4).  Confirm the name on the order form: JLC renames stack-ups |
| Outer copper | 1 oz | 0.5 mm-pitch QFNs; the pack current rides the L1 pours + the L3 band |
| **Inner copper** | **1 oz** (select it explicitly; JLC's 4-layer default is 0.5 oz) | the pack current rides the L3 VBAT band (DESIGN 6.2); the extra copper is two inner layers of 85 x 35 mm, ~3 g |
| Board size | **85 x 35 mm**, 1 design (fixed for v2) | PLACEMENT 1 |
| Surface finish | ENIG | flat pads for the QFN / LQFP / PDFN parts |
| **Via-in-pad** | **yes: epoxy-filled and capped (POFV), 0.40 mm pad / 0.20 mm drill** (JLC's POFV minimum drill is 0.2 mm; paid on 4-layer boards) | 16 vias: U2 pins 13, 14, 18, 19, 21, 22, 23, 24 (staggered 0.5 mm along the pads; 0.175 mm to the neighbouring pad), RS2 pad 1 (SL_B), NT1/NT2/NT3 SN pads (0.45/0.20); the weapon gate/Kelvin fan-out has no room otherwise (DESIGN 6.2, review/v2_layout/gate_corridor.md).  Drive fan-out (kicad/gen/v2_drive.py): U1 pin 42 (L_SOB_F, 32.90/27.00) and pin 45 (DRV_OFF to R50 below it, 32.95/28.50), U4 pin 5 (R_SWBK, 19.93/22.75) and pin 37 (VREF/AVDD, 22.25/19.95), all 0.40/0.20 (U1: at the pad's inner end; U4: at the outer end, clear of the thermal-via field).  Add U2/U3/U4 exposed-pad thermal vias if they are filled.  Confirm on the order form |
| Min track / space | 0.15 / 0.127 mm on logic nets (Default class; 0.10 board minimum for pad escapes); 0.15 clearance on power, drive, gate, sense, rail classes (JLC 4-layer: 0.09 / 0.09) | motor_board.kicad_pro, motor_board.kicad_dru |
| Hole to copper | via hole 0.20 mm; PTH hole 0.30 mm (JLC 4-layer: via 0.2, PTH 0.28, 0.35 recommended); pad hole-to-hole 0.45 | motor_board.kicad_dru |
| Min via | 0.4 mm pad / 0.2 mm drill (Default); 0.45 / 0.25 sense and rails; 0.5 / 0.25 gate; 0.6 / 0.3 power (JLC 4-layer min 0.25 / 0.15) | motor_board.kicad_pro |
| Impedance control | no | nothing on the board needs it (layout step 0) |
| Mask / silk | any colour; silk on both sides | wire names are on the bottom silk |
| Order number | "specify a location" (a clear spot on the bottom) or remove | cosmetic |

## Assembly options (PCBA)
| Option | Value | Why / source |
|---|---|---|
| Type | **Standard PCBA, both sides** | parts on top and bottom (PLACEMENT 5.1) |
| Panel / rails | board under 70 x 70 mm: **rails on all four edges**, **mouse-bite tabs (no V-cut) on the rear edge**, tabs away from J2, J3, C29, C30, R402 | pads are 0.40 mm from the rear edge (PLACEMENT 6) |
| Fiducials | added by JLC | JLC help (PLACEMENT 6) |
| Reflow order | bottom side first | nothing on the bottom is heavy |
| Through-hole | J4 (JST B5B-XH-A vertical): JLC THT assembly **or** hand-solder | BOM.md |
| **CPL rotation check** | **J2, J3 (JST BM06B) and J4 (B5B-XH-A): JLC's footprints are ours rotated 180° (J4's origin is also at the body centre: +5 mm X offset).  Correct them in the CPL and check pin 1 in JLC's placement preview**: a reversed J4 puts B− on pin 5, a reversed J2/J3 swaps all six signals.  Also check U6 (WQFN-14 pin 1) and D2 (cathode = pad 1) | review/v2_parts/adversarial/jlc_footprints.md |
| Not assembled | wire holes JBAT1/2, JW1-3, JL1-3, JR1-3; test pads; net ties; solder jumpers JP1/JP2 (copper, bridged 1-2 by default); MH1-MH4 | out of the BOM by design |
| DNP | C110-C112, C114-C116 (sensor line filters, fit only for Hall sensors) | BOM.md |
| BOM / CPL | from the KiCad board (the LCSC field is on every part) | kicad-jlcpcb-tools |
| **Check in JLC's 3D/placement preview** | D3 (vendor pin numbering is reversed: check the cathode mark), every diode and polarized cap (D1, D2, D4, D5, D7-D10, C1), the PQFN FETs' pin 1, U1-U14 pin 1, J1 pin 1, J2/J3 orientation (mating face at the rear edge), J4 (mating face at the left edge) | BOM.md, DESIGN 3.1 |

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
