"""Edits on top of frozen/board.kicad_pcb (see tail.py for the ops).  Kept in order; each group says why.
Earlier rounds, already in the frozen board: tail_log/NN_*.py."""

L3, L4 = "In2.Cu", "In3.Cu"
B = "B.Cu"
from tail_auto import auto  # noqa: E402

RR = dict(margin=5.0, max_ratio=3.0)
EDITS = [
]
# L5 (In4, GND plane) now takes short jumpers where the four signal layers are full around U1 (layer cost 4, so
# the router uses it only to get past a fence); the plane refills around them.  Slow logic nets only.
ALL5 = ["F.Cu", "B.Cu", "In3.Cu", "In2.Cu", "In4.Cu"]
EDITS = [dict(e, layers=ALL5, layer_cost={"In4.Cu": 4.0}, margin=10.0, max_ratio=3.0,
              w=(0.2 if e["net"] in ("+3V3", "+5V") else 0.127)) for e in auto(drc=__import__("pathlib").Path(__file__).resolve().parent / "21_input_drc.json", skip=("GND", "/drive_right/R_VM"))]
