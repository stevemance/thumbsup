"""Edits on top of frozen/board.kicad_pcb (see tail.py for the ops).  Kept in order; each group says why.
Earlier rounds, already in the frozen board: tail_log/NN_*.py."""

import ast
from pathlib import Path

L3, L4 = "In2.Cu", "In3.Cu"

# every GND pad that reached the planes only through the outer GND fill gets its own drop via where one fits, so
# later tracks on F/B cannot strand it (fillonly.py lists them)
SKIP = {("D7", "1"), ("C307", "2"), ("C308", "2"), ("U3", "15")}
_P = ast.literal_eval((Path(__file__).resolve().parent / "tail_log" / "05_fillonly.txt").read_text())
EDITS = [dict(op="drop", pad=p, net="GND", margin=1.5, w=0.25, via=0.4, drill=0.2) for p in _P if p not in SKIP]
# +3V3 pads the new GND vias cut off from the L4 +3V3 fill: their own drops after
EDITS += [dict(op="drop", pad=p, net="+3V3", margin=3.0, w=0.2, via=0.4, drill=0.2)
          for p in (("U3", "23"), ("U3", "28"), ("R16", "2"), ("R17", "2"), ("C74", "1"), ("D7", "2"), ("C47", "1"), ("U1", "48"),
                    ("C62", "1"), ("U9", "8"), ("R60", "1"), ("JP2", "1"), ("C23", "1"), ("R52", "1"))]
