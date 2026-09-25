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
| Layers | 4 | DESIGN 6.1-6.2 |
| Stack-up | **JLC04161H-7628** (1.6 mm; L1-L2 prepreg 0.21 mm) | the thin L1-L2 gap keeps the commutation loop ~4 nH (PLACEMENT 3) |
| Outer copper | 1 oz | 0.5 mm-pitch QFNs; the pack current rides L1 + L3 pours |
| **Inner copper** | **1 oz** (JLC's default is 0.5 oz: change it) | DESIGN 6.1 |
| Board size | 75 x 35 mm, 1 design | PLACEMENT 1 |
| Surface finish | ENIG | flat pads for the QFN / LQFP / PDFN parts |
| **Via-in-pad** | **yes: epoxy-filled and capped** | thermal vias in U2/U3/U4's exposed pads and 8 vias in RS2's GND pad (layout step 1) |
| Min track / space | 0.127 / 0.127 mm (standard 4-layer capability) | project rules |
| Min via | 0.45 mm pad / 0.25 mm drill | project rules |
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
| Through-hole | J4 (JST S5B-XH-A): JLC THT assembly **or** hand-solder | BOM.md |
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
