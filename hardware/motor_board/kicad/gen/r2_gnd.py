"""r2 stage: GND.  Base = the routed board after kicad/v2/gndvias.py (a via + stub next to every SMD GND pad that has a
spot); this stage adds (1) a router drop to the planes for every GND pad gndvias found no spot for (out/r2_gnd_missed.txt)
and (2) the L3 GND stitching vias from kicad/v2/r2/stitch.py (out/r2_stitch.json: >= 2 GND vias in every L3 GND
piece above the size limit)."""
import json
from pathlib import Path

import v2_pre
from v2_pre import EDITS, via, RV  # noqa: F401

v2_pre.VIA_PITCH = 0.9
V2 = Path(__file__).resolve().parents[1] / "v2" / "out"
for x, y in json.load(open(V2 / "r2_stitch.json")) if (V2 / "r2_stitch.json").exists() else []:
    EDITS.append(dict(op="via", net="GND", c=(x, y), d=0.45, drill=0.25))
missed = (V2 / "r2_gnd_missed.txt").read_text().split() if (V2 / "r2_gnd_missed.txt").exists() else []
for rp in missed:
    ref, num = rp.split(".")
    if (ref, num) in (("U2", "49"), ("U3", "41"), ("U4", "41"), ("U8", "21"), ("U6", "15")):
        continue                                         # exposed pads: the thermal arrays below
    EDITS.append(dict(op="drop", pad=(ref, num), net="GND", margin=2.5, w=0.25, via=0.45, drill=0.25,
                      layers=["F.Cu", "B.Cu"]))
    EDITS[-1]["avoid"] = [["*", 44.2, 17.85, 45.1, 18.75, "tracks"]]   # (+5V via at (44.65, 18.3): Rail clearance)

# exposed-pad thermal vias (filled / capped like the POFV list): U2 4 x 4 at 1.29 mm, U3 / U4 at 1.2 mm (their L3
# islands allow vias), U8 2 x 2 at 1.0 mm, U6 one in its 1.0 x 1.5 pad (U6 at (57.5, 25.2))
EP = {"U2": [(60.925, 21.425, 66.075, 26.575), 1.29], "U3": [(6.65, 22.45, 12.35, 26.15), 1.2],
      "U4": [(20.65, 20.65, 24.35, 26.35), 1.2]}
for ref, (bx, pitch) in EP.items():
    nx = int((bx[2] - bx[0] - 0.8) / pitch) + 1
    ny = int((bx[3] - bx[1] - 0.8) / pitch) + 1
    x0 = (bx[0] + bx[2]) / 2 - (nx - 1) * pitch / 2
    y0 = (bx[1] + bx[3]) / 2 - (ny - 1) * pitch / 2
    for i in range(nx):
        for j in range(ny):
            EDITS.append(dict(op="via", net="GND", c=(round(x0 + i * pitch, 3), round(y0 + j * pitch, 3)),
                              d=0.45, drill=0.25))
EDITS.append(dict(op="via", net="GND", c=(57.5, 25.2), d=0.45, drill=0.25))
# gndvias' stub from (44.75, 19.12) passes the +5V via at (44.65, 18.3) too close for the Rail class: join C44.2 to the GND run at x 43.73 instead
EDITS.append(dict(op="rip", box=(44.95, 18.3, 45.25, 18.8), nets=["GND"], layers=["B.Cu"], cross=True))
EDITS.append(dict(op="track", net="GND", layer="B.Cu", pts=[(44.75, 19.12), (43.73, 19.12)], w=0.25))   # C44.2 -> GND run
# r2_main's L_H3B via next to JR3 breaks the JLC via-hole-to-PTH-pad 0.3 mm rule: re-route that run
EDITS.append(dict(op="rip", box=(27.3, 30.8, 28.4, 31.9), nets=["/sensors/L_H3B"], reroute=dict(margin=6.0)))
