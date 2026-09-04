# ThumbsUp hardware

Custom control / power / motor board for the 1 lb plastic-antweight robot.

| Document | What it is |
|---|---|
| [REVIEW.md](REVIEW.md) | 2026-09-03 design reviews (initial + layout-readiness): what was wrong, what changed, what is still open. |
| [LAYOUT.md](LAYOUT.md) | Layout brief: stackup, net classes and currents, Kelvin/ground strategy, placement and thermal rules, DFM. |
| [DESIGN_REQUIREMENTS.md](DESIGN_REQUIREMENTS.md) | v1 board spec: simple teleop + instrumentation for later autonomy. |
| [PARTS.md](PARTS.md) | BOM with LCSC numbers verified on the JLC/LCSC part pages. |
| [PINMAP.md](PINMAP.md) | Pico GPIO and AM32 `AT32DEV_F421` pins. |
| [kicad/](kicad/) | Generated hierarchical schematic. Layout is not started. |
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
```

Rebuild the schematic:

```bash
python3 -m venv hardware/tools/.venv
hardware/tools/.venv/bin/pip install -r hardware/tools/requirements.txt
hardware/tools/.venv/bin/python hardware/tools/sch/build.py --render   # previews in kicad/preview/
```

The build fails if the drawn schematic's netlist differs from the SKiDL circuit or if
KiCad ERC reports an error.

Firmware that this board must support lives in `../firmware/`. Mechanical parts are in
`../models/`.
