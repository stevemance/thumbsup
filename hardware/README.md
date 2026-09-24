# ThumbsUp hardware

Custom control / power / motor board for the 1 lb plastic-antweight robot.

| Document | What it is |
|---|---|
| [motor_board/](motor_board/) | **Current direction (2026-09-23):** two-board stack, this is the motor board: STM32G474 + DRV8323RS weapon + 2 × DRV8316R FOC drive, 4S. Design, netlist, BOM, SPICE. |
| [REVIEW.md](REVIEW.md) | 2026-09-03 design reviews (initial + layout-readiness): what was wrong, what changed, what is still open. |
| [LAYOUT.md](LAYOUT.md) | The generated layout: mechanical frame, stackup and rules, floorplan, copper plan, routing, what is left for a human. |
| [DESIGN_REQUIREMENTS.md](DESIGN_REQUIREMENTS.md) | v1 board spec: simple teleop + instrumentation for later autonomy. |
| [PARTS.md](PARTS.md) | BOM with LCSC numbers verified on the JLC/LCSC part pages. |
| [PINMAP.md](PINMAP.md) | Pico GPIO and AM32 `AT32DEV_F421` pins. |
| [kicad/](kicad/) | Generated hierarchical schematic and PCB (`thumbsup.kicad_pcb`, previews in `kicad/preview/`). |
| [fab/](fab/) | JLCPCB outputs: Gerber/drill zip, BOM, CPL (`tools/pcb/fab.py`). |
| [mech/](mech/) | Board outline, boss positions and standoff height derived from the chassis 3MF (`tools/mech/chassis.py`). |
| [datasheets.json](datasheets.json) | Datasheet URLs. `python3 hardware/tools/download_datasheets.py` |

## Tooling

```
tools/sch/circuit.py    the circuit (SKiDL) — the only place connectivity lives
tools/sch/layouts.py    explicit placement per sheet
tools/sch/draw.py       drawing layer on kicad-sch-api (wires, labels, power symbols, junctions)
tools/sch/symbols.py    custom symbols: AT32F421K8U7, FD6288Q, SK6812MINI-C, fixed Pico W
tools/sch/build.py      build + KiCad ERC + SKiDL/KiCad netlist equivalence + PNG previews
tools/spice/            ngspice (via KiCad's libngspice) checks: reverse-polarity FET,
                        buck EN/UVLO divider, bootstrap droop
tools/mech/chassis.py   Bambu 3MF -> slices, floor height map, PCB bay outline + fit check
tools/pcb/build_pcb.py  netlist -> board: rules, net classes, outline, placement, copper, routing, DRC
tools/pcb/placement.py  top-side floorplan + obstacle-aware bottom packer + placement checks
tools/pcb/copper.py     power pours, via fields, gate vias/notches, Kelvin stubs
tools/pcb/route.py      Freerouting (Specctra DSN/SES) for the logic nets
tools/pcb/fab.py        Gerbers, drills, JLC BOM and CPL
```

Rebuild the schematic:

```bash
python3 -m venv hardware/tools/.venv
hardware/tools/.venv/bin/pip install -r hardware/tools/requirements.txt
hardware/tools/.venv/bin/python hardware/tools/sch/build.py --render   # previews in kicad/preview/
```

The build fails if the drawn schematic's netlist differs from the SKiDL circuit or if
KiCad ERC reports an error.

Rebuild the board (system python with KiCad 10's `pcbnew`; Freerouting's linux-x64 bundle
unpacked in `tools/freerouting/`):

```bash
/usr/bin/python3 hardware/tools/mech/chassis.py outline     # only when the chassis changes
/usr/bin/python3 hardware/tools/pcb/build_pcb.py --render   # add --no-route to skip Freerouting
/usr/bin/python3 hardware/tools/pcb/fab.py
```

Firmware that this board must support lives in `../firmware/`. Mechanical parts are in
`../models/`.
