"""Edits on top of frozen/board.kicad_pcb (see tail.py for the ops).  Kept in order; each group says why.
Earlier rounds, already in the frozen board: tail_log/NN_*.py."""

L3, L4 = "In2.Cu", "In3.Cu"
B = "B.Cu"
from tail_auto import auto  # noqa: E402

RR = dict(margin=5.0, max_ratio=3.0)
# why L_INHC 25.25-27.4 lifting []
EDITS = [{"op": "route", "net": "L_INHC", "a": ["pt", 25.25, 33.2, "In2.Cu"], "b": ["pt", 27.4, 24.95, "In2.Cu"], "w": 0.127, "margin": 10.0, "max_ratio": 3.5, "tag": "L_INHC 25.25-27.4", "layers": ["F.Cu", "B.Cu", "In3.Cu", "In2.Cu", "In4.Cu"], "layer_cost": {"In4.Cu": 4.0}}]
